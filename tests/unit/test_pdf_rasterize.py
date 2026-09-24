"""PDF OCR rasterization retains no more than one decoded page."""

from __future__ import annotations

import pdf2image
import pytest
from pdf2image.exceptions import PDFPopplerTimeoutError
from PIL import Image

from coa_profiler.config import Config
from coa_profiler.errors import ProcessingTimeoutError
from coa_profiler.parser import _acquire_text
from coa_profiler.parser.ocr import OCRResult
from coa_profiler.parser.pdf_rasterize import _rasterize_pdf2image, rasterize_pdf


def test_rasterizer_is_lazy(monkeypatch):
    from coa_profiler.parser import pdf_rasterize

    events = []

    def fake_pages(_path, _dpi, timeout_seconds):
        assert timeout_seconds == 30
        events.append("first")
        yield Image.new("RGB", (2, 2), "white")
        events.append("second")
        yield Image.new("RGB", (2, 2), "white")

    monkeypatch.setattr(pdf_rasterize, "_rasterize_pdf2image", fake_pages)
    pages = rasterize_pdf("unused.pdf")
    assert events == []

    first = next(pages)
    assert events == ["first"]
    first.close()
    second = next(pages)
    assert events == ["first", "second"]
    second.close()
    with pytest.raises(StopIteration):
        next(pages)


def test_parser_closes_each_raster_before_requesting_next(monkeypatch, tmp_path):
    from coa_profiler.parser import ocr, pdf_rasterize, resource_limits, text_extract

    images = [Image.new("RGB", (2, 2), "white") for _ in range(2)]
    first_closed_before_second = []

    def pages(_path, dpi, timeout_seconds):
        assert dpi == 200
        assert timeout_seconds == 19
        yield images[0]
        with pytest.raises(ValueError):
            images[0].getpixel((0, 0))
        first_closed_before_second.append(True)
        yield images[1]

    def fake_ocr(_image, *, timeout_seconds):
        assert timeout_seconds == 19
        return OCRResult("Certificate of Analysis Total THC 20 % " * 4, 95.0, 32)

    monkeypatch.setattr(resource_limits, "validate_pdf_resources", lambda *args, **kwargs: None)
    monkeypatch.setattr(text_extract, "extract_text_pages", lambda _path: [""])
    monkeypatch.setattr(pdf_rasterize, "rasterize_pdf", pages)
    monkeypatch.setattr(ocr, "ocr_image", fake_ocr)

    page_texts, confidence = _acquire_text(tmp_path / "unused.pdf", "pdf", Config(ocr_timeout_seconds=19))

    assert len(page_texts) == 2
    assert confidence == 95.0
    assert first_closed_before_second == [True]
    with pytest.raises(ValueError):
        images[1].getpixel((0, 0))


def test_poppler_info_and_page_render_calls_are_individually_timed(monkeypatch):
    calls = []

    def fake_info(_path, *, timeout):
        calls.append(("info", timeout))
        return {"Pages": 1}

    def fake_convert(_path, **kwargs):
        calls.append(("page", kwargs["timeout"]))
        return [Image.new("RGB", (2, 2), "white")]

    monkeypatch.setattr(pdf2image, "pdfinfo_from_path", fake_info)
    monkeypatch.setattr(pdf2image, "convert_from_path", fake_convert)

    pages = list(_rasterize_pdf2image("unused.pdf", 200, timeout_seconds=13))
    try:
        assert calls == [("info", 13), ("page", 13)]
    finally:
        for page in pages:
            page.close()


def test_poppler_timeout_maps_to_typed_processing_error(monkeypatch):
    from coa_profiler.parser import pdf_rasterize

    def time_out(*args, **kwargs):
        raise PDFPopplerTimeoutError("Run poppler timeout")

    monkeypatch.setattr(pdf_rasterize, "_rasterize_pdf2image", time_out)

    with pytest.raises(ProcessingTimeoutError, match="PDF page rendering"):
        next(rasterize_pdf("unused.pdf", timeout_seconds=1))
