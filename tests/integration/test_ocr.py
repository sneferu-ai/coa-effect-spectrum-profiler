"""Integration: OCR path (FR-003). Requires Tesseract + OpenCV."""

import time
from pathlib import Path

import pytest

from coa_profiler.errors import UnreadableDocumentError
from coa_profiler.parser import parse_coa
from coa_profiler.parser.ocr import ocr_image, tesseract_available

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

pytestmark = pytest.mark.skipif(not tesseract_available(), reason="tesseract not installed")


def test_unreadable_photo_typed_error():
    started = time.monotonic()
    with pytest.raises(UnreadableDocumentError):
        parse_coa(FIXTURES / "unreadable_coa.jpg")
    assert time.monotonic() - started < 60  # sanity bound on the OCR path


def test_ocr_reads_clear_printed_text():
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(img)
    draw.text((40, 90), "Total THC 18.2 %  Myrcene 0.85 %", fill="black")
    result = ocr_image(img)
    assert "18.2" in result.text or "THC" in result.text.upper()
