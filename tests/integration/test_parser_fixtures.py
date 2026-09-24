"""Integration: parse the generated fixture PDFs through the real pipeline."""

import json
import shutil
from pathlib import Path

import pytest

from coa_profiler.errors import (
    HeicUnsupportedError,
    InvalidFileTypeError,
    NotACOAError,
    NoUsableChemistryError,
)
from coa_profiler.parser import parse_coa, sniff_file_type
from coa_profiler.parser.ocr import heic_decoder_available
from coa_profiler.scorer import score

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

try:
    import fitz  # noqa: F401

    _PDF_ENGINE = True
except ImportError:
    try:
        import pdfplumber  # noqa: F401

        _PDF_ENGINE = True
    except ImportError:
        _PDF_ENGINE = False

pytestmark = pytest.mark.skipif(not _PDF_ENGINE, reason="no PDF engine installed")


def test_sample_matches_expected_json():
    expected = json.loads((FIXTURES / "fl_coa_sample_expected.json").read_text())
    chem = parse_coa(FIXTURES / "fl_coa_sample.pdf")
    assert chem.lab_format == expected["lab_format"]
    result = score(chem)
    assert result.score == expected["score"]
    for name, want in expected["fields"].items():
        table = chem.cannabinoids if name in chem.cannabinoids else chem.terpenes
        got = table[name]
        assert got.status == "verified"
        assert got.value == pytest.approx(want["value"], rel=0.01)
        assert got.original_unit == want["unit"]


def test_format_detection_by_content_not_filename(tmp_path):
    # AC-032: neutral filenames, content drives the detection.
    cases = {
        "confident_cannabis": "confident_cannabis_coa.pdf",
        "sc_labs": "sc_labs_coa.pdf",
        "generic_ommu": "generic_ommu_coa.pdf",
    }
    detected = []
    for i, (fmt, filename) in enumerate(cases.items(), start=1):
        neutral = tmp_path / f"f{i}.pdf"
        shutil.copy(FIXTURES / "formats" / filename, neutral)
        detected.append(parse_coa(neutral).lab_format)
    assert detected == ["confident_cannabis", "sc_labs", "generic_ommu"]


def test_multi_page_cross_page_extraction():
    chem = parse_coa(FIXTURES / "multi_page_coa.pdf")
    assert chem.cannabinoids["thc_total"].value == pytest.approx(21.6)
    assert chem.terpenes["myrcene"].value == pytest.approx(0.95)
    assert score(chem).completeness == "full"


def test_thca_derivation_marks_derived():
    chem = parse_coa(FIXTURES / "thca_cbda_coa.pdf")
    total = chem.cannabinoids["thc_total"]
    assert total.derived is True
    assert total.value == pytest.approx(1.2 + 0.877 * 20.0)


def test_plausibility_flag_on_high_thc():
    chem = parse_coa(FIXTURES / "plausibility_high_coa.pdf")
    assert chem.cannabinoids["thc_total"].plausibility_flag is True
    # Single outlier: still scores (no forced refusal).
    assert chem.forced_refusal_reason is None
    assert score(chem).completeness == "full"


def test_magic_bytes_not_extension(tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_bytes((FIXTURES / "not_a_coa.txt").read_bytes())
    assert sniff_file_type(fake.read_bytes()) is None
    with pytest.raises(InvalidFileTypeError):
        parse_coa(fake)


def test_not_a_coa_typed_error(tmp_path):
    # A real PDF with plenty of text but no certificate structure.
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    path = tmp_path / "letter.pdf"
    c = canvas.Canvas(str(path), pagesize=letter, invariant=True)
    words = (
        "This letter confirms your appointment next Tuesday at the clinic. "
        "Please bring your paperwork and arrive ten minutes early. " * 6
    )
    y = letter[1] - 72
    for chunk in [words[i : i + 90] for i in range(0, len(words), 90)]:
        c.drawString(72, y, chunk)
        y -= 14
    c.showPage()
    c.save()
    with pytest.raises(NotACOAError):
        parse_coa(path)


def test_no_usable_chemistry_typed_error(tmp_path):
    # Certificate structure present but zero extractable chemistry values.
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    path = tmp_path / "bare.pdf"
    c = canvas.Canvas(str(path), pagesize=letter, invariant=True)
    y = letter[1] - 72
    for line in [
        "Certificate of Analysis",
        "Cannabinoid Profile",
        "Terpene Profile",
        "All values were below the reporting cutoff on this certificate.",
        "Please contact the laboratory with questions about this document.",
    ]:
        c.drawString(72, y, line)
        y -= 14
    c.showPage()
    c.save()
    with pytest.raises(NoUsableChemistryError):
        parse_coa(path)


def test_heic_magic_and_decoder_gate():
    data = (FIXTURES / "heic_sample.heic").read_bytes()
    assert sniff_file_type(data) == "heic"
    if not heic_decoder_available():
        with pytest.raises(HeicUnsupportedError):
            parse_coa(FIXTURES / "heic_sample.heic")


def test_heic_detected_by_magic_bytes_not_extension(tmp_path):
    """A HEIC file with a non-HEIC extension is still detected via magic bytes
    (FR-001: extension is never trusted). open_image_any sniffs, not guesses."""
    from coa_profiler.parser.ocr import _is_heic_path

    heic_data = (FIXTURES / "heic_sample.heic").read_bytes()
    # Save with a .jpg extension — extension alone must not fool the sniff.
    misnamed = tmp_path / "photo.jpg"
    misnamed.write_bytes(heic_data)
    assert _is_heic_path(str(misnamed)) is True

    # A real JPEG is NOT misidentified as HEIC.
    from PIL import Image

    real_jpg = tmp_path / "real.jpg"
    Image.new("RGB", (10, 10), "red").save(real_jpg, format="JPEG")
    assert _is_heic_path(str(real_jpg)) is False


def test_refusal_fixture_zero_terpenes():
    chem = parse_coa(FIXTURES / "no_chemistry.pdf")
    assert score(chem).completeness == "refusal"


def test_degraded_fixture_partial_terpenes():
    chem = parse_coa(FIXTURES / "cannabinoids_only.pdf")
    result = score(chem)
    assert result.completeness == "degraded"
    assert result.confidence_combined >= 0.25  # above the degraded floor
