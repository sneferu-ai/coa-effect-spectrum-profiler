"""One-page US-Letter PDF strain profile (FR-011, DIS-12).

ReportLab in invariant mode: no generation timestamp is embedded anywhere —
not visible, not in metadata — so identical inputs produce byte-identical
PDFs within the same build (FR-022). Provenance is the scorer version string
(git tag, fixed at build time) and the SHA-256 of ``weights.py``.

Fonts: the Bitstream Vera TTFs bundled with ReportLab are registered and
embedded (subset), so the document carries no external font references.

The renderer accepts optional ``customer_name`` and ``branding_logo`` for
operator batch runs (FR-017); both are None for the public tool.
"""

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from coa_profiler.lexicon import (
    BAND_NOTE,
    CONFIDENCE_NOTE,
    DEGRADED_NOTICE,
    STANDING_DISCLAIMER,
)
from coa_profiler.result_data import build_result_json, build_source_json, display_name, field_rows
from coa_profiler.scorer.placement import placement_label
from coa_profiler.scorer.weights import WEIGHTS

if TYPE_CHECKING:
    from coa_profiler.parser.fields import COAChemistry, ParsedField
    from coa_profiler.scorer.placement import PlacementResult

_FONT_DIR = os.path.join(os.path.dirname(__import__("reportlab").__file__), "fonts")
pdfmetrics.registerFont(TTFont("Vera", os.path.join(_FONT_DIR, "Vera.ttf")))
pdfmetrics.registerFont(TTFont("VeraBd", os.path.join(_FONT_DIR, "VeraBd.ttf")))
pdfmetrics.registerFont(TTFont("VeraIt", os.path.join(_FONT_DIR, "VeraIt.ttf")))

_PAGE_W, _PAGE_H = letter
_MARGIN = 0.75 * inch

TOOL_NAME = "COA Effect-Spectrum Profiler"
FREE_FOOTER = "Free public tool"
ALGORITHM_LINE = "How this is calculated: see the /algorithm page of the COA Effect-Spectrum Profiler."
RESULT_ATTACHMENT = "coa-profile-data.json"
SOURCE_ATTACHMENT = "coa-profile-sources.json"
_FIXED_PDF_DATE = "D:20260101000000Z"

# Bitstream Vera is deliberately bundled for deterministic PDF output, but
# its ReportLab encoding does not reliably round-trip these Greek glyphs.
# Use readable ASCII names at the PDF boundary instead of emitting a tofu box
# or NUL in extracted text. The HTML surface can retain the typographic forms.
_PDF_TEXT_REPLACEMENTS = str.maketrans(
    {
        "α": "Alpha",
        "β": "Beta",
        "—": "-",
        "–": "-",
        "‑": "-",
        "…": "...",
        "×": "x",
    }
)


def _pdf_safe_text(text: str) -> str:
    return text.translate(_PDF_TEXT_REPLACEMENTS)


def _wrap(text: str, max_chars: int) -> list[str]:
    words = _pdf_safe_text(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) <= max_chars:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _draw_text_block(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    font: str = "Vera",
    size: float = 8.5,
    leading: float = 11.0,
    max_chars: int = 105,
) -> float:
    c.setFont(font, size)
    for line in _wrap(text, max_chars):
        c.drawString(x, y, line)
        y -= leading
    return y


def _field_value_text(field: ParsedField) -> str:
    """Compact one-line value text for the bounded chemistry grid."""
    if field.status not in {"verified", "derived"} or field.value is None:
        return "unreadable [U]"
    if field.original_unit and field.original_unit != "%" and field.original_value is not None:
        base = f"{field.original_value:g} {field.original_unit} -> {field.value:g}%"
    else:
        base = f"{field.value:g}%"
    if field.derived:
        base += " [D]"
    if field.plausibility_flag:
        base += " [!]"
    return base


def _draw_fitted_string(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    max_width: float,
    *,
    font: str = "Vera",
    preferred_size: float = 7.2,
    minimum_size: float = 5.2,
) -> None:
    """Draw a complete row, shrinking only as much as the column requires."""
    safe = _pdf_safe_text(text)
    size = preferred_size
    while size > minimum_size and pdfmetrics.stringWidth(safe, font, size) > max_width:
        size -= 0.2
    c.setFont(font, size)
    c.drawString(x, y, safe)


def _draw_chemistry_grid(
    c: canvas.Canvas,
    y: float,
    chemistry: COAChemistry,
) -> float:
    """Draw every recognized chemistry row in a deterministic two-column grid."""
    all_fields = list(chemistry.cannabinoids.items()) + list(chemistry.terpenes.items())
    c.setFont("VeraBd", 9.2)
    c.drawString(_MARGIN, y, f"Chemistry inputs read for this model ({len(all_fields)} rows)")
    y -= 12

    row_count = (len(all_fields) + 1) // 2
    columns = (all_fields[:row_count], all_fields[row_count:])
    gutter = 14
    column_width = (_PAGE_W - 2 * _MARGIN - gutter) / 2
    column_x = (_MARGIN + 4, _MARGIN + column_width + gutter + 4)
    row_leading = 9.0
    for column_index, column in enumerate(columns):
        for row_index, (name, field) in enumerate(column):
            line = f"{display_name(name)}: {_field_value_text(field)}"
            _draw_fitted_string(
                c,
                column_x[column_index],
                y - row_index * row_leading,
                line,
                column_width - 8,
            )
    y -= row_count * row_leading + 2
    c.setFont("VeraIt", 6.7)
    c.drawString(
        _MARGIN,
        y,
        "[D] derived  [U] unreadable  [!] plausibility warning; full source citations are attached.",
    )
    return y - 11


def _top_weighted_terpenes(chemistry: COAChemistry) -> list[tuple[str, float]]:
    """Rank terpene inputs by the model's weighted reference-max ratio.

    Monitored and unscored compounds have no directional contribution and are
    excluded even when their raw percentage is higher than every scored row.
    """
    ranked: list[tuple[str, float, float]] = []
    for name, field in chemistry.terpenes.items():
        spec = WEIGHTS.get(name)
        if (
            spec is None
            or spec.get("kind") != "terpene"
            or spec.get("monitored")
            or field.status != "verified"
            or field.value is None
        ):
            continue
        reference_max = spec.get("reference_max")
        if not isinstance(reference_max, (int, float)) or reference_max <= 0:
            continue
        contribution = float(spec["weight"]) * (field.value / reference_max)
        if contribution > 0:
            ranked.append((name, field.value, contribution))

    ranked.sort(key=lambda item: (-item[2], item[0]))
    return [(name, value) for name, value, _contribution in ranked[:3]]


def _draw_spectrum_bar(
    c: canvas.Canvas,
    y: float,
    score: int,
    band_low: int,
    band_high: int,
) -> float:
    """Draw the print-safe gradient, hatched uncertainty band, and marker."""
    bar_x, bar_w = _MARGIN, _PAGE_W - 2 * _MARGIN
    bar_h = 16
    bar_y = y - bar_h
    amber = (0.85, 0.47, 0.05)
    stone = (0.47, 0.44, 0.42)
    violet = (0.49, 0.23, 0.93)
    segments = 120
    for index in range(segments):
        position = index / (segments - 1)
        if position <= 0.5:
            local = position * 2
            start, end = amber, stone
        else:
            local = (position - 0.5) * 2
            start, end = stone, violet
        color = tuple(start[channel] + (end[channel] - start[channel]) * local for channel in range(3))
        c.setFillColorRGB(*color)
        segment_x = bar_x + bar_w * index / segments
        c.rect(segment_x, bar_y, bar_w / segments + 0.25, bar_h, stroke=0, fill=1)

    band_left = bar_x + bar_w * band_low / 100
    band_width = bar_w * (band_high - band_low) / 100
    c.setFillGray(0.92)
    c.rect(band_left, bar_y, band_width, bar_h, stroke=0, fill=1)
    c.saveState()
    clip = c.beginPath()
    clip.rect(band_left, bar_y, band_width, bar_h)
    c.clipPath(clip, stroke=0, fill=0)
    c.setStrokeGray(0.35)
    c.setLineWidth(0.55)
    hatch_x = band_left - bar_h
    while hatch_x < band_left + band_width:
        c.line(hatch_x, bar_y, hatch_x + bar_h, bar_y + bar_h)
        hatch_x += 4.5
    c.restoreState()
    c.setStrokeGray(0.18)
    c.setDash(3, 2)
    c.line(band_left, bar_y - 1, band_left, bar_y + bar_h + 1)
    c.line(band_left + band_width, bar_y - 1, band_left + band_width, bar_y + bar_h + 1)
    c.setDash()
    c.setLineWidth(0.8)
    c.rect(bar_x, bar_y, bar_w, bar_h, stroke=1, fill=0)
    marker_x = bar_x + bar_w * score / 100
    c.setStrokeGray(0.0)
    c.setLineWidth(2)
    c.line(marker_x, bar_y - 3, marker_x, bar_y + bar_h + 3)
    c.setLineWidth(1)
    c.setFillGray(0.0)
    c.setFont("Vera", 7)
    c.drawString(bar_x, bar_y - 10, "0 (sativa-leaning)")
    c.drawRightString(bar_x + bar_w, bar_y - 10, "100 (indica-leaning)")
    return bar_y - 22


def _scrub_branding_logo(path: str) -> bytes:
    """Re-encode logo pixels as deterministic PNG without EXIF, ICC, or thumbnails."""
    from PIL import Image

    with Image.open(path) as source:
        source.load()
        mode = "RGBA" if "A" in source.getbands() else "RGB"
        pixels = source.convert(mode)
        clean = Image.frombytes(mode, pixels.size, pixels.tobytes())
    output = io.BytesIO()
    clean.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def _embed_audit_attachments(pdf_data: bytes, result_json: str, source_json: str) -> bytes:
    """Attach deterministic JSON artifacts while preserving the PDF 1.4 contract."""
    try:
        import pymupdf
    except ImportError:  # PyMuPDF 1.24 compatibility name
        import fitz as pymupdf  # type: ignore[no-redef]

    document = pymupdf.open(stream=pdf_data, filetype="pdf")
    try:
        document.set_metadata(
            {
                "title": f"{TOOL_NAME} - strain profile",
                "author": TOOL_NAME,
                "creator": TOOL_NAME,
                "producer": TOOL_NAME,
                "subject": "Chemistry-derived tendency placement",
                "creationDate": _FIXED_PDF_DATE,
                "modDate": _FIXED_PDF_DATE,
            }
        )
        document.embfile_add(
            RESULT_ATTACHMENT,
            result_json.encode("utf-8"),
            filename=RESULT_ATTACHMENT,
            ufilename=RESULT_ATTACHMENT,
            desc="Deterministic result data matching the HTML result",
        )
        document.embfile_add(
            SOURCE_ATTACHMENT,
            source_json.encode("utf-8"),
            filename=SOURCE_ATTACHMENT,
            ufilename=SOURCE_ATTACHMENT,
            desc="Full source citations for recognized chemistry fields",
        )
        # PyMuPDF assigns the wall clock to embedded-file streams. Replace it
        # with the fixed artifact epoch so outputs remain byte-identical across
        # seconds and machines, not merely within one render call.
        for xref in range(1, document.xref_length()):
            if document.xref_get_key(xref, "Type") == ("name", "/EmbeddedFile"):
                document.xref_set_key(xref, "Params/CreationDate", f"({_FIXED_PDF_DATE})")
                document.xref_set_key(xref, "Params/ModDate", f"({_FIXED_PDF_DATE})")
        save_options = {
            "garbage": 3,
            "clean": True,
            "deflate": True,
            "no_new_id": True,
        }
        try:
            return document.tobytes(**save_options, reproducible=True)
        except TypeError:  # PyMuPDF versions before ``reproducible``
            return document.tobytes(**save_options)
    finally:
        document.close()


def render_profile_pdf(
    chemistry: COAChemistry,
    placement: PlacementResult,
    *,
    version: str,
    weights_hash: str,
    customer_name: str | None = None,
    branding_logo: str | None = None,
    result_json: str | None = None,
) -> bytes:
    """Render one Letter page with deterministic JSON audit attachments."""
    fields = field_rows(chemistry, placement)
    if result_json is None:
        result_json = build_result_json(placement, fields, version, weights_hash)
    source_json = build_source_json(chemistry)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter, invariant=True, pdfVersion=(1, 4))
    c.setTitle(f"{TOOL_NAME} - strain profile")
    c.setAuthor(TOOL_NAME)
    c.setCreator(TOOL_NAME)
    c.setSubject("Chemistry-derived tendency placement")

    y = _PAGE_H - _MARGIN

    # Header ----------------------------------------------------------------
    if branding_logo:
        try:
            c.drawImage(
                ImageReader(io.BytesIO(_scrub_branding_logo(branding_logo))),
                _PAGE_W - _MARGIN - 0.9 * inch,
                y - 0.35 * inch,
                width=0.9 * inch,
                height=0.45 * inch,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:  # noqa: BLE001,S110 - optional branding never blocks the profile
            pass
    c.setFont("VeraBd", 16)
    c.drawString(_MARGIN, y, TOOL_NAME)
    y -= 16
    c.setFont("Vera", 8)
    c.drawString(_MARGIN, y, f"Scorer version: {version}    Weights file SHA-256: {weights_hash[:16]}...")
    y -= 12
    if customer_name:
        c.setFont("VeraBd", 10)
        c.drawString(_MARGIN, y, f"Prepared for: {customer_name}")
        y -= 14
    c.setFont("Vera", 9)
    c.drawString(_MARGIN, y, f"Lab format detected: {chemistry.lab_format}")
    y -= 18

    if placement.completeness == "refusal":
        c.setFont("VeraBd", 12)
        c.drawString(_MARGIN, y, "No spectrum placement could be computed for this certificate.")
        y -= 16
        reason = placement.refusal_reason or "Insufficient readable chemistry."
        y = _draw_text_block(c, _MARGIN, y, reason, size=9, leading=12)
        y -= 6
    else:
        # Spectrum bar with uncertainty band --------------------------------
        c.setFont("VeraBd", 12)
        c.drawString(_MARGIN, y, f"Placement: {placement.score} of 100 - {placement_label(placement.score)}")
        y -= 12
        c.setFont("Vera", 9)
        c.drawString(_MARGIN, y, f"Uncertainty band: {placement.band_low}-{placement.band_high}")
        y -= 8
        y = _draw_spectrum_bar(c, y, placement.score, placement.band_low, placement.band_high)
        y = _draw_text_block(c, _MARGIN, y, BAND_NOTE, font="VeraIt", size=7.5, leading=9)
        y -= 4
        if placement.completeness == "degraded":
            c.setFont("VeraBd", 9)
            y = _draw_text_block(c, _MARGIN, y, DEGRADED_NOTICE, size=8.5, leading=11)
            y -= 4

        # Confidence ---------------------------------------------------------
        c.setFont("Vera", 9)
        c.drawString(
            _MARGIN,
            y,
            f"Data completeness: {placement.confidence_data * 100:.0f}%.  "
            f"Model confidence: {placement.confidence_model * 100:.0f}%.  "
            f"Combined: {placement.confidence_combined * 100:.0f}%.",
        )
        y -= 12
        y = _draw_text_block(c, _MARGIN, y, CONFIDENCE_NOTE, font="VeraIt", size=7.5, leading=9)
        y -= 6

        # Rationale ----------------------------------------------------------
        c.setFont("VeraBd", 10)
        c.drawString(_MARGIN, y, "Why this placement")
        y -= 12
        rationale_lines: list[str] = []
        for sentence in placement.rationale:
            rationale_lines.extend(_wrap("- " + sentence, 130))
        # Reserve a bounded chemistry region. The complete rationale remains
        # byte-for-byte available in the result-data attachment.
        max_lines = max(2, min(14, int((y - 310) / 8.0)))
        if len(rationale_lines) > max_lines:
            rationale_lines = rationale_lines[: max_lines - 1] + [
                "... Full rationale is available in the attached result data."
            ]
        c.setFont("Vera", 7.3)
        for line in rationale_lines:
            c.drawString(_MARGIN + 8, y, line)
            y -= 8.0
        y -= 4

    # A completeness refusal has no directional placement, so labeling any
    # terpene as "dominant" would imply a computation the gate rejected.
    dominant = [] if placement.completeness == "refusal" else _top_weighted_terpenes(chemistry)
    if dominant:
        dominant_text = "Dominant terpenes: " + ", ".join(
            f"{display_name(name)} {value:g}%" for name, value in dominant
        )
        y = _draw_text_block(c, _MARGIN, y, dominant_text, font="VeraBd", size=7.6, leading=9)
        y -= 3

    y = _draw_chemistry_grid(c, y, chemistry)

    c.setFont("Vera", 8)
    c.drawString(_MARGIN, y, f"Completeness: {placement.completeness}")
    y -= 10
    c.setFont("VeraIt", 6.8)
    c.drawString(
        _MARGIN,
        y,
        f"Audit attachments: {RESULT_ATTACHMENT} and {SOURCE_ATTACHMENT}.",
    )

    # Disclaimer + footer -----------------------------------------------------
    _draw_text_block(
        c,
        _MARGIN,
        1.62 * inch,
        STANDING_DISCLAIMER,
        font="VeraIt",
        size=6.6,
        leading=7.5,
        max_chars=135,
    )
    c.setFont("Vera", 7.0)
    c.drawString(_MARGIN, 0.48 * inch, ALGORITHM_LINE)
    c.drawRightString(_PAGE_W - _MARGIN, 0.48 * inch, FREE_FOOTER)

    c.showPage()
    c.save()
    data = _embed_audit_attachments(buf.getvalue(), result_json, source_json)
    if len(data) > 500 * 1024:  # FR-011 size cap - never deliver a bloated PDF
        raise RuntimeError("generated profile exceeds the 500 KB contract limit")
    return data
