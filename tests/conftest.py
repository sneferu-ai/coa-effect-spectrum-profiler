"""Shared test fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES = ROOT / "fixtures"


@pytest.fixture()
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture()
def cfg(tmp_path):
    """Test config: HTTP cookies, HEIC dropped (no decoder in CI), tmp sessions."""
    from coa_profiler.config import Config

    return Config(
        session_cookie_secure=False,
        heic_enabled=False,
        session_tmp_root=str(tmp_path / "coa_profiler_sessions"),
    )


@pytest.fixture()
def client(cfg):
    """A running app (lifespan included) against a throwaway config."""
    from fastapi.testclient import TestClient

    from coa_profiler.app import create_app

    with TestClient(create_app(cfg)) as test_client:
        yield test_client


def upload(client, path: Path, name: str | None = None):
    with open(path, "rb") as fh:
        data = fh.read()
    return client.post("/upload", files={"file": (name or path.name, data)})


def make_field(name: str, value: float | None, unit: str = "%", status: str = "verified"):
    """Build a ParsedField for synthetic chemistry tests."""
    from coa_profiler.parser.fields import ParsedField, normalize_unit

    if value is None or status == "unreadable":
        return ParsedField(name=name, status="unreadable", unreadable_reason="test")
    normalized, canonical = normalize_unit(value, unit)
    return ParsedField(
        name=name,
        value=normalized,
        original_value=value,
        original_unit=canonical,
        status="verified",
        source_span=f"{name} {value} {unit}",
    )


def make_chemistry(
    cannabinoids: dict,
    terpenes: dict,
    total_reported_terpenes=None,
    ocr_mean_confidence=None,
    lab_format: str = "generic_ommu",
):
    from coa_profiler.parser.fields import COAChemistry

    return COAChemistry(
        cannabinoids={
            k: (v if not isinstance(v, tuple) else make_field(k, *v)) for k, v in cannabinoids.items()
        },
        terpenes={k: (v if not isinstance(v, tuple) else make_field(k, *v)) for k, v in terpenes.items()},
        lab_format=lab_format,
        total_reported_terpenes=total_reported_terpenes,
        ocr_mean_confidence=ocr_mean_confidence,
    )
