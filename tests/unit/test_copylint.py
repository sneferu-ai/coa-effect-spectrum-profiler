"""FR-019 copy-lint: clean templates, hit detection, boot budget."""

import time
from pathlib import Path

from coa_profiler.copylint import main as copylint_main
from coa_profiler.copylint import scan_templates
from coa_profiler.lexicon import BANNED_TERMS

TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "coa_profiler" / "web" / "templates"


def test_shipped_templates_are_clean():
    assert scan_templates(TEMPLATES) == []


def test_hit_detection(tmp_path):
    target = tmp_path / "t.html"
    target.write_text(f"<p>this copy says {BANNED_TERMS[0]} plainly</p>", encoding="utf-8")
    hits = scan_templates(tmp_path)
    assert len(hits) == 1
    assert hits[0].term == BANNED_TERMS[0]
    assert "t.html" in hits[0].location


def test_cli_exit_codes(tmp_path):
    assert copylint_main(["--templates", str(TEMPLATES)]) == 0
    target = tmp_path / "bad.html"
    target.write_text(f"<p>{BANNED_TERMS[3]}</p>", encoding="utf-8")
    assert copylint_main(["--templates", str(tmp_path)]) == 1


def test_boot_scan_within_budget():
    started = time.monotonic()
    scan_templates(TEMPLATES)
    assert time.monotonic() - started < 5.0  # AC-043
