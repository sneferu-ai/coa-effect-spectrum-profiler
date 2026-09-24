"""Picklable child-process workers used by isolation tests."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from coa_profiler.errors import NotACOAError


def return_value(value):
    return {"value": value, "child_pid": os.getpid()}


def raise_typed_error(_value):
    raise NotACOAError("typed child error probe")


def hang_with_grandchild(marker_path: str) -> None:
    grandchild = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(300)"],
        close_fds=True,
    )
    Path(marker_path).write_text(f"{os.getpid()} {grandchild.pid}", encoding="utf-8")
    while True:
        time.sleep(1)


def delayed_real_upload(data, file_type, session_dir, config):
    marker = Path(session_dir) / "worker-started-at"
    marker.write_text(str(time.time()), encoding="utf-8")
    time.sleep(0.05)
    # The parent monkeypatch does not exist in this clean spawned interpreter.
    from coa_profiler.web.routes import process_upload

    return process_upload(data, file_type, session_dir, config)


def hang_upload(_data, _file_type, session_dir, _config):
    Path(session_dir, "worker-pid").write_text(str(os.getpid()), encoding="utf-8")
    while True:
        time.sleep(1)
