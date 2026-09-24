"""Unit regressions for OCR text-layout preservation."""

import pytest
from PIL import Image

from coa_profiler.errors import ProcessingTimeoutError
from coa_profiler.parser.ocr import (
    DESKEW_SAMPLE_MAX_PIXELS,
    OCR_ANALYSIS_MAX_DIMENSION,
    OCR_ANALYSIS_MAX_PIXELS,
    ocr_image,
    preprocess,
)


def test_ocr_preserves_tesseract_line_boundaries(monkeypatch):
    import pytesseract

    data = {
        "text": ["THCA", "26.9", "Myrcene", "0.50"],
        "conf": ["95", "94", "93", "92"],
        "page_num": [1, 1, 1, 1],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 2, 2],
    }
    monkeypatch.setattr(pytesseract, "image_to_data", lambda *args, **kwargs: data)

    image = Image.new("RGB", (10, 10), "white")
    result = ocr_image(image, do_preprocess=False)

    assert result.text == "THCA 26.9\nMyrcene 0.50"
    assert result.tokens == 4
    assert result.mean_confidence == 93.5


def test_ocr_passes_bounded_timeout_to_tesseract(monkeypatch):
    import pytesseract

    captured = {}

    def fake_image_to_data(*args, **kwargs):
        captured.update(kwargs)
        return {"text": [], "conf": []}

    monkeypatch.setattr(pytesseract, "image_to_data", fake_image_to_data)
    image = Image.new("RGB", (10, 10), "white")

    ocr_image(image, do_preprocess=False, timeout_seconds=17)

    assert captured["timeout"] == 17


def test_tesseract_timeout_maps_to_typed_processing_error(monkeypatch):
    import pytesseract

    def time_out(*args, **kwargs):
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(pytesseract, "image_to_data", time_out)
    image = Image.new("RGB", (10, 10), "white")

    with pytest.raises(ProcessingTimeoutError, match="OCR page exceeded"):
        ocr_image(image, do_preprocess=False, timeout_seconds=1)


def test_non_timeout_tesseract_runtime_error_is_not_misclassified(monkeypatch):
    import pytesseract

    def fail(*args, **kwargs):
        raise RuntimeError("Tesseract language data unavailable")

    monkeypatch.setattr(pytesseract, "image_to_data", fail)
    image = Image.new("RGB", (10, 10), "white")

    with pytest.raises(RuntimeError, match="language data"):
        ocr_image(image, do_preprocess=False)


def test_preprocess_upscale_cannot_explode_pathological_aspect_ratio():
    image = Image.new("RGB", (1, 8_000), "white")
    prepared = preprocess(image)

    assert prepared.width * prepared.height <= OCR_ANALYSIS_MAX_PIXELS
    assert max(prepared.size) <= OCR_ANALYSIS_MAX_DIMENSION


def test_preprocess_still_upscales_normal_small_image():
    image = Image.new("RGB", (900, 220), "white")
    prepared = preprocess(image)

    assert prepared.width == 1_200
    assert prepared.width * prepared.height <= OCR_ANALYSIS_MAX_PIXELS


def test_deskew_coordinate_input_is_sampled_and_int32(monkeypatch):
    import cv2

    observed = {}
    real_find_non_zero = cv2.findNonZero

    def capture_find_non_zero(image):
        observed["pixels"] = image.size
        coords = real_find_non_zero(image)
        observed["dtype"] = coords.dtype if coords is not None else None
        return coords

    monkeypatch.setattr(cv2, "findNonZero", capture_find_non_zero)
    image = Image.new("RGB", (2_000, 2_000), "black")
    prepared = preprocess(image)
    prepared.close()

    assert observed["pixels"] <= DESKEW_SAMPLE_MAX_PIXELS
    assert str(observed["dtype"]) == "int32"
