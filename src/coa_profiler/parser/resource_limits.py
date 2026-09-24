"""Preflight limits for inputs that expand during parsing or OCR.

Upload byte limits alone do not bound decoded image memory: a tiny compressed
PDF or PNG can expand into hundreds of millions of pixels.  These checks run
from the parser as well as the web upload path so CLI/batch callers get the
same typed, recoverable refusal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from coa_profiler.errors import DocumentResourceLimitError

if TYPE_CHECKING:
    from PIL import Image


@dataclass(frozen=True)
class ResourceLimits:
    max_pdf_pages: int = 20
    max_pdf_page_pixels: int = 8_000_000
    max_pdf_total_pixels: int = 48_000_000
    max_image_pixels: int = 12_000_000
    max_image_dimension: int = 8_000

    @classmethod
    def from_config(cls, config=None) -> ResourceLimits:
        if config is None:
            return cls()
        return cls(
            max_pdf_pages=getattr(config, "max_pdf_pages", cls.max_pdf_pages),
            max_pdf_page_pixels=getattr(config, "max_pdf_page_pixels", cls.max_pdf_page_pixels),
            max_pdf_total_pixels=getattr(config, "max_pdf_total_pixels", cls.max_pdf_total_pixels),
            max_image_pixels=getattr(config, "max_image_pixels", cls.max_image_pixels),
            max_image_dimension=getattr(config, "max_image_dimension", cls.max_image_dimension),
        )


def validate_pdf_resources(
    pdf_path: str | Path,
    limits: ResourceLimits,
    *,
    dpi: int = 200,
) -> None:
    """Reject excessive page counts or projected raster allocations."""
    import fitz  # type: ignore[import-not-found]

    with fitz.open(str(pdf_path)) as document:
        page_count = document.page_count
        if page_count > limits.max_pdf_pages:
            raise DocumentResourceLimitError(f"PDF page count {page_count} exceeds {limits.max_pdf_pages}")

        total_pixels = 0
        scale = dpi / 72.0
        for page_number, page in enumerate(document, start=1):
            width_points = float(page.rect.width)
            height_points = float(page.rect.height)
            if (
                not math.isfinite(width_points)
                or not math.isfinite(height_points)
                or width_points <= 0
                or height_points <= 0
            ):
                raise DocumentResourceLimitError(f"PDF page {page_number} has invalid dimensions")
            width_pixels = math.ceil(width_points * scale)
            height_pixels = math.ceil(height_points * scale)
            page_pixels = width_pixels * height_pixels
            if page_pixels > limits.max_pdf_page_pixels:
                raise DocumentResourceLimitError(f"PDF page {page_number} projects to {page_pixels} pixels")
            total_pixels += page_pixels
            if total_pixels > limits.max_pdf_total_pixels:
                raise DocumentResourceLimitError(f"PDF projects to {total_pixels} total raster pixels")


def validate_image_resources(image: Image.Image, limits: ResourceLimits) -> None:
    """Reject decoded image dimensions before loading/re-encoding pixel data."""
    width, height = image.size
    if width < 1 or height < 1:
        raise DocumentResourceLimitError("Image has invalid dimensions")
    if width > limits.max_image_dimension or height > limits.max_image_dimension:
        raise DocumentResourceLimitError(
            f"Image dimensions {width}x{height} exceed {limits.max_image_dimension}"
        )
    pixels = width * height
    if pixels > limits.max_image_pixels:
        raise DocumentResourceLimitError(f"Image dimensions {width}x{height} expand to {pixels} pixels")
