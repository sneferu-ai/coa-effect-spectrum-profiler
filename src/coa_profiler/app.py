"""FastAPI application factory (S1–S7).

Boot sequence (lifespan startup):
1. boot-time copy-lint scan of the static templates (FR-019) — FATAL by
   default; ``COPYLINT_SOFT_FAIL=true`` downgrades to a loud warning
2. HEIC decoder check (DIS-9) — fatal at boot when HEIC is enabled and the
   decoder is missing; the reversible fallback is dropping HEIC entirely
   (``HEIC_ENABLED=false``, assumption A-04)
3. boot-time audit logs: ``INFERENCE_ASSIST_ACTIVE`` (FR-026) and, when
   applicable, ``COPYLINT_SOFT_FAIL_ACTIVE``
4. startup sweep of stale session temp directories (FR-012)
5. session sweeper background task (FR-012)

Shutdown logs the ephemeral feedback aggregate (FR-024).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from coa_profiler.config import Config, load_config
from coa_profiler.errors import COAError
from coa_profiler.parser.ocr import heic_decoder_available
from coa_profiler.web.body_limit import (
    UPLOAD_BODY_TOO_LARGE_SCOPE_KEY,
    UploadBodyLimitMiddleware,
    upload_too_large_response,
)
from coa_profiler.web.process_isolation import UploadProcessManager
from coa_profiler.web.rate_limit import RateLimiter, client_ip
from coa_profiler.web.routes import FeedbackAggregate, router
from coa_profiler.web.session import SessionStore, startup_sweep

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("coa_profiler.app")

_WEB_DIR = Path(__file__).parent / "web"

#: Boot copy-lint must stay fast (AC-043); a slower static scan is logged.
_BOOT_SCAN_BUDGET_S = 5.0
# Cancellation polling plus TERM/KILL grace in process_isolation is under two
# seconds. Shutdown waits a bounded extra margin, never on native parser work.
_UPLOAD_SHUTDOWN_GRACE_S = 3.0


def _format_ip(ip: str, mode: str) -> str:
    """FR-013 access-log IP handling per LOG_IP_RETENTION."""
    if mode == "disabled":
        return "-"
    if mode == "full":
        return ip
    if mode == "truncated":
        if "." in ip:
            return ip.rsplit(".", 1)[0] + ".0"
        if ":" in ip:
            return ip.rsplit(":", 1)[0] + ":0"
        return ip
    # hashed (default): SHA-256 with a daily-rotated salt
    daily_salt = datetime.now(UTC).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{daily_salt}:{ip}".encode()).hexdigest()[:16]


def create_app(config: Config | None = None) -> FastAPI:
    cfg = config or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 1. Boot-time copy-lint (static templates only, fast).
        from coa_profiler.copylint import scan_templates

        started = time.monotonic()
        hits = scan_templates(_WEB_DIR / "templates")
        elapsed = time.monotonic() - started
        if elapsed >= _BOOT_SCAN_BUDGET_S:
            log.warning("boot copy-lint took %.2fs (budget %.0fs)", elapsed, _BOOT_SCAN_BUDGET_S)
        if cfg.copylint_soft_fail:
            log.warning("COPYLINT_SOFT_FAIL_ACTIVE: true")
        if hits and not cfg.copylint_soft_fail:
            for hit in hits[:5]:
                log.error("copy-lint: banned term %r in %s", hit.term, hit.location)
            raise RuntimeError(
                f"copy-lint found {len(hits)} banned term(s) in templates; refusing to start "
                "(walk-away gate 4). Set COPYLINT_SOFT_FAIL=true for emergency override."
            )
        if hits:
            log.warning("copy-lint: %d banned term(s) allowed by COPYLINT_SOFT_FAIL", len(hits))
        else:
            log.info("copy-lint: clean (%d templates)", len(list((_WEB_DIR / "templates").glob("*.html"))))

        # 2. HEIC decoder (DIS-9: absence is fatal when HEIC is enabled).
        if cfg.heic_enabled and not heic_decoder_available():
            raise RuntimeError(
                "HEIC decoder (pillow-heif / libheif) is unavailable and HEIC support is enabled. "
                "Install pillow-heif + libheif, or set HEIC_ENABLED=false to drop HEIC (A-04)."
            )
        log.info("heic_enabled=%s heic_decoder=%s", cfg.heic_enabled, heic_decoder_available())

        # 3. Boot-time audit logs (FR-026).
        if cfg.inference_assist_enabled:
            log.warning("INFERENCE_ASSIST_ACTIVE: true, url=%s", cfg.inference_assist_url)
        else:
            log.info("INFERENCE_ASSIST_ACTIVE: false")

        # 4. Startup sweep of stale session temp dirs (FR-012).
        removed = startup_sweep(cfg.session_tmp_root)
        if removed:
            log.info("startup sweep removed %d stale session dir(s)", removed)

        # 5. Background session sweeper (FR-012).
        app.state.sessions.start_sweeper()
        log.info("coa_profiler %s ready (port %s)", cfg.version, cfg.port)
        try:
            yield
        finally:
            await app.state.sessions.stop_sweeper()
            # Stop every process group before deleting working copies. The
            # bounded wait cannot inherit a native parser hang; supervisors
            # escalate TERM to KILL and report idle independently of the pool.
            app.state.upload_processes.cancel_all()
            upload_workers_stopped = await asyncio.to_thread(
                app.state.upload_processes.wait_for_idle,
                _UPLOAD_SHUTDOWN_GRACE_S,
            )
            if not upload_workers_stopped:
                log.critical("isolated upload supervisors exceeded shutdown grace")
            app.state.pool.shutdown(wait=upload_workers_stopped, cancel_futures=True)
            cleaned, remaining = app.state.sessions.teardown_all()
            log.info("shutdown session cleanup: cleaned=%d, remaining=%d", cleaned, remaining)
            if remaining:
                log.error("shutdown retained %d session(s) after deletion failures", remaining)
            aggregate: FeedbackAggregate = app.state.feedback
            log.info("feedback_summary: %s", aggregate.summary())

    # The public product has a closed route manifest and no third-party/CDN
    # resources. FastAPI's default documentation shells add undeclared routes
    # and reference CDN scripts, so they are deliberately absent in production.
    app = FastAPI(
        title="COA Effect-Spectrum Profiler",
        version=cfg.version,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.config = cfg
    app.state.sessions = SessionStore(cfg.session_ttl_seconds, cfg.session_tmp_root)
    app.state.rate_limiter = RateLimiter()
    app.state.feedback = FeedbackAggregate()
    app.state.pool = ThreadPoolExecutor(
        max_workers=cfg.processing_thread_pool_size, thread_name_prefix="coa-worker"
    )
    app.state.upload_processes = UploadProcessManager(app.state.pool)
    app.state.pool_in_flight = 0
    app.state.templates = Jinja2Templates(directory=str(_WEB_DIR / "templates"))
    # UI wiring: every page (including error surfaces rendered by the
    # exception handlers) gets the cache-busting static version and the public
    # contact address without each route re-passing them.
    app.state.templates.env.globals["static_version"] = cfg.version
    app.state.templates.env.globals["contact_email"] = cfg.contact_email

    @app.middleware("http")
    async def access_log_and_headers(request: Request, call_next):
        # Opportunistic expiry sweep (throttled): the cookie's max-age equals
        # the TTL, so expired tokens may never arrive again.
        request.app.state.sessions.maybe_sweep()
        started = time.monotonic()
        response: Response = await call_next(request)
        if request.scope.get(UPLOAD_BODY_TOO_LARGE_SCOPE_KEY):
            # BaseHTTPMiddleware may wrap receive-channel exceptions before
            # FastAPI sees them. Keep the inner response and access log aligned
            # with the outer ASGI limiter's typed 422 response.
            response = upload_too_large_response(is_https=request.url.scheme == "https")
        elapsed_ms = (time.monotonic() - started) * 1000
        # FR-013: IP per LOG_IP_RETENTION; endpoint path, status, response
        # time. Cookie headers are never logged. Session tokens live in
        # cookies, so access logs record clean endpoint paths only.
        ip = _format_ip(client_ip(request, cfg), cfg.log_ip_retention)
        log.info(
            "access ip=%s method=%s path=%s status=%d ms=%.1f",
            ip,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), geolocation=(), microphone=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; connect-src 'self'; "
            "font-src 'self'; form-action 'self'; frame-ancestors 'none'; "
            "img-src 'self' data:; object-src 'none'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'",
        )
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        if request.url.path.startswith(("/result", "/upload", "/new")):
            # Result pages and generated downloads contain the user's chemistry.
            # They must never be retained by a browser or shared intermediary.
            response.headers["Cache-Control"] = "private, no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Vary"] = "Cookie"
        elif request.url.path.startswith("/static/") and request.query_params.get("v") == cfg.version:
            # Only the active build identifier is immutable.  Arbitrary or
            # stale query values must not turn a mutable asset into a one-year
            # cache entry.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif request.url.path.startswith("/static/") and request.query_params.get("v"):
            response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
        return response

    @app.exception_handler(COAError)
    async def coa_error_handler(request: Request, exc: COAError) -> Response:
        return request.app.state.templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": exc.user_title,
                "message": exc.user_message,
                "recovery": exc.recovery,
                "error_code": exc.error_code,
            },
            status_code=exc.http_status,
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> Response:
        log.exception("unhandled error on %s", request.url.path)
        err = COAError()
        return request.app.state.templates.TemplateResponse(
            request,
            "error.html",
            {
                "title": err.user_title,
                "message": err.user_message,
                "recovery": err.recovery,
                "error_code": err.error_code,
            },
            status_code=500,
        )

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")
    # Added last so it is the outermost user middleware. Upload multipart and
    # feedback JSON bodies are bounded before dependency resolution parses them.
    app.add_middleware(
        UploadBodyLimitMiddleware,
        max_file_bytes=cfg.max_upload_bytes,
        max_concurrent_bodies=cfg.processing_thread_pool_size,
    )
    return app


app = create_app()
