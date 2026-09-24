"""Per-IP in-memory rate limiting (FR-014).

Sliding-window counters, in-memory only (state resets on restart — acceptable
per assumption A-11). When ``TRUSTED_PROXY_HEADER`` is configured (e.g.
``X-Forwarded-For``), the real client IP is read from that header instead of
the socket peer (which is 127.0.0.1 behind Nginx).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from math import ceil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request

    from coa_profiler.config import Config


class RateLimiter:
    """Thread-safe sliding-window limiter with bounded identity cardinality.

    Every request-controlled client key must have a hard upper bound.  Stale
    identities are swept periodically across all buckets, while a full active
    table fails closed for previously unseen identities instead of evicting an
    active key and resetting that caller's limit.
    """

    def __init__(
        self,
        window_seconds: float = 60.0,
        *,
        max_keys: int = 10_000,
        sweep_interval_seconds: float = 5.0,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if max_keys < 1:
            raise ValueError("max_keys must be positive")
        if sweep_interval_seconds <= 0:
            raise ValueError("sweep_interval_seconds must be positive")
        self.window = window_seconds
        self.max_keys = max_keys
        self.sweep_interval = min(sweep_interval_seconds, window_seconds)
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = 0.0

    def _sweep_stale_locked(self, cutoff: float) -> None:
        """Drop identities with no hit remaining inside the active window."""
        stale = [identity for identity, hits in self._hits.items() if not hits or hits[-1] < cutoff]
        for identity in stale:
            del self._hits[identity]

    def _capacity_retry_locked(self, now: float) -> int:
        """Seconds until the earliest tracked identity can become stale."""
        oldest_last_hit = min((hits[-1] for hits in self._hits.values() if hits), default=now)
        return max(1, ceil(self.window - (now - oldest_last_hit)))

    def check(self, bucket: str, key: str, limit: int) -> tuple[bool, int]:
        """Record one hit. Returns (allowed, retry_after_seconds)."""
        if limit < 1:
            # A bad deployment value must fail closed, not turn every request
            # into an internal error before the operator can correct it.
            return False, max(1, ceil(self.window))
        now = time.monotonic()
        cutoff = now - self.window
        identity = (bucket, key)
        with self._lock:
            # Sweep at a fixed cadence, not on every capacity rejection: an
            # attacker rotating keys cannot force an O(n) scan per request.
            if now - self._last_sweep >= self.sweep_interval:
                self._sweep_stale_locked(cutoff)
                self._last_sweep = now

            hits = self._hits.get(identity)
            if hits is None:
                if len(self._hits) >= self.max_keys:
                    return False, self._capacity_retry_locked(now)
                hits = deque()
                self._hits[identity] = hits
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= limit:
                retry = max(1, int(self.window - (now - hits[0]))) if hits else int(self.window)
                return False, retry
            hits.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._last_sweep = 0.0


def client_ip(request: Request, config: Config) -> str:
    """Real client IP: trusted proxy header when configured, else socket peer."""
    if config.trusted_proxy_header:
        header_value = request.headers.get(config.trusted_proxy_header, "")
        if header_value:
            return header_value.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"
