"""Scorer package: deterministic chemistry-to-spectrum placement (FR-006..FR-009)."""

from coa_profiler.scorer.placement import (
    PlacementResult,
    apply_sufficiency_gate,
    band_half_width,
    compute_confidence,
    placement_bin,
    placement_label,
    score_chemistry,
)
from coa_profiler.scorer.rationale import build_rationale
from coa_profiler.scorer.weights import (
    CONFIDENCE_FLOOR_DEGRADED,
    CONTRACTION_DEGRADED,
    CONTRACTION_FULL,
    MODEL_CONFIDENCE,
    WEIGHTS,
    weights_file_hash,
)

__all__ = [
    "CONFIDENCE_FLOOR_DEGRADED",
    "CONTRACTION_DEGRADED",
    "CONTRACTION_FULL",
    "MODEL_CONFIDENCE",
    "WEIGHTS",
    "PlacementResult",
    "apply_sufficiency_gate",
    "band_half_width",
    "build_rationale",
    "compute_confidence",
    "placement_bin",
    "placement_label",
    "score",
    "score_chemistry",
    "weights_file_hash",
]


def score(chemistry) -> PlacementResult:
    """Public entry point: score(parse_coa(path)) -> PlacementResult.

    Runs the sufficiency gate, placement computation, and rationale
    generation, returning one assembled PlacementResult.
    """
    result = score_chemistry(chemistry)
    if not result.rationale:
        result.rationale = build_rationale(chemistry, result.driving_compounds, result.completeness)
    return result
