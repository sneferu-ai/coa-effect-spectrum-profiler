"""Cancellation retains capacity until the spawned process is confirmed dead."""

from __future__ import annotations

import asyncio
import io

import pytest
from fastapi import UploadFile
from starlette.requests import Request

from coa_profiler.app import create_app
from coa_profiler.config import Config
from coa_profiler.web import routes
from tests.process_worker_helpers import hang_upload


def test_cancelled_upload_kills_worker_then_releases_capacity(tmp_path, fixtures_dir, monkeypatch):
    monkeypatch.setattr(routes, "process_upload", hang_upload)
    config = Config(
        session_cookie_secure=False,
        heic_enabled=False,
        processing_thread_pool_size=1,
        session_tmp_root=str(tmp_path / "sessions"),
    )
    app = create_app(config)

    async def exercise_cancellation():
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/upload",
            "raw_path": b"/upload",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "app": app,
        }
        request = Request(scope)
        upload = UploadFile(
            file=io.BytesIO((fixtures_dir / "fl_coa_sample.pdf").read_bytes()),
            filename="coa.pdf",
        )
        task = asyncio.create_task(routes.upload(request, upload))
        deadline = asyncio.get_running_loop().time() + 5
        marker = None
        while marker is None and asyncio.get_running_loop().time() < deadline:
            markers = list((tmp_path / "sessions").glob("coa_profiler_session_*/worker-pid"))
            marker = markers[0] if markers else None
            await asyncio.sleep(0.01)
        assert marker is not None

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        deadline = asyncio.get_running_loop().time() + 3
        while app.state.pool_in_flight and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.01)
        assert app.state.pool_in_flight == 0
        assert app.state.upload_processes.active_count == 0
        assert not list((tmp_path / "sessions").glob("coa_profiler_session_*"))

    try:
        asyncio.run(exercise_cancellation())
    finally:
        app.state.upload_processes.cancel_all()
        assert app.state.upload_processes.wait_for_idle(3)
        app.state.pool.shutdown(wait=True, cancel_futures=True)
