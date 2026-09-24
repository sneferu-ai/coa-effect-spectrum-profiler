"""PDF rasterization (FR-003 fallback path).

Primary engine: pdf2image (requires poppler-utils; spec section 6).
Portability fallback: PyMuPDF pixmap rendering, which needs no external
binary. Yields one PIL Image at a time so multi-page documents never retain
every decoded raster in memory simultaneously.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from coa_profiler.errors import ProcessingTimeoutError

if TYPE_CHECKING:
    from PIL import Image


def rasterize_pdf(
    pdf_path: str | Path,
    dpi: int = 200,
    timeout_seconds: int = 30,
) -> Iterator[Image.Image]:
    """Lazily rasterize a PDF, retaining at most one decoded page."""
    try:
        import pdf2image  # type: ignore[import-not-found]  # noqa: F401
        from pdf2image.exceptions import PDFPopplerTimeoutError
    except ImportError:
        yield from _rasterize_fitz(pdf_path, dpi)
        return

    yielded = 0
    try:
        for image in _rasterize_pdf2image(pdf_path, dpi, timeout_seconds):
            yielded += 1
            yield image
    except PDFPopplerTimeoutError as exc:
        # pdf2image terminates the timed-out Poppler child before raising.
        raise ProcessingTimeoutError("PDF page rendering exceeded its deadline") from exc
    except Exception as exc:
        # pdf2image raises when the poppler binaries are absent; fall back to
        # the self-contained engine only when no page was already delivered.
        # Restarting after a partial delivery would OCR duplicate pages.
        message = str(exc).lower()
        if yielded == 0 and ("poppler" in message or "unable to get page" in message):
            yield from _rasterize_fitz(pdf_path, dpi)
            return
        raise


def _rasterize_pdf2image(
    pdf_path: str | Path,
    dpi: int,
    timeout_seconds: int,
) -> Iterator[Image.Image]:
    from pdf2image import convert_from_path, pdfinfo_from_path  # type: ignore[import-not-found]

    info = pdfinfo_from_path(str(pdf_path), timeout=timeout_seconds)
    page_count = int(info["Pages"])
    for page_number in range(1, page_count + 1):
        images = convert_from_path(
            str(pdf_path),
            dpi=dpi,
            first_page=page_number,
            last_page=page_number,
            thread_count=1,
            timeout=timeout_seconds,
        )
        if len(images) != 1:
            for image in images:
                image.close()
            raise RuntimeError(f"PDF rasterizer returned {len(images)} images for one page")
        yield images[0]


def _rasterize_fitz(pdf_path: str | Path, dpi: int) -> Iterator[Image.Image]:
    import io

    import fitz  # type: ignore[import-not-found]
    from PIL import Image

    zoom = dpi / 72.0
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            with Image.open(io.BytesIO(pix.tobytes("png"))) as encoded:
                image = encoded.copy()
            yield image
