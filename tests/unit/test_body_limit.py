"""Write-body caps run on the ASGI receive channel, before parsing."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from coa_profiler.app import create_app
from coa_profiler.config import Config
from coa_profiler.web.body_limit import (
    FEEDBACK_MAX_BODY_BYTES,
    MULTIPART_OVERHEAD_BYTES,
    UploadBodyLimitMiddleware,
)


def test_declared_oversize_never_enters_multipart_parser(tmp_path, monkeypatch):
    from starlette.formparsers import MultiPartParser

    async def parser_must_not_run(_self):
        raise AssertionError("multipart parser was entered for a declared oversized body")

    monkeypatch.setattr(MultiPartParser, "parse", parser_must_not_run)
    cfg = Config(
        max_upload_mb=1,
        session_cookie_secure=False,
        heic_enabled=False,
        session_tmp_root=str(tmp_path / "sessions"),
    )
    with TestClient(create_app(cfg), base_url="https://testserver") as client:
        response = client.post(
            "/upload",
            files={"file": ("large.pdf", b"%PDF-1.4\n" + b"x" * (2 * 1024 * 1024))},
        )

    assert response.status_code == 422
    assert "FILE_TOO_LARGE" in response.text
    assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"


def test_chunked_body_stops_at_first_cumulative_overage():
    received_by_downstream = 0
    downstream_called = False

    async def downstream(_scope, receive, _send):
        nonlocal received_by_downstream, downstream_called
        downstream_called = True
        while True:
            message = await receive()
            received_by_downstream += len(message.get("body", b""))
            if not message.get("more_body", False):
                break

    cap = 1024 + MULTIPART_OVERHEAD_BYTES
    chunks = [b"a" * (cap // 2), b"b" * (cap // 2), b"c" * 2, b"never-read"]
    receive_calls = 0
    sent: list[dict] = []

    async def receive():
        nonlocal receive_calls
        chunk = chunks[receive_calls]
        receive_calls += 1
        return {"type": "http.request", "body": chunk, "more_body": receive_calls < len(chunks)}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/upload",
        "raw_path": b"/upload",
        "query_string": b"",
        "headers": [(b"content-type", b"multipart/form-data; boundary=x")],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }
    middleware = UploadBodyLimitMiddleware(downstream, max_file_bytes=1024, max_concurrent_bodies=1)
    asyncio.run(middleware(scope, receive, send))

    assert downstream_called is True
    assert receive_calls == 3
    assert received_by_downstream == cap
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 422
    body = b"".join(message.get("body", b"") for message in sent)
    assert b"FILE_TOO_LARGE" in body


def test_limit_only_applies_to_public_body_endpoints():
    calls = 0

    async def downstream(_scope, _receive, send):
        nonlocal calls
        calls += 1
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def exercise():
        for method, path in (("POST", "/other"), ("GET", "/upload")):
            sent = []

            async def send(message, target=sent):
                target.append(message)

            scope = {
                "type": "http",
                "method": method,
                "path": path,
                "headers": [(b"content-length", b"999999")],
            }
            await UploadBodyLimitMiddleware(downstream, max_file_bytes=1, max_concurrent_bodies=1)(
                scope, receive, send
            )

    asyncio.run(exercise())
    assert calls == 2


def test_declared_oversize_feedback_never_enters_json_parser(tmp_path, monkeypatch):
    from starlette.requests import Request

    async def json_parser_must_not_run(_self):
        raise AssertionError("JSON parser entered for declared oversized feedback")

    monkeypatch.setattr(Request, "json", json_parser_must_not_run)
    cfg = Config(
        session_cookie_secure=False,
        heic_enabled=False,
        session_tmp_root=str(tmp_path / "sessions"),
    )
    with TestClient(create_app(cfg)) as client:
        response = client.post(
            "/feedback",
            content=b"x" * (FEEDBACK_MAX_BODY_BYTES + 1),
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 413
    assert response.json() == {"error": "FEEDBACK_BODY_TOO_LARGE"}
    assert response.headers["Cache-Control"] == "private, no-store, max-age=0"


def test_chunked_feedback_stops_at_first_cumulative_overage():
    received_by_downstream = 0
    chunks = [b"a" * 2048, b"b" * 2048, b"c", b"never-read"]
    receive_calls = 0
    sent: list[dict] = []

    async def downstream(_scope, receive, _send):
        nonlocal received_by_downstream
        while True:
            message = await receive()
            received_by_downstream += len(message.get("body", b""))
            if not message.get("more_body", False):
                break

    async def receive():
        nonlocal receive_calls
        chunk = chunks[receive_calls]
        receive_calls += 1
        return {"type": "http.request", "body": chunk, "more_body": True}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/feedback",
        "headers": [(b"content-type", b"application/json")],
    }
    middleware = UploadBodyLimitMiddleware(downstream, max_file_bytes=1, max_concurrent_bodies=1)
    asyncio.run(middleware(scope, receive, send))

    assert receive_calls == 3
    assert received_by_downstream == FEEDBACK_MAX_BODY_BYTES
    assert sent[0]["status"] == 413
    assert b"FEEDBACK_BODY_TOO_LARGE" in sent[1]["body"]


def test_slow_feedback_body_holds_admission_and_second_is_rejected_without_reading():
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    downstream_calls = 0
    second_receive_calls = 0
    second_sent: list[dict] = []

    async def downstream(_scope, receive, send):
        nonlocal downstream_calls
        downstream_calls += 1
        await receive()
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def first_receive():
        first_started.set()
        await release_first.wait()
        return {"type": "http.request", "body": b"{}", "more_body": False}

    async def second_receive():
        nonlocal second_receive_calls
        second_receive_calls += 1
        return {"type": "http.request", "body": b"{}", "more_body": False}

    async def first_send(_message):
        return None

    async def second_send(message):
        second_sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/feedback",
        "headers": [],
    }

    async def exercise():
        middleware = UploadBodyLimitMiddleware(downstream, max_file_bytes=1024, max_concurrent_bodies=1)
        first_task = asyncio.create_task(middleware(scope, first_receive, first_send))
        await first_started.wait()
        await middleware(scope, second_receive, second_send)
        release_first.set()
        await first_task

    asyncio.run(exercise())

    assert downstream_calls == 1
    assert second_receive_calls == 0
    assert second_sent[0]["status"] == 503
    assert dict(second_sent[0]["headers"])[b"retry-after"] == b"30"


def test_slow_body_holds_admission_and_next_upload_is_rejected_without_reading():
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    downstream_calls: list[str] = []
    second_receive_calls = 0
    second_sent: list[dict] = []

    async def downstream(scope, receive, send):
        downstream_calls.append(scope["request_id"])
        await receive()
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def first_receive():
        first_started.set()
        await release_first.wait()
        return {"type": "http.request", "body": b"small", "more_body": False}

    async def second_receive():
        nonlocal second_receive_calls
        second_receive_calls += 1
        return {"type": "http.request", "body": b"small", "more_body": False}

    async def second_send(message):
        second_sent.append(message)

    def scope(request_id: str) -> dict:
        return {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/upload",
            "headers": [],
            "request_id": request_id,
        }

    async def exercise():
        middleware = UploadBodyLimitMiddleware(
            downstream,
            max_file_bytes=1024,
            max_concurrent_bodies=1,
        )
        first_sent = []

        async def first_send(message):
            first_sent.append(message)

        first_task = asyncio.create_task(middleware(scope("first"), first_receive, first_send))
        await first_started.wait()

        await middleware(scope("second"), second_receive, second_send)
        assert not first_task.done()

        release_first.set()
        await first_task

        # The slot is released after completion, so a later request is admitted.
        await middleware(scope("third"), second_receive, second_send)

    asyncio.run(exercise())

    assert downstream_calls == ["first", "third"]
    assert second_receive_calls == 1  # third only; the rejected second body was untouched
    assert second_sent[0]["status"] == 503
    headers = dict(second_sent[0]["headers"])
    assert headers[b"retry-after"] == b"30"
    assert b"SERVER_BUSY" in second_sent[1]["body"]


def test_lingering_processing_worker_rejects_before_body_read():
    downstream_calls = 0
    receive_calls = 0
    sent: list[dict] = []

    async def downstream(_scope, _receive, _send):
        nonlocal downstream_calls
        downstream_calls += 1

    async def receive():
        nonlocal receive_calls
        receive_calls += 1
        return {"type": "http.request", "body": b"small", "more_body": False}

    async def send(message):
        sent.append(message)

    app = type("App", (), {"state": type("State", (), {"pool_in_flight": 1})()})()
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "http",
        "path": "/upload",
        "headers": [],
        "app": app,
    }
    middleware = UploadBodyLimitMiddleware(
        downstream,
        max_file_bytes=1024,
        max_concurrent_bodies=1,
    )
    asyncio.run(middleware(scope, receive, send))

    assert downstream_calls == 0
    assert receive_calls == 0
    assert sent[0]["status"] == 503
