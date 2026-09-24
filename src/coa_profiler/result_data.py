"""Deterministic result serialization shared by web, PDF, and batch outputs.

Keeping this module below every presentation layer prevents the offline batch
pipeline from importing private HTTP helpers and guarantees that the JSON
embedded in the HTML result and attached to the PDF has one implementation.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from coa_profiler.scorer.placement import placement_label
from coa_profiler.scorer.weights import CONTRACTION_DEGRADED, CONTRACTION_FULL, WEIGHTS

if TYPE_CHECKING:
    from coa_profiler.parser.fields import COAChemistry
    from coa_profiler.scorer.placement import PlacementResult

_ACRONYMS = {"cbd", "thc", "thca", "cbda", "cbg", "cbn", "cbc", "thcv", "cbdv"}


def display_name(name: str) -> str:
    """Return the stable human-facing compound name used by every surface."""
    if spec := WEIGHTS.get(name):
        return str(spec["display"])
    return " ".join(
        part.upper() if part.lower() in _ACRONYMS else part.title() for part in name.replace("_", " ").split()
    )


def field_rows(chemistry: COAChemistry, placement: PlacementResult) -> list[dict]:
    """Build the complete presentation row model for recognized chemistry."""
    degraded = placement.completeness == "degraded"
    rows: list[dict] = []
    for category, table in (("cannabinoid", chemistry.cannabinoids), ("terpene", chemistry.terpenes)):
        for name, field in table.items():
            verified = field.status in ("verified", "derived") and field.value is not None
            if verified:
                original = field.original_value if field.original_value is not None else field.value
                if field.original_unit and field.original_unit != "%":
                    reported = f"{original:g} {field.original_unit}"
                else:
                    reported = f"{original:g}%"
                normalized = f"{field.value:g}%"
                reported_value: float | None = original
                normalized_value: float | None = field.value
                reported_unit: str | None = field.original_unit or "%"
            else:
                reported = None
                normalized = None
                reported_value = None
                normalized_value = None
                reported_unit = None
            status = "derived" if (verified and field.derived) else field.status
            rows.append(
                {
                    "compound": display_name(name),
                    "key": name,
                    "category": category,
                    "reported": reported,
                    "reported_value": reported_value,
                    "reported_unit": reported_unit,
                    "normalized": normalized,
                    "normalized_value": normalized_value,
                    "status": status,
                    "source_span": field.source_span or None,
                    "unreadable_reason": field.unreadable_reason or None,
                    "plausibility_flag": field.plausibility_flag,
                    "derived_note": field.derivation_note if status == "derived" else None,
                    "not_used_in_placement": bool(degraded and category == "terpene" and verified),
                    "conflicting_note": (
                        "This value also appeared elsewhere; the strongest matching page was used."
                        if field.conflicting_value
                        else None
                    ),
                }
            )
    return rows


def build_result_json(
    placement: PlacementResult,
    fields: list[dict],
    version: str,
    weights_hash: str,
) -> str:
    """Return deterministic SPEC section 15.6 JSON for HTML and PDF."""
    refused = placement.completeness == "refusal"
    contraction = (
        None if refused else (CONTRACTION_FULL if placement.completeness == "full" else CONTRACTION_DEGRADED)
    )
    payload = {
        "completeness": placement.completeness,
        # Refusal is a completed analysis with no placement. Keep the stable
        # schema while representing unavailable placement values as JSON null,
        # never internal sentinels (-1) or derived nonsense bands (0-4).
        "score": None if refused else placement.score,
        "label": None if refused else placement_label(placement.score),
        "band_low": None if refused else placement.band_low,
        "band_high": None if refused else placement.band_high,
        "confidence": {
            "data_completeness_pct": round(placement.confidence_data * 100),
            "model_confidence_pct": round(placement.confidence_model * 100),
            "combined_pct": round(placement.confidence_combined * 100),
        },
        "rationale": placement.rationale,
        "fields": [
            {
                "compound": field["compound"],
                "category": field["category"],
                "reported": field["reported"],
                "normalized": field["normalized"],
                "status": field["status"],
                "plausibility_flag": field["plausibility_flag"],
                "not_used_in_placement": field["not_used_in_placement"],
            }
            for field in fields
        ],
        "version": version,
        "weights_hash": weights_hash,
        "scoring_steps": {
            "raw_score": None if refused else placement.raw_score,
            "contraction_factor": contraction,
            "contracted_score": (None if refused else 50 + (placement.raw_score - 50) * contraction),
            "rounded_score": None if refused else placement.score,
        },
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    # This exact string is embedded in an HTML script block and attached to the
    # PDF. Escaping HTML-significant characters keeps both artifacts identical
    # while remaining valid JSON.
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build_source_json(chemistry: COAChemistry) -> str:
    """Return a deterministic audit attachment containing every source span."""
    sources: list[dict] = []
    for category, table in (("cannabinoid", chemistry.cannabinoids), ("terpene", chemistry.terpenes)):
        for name, field in table.items():
            sources.append(
                {
                    "category": category,
                    "compound": display_name(name),
                    "key": name,
                    "status": "derived" if field.derived else field.status,
                    "source_span": field.source_span,
                    "conflict_span": field.conflict_span,
                    "derivation_note": field.derivation_note,
                    "unreadable_reason": field.unreadable_reason,
                }
            )
    payload = {
        "schema_version": 1,
        "lab_format": chemistry.lab_format,
        "sources": sources,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
