"""FR-012 sessions: TTL expiry, teardown deletes temp dirs, sweeper logging."""

import logging
import os
import stat

import pytest

from coa_profiler.scorer.placement import PlacementResult
from coa_profiler.web import session as session_module
from coa_profiler.web.routes import _discard_dir
from coa_profiler.web.session import SessionStore, startup_sweep
from tests.conftest import make_chemistry


def _placement():
    return PlacementResult(
        score=70,
        raw_score=70.0,
        confidence_data=1.0,
        confidence_model=0.75,
        confidence_combined=0.75,
        completeness="full",
    )


def _chemistry():
    return make_chemistry({"thc_total": (18.2, "%")}, {"myrcene": (0.85, "%")})


def test_create_get_roundtrip(tmp_path):
    store = SessionStore(300, str(tmp_path))
    session_dir = store.new_session_dir("a" * 32)
    working = session_dir / "working.pdf"
    working.write_bytes(b"%PDF-1.4 probe")
    record = store.create(_chemistry(), _placement(), str(working), token="a" * 32)
    assert len(record.session_token) == 32
    assert store.get("a" * 32) is record


def test_session_directory_is_owner_only(tmp_path):
    store = SessionStore(300, str(tmp_path))
    session_dir = store.new_session_dir("f" * 32)
    assert session_dir.stat().st_mode & 0o777 == 0o700


def test_session_root_hides_token_leaf_names_under_permissive_umask(tmp_path):
    root = tmp_path / "sessions"
    previous_umask = os.umask(0)
    try:
        store = SessionStore(300, str(root))
        session_dir = store.new_session_dir("1" * 32)
    finally:
        os.umask(previous_umask)

    # Group/other users cannot list or traverse the parent to discover token
    # leaf names, even when the process starts with a fully permissive umask.
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE(root.stat().st_mode) & 0o077 == 0
    assert stat.S_IMODE(session_dir.stat().st_mode) == 0o700


def test_session_root_rejects_symlink_and_non_directory(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    symlink_root = tmp_path / "sessions-link"
    symlink_root.symlink_to(target, target_is_directory=True)
    with pytest.raises(RuntimeError, match="must not be a symlink"):
        SessionStore(300, str(symlink_root))

    file_root = tmp_path / "sessions-file"
    file_root.write_text("not a directory")
    with pytest.raises(RuntimeError, match="unable to create session temp root"):
        SessionStore(300, str(file_root))


def test_expired_session_torn_down_lazily(tmp_path):
    store = SessionStore(0, str(tmp_path))  # ttl 0: immediately expired
    session_dir = store.new_session_dir("b" * 32)
    working = session_dir / "working.pdf"
    working.write_bytes(b"%PDF-1.4 probe")
    store.create(_chemistry(), _placement(), str(working), token="b" * 32)
    assert store.get("b" * 32) is None
    assert not session_dir.exists()  # temp dir deleted on expiry (AC-006)


def test_teardown_removes_dir(tmp_path):
    store = SessionStore(300, str(tmp_path))
    session_dir = store.new_session_dir("c" * 32)
    working = session_dir / "working.png"
    working.write_bytes(b"png")
    store.create(_chemistry(), _placement(), str(working), token="c" * 32)
    assert store.teardown("c" * 32) is True
    assert not session_dir.exists()
    assert store.teardown("c" * 32) is False


def test_removal_failure_retains_record_for_retry_and_logs(tmp_path, monkeypatch, caplog):
    store = SessionStore(300, str(tmp_path))
    token = "9" * 32
    session_dir = store.new_session_dir(token)
    working = session_dir / "working.pdf"
    working.write_bytes(b"private chemistry")
    store.create(_chemistry(), _placement(), str(working), token=token)
    real_rmtree = session_module.shutil.rmtree
    calls = 0

    def fail_once(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("simulated removal failure")
        real_rmtree(path)

    monkeypatch.setattr(session_module.shutil, "rmtree", fail_once)
    caplog.set_level(logging.ERROR, logger="coa_profiler.session")

    assert store.teardown(token) is False
    assert len(store) == 1
    assert working.exists()
    assert "deletion will be retried" in caplog.text

    assert store.teardown(token) is True
    assert len(store) == 0
    assert not session_dir.exists()


def test_sweep_counts(tmp_path):
    store = SessionStore(0, str(tmp_path))
    for ch in "def":
        d = store.new_session_dir(ch * 32)
        (d / "working.pdf").write_bytes(b"x")
        store.create(_chemistry(), _placement(), str(d / "working.pdf"), token=ch * 32)
    cleaned, remaining = store.sweep()
    assert cleaned == 3 and remaining == 0
    assert list(tmp_path.iterdir()) == []


def test_startup_sweep_removes_stale_dirs(tmp_path):
    root = tmp_path / "sessions"
    (root / "coa_profiler_session_old1").mkdir(parents=True)
    (root / "coa_profiler_session_old2").mkdir(parents=True)
    (root / "keep_this").mkdir()
    assert startup_sweep(str(root)) == 2
    assert (root / "keep_this").is_dir()
    assert not (root / "coa_profiler_session_old1").exists()


def test_startup_sweep_counts_only_success_and_logs_failures(tmp_path, monkeypatch, caplog):
    root = tmp_path / "sessions"
    removed_dir = root / "coa_profiler_session_removed"
    retained_dir = root / "coa_profiler_session_retained"
    removed_dir.mkdir(parents=True)
    retained_dir.mkdir()
    real_rmtree = session_module.shutil.rmtree

    def fail_retained(path):
        if path == retained_dir:
            raise PermissionError("simulated startup removal failure")
        real_rmtree(path)

    monkeypatch.setattr(session_module.shutil, "rmtree", fail_retained)
    caplog.set_level(logging.ERROR, logger="coa_profiler.session")

    assert startup_sweep(str(root)) == 1
    assert not removed_dir.exists()
    assert retained_dir.exists()
    assert str(retained_dir) in caplog.text


def test_create_uses_upload_start_for_ttl(tmp_path):
    store = SessionStore(300, str(tmp_path))
    token = "8" * 32
    session_dir = store.new_session_dir(token)
    working = session_dir / "working.pdf"
    working.write_bytes(b"private chemistry")
    upload_started_at = 1234.5

    record = store.create(
        _chemistry(),
        _placement(),
        str(working),
        token=token,
        created_at=upload_started_at,
    )

    assert record.created_at == upload_started_at


def test_unregistered_discard_failure_is_logged_and_retryable(tmp_path, monkeypatch, caplog):
    session_dir = tmp_path / "coa_profiler_session_pending"
    session_dir.mkdir()
    working = session_dir / "working.pdf"
    working.write_bytes(b"private chemistry")
    real_rmtree = session_module.shutil.rmtree
    calls = 0

    def fail_once(path):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("simulated discard failure")
        real_rmtree(path)

    monkeypatch.setattr(session_module.shutil, "rmtree", fail_once)
    caplog.set_level(logging.ERROR, logger="coa_profiler.web")

    assert _discard_dir(session_dir) is False
    assert working.exists()
    assert "startup sweep will retry" in caplog.text
    assert _discard_dir(session_dir) is True
    assert not session_dir.exists()


def test_foreign_dir_never_removed(tmp_path):
    store = SessionStore(300, str(tmp_path))
    outside = tmp_path.parent / "not_a_session" / "working.pdf"
    outside.parent.mkdir()
    outside.write_bytes(b"x")
    store._remove_dir(str(outside))
    assert outside.exists()  # safety: only prefixed dirs inside tmp_root go
