"""Spawned upload workers preserve results/errors and are forcibly bounded."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from coa_profiler.errors import NotACOAError, ProcessingTimeoutError
from coa_profiler.web.process_isolation import (
    DEFAULT_UPLOAD_PROCESS_CLEANUP_BUDGET_S,
    UploadProcessManager,
    run_isolated_upload,
)
from tests.process_worker_helpers import hang_with_grandchild, raise_typed_error, return_value


def _process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A killed descendant may briefly remain as a zombie until init reaps it;
    # it can no longer execute or retain parser resources.
    status = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return bool(status) and not status.startswith("Z")


def _wait_not_running(pid: int, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_is_running(pid):
            return True
        time.sleep(0.02)
    return not _process_is_running(pid)


def test_spawned_worker_returns_pickled_result():
    result = run_isolated_upload(return_value, "ok", timeout_seconds=5)
    assert result["value"] == "ok"
    assert result["child_pid"] != os.getpid()


def test_child_deadline_leaves_route_time_for_forced_cleanup():
    from coa_profiler.web.routes import ISOLATED_PIPELINE_TIMEOUT_S, PROCESSING_TIMEOUT_S

    assert ISOLATED_PIPELINE_TIMEOUT_S + DEFAULT_UPLOAD_PROCESS_CLEANUP_BUDGET_S < PROCESSING_TIMEOUT_S


def test_spawned_worker_rehydrates_typed_coa_error():
    with pytest.raises(NotACOAError, match="typed child error probe") as raised:
        run_isolated_upload(raise_typed_error, None, timeout_seconds=5)
    assert raised.value.error_code == "NOT_A_COA"


@pytest.mark.skipif(os.name != "posix", reason="production process-group isolation is POSIX")
def test_deadline_kills_child_and_grandchild_process_group(tmp_path):
    marker = tmp_path / "pids"
    with pytest.raises(ProcessingTimeoutError):
        run_isolated_upload(
            hang_with_grandchild,
            str(marker),
            timeout_seconds=2,
            terminate_grace_s=0.1,
            kill_grace_s=0.5,
        )

    child_pid, grandchild_pid = map(int, marker.read_text(encoding="utf-8").split())
    assert _wait_not_running(child_pid)
    assert _wait_not_running(grandchild_pid)


def test_timeout_releases_manager_capacity_for_next_upload(tmp_path):
    marker = tmp_path / "pids"
    with ThreadPoolExecutor(max_workers=1) as pool:
        manager = UploadProcessManager(pool)
        timed_out = manager.submit(
            hang_with_grandchild,
            str(marker),
            timeout_seconds=1,
        )
        with pytest.raises(ProcessingTimeoutError):
            timed_out.future.result(timeout=5)
        assert manager.wait_for_idle(1)
        assert manager.active_count == 0

        following = manager.submit(return_value, "next", timeout_seconds=5)
        assert following.future.result(timeout=8)["value"] == "next"
        assert manager.wait_for_idle(1)


def test_shutdown_cancellation_is_bounded_and_kills_active_child(tmp_path):
    marker = tmp_path / "pids"
    pool = ThreadPoolExecutor(max_workers=1)
    manager = UploadProcessManager(pool)
    job = manager.submit(hang_with_grandchild, str(marker), timeout_seconds=60)
    deadline = time.monotonic() + 5
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert marker.exists()

    started = time.monotonic()
    manager.cancel_all()
    assert manager.wait_for_idle(3)
    assert time.monotonic() - started < 3
    pool.shutdown(wait=True, cancel_futures=True)

    child_pid, grandchild_pid = map(int, marker.read_text(encoding="utf-8").split())
    assert _wait_not_running(child_pid)
    assert _wait_not_running(grandchild_pid)
    assert job.future.done()


def test_application_lifespan_shutdown_does_not_wait_for_hung_parser(tmp_path):
    from coa_profiler.app import create_app
    from coa_profiler.config import Config

    marker = tmp_path / "lifespan-pids"
    app = create_app(
        Config(
            heic_enabled=False,
            session_cookie_secure=False,
            session_tmp_root=str(tmp_path / "sessions"),
            processing_thread_pool_size=1,
        )
    )

    async def exercise():
        async with app.router.lifespan_context(app):
            job = app.state.upload_processes.submit(
                hang_with_grandchild,
                str(marker),
                timeout_seconds=60,
            )
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                await asyncio.sleep(0.02)
            assert marker.exists()
            shutdown_started = time.monotonic()
        return job, time.monotonic() - shutdown_started

    job, shutdown_elapsed = asyncio.run(exercise())
    assert shutdown_elapsed < 4
    assert app.state.upload_processes.active_count == 0
    assert job.future.done()

    child_pid, grandchild_pid = map(int, marker.read_text(encoding="utf-8").split())
    assert _wait_not_running(child_pid)
    assert _wait_not_running(grandchild_pid)
