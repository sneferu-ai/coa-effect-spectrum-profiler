"""Parser package: document -> structured chemistry (FR-001..FR-005, FR-028).

Public entry point ``parse_coa(path, config=None) -> COAChemistry``:

1. magic-byte file-type sniffing (extension is never trusted)
2. text acquisition — PDF text layer (all pages), OCR fallback for empty or
   garbled layers, direct OCR for images
3. deterministic layout detection across the Florida format families
4. cite-and-verify field extraction with unit normalization, THCA/CBDA
   derivation, multi-page conflict resolution, and plausibility flagging
5. the FR-028 systematic-misextraction rule (>50% implausible -> generic
   re-extract -> still implausible -> forced refusal)

Any field that cannot be verified against the extracted text is recorded as
``unreadable`` — never interpolated, defaulted, or estimated.
"""

from __future__ import annotations

import re
from pathlib import Path

from coa_profiler.errors import (
    DocumentResourceLimitError,
    HeicUnsupportedError,
    InvalidFileTypeError,
    NotACOAError,
    NoUsableChemistryError,
    UnreadableDocumentError,
)
from coa_profiler.parser import fields as fields_mod
from coa_profiler.parser import layout as layout_mod
from coa_profiler.parser.fields import COAChemistry, ParsedField

__all__ = [
    "COAChemistry",
    "ParsedField",
    "extract_chemistry",
    "parse_coa",
    "sniff_file_type",
]

#: FR-001 magic-byte signatures (extension alone is never trusted).
_MAGIC = {
    "pdf": (b"%PDF",),
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG",),
}

_HEIC_BRANDS = (b"ftypheic", b"ftypheix", b"ftypmif1")

_TOKEN_RE = re.compile(r"[A-Za-z0-9%./-]+")

#: A text layer with fewer recognizable tokens than this is treated as absent
#: (scanned PDF) and re-acquired through OCR (FR-003).
MIN_TEXT_TOKENS = 50


def sniff_file_type(data: bytes) -> str | None:
    """Classify the first bytes of an upload: pdf | jpeg | png | heic | None."""
    if len(data) < 12:
        return None
    for ftype, signatures in _MAGIC.items():
        if any(data.startswith(sig) for sig in signatures):
            return ftype
    if any(data[4:12].startswith(brand) for brand in _HEIC_BRANDS):
        return "heic"
    return None


def _token_count(text: str) -> int:
    return len(_TOKEN_RE.findall(text))


def _acquire_text(path: Path, ftype: str, config=None) -> tuple[list[str], float | None]:
    """FR-003 text acquisition. Returns (page texts, OCR mean confidence)."""
    from coa_profiler.parser import ocr as ocr_mod
    from coa_profiler.parser import pdf_rasterize, text_extract
    from coa_profiler.parser.resource_limits import (
        ResourceLimits,
        validate_image_resources,
        validate_pdf_resources,
    )

    limits = ResourceLimits.from_config(config)
    ocr_timeout_seconds = getattr(config, "ocr_timeout_seconds", 30)

    if ftype == "pdf":
        # Validate the expansion cost even when a usable text layer exists:
        # parser fallbacks may rasterize the same document later.
        validate_pdf_resources(path, limits, dpi=200)
        pages = text_extract.extract_text_pages(path)
        combined = "\n".join(pages)
        if _token_count(combined) >= MIN_TEXT_TOKENS:
            return pages, None
        # Empty or garbled text layer: rasterize all pages and OCR.
        ocr_pages: list[str] = []
        confs: list[float] = []
        for image in pdf_rasterize.rasterize_pdf(path, dpi=200, timeout_seconds=ocr_timeout_seconds):
            try:
                result = ocr_mod.ocr_image(image, timeout_seconds=ocr_timeout_seconds)
                ocr_pages.append(result.text)
                confs.append(result.mean_confidence)
            finally:
                image.close()
        mean = (sum(confs) / len(confs)) if confs else 0.0
        return ocr_pages, mean

    # Image path: direct OCR.
    from PIL import Image

    try:
        with ocr_mod.open_image_any(str(path)) as image:
            validate_image_resources(image, limits)
            result = ocr_mod.ocr_image(image, timeout_seconds=ocr_timeout_seconds)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise DocumentResourceLimitError("Image decoder rejected excessive dimensions") from exc
    return [result.text], result.mean_confidence


def _extract_with_format(
    pages: list[str], layout: layout_mod.LayoutResult, forced_format: str | None
) -> COAChemistry:
    page_extractions: list[fields_mod.PageExtraction] = []
    for idx, text in enumerate(pages):
        sub_format = layout.page_formats[idx] if idx < len(layout.page_formats) else layout.document_format
        score = 0.0
        if idx < len(layout.page_scores):
            score = layout.page_scores[idx].get(sub_format, 0.0)
        if forced_format is not None:
            sub_format = forced_format
        page_extractions.append(fields_mod.extract_page(idx, text, sub_format, score))
    cann, terp = fields_mod.merge_pages(page_extractions, layout.document_format)
    fields_mod.derive_totals(cann)
    total_reported_terps = fields_mod.count_reported_terpenes(pages)
    return COAChemistry(
        cannabinoids=cann,
        terpenes=terp,
        lab_format=layout.document_format,
        total_reported_terpenes=total_reported_terps,
    )


def extract_chemistry(pages: list[str], config=None) -> COAChemistry:
    """Layout detection + cite-and-verify extraction over page texts."""
    layout = layout_mod.detect_layout(pages)
    if not layout.is_certificate:
        raise NotACOAError()

    if layout.document_format == layout_mod.FORMAT_UNKNOWN and config is not None:
        # FR-026: optional inference-assist, only on unknown formats, only
        # when explicitly enabled. Deterministic result is kept on any error.
        from coa_profiler.parser import inference_assist

        assisted = inference_assist.classify_layout("\n".join(pages), config)
        if assisted:
            layout.document_format = assisted
            layout.page_formats = [assisted for _ in layout.page_formats]

    chemistry = _extract_with_format(pages, layout, None)
    fields_mod.apply_plausibility(chemistry)

    # FR-028: systematic misextraction — more than half the extracted values
    # exceed plausibility ranges. Re-run with the generic fallback parser; if
    # still implausible, downgrade to refusal.
    if fields_mod.implausible_fraction(chemistry) > 0.50:
        retry = _extract_with_format(pages, layout, layout_mod.FORMAT_GENERIC_OMMU)
        retry.ocr_mean_confidence = chemistry.ocr_mean_confidence
        fields_mod.apply_plausibility(retry)
        if fields_mod.implausible_fraction(retry) > 0.50:
            retry.forced_refusal_reason = "Extracted values appear inconsistent — please try a clearer photo."
        chemistry = retry
    return chemistry


def parse_coa(path: str | Path, config=None) -> COAChemistry:
    """Parse a certificate file into a structured chemistry record."""
    path = Path(path)
    data = path.read_bytes()
    ftype = sniff_file_type(data)
    if ftype is None:
        raise InvalidFileTypeError()
    if ftype == "heic":
        from coa_profiler.parser import ocr as ocr_mod

        if config is not None and not getattr(config, "heic_enabled", True):
            raise HeicUnsupportedError()
        if not ocr_mod.heic_decoder_available():
            raise HeicUnsupportedError()

    pages, ocr_mean = _acquire_text(path, ftype, config)

    if ocr_mean is not None and ocr_mean < 60.0:
        raise UnreadableDocumentError()

    chemistry = extract_chemistry(pages, config)
    chemistry.ocr_mean_confidence = ocr_mean

    any_verified = any(
        f.status == "verified" for f in (*chemistry.cannabinoids.values(), *chemistry.terpenes.values())
    )
    if not any_verified:
        raise NoUsableChemistryError()
    return chemistry
