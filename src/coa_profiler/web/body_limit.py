"""Pre-parser request-body limits for public write endpoints.

FastAPI resolves ``UploadFile`` parameters before entering the route, so a
limit implemented in the route is too late to prevent Starlette from spooling
an oversized multipart body.  This raw ASGI middleware meters the receive
channel instead.  It handles both a declared Content-Length and bodies whose
size is only known as chunks arrive.
"""

from __future__ import annotations

import asyncio
import html
import logging
from collections.abc import Awaitable, Callable

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.types import Message, Receive, Scope, Send

log = logging.getLogger("coa_profiler.web.body_limit")

ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

# Multipart boundaries and the single part's headers sit outside the uploaded
# file bytes.  Keep a small fixed allowance so a file exactly at MAX_UPLOAD_MB
# remains valid; the route still enforces the exact file-byte limit.
MULTIPART_OVERHEAD_BYTES = 64 * 1024
FEEDBACK_MAX_BODY_BYTES = 4 * 1024
UPLOAD_BODY_TOO_LARGE_SCOPE_KEY = "coa_profiler.upload_body_too_large"
UPLOAD_BUSY_RETRY_AFTER_SECONDS = 30


class _BodyTooLarge(HTTPException):
    def __init__(self, *, status_code: int, error_code: str) -> None:
        # FastAPI explicitly re-raises HTTPException during body parsing.  The
        # middleware replaces that internal response with the typed UI below.
        super().__init__(status_code=status_code, detail=error_code)


class _UploadLimitResponseSent(Exception):
    """Internal control flow after the downstream response is replaced."""


def _content_length(scope: Scope) -> int | None:
    raw = Headers(scope=scope).get("content-length")
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    # Treat invalid negative values like an absent header and meter the stream.
    return value if value >= 0 else None


def _controlled_upload_response(
    *,
    title: str,
    message: str,
    recovery: str,
    error_code: str,
    status_code: int,
    is_https: bool,
    retry_after: int | None = None,
) -> HTMLResponse:
    headers = {
        "Cache-Control": "private, no-store, max-age=0",
        "Pragma": "no-cache",
        "Vary": "Cookie",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
        "Content-Security-Policy": (
            "default-src 'self'; base-uri 'self'; connect-src 'self'; "
            "font-src 'self'; form-action 'self'; frame-ancestors 'none'; "
            "img-src 'self' data:; object-src 'none'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'"
        ),
    }
    if is_https:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    escaped = tuple(html.escape(value) for value in (title, message, recovery, error_code))
    return HTMLResponse(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escaped[0]} — COA Effect-Spectrum Profiler</title></head>
<body><main><h1>{escaped[0]}</h1><p>{escaped[1]}</p><p>{escaped[2]}</p>
<p>Reference: {escaped[3]}</p><p><a href="/">Back to upload</a></p></main></body></html>""",
        status_code=status_code,
        headers=headers,
    )


def upload_too_large_response(*, is_https: bool = False) -> HTMLResponse:
    # This response is deliberately self-contained: a declared oversize body
    # is rejected without entering FastAPI, templates, or multipart parsing.
    return _controlled_upload_response(
        title="File too large",
        message="The file is larger than the upload limit.",
        recovery="Try a smaller photo or the original PDF. The limit is shown on the upload page.",
        error_code="FILE_TOO_LARGE",
        status_code=422,
        is_https=is_https,
    )


def upload_busy_response(*, is_https: bool = False) -> HTMLResponse:
    return _controlled_upload_response(
        title="Server busy",
        message="The analysis queue is full right now.",
        recovery="Wait about 30 seconds and try again.",
        error_code="SERVER_BUSY",
        status_code=503,
        is_https=is_https,
        retry_after=UPLOAD_BUSY_RETRY_AFTER_SECONDS,
    )


def _controlled_json_response(
    *, error_code: str, status_code: int, is_https: bool, retry_after: int | None = None
) -> JSONResponse:
    headers = {
        "Cache-Control": "private, no-store, max-age=0",
        "Pragma": "no-cache",
        "Vary": "Cookie",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
    if is_https:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse({"error": error_code}, status_code=status_code, headers=headers)


def feedback_too_large_response(*, is_https: bool = False) -> JSONResponse:
    return _controlled_json_response(error_code="FEEDBACK_BODY_TOO_LARGE", status_code=413, is_https=is_https)


def feedback_busy_response(*, is_https: bool = False) -> JSONResponse:
    return _controlled_json_response(
        error_code="SERVER_BUSY",
        status_code=503,
        is_https=is_https,
        retry_after=UPLOAD_BUSY_RETRY_AFTER_SECONDS,
    )


class UploadBodyLimitMiddleware:
    """Cap upload and feedback bodies before FastAPI parses them."""

    def __init__(self, app: ASGIApp, *, max_file_bytes: int, max_concurrent_bodies: int) -> None:
        self.app = app
        self.max_body_bytes = max_file_bytes + MULTIPART_OVERHEAD_BYTES
        self.max_feedback_body_bytes = FEEDBACK_MAX_BODY_BYTES
        self.max_concurrent_bodies = max_concurrent_bodies
        # Independent counters prevent tiny feedback requests from consuming
        # upload admission while bounding aggregate JSON allocations.
        self._in_flight = {"upload": 0, "feedback": 0}
        self._admission_lock = asyncio.Lock()

    async def _try_admit(self, body_kind: str) -> bool:
        async with self._admission_lock:
            if self._in_flight[body_kind] >= self.max_concurrent_bodies:
                return False
            self._in_flight[body_kind] += 1
            return True

    async def _release(self, body_kind: str) -> None:
        async with self._admission_lock:
            self._in_flight[body_kind] -= 1

    def _processing_capacity_full(self, scope: Scope) -> bool:
        """Reject before parsing when timed-out workers still occupy the pool."""
        app = scope.get("app")
        state = getattr(app, "state", None)
        pool_in_flight = getattr(state, "pool_in_flight", 0)
        return pool_in_flight >= self.max_concurrent_bodies

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method", "").upper() != "POST":
            await self.app(scope, receive, send)
            return
        path = scope.get("path")
        if path == "/upload":
            body_kind = "upload"
            max_body_bytes = self.max_body_bytes
            too_large_response = upload_too_large_response
            busy_response = upload_busy_response
        elif path == "/feedback":
            body_kind = "feedback"
            max_body_bytes = self.max_feedback_body_bytes
            too_large_response = feedback_too_large_response
            busy_response = feedback_busy_response
        else:
            await self.app(scope, receive, send)
            return

        declared_size = _content_length(scope)
        if declared_size is not None and declared_size > max_body_bytes:
            log.warning("rejected %s with declared request size over configured limit", body_kind)
            await too_large_response(is_https=scope.get("scheme") == "https")(scope, receive, send)
            return

        if (body_kind == "upload" and self._processing_capacity_full(scope)) or not await self._try_admit(
            body_kind
        ):
            log.warning("rejected %s before body parsing because admission limit is full", body_kind)
            await busy_response(is_https=scope.get("scheme") == "https")(scope, receive, send)
            return

        try:
            await self._receive_bounded_body(
                scope,
                receive,
                send,
                body_kind=body_kind,
                max_body_bytes=max_body_bytes,
                too_large_response=too_large_response,
            )
        finally:
            await self._release(body_kind)

    async def _receive_bounded_body(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        body_kind: str,
        max_body_bytes: int,
        too_large_response: Callable[..., Response],
    ) -> None:
        total_size = 0
        over_limit = False
        response_started = False

        async def receive_with_limit() -> Message:
            nonlocal total_size, over_limit
            message = await receive()
            if message["type"] == "http.request":
                total_size += len(message.get("body", b""))
                if total_size > max_body_bytes:
                    over_limit = True
                    if body_kind == "upload":
                        scope[UPLOAD_BODY_TOO_LARGE_SCOPE_KEY] = True
                    # Do not expose the chunk that crosses the cap to the
                    # multipart parser (and therefore never spool the full body).
                    raise _BodyTooLarge(
                        status_code=422 if body_kind == "upload" else 413,
                        error_code="FILE_TOO_LARGE" if body_kind == "upload" else "FEEDBACK_BODY_TOO_LARGE",
                    )
            return message

        async def send_with_limit(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                if over_limit:
                    log.warning(
                        "rejected streaming %s after request size crossed configured limit", body_kind
                    )
                    await too_large_response(is_https=scope.get("scheme") == "https")(scope, receive, send)
                    raise _UploadLimitResponseSent
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive_with_limit, send_with_limit)
        except _BodyTooLarge:
            # Normally ExceptionMiddleware turns this into a response and
            # send_with_limit replaces it.  This fallback covers a minimal ASGI
            # app with no exception layer.
            if response_started:
                raise
            await too_large_response(is_https=scope.get("scheme") == "https")(scope, receive, send)
        except _UploadLimitResponseSent:
            pass
