"""OCR pipeline (FR-003).

Tesseract with documented, deterministic preprocessing:

- grayscale conversion
- deskew (auto-angle detection up to +/-15 degrees)
- adaptive thresholding (block size 31, C=10)
- minimum 150-DPI-equivalent resolution (small images are upscaled)

Determinism controls (FR-022): ``OMP_THREAD_LIMIT=1`` is set in the
environment and Tesseract runs with ``--psm 6`` (uniform page segmentation).
Tesseract itself is pinned by the Docker image; bare-metal deployments record
``tesseract --version`` in the deployment log (assumption A-10).

Preprocessing uses OpenCV (opencv-python-headless); Pillow handles image I/O.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

os.environ.setdefault("OMP_THREAD_LIMIT", "1")

#: Mean per-region confidence below this -> typed "document unreadable" error.
OCR_CONFIDENCE_REJECT = 60.0
#: Mean confidence in [60, 75) -> process continues with a DC penalty (FR-009).
OCR_CONFIDENCE_PENALTY_BELOW = 75.0

TESSERACT_CONFIG = "--psm 6"

# OCR/OpenCV working images are bounded independently from accepted source
# photos.  This prevents the 1200px minimum-width upscale from exploding a
# very narrow/tall image and limits scratch arrays across four workers.
OCR_ANALYSIS_MAX_PIXELS = 8_000_000
OCR_ANALYSIS_MAX_DIMENSION = 8_000
DESKEW_SAMPLE_MAX_PIXELS = 1_000_000

#: HEIC ftyp brands — shared with parser.__init__ sniff_file_type (FR-001).
_HEIC_BRANDS = (b"ftypheic", b"ftypheix", b"ftypmif1")


@dataclass
class OCRResult:
    text: str
    mean_confidence: float  # 0.0–100.0 over recognized tokens
    tokens: int


def tesseract_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001 - availability probes collapse every runtime failure to false
        return False


def preprocess(image: Image.Image) -> Image.Image:
    """Grayscale -> deskew (±15°) -> adaptive threshold (31, C=10) -> >=150 DPI."""
    import cv2
    import numpy as np
    from PIL import Image

    width, height = image.size
    requested_scale = max(1.0, 1200 / width)
    pixel_scale = math.sqrt(OCR_ANALYSIS_MAX_PIXELS / (width * height))
    dimension_scale = OCR_ANALYSIS_MAX_DIMENSION / max(width, height)
    scale = min(requested_scale, pixel_scale, dimension_scale)
    prepared_source = image
    if abs(scale - 1.0) > 0.001:
        prepared_source = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.Resampling.BICUBIC,
        )
    try:
        arr = np.array(prepared_source.convert("L"))
    finally:
        if prepared_source is not image:
            prepared_source.close()
    # Deskew via minAreaRect on the ink pixels.
    sample_step = max(1, math.ceil(math.sqrt(arr.size / DESKEW_SAMPLE_MAX_PIXELS)))
    deskew_sample = arr[::sample_step, ::sample_step]
    inverted = cv2.bitwise_not(deskew_sample)
    # OpenCV keeps coordinates as int32 rather than NumPy's platform-sized
    # indices. Combined with the sample cap this bounds worst-case deskew
    # coordinate storage to roughly 8 MB.
    coords = cv2.findNonZero(inverted)
    angle = 0.0
    if coords is not None:
        rect = cv2.minAreaRect(coords)
        angle = rect[-1]
        if angle < -45:
            angle += 90
        if angle > 45:
            angle -= 90
        angle = max(-15.0, min(15.0, angle))
    if abs(angle) > 0.05:
        h, w = arr.shape
        m = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        arr = cv2.warpAffine(arr, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    # Adaptive threshold (block size 31, C=10) per FR-003.
    arr = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    return Image.fromarray(arr)


def ocr_image(
    image: Image.Image,
    do_preprocess: bool = True,
    timeout_seconds: int = 30,
) -> OCRResult:
    """OCR one image; returns text plus mean per-region confidence."""
    import pytesseract

    from coa_profiler.errors import ProcessingTimeoutError

    prepared = preprocess(image) if do_preprocess else image
    try:
        try:
            data = pytesseract.image_to_data(
                prepared,
                config=TESSERACT_CONFIG,
                output_type=pytesseract.Output.DICT,
                timeout=timeout_seconds,
            )
        except RuntimeError as exc:
            # pytesseract kills the child process before raising this stable error.
            # Do not collapse unrelated Tesseract runtime failures into a timeout.
            if "tesseract process timeout" in str(exc).lower():
                raise ProcessingTimeoutError("OCR page exceeded its processing deadline") from exc
            raise
    finally:
        if prepared is not image:
            prepared.close()
    words: list[str] = []
    lines: list[str] = []
    line_words: list[str] = []
    current_line: tuple[int, int, int, int] | None = None
    confs: list[float] = []
    row_count = len(data["text"])
    page_nums = data.get("page_num", [0] * row_count)
    block_nums = data.get("block_num", [0] * row_count)
    par_nums = data.get("par_num", [0] * row_count)
    line_nums = data.get("line_num", [0] * row_count)
    for idx, (text, conf) in enumerate(zip(data["text"], data["conf"])):
        text = (text or "").strip()
        try:
            c = float(conf)
        except (TypeError, ValueError):
            continue
        if not text or c < 0:
            continue
        line_key = (
            int(page_nums[idx]),
            int(block_nums[idx]),
            int(par_nums[idx]),
            int(line_nums[idx]),
        )
        if current_line is not None and line_key != current_line:
            lines.append(" ".join(line_words))
            line_words = []
        current_line = line_key
        line_words.append(text)
        words.append(text)
        confs.append(c)
    if line_words:
        lines.append(" ".join(line_words))
    mean_conf = (sum(confs) / len(confs)) if confs else 0.0
    return OCRResult(text="\n".join(lines), mean_confidence=mean_conf, tokens=len(words))


def _is_heic_path(path: str) -> bool:
    """Detect HEIC by extension OR magic bytes (FR-001 sniff, not extension)."""
    lower = str(path).lower()
    if lower.endswith((".heic", ".heif")):
        return True
    # Magic-byte sniff: HEIC files carry ftypheic/ftypheix/ftypmif1 at offset 4.
    try:
        with open(path, "rb") as f:
            head = f.read(12)
        return len(head) >= 12 and any(head[4:12].startswith(b) for b in _HEIC_BRANDS)
    except OSError:
        return False


def open_image_any(path: str) -> Image.Image:
    """Open an image file, registering the HEIC opener when available.

    HEIC is detected by extension OR magic bytes (FR-001), so a HEIC file
    with a non-HEIC extension still works in the CLI/batch flow.
    Raises HeicUnsupportedError for HEIC files when the decoder is absent.
    """
    from PIL import Image

    if _is_heic_path(path):
        if not heic_decoder_available():
            from coa_profiler.errors import HeicUnsupportedError

            raise HeicUnsupportedError()
        import pillow_heif  # type: ignore[import-not-found]

        pillow_heif.register_heif_opener()
    return Image.open(path)


def heic_decoder_available() -> bool:
    try:
        import pillow_heif  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False
