"""Deterministic layout detection (FR-004).

Three Florida lab format families are recognized by content signatures
computed from extracted text (never by filename, AC-032):

- ``confident_cannabis`` — Confident Cannabis branding / panel header pattern
- ``sc_labs``            — "SC Labs" or "PhytoFacts" marker
- ``generic_ommu``       — "Certificate of Analysis" + cannabinoid table with
                           THC and CBD entries (keyword + numeric patterns);
                           this is also the safety-net fallback parser for any
                           OMMU-compliant format not explicitly modeled

Layout is detected per document (strongest aggregate signature across all
pages); each page's compounds are extracted under that page's best-matching
sub-format rules. Documents with a certificate structure but no family match
are recorded as ``unknown`` and parsed with the generic rules; documents with
no certificate structure at all are refused by the caller (NotACOAError).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

FORMAT_CONFIDENT_CANNABIS = "confident_cannabis"
FORMAT_SC_LABS = "sc_labs"
FORMAT_GENERIC_OMMU = "generic_ommu"
FORMAT_UNKNOWN = "unknown"

_SIGNATURES: dict[str, list[tuple[re.Pattern[str], float]]] = {
    FORMAT_CONFIDENT_CANNABIS: [
        (re.compile(r"(?i)confident\s*cannabis"), 3.0),
        (re.compile(r"(?i)confidentcannabis\.com"), 3.0),
        (re.compile(r"(?i)\banalysis\s+id\b"), 1.0),
    ],
    FORMAT_SC_LABS: [
        (re.compile(r"(?i)\bsc\s*labs\b"), 3.0),
        (re.compile(r"(?i)phytofacts"), 3.0),
        (re.compile(r"(?i)sclabs\.com"), 2.0),
    ],
    FORMAT_GENERIC_OMMU: [
        (re.compile(r"(?i)certificate\s+of\s+analysis"), 2.0),
        (re.compile(r"(?i)\bcannabinoid(s)?\b"), 1.0),
        (re.compile(r"(?i)\bterpene(s)?\b"), 1.0),
        (re.compile(r"(?i)\bthc\b"), 0.5),
        (re.compile(r"(?i)\bcbd\b"), 0.5),
        (re.compile(r"(?i)\bommu\b"), 1.0),
        (re.compile(r"(?i)florida"), 0.5),
    ],
}

#: Minimum aggregate score for the generic family to count as a COA structure.
_GENERIC_MIN = 2.0

#: Bare-minimum certificate vocabulary: without any of these the document is
#: not a COA at all.
_CERTIFICATE_MARKERS = [
    re.compile(r"(?i)certificate\s+of\s+analysis"),
    re.compile(r"(?i)\bcoa\b"),
    re.compile(r"(?i)cannabinoid"),
    re.compile(r"(?i)terpene"),
    re.compile(r"(?i)\bthc\b"),
]


@dataclass
class LayoutResult:
    document_format: str
    page_formats: list[str]  # per-page best-matching sub-format
    page_scores: list[dict[str, float]]
    is_certificate: bool


def score_signatures(text: str) -> dict[str, float]:
    return {
        family: sum(w for pattern, w in patterns if pattern.search(text))
        for family, patterns in _SIGNATURES.items()
    }


def _page_format(scores: dict[str, float]) -> str:
    best = max(scores, key=lambda f: scores[f])
    if scores[best] <= 0:
        return FORMAT_GENERIC_OMMU
    return best


def detect_layout(pages: list[str]) -> LayoutResult:
    """Detect the document-level format and per-page sub-formats."""
    combined = "\n".join(pages)
    is_certificate = any(p.search(combined) for p in _CERTIFICATE_MARKERS)

    page_scores = [score_signatures(p) for p in pages]
    aggregate = {f: sum(s[f] for s in page_scores) for f in _SIGNATURES}

    brand = {f: aggregate[f] for f in (FORMAT_CONFIDENT_CANNABIS, FORMAT_SC_LABS)}
    best_brand = max(brand, key=lambda f: brand[f])
    if brand[best_brand] >= 3.0:
        document_format = best_brand
    elif aggregate[FORMAT_GENERIC_OMMU] >= _GENERIC_MIN:
        document_format = FORMAT_GENERIC_OMMU
    elif is_certificate:
        document_format = FORMAT_UNKNOWN
    else:
        document_format = FORMAT_UNKNOWN

    page_formats = [_page_format(s) for s in page_scores]
    return LayoutResult(
        document_format=document_format,
        page_formats=page_formats,
        page_scores=page_scores,
        is_certificate=is_certificate,
    )
