"""In-memory session store (FR-012, FR-013).

One session per upload, identified by a 128-bit cryptographically random
token carried in an HttpOnly, SameSite=Strict cookie. TTL defaults to 5
minutes (configurable). Teardown deletes the per-session temp directory and
the in-memory record. A background asyncio task sweeps expired sessions every
60 seconds and logs ``session_sweeper: cleaned=<N>, remaining=<M>``; expired
sessions are also removed lazily on access so a session is never served past
its TTL. At startup, any stale ``coa_profiler_session_*`` temp directory is
swept. Nothing reaches durable store.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import shutil
import stat
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from coa_profiler.parser.fields import COAChemistry
    from coa_profiler.scorer.placement import PlacementResult

log = logging.getLogger("coa_profiler.session")

SESSION_COOKIE = "session"
SESSION_DIR_PREFIX = "coa_profiler_session_"
SWEEP_INTERVAL_SECONDS = 60


@dataclass
class SessionRecord:
    """Spec section 5 data model."""

    session_token: str  # 128-bit hex; HttpOnly cookie only
    chemistry: COAChemistry
    placement: PlacementResult
    working_copy_path: str
    created_at: float
    ttl_seconds: int


class SessionStore:
    def __init__(self, ttl_seconds: int = 300, tmp_root: str | None = None) -> None:
        self.ttl_seconds = ttl_seconds
        # Session dirs live directly under tmp_root with the reserved prefix
        # (default /tmp/coa_profiler_sessions, AC-006).
        self.tmp_root = Path(tmp_root) if tmp_root else Path(tempfile.gettempdir()) / "coa_profiler_sessions"
        self._records: dict[str, SessionRecord] = {}
        self._lock = threading.Lock()
        self._sweeper_task: asyncio.Task | None = None
        self._ensure_private_root()

    # -- temp dirs -----------------------------------------------------------
    def _ensure_private_root(self) -> None:
        """Create and validate the owner-only parent for every session dir."""
        try:
            self.tmp_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as exc:
            raise RuntimeError(f"unable to create session temp root: {self.tmp_root}") from exc

        try:
            root_stat = self.tmp_root.lstat()
        except OSError as exc:
            raise RuntimeError(f"unable to inspect session temp root: {self.tmp_root}") from exc
        if stat.S_ISLNK(root_stat.st_mode):
            raise RuntimeError(f"session temp root must not be a symlink: {self.tmp_root}")
        if not stat.S_ISDIR(root_stat.st_mode):
            raise RuntimeError(f"session temp root must be a directory: {self.tmp_root}")

        # mkdir's requested mode is still filtered by umask, and an existing
        # root may have been created with broader permissions. Correct it
        # explicitly before any token-derived leaf name is created.
        try:
            self.tmp_root.chmod(0o700)
            final_stat = self.tmp_root.lstat()
        except OSError as exc:
            raise RuntimeError(f"unable to secure session temp root: {self.tmp_root}") from exc
        if stat.S_ISLNK(final_stat.st_mode) or stat.S_IMODE(final_stat.st_mode) != 0o700:
            raise RuntimeError(f"session temp root is not owner-only: {self.tmp_root}")

    def new_session_dir(self, token: str) -> Path:
        # Revalidate in case the configured root was replaced after startup.
        self._ensure_private_root()
        path = self.tmp_root / f"{SESSION_DIR_PREFIX}{token}"
        path.mkdir(mode=0o700, exist_ok=False)
        # A permissive process umask must not make uploaded health documents
        # readable by other users on a shared host.
        path.chmod(0o700)
        return path

    def _remove_dir(self, working_copy_path: str) -> bool:
        """Remove the session directory, returning true only when it is gone.

        A failed deletion is deliberately observable and retryable. Callers
        must retain the in-memory record until this function succeeds so a
        later sweep can try again instead of forgetting retained health data.
        """
        session_dir = Path(working_copy_path).parent
        if (
            session_dir.parent != self.tmp_root
            or not session_dir.name.startswith(SESSION_DIR_PREFIX)
            or session_dir.is_symlink()
        ):
            log.warning("refused to remove non-session dir for %s", working_copy_path)
            return False
        if not session_dir.exists():
            return True
        try:
            shutil.rmtree(session_dir)
        except OSError:
            log.exception("failed to remove session dir for %s; deletion will be retried", working_copy_path)
            return False
        if session_dir.exists():
            log.error(
                "session dir still exists after removal for %s; deletion will be retried", working_copy_path
            )
            return False
        return True

    # -- lifecycle ------------------------------------------------------------
    def create(
        self,
        chemistry: COAChemistry,
        placement: PlacementResult,
        working_copy_path: str,
        token: str | None = None,
        created_at: float | None = None,
    ) -> SessionRecord:
        token = token or secrets.token_hex(16)  # 128-bit
        record = SessionRecord(
            session_token=token,
            chemistry=chemistry,
            placement=placement,
            working_copy_path=working_copy_path,
            created_at=time.time() if created_at is None else created_at,
            ttl_seconds=self.ttl_seconds,
        )
        with self._lock:
            self._records[token] = record
        return record

    def get(self, token: str | None) -> SessionRecord | None:
        """Fetch a live session; expired sessions are torn down on access."""
        if not token or len(token) != 32:
            return None
        with self._lock:
            record = self._records.get(token)
        if record is None:
            return None
        if time.time() - record.created_at > record.ttl_seconds:
            self.teardown(token)
            return None
        return record

    def teardown(self, token: str | None) -> bool:
        if not token:
            return False
        with self._lock:
            record = self._records.get(token)
        if record is None:
            return False
        if not self._remove_dir(record.working_copy_path):
            return False
        with self._lock:
            # Another cleanup may have completed while deletion ran. Only the
            # operation that actually removes this exact record reports true.
            if self._records.get(token) is not record:
                return False
            self._records.pop(token)
            return True

    def sweep(self) -> tuple[int, int]:
        """Remove all expired sessions. Returns (cleaned, remaining)."""
        now = time.time()
        with self._lock:
            expired = [
                token
                for token, record in self._records.items()
                if now - record.created_at > record.ttl_seconds
            ]
        cleaned = sum(1 for token in expired if self.teardown(token))
        with self._lock:
            remaining = len(self._records)
        self._last_opportunistic = now
        return cleaned, remaining

    def teardown_all(self) -> tuple[int, int]:
        """Delete every live session, retaining any record whose deletion fails."""
        with self._lock:
            tokens = list(self._records)
        cleaned = sum(1 for token in tokens if self.teardown(token))
        with self._lock:
            remaining = len(self._records)
        return cleaned, remaining

    _last_opportunistic: float = 0.0

    def maybe_sweep(self, throttle_s: float = 1.0) -> None:
        """Throttled opportunistic sweep called per request.

        The session cookie's max-age equals the TTL, so an expired session's
        token may never reach the server again — the 60 s logging sweeper
        alone would leave stale temp dirs for up to a minute (AC-006 expects
        them gone at the first post-expiry contact). This runs at most once
        per second and costs one dict scan over a tiny in-memory map.
        """
        if time.time() - self._last_opportunistic >= throttle_s:
            self.sweep()

    async def sweep_loop(self, interval: float = SWEEP_INTERVAL_SECONDS) -> None:
        """Background sweeper (FR-012): runs every 60s and logs the counts."""
        while True:
            await asyncio.sleep(interval)
            try:
                cleaned, remaining = self.sweep()
                log.info("session_sweeper: cleaned=%d, remaining=%d", cleaned, remaining)
            except Exception:  # the sweeper must never die
                log.exception("session_sweeper: sweep failed")

    def start_sweeper(self) -> None:
        if self._sweeper_task is None:
            self._sweeper_task = asyncio.create_task(self.sweep_loop())

    async def stop_sweeper(self) -> None:
        if self._sweeper_task is not None:
            self._sweeper_task.cancel()
            try:
                await self._sweeper_task
            except asyncio.CancelledError:
                pass
            except Exception:  # shutdown must complete even if a sweeper failed
                log.exception("session_sweeper: failed during shutdown")
            self._sweeper_task = None

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)


def startup_sweep(tmp_root: str) -> int:
    """Remove stale session temp directories from previous runs (FR-012)."""
    root = Path(tmp_root)
    if not root.is_dir():
        return 0
    removed = 0
    for child in root.iterdir():
        if child.name.startswith(SESSION_DIR_PREFIX) and child.is_dir():
            try:
                shutil.rmtree(child)
            except OSError:
                log.exception("startup_sweep: failed to remove stale session dir %s", child)
                continue
            if child.exists():
                log.error("startup_sweep: stale session dir still exists after removal: %s", child)
                continue
            removed += 1
    return removed
