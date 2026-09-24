"""AC-031 / FR-019 / DIS-9 boot gates: copy-lint fatal vs soft-fail, HEIC."""

import pytest
from fastapi.testclient import TestClient

from coa_profiler.app import create_app
from coa_profiler.config import Config
from coa_profiler.copylint import CopyHit


def _cfg(tmp_path, **kw):
    defaults = {
        "session_cookie_secure": False,
        "heic_enabled": False,
        "session_tmp_root": str(tmp_path / "sessions"),
    }
    defaults.update(kw)
    return Config(**defaults)


def _fake_hit():
    return [CopyHit(location="result.html", term="treat", matched="treat", context="... injected ...")]


class TestCopylintBoot:
    def test_fatal_by_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr("coa_profiler.copylint.scan_templates", lambda _d: _fake_hit())
        with pytest.raises(RuntimeError, match="copy-lint"), TestClient(create_app(_cfg(tmp_path))):
            pass

    def test_soft_fail_allows_boot_and_logs(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr("coa_profiler.copylint.scan_templates", lambda _d: _fake_hit())
        with (
            caplog.at_level("WARNING"),
            TestClient(create_app(_cfg(tmp_path, copylint_soft_fail=True))) as client,
        ):
            assert client.get("/healthz").status_code == 200
        assert any("COPYLINT_SOFT_FAIL_ACTIVE: true" in r.message for r in caplog.records)


class TestHeicBoot:
    def test_missing_decoder_is_fatal_when_enabled(self, tmp_path, monkeypatch):
        monkeypatch.setattr("coa_profiler.app.heic_decoder_available", lambda: False)
        with (
            pytest.raises(RuntimeError, match="HEIC"),
            TestClient(create_app(_cfg(tmp_path, heic_enabled=True))),
        ):
            pass

    def test_disabled_heic_boots(self, tmp_path, monkeypatch):
        monkeypatch.setattr("coa_profiler.app.heic_decoder_available", lambda: False)
        with TestClient(create_app(_cfg(tmp_path, heic_enabled=False))) as client:
            assert client.get("/healthz").status_code == 200


class TestAuditLog:
    def test_inference_assist_lines(self, tmp_path, caplog):
        with caplog.at_level("INFO"), TestClient(create_app(_cfg(tmp_path))):
            pass
        assert any("INFERENCE_ASSIST_ACTIVE: false" in r.message for r in caplog.records)

    def test_inference_assist_enabled_line(self, tmp_path, caplog):
        with (
            caplog.at_level("INFO"),
            TestClient(
                create_app(
                    _cfg(
                        tmp_path, inference_assist_enabled=True, inference_assist_url="http://localhost:9999"
                    )
                )
            ),
        ):
            pass
        assert any(
            "INFERENCE_ASSIST_ACTIVE: true, url=http://localhost:9999" in r.message for r in caplog.records
        )
