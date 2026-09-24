"""Runtime configuration (deploy-time durable state; see spec section 5).

All values have safe defaults and are read from the environment (a local
``.env`` file is honored when present). No secret is required in the default
configuration. The scorer version string is fixed at build time (git tag or
``dev-<short_hash>``) and never contains a timestamp or random component
(DIS-12).
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("coa_profiler.config")

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Across the bounded worker pool, decoded uploads may not exceed this many
# pixels at once.  The default 4 x 12 MP envelope is approximately 144 MB for
# source RGB buffers before bounded OCR working copies.
MAX_DECODED_PIXELS_IN_FLIGHT = 48_000_000


def _read_env_file(path: Path) -> dict[str, str]:
    """Minimal .env parser (KEY=VALUE lines, # comments, optional quotes)."""
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                out[key] = value
    except OSError:
        pass
    return out


def _env(environ: dict[str, str], key: str, default: str) -> str:
    return environ.get(key, default)


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def detect_version(repo_root: Path | None = None) -> str:
    """Scorer version string: git tag at build time, else dev-<short_hash>.

    Fixed at build time; never a timestamp or random component (DIS-12).
    ``COA_PROFILER_VERSION`` env var wins when set (used by Docker builds).
    """
    override = os.environ.get("COA_PROFILER_VERSION", "").strip()
    if override:
        return override
    root = repo_root or _REPO_ROOT
    try:
        tag = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if tag.returncode == 0 and tag.stdout.strip():
            return tag.stdout.strip()
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if sha.returncode == 0 and sha.stdout.strip():
            return f"dev-{sha.stdout.strip()}"
    except (OSError, subprocess.SubprocessError):
        pass
    return "dev-unknown"


@dataclass(frozen=True)
class Config:
    max_upload_mb: int = 15
    max_pdf_pages: int = 20
    max_pdf_page_pixels: int = 8_000_000
    max_pdf_total_pixels: int = 48_000_000
    max_image_pixels: int = 12_000_000
    max_image_dimension: int = 8_000
    ocr_timeout_seconds: int = 30
    session_ttl_seconds: int = 300
    session_cookie_secure: bool = True
    rate_limit_per_minute: int = 20
    feedback_rate_limit_per_minute: int = 10
    port: int = 8080
    contact_email: str = ""
    inference_assist_enabled: bool = False
    inference_assist_url: str = ""
    inference_assist_api_key: str = ""
    trusted_proxy_header: str = ""
    log_ip_retention: str = "hashed"  # hashed | full | truncated | disabled
    processing_thread_pool_size: int = 4
    copylint_soft_fail: bool = False
    heic_enabled: bool = True
    # Root for per-session working directories (AC-006 lists
    # /tmp/coa_profiler_sessions/). Overridable for tests.
    session_tmp_root: str = "/tmp/coa_profiler_sessions"
    version: str = field(default_factory=detect_version)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def validate(self) -> None:
        if self.log_ip_retention not in {"hashed", "full", "truncated", "disabled"}:
            raise ValueError(
                f"LOG_IP_RETENTION must be hashed|full|truncated|disabled, got {self.log_ip_retention!r}"
            )
        if self.max_upload_mb < 1:
            raise ValueError("MAX_UPLOAD_MB must be >= 1")
        resource_limits = {
            "MAX_PDF_PAGES": self.max_pdf_pages,
            "MAX_PDF_PAGE_PIXELS": self.max_pdf_page_pixels,
            "MAX_PDF_TOTAL_PIXELS": self.max_pdf_total_pixels,
            "MAX_IMAGE_PIXELS": self.max_image_pixels,
            "MAX_IMAGE_DIMENSION": self.max_image_dimension,
            "OCR_TIMEOUT_SECONDS": self.ocr_timeout_seconds,
        }
        for name, value in resource_limits.items():
            if value < 1:
                raise ValueError(f"{name} must be >= 1")
        # Keep the child-process deadline strictly inside the upload route's
        # 110-second wall-clock deadline so Tesseract is killed first.
        if self.ocr_timeout_seconds >= 110:
            raise ValueError("OCR_TIMEOUT_SECONDS must be < 110")
        if self.session_ttl_seconds < 1:
            raise ValueError("SESSION_TTL_SECONDS must be >= 1")
        if self.processing_thread_pool_size < 1:
            raise ValueError("PROCESSING_THREAD_POOL_SIZE must be >= 1")
        decoded_pixels_in_flight = (
            max(self.max_pdf_page_pixels, self.max_image_pixels) * self.processing_thread_pool_size
        )
        if decoded_pixels_in_flight > MAX_DECODED_PIXELS_IN_FLIGHT:
            raise ValueError(
                "decoded pixel limit times PROCESSING_THREAD_POOL_SIZE exceeds "
                f"{MAX_DECODED_PIXELS_IN_FLIGHT}"
            )
        if self.contact_email and (
            "@" not in self.contact_email or any(ch.isspace() for ch in self.contact_email)
        ):
            raise ValueError("CONTACT_EMAIL must be empty or a valid email address")


def load_config(
    environ: dict[str, str] | None = None,
    env_file: str | os.PathLike[str] | None = None,
) -> Config:
    """Build a Config from the environment plus an optional .env file.

    Process environment wins over .env file values (standard twelve-factor).
    """
    file_vals: dict[str, str] = {}
    env_path = Path(env_file) if env_file else Path.cwd() / ".env"
    if env_path.is_file():
        file_vals = _read_env_file(env_path)
    merged: dict[str, str] = dict(file_vals)
    merged.update(os.environ if environ is None else environ)

    cfg = Config(
        max_upload_mb=_as_int(_env(merged, "MAX_UPLOAD_MB", "15"), 15),
        max_pdf_pages=_as_int(_env(merged, "MAX_PDF_PAGES", "20"), 20),
        max_pdf_page_pixels=_as_int(_env(merged, "MAX_PDF_PAGE_PIXELS", "8000000"), 8_000_000),
        max_pdf_total_pixels=_as_int(_env(merged, "MAX_PDF_TOTAL_PIXELS", "48000000"), 48_000_000),
        max_image_pixels=_as_int(_env(merged, "MAX_IMAGE_PIXELS", "12000000"), 12_000_000),
        max_image_dimension=_as_int(_env(merged, "MAX_IMAGE_DIMENSION", "8000"), 8_000),
        ocr_timeout_seconds=_as_int(_env(merged, "OCR_TIMEOUT_SECONDS", "30"), 30),
        session_ttl_seconds=_as_int(_env(merged, "SESSION_TTL_SECONDS", "300"), 300),
        session_cookie_secure=_as_bool(_env(merged, "SESSION_COOKIE_SECURE", "true")),
        rate_limit_per_minute=_as_int(_env(merged, "RATE_LIMIT_PER_MINUTE", "20"), 20),
        feedback_rate_limit_per_minute=_as_int(_env(merged, "FEEDBACK_RATE_LIMIT_PER_MINUTE", "10"), 10),
        port=_as_int(_env(merged, "PORT", "8080"), 8080),
        contact_email=_env(merged, "CONTACT_EMAIL", "").strip(),
        inference_assist_enabled=_as_bool(_env(merged, "INFERENCE_ASSIST_ENABLED", "false")),
        inference_assist_url=_env(merged, "INFERENCE_ASSIST_URL", ""),
        inference_assist_api_key=_env(merged, "INFERENCE_ASSIST_API_KEY", ""),
        trusted_proxy_header=_env(merged, "TRUSTED_PROXY_HEADER", ""),
        log_ip_retention=_env(merged, "LOG_IP_RETENTION", "hashed").strip().lower(),
        processing_thread_pool_size=_as_int(_env(merged, "PROCESSING_THREAD_POOL_SIZE", "4"), 4),
        copylint_soft_fail=_as_bool(_env(merged, "COPYLINT_SOFT_FAIL", "false")),
        heic_enabled=_as_bool(_env(merged, "HEIC_ENABLED", "true")),
        session_tmp_root=_env(merged, "COA_PROFILER_TMP_DIR", "/tmp/coa_profiler_sessions"),
    )
    cfg.validate()
    return cfg
