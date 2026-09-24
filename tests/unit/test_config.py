"""Config loading: defaults, env overrides, validation."""

from pathlib import Path

import pytest

from coa_profiler.config import MAX_DECODED_PIXELS_IN_FLIGHT, Config, load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_defaults():
    cfg = Config()
    assert cfg.max_upload_mb == 15
    assert cfg.max_pdf_pages == 20
    assert cfg.max_pdf_page_pixels == 8_000_000
    assert cfg.max_pdf_total_pixels == 48_000_000
    assert cfg.max_image_pixels == 12_000_000
    assert cfg.max_image_dimension == 8_000
    assert cfg.ocr_timeout_seconds == 30
    assert cfg.session_ttl_seconds == 300
    assert cfg.session_cookie_secure is True
    assert cfg.inference_assist_enabled is False
    assert cfg.log_ip_retention == "hashed"
    assert cfg.processing_thread_pool_size == 4
    assert cfg.copylint_soft_fail is False
    assert cfg.contact_email == ""
    assert cfg.version  # non-empty version string always


def test_checked_in_env_example_is_valid():
    cfg = load_config(environ={}, env_file=REPO_ROOT / ".env.example")
    cfg.validate()
    assert cfg.max_pdf_page_pixels == 8_000_000
    assert cfg.max_pdf_total_pixels == 48_000_000
    assert cfg.max_image_pixels == 12_000_000
    assert cfg.ocr_timeout_seconds == 30


def test_env_overrides(monkeypatch, tmp_path):
    for key in list(__import__("os").environ):
        if key.startswith(
            (
                "MAX_UPLOAD",
                "SESSION_",
                "RATE_",
                "FEEDBACK_",
                "INFERENCE_",
                "TRUSTED_",
                "LOG_IP",
                "PROCESSING_",
                "COPYLINT_",
                "PORT",
                "HEIC_",
                "COA_PROFILER_TMP",
            )
        ):
            monkeypatch.delenv(key)
    monkeypatch.setenv("MAX_UPLOAD_MB", "7")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("INFERENCE_ASSIST_ENABLED", "true")
    monkeypatch.setenv("LOG_IP_RETENTION", "disabled")
    cfg = load_config(env_file=tmp_path / "missing.env")
    assert cfg.max_upload_mb == 7
    assert cfg.session_cookie_secure is False
    assert cfg.inference_assist_enabled is True
    assert cfg.log_ip_retention == "disabled"


def test_env_file_read(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MAX_UPLOAD_MB=9\n# comment\nSESSION_TTL_SECONDS=120\n")
    monkeypatch.delenv("MAX_UPLOAD_MB", raising=False)
    monkeypatch.delenv("SESSION_TTL_SECONDS", raising=False)
    cfg = load_config(environ={}, env_file=env_file)
    assert cfg.max_upload_mb == 9
    assert cfg.session_ttl_seconds == 120


def test_resource_limits_from_environment(tmp_path):
    cfg = load_config(
        environ={
            "MAX_PDF_PAGES": "7",
            "MAX_PDF_PAGE_PIXELS": "800",
            "MAX_PDF_TOTAL_PIXELS": "900",
            "MAX_IMAGE_PIXELS": "600",
            "MAX_IMAGE_DIMENSION": "500",
            "OCR_TIMEOUT_SECONDS": "21",
        },
        env_file=tmp_path / "missing.env",
    )
    assert cfg.max_pdf_pages == 7
    assert cfg.max_pdf_page_pixels == 800
    assert cfg.max_pdf_total_pixels == 900
    assert cfg.max_image_pixels == 600
    assert cfg.max_image_dimension == 500
    assert cfg.ocr_timeout_seconds == 21


def test_invalid_ip_retention_rejected():
    with pytest.raises(ValueError):
        Config(log_ip_retention="everything").validate()


@pytest.mark.parametrize(
    "field",
    [
        "max_pdf_pages",
        "max_pdf_page_pixels",
        "max_pdf_total_pixels",
        "max_image_pixels",
        "max_image_dimension",
        "ocr_timeout_seconds",
    ],
)
def test_resource_limits_must_be_positive(field):
    with pytest.raises(ValueError, match="must be >= 1"):
        Config(**{field: 0}).validate()


def test_ocr_timeout_must_be_below_upload_deadline():
    with pytest.raises(ValueError, match="OCR_TIMEOUT_SECONDS must be < 110"):
        Config(ocr_timeout_seconds=110).validate()


def test_decoded_pixel_concurrency_envelope_is_enforced():
    cfg = Config()
    assert (
        max(cfg.max_pdf_page_pixels, cfg.max_image_pixels) * cfg.processing_thread_pool_size
        == MAX_DECODED_PIXELS_IN_FLIGHT
    )
    with pytest.raises(ValueError, match="decoded pixel limit"):
        Config(max_image_pixels=12_000_001).validate()


def test_pixel_envelope_can_be_rebalanced_for_fewer_workers():
    Config(max_image_pixels=24_000_000, processing_thread_pool_size=2).validate()


def test_contact_email_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CONTACT_EMAIL", "operator@example.test")
    cfg = load_config(env_file=tmp_path / "missing.env")
    assert cfg.contact_email == "operator@example.test"


@pytest.mark.parametrize("value", ["missing-at.example", "bad address@example.test"])
def test_invalid_contact_email_rejected(value):
    with pytest.raises(ValueError, match="CONTACT_EMAIL"):
        Config(contact_email=value).validate()
