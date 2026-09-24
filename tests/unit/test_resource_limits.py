"""Resource expansion limits reject valid-but-pathological documents early."""

from __future__ import annotations

import fitz
import pytest
from PIL import Image

from coa_profiler.config import Config
from coa_profiler.errors import DocumentResourceLimitError
from coa_profiler.parser import parse_coa
from coa_profiler.parser.resource_limits import (
    ResourceLimits,
    validate_image_resources,
    validate_pdf_resources,
)
from coa_profiler.web.routes import _strip_and_store


def _make_pdf(tmp_path, page_sizes: list[tuple[float, float]]):
    path = tmp_path / "resource-test.pdf"
    with fitz.open() as document:
        for width, height in page_sizes:
            document.new_page(width=width, height=height)
        document.save(path)
    return path


def test_pdf_page_count_is_bounded_before_text_extraction(tmp_path, monkeypatch):
    path = _make_pdf(tmp_path, [(100, 100), (100, 100)])

    def must_not_extract(_path):
        raise AssertionError("text extraction ran before PDF resource preflight")

    monkeypatch.setattr("coa_profiler.parser.text_extract.extract_text_pages", must_not_extract)
    with pytest.raises(DocumentResourceLimitError, match="page count"):
        parse_coa(path, Config(max_pdf_pages=1))


def test_pdf_projected_pixels_are_bounded_per_page(tmp_path):
    path = _make_pdf(tmp_path, [(1000, 1000)])
    limits = ResourceLimits(
        max_pdf_pages=2,
        max_pdf_page_pixels=999_999,
        max_pdf_total_pixels=2_000_000,
    )
    with pytest.raises(DocumentResourceLimitError, match="page 1 projects"):
        validate_pdf_resources(path, limits, dpi=72)


def test_pdf_projected_pixels_are_bounded_across_document(tmp_path):
    path = _make_pdf(tmp_path, [(10, 10), (10, 10)])
    limits = ResourceLimits(
        max_pdf_pages=2,
        max_pdf_page_pixels=1_000,
        max_pdf_total_pixels=150,
    )
    with pytest.raises(DocumentResourceLimitError, match="total raster pixels"):
        validate_pdf_resources(path, limits, dpi=72)


@pytest.mark.parametrize(
    ("size", "limits", "message"),
    [
        ((101, 10), ResourceLimits(max_image_dimension=100), "dimensions"),
        ((20, 20), ResourceLimits(max_image_pixels=399), "expand"),
    ],
)
def test_uploaded_image_dimensions_are_bounded(size, limits, message):
    with Image.new("RGB", size) as image, pytest.raises(DocumentResourceLimitError, match=message):
        validate_image_resources(image, limits)


def test_decoder_decompression_bomb_maps_to_typed_limit(tmp_path, monkeypatch):
    def reject_dimensions(_path):
        raise Image.DecompressionBombError("decoder allocation limit")

    monkeypatch.setattr("coa_profiler.parser.ocr.open_image_any", reject_dimensions)
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    with pytest.raises(DocumentResourceLimitError, match="decoder rejected"):
        _strip_and_store(b"\xff\xd8\xffplaceholder", "jpeg", session_dir)
