"""Placement computation (FR-006 sufficiency gate, FR-007 scoring, FR-009
confidence, FR-029 uncertainty band).

Pure functions over the parsed chemistry record. No I/O, no clocks, no
randomness — identical inputs always produce identical outputs (FR-022).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from coa_profiler.errors import NoUsableChemistryError
from coa_profiler.scorer.weights import (
    CONFIDENCE_FLOOR_DEGRADED,
    CONTRACTION_DEGRADED,
    CONTRACTION_FULL,
    DEGRADED_PARTICIPANTS,
    EXPECTED_CANNABINOIDS,
    MODEL_CONFIDENCE,
    WEIGHTS,
)

if TYPE_CHECKING:  # avoid a hard import cycle with the parser package
    from coa_profiler.parser.fields import COAChemistry, ParsedField


@dataclass
class PlacementResult:
    """Spec section 5 data model."""

    score: int  # 0–100, rounded to nearest 5; -1 sentinel when completeness == "refusal"
    raw_score: float
    confidence_data: float  # DC, 0.0–1.0
    confidence_model: float  # MC, 0.75 at launch (tuning parameter, not statistical)
    confidence_combined: float  # DC × MC
    completeness: str  # "full" | "degraded" | "refusal"
    rationale: list[str] = field(default_factory=list)
    driving_compounds: list[tuple[str, float, str]] = field(default_factory=list)
    band_half_width: int = 5
    refusal_reason: str | None = None

    @property
    def band_low(self) -> int:
        return max(0, self.score - self.band_half_width)

    @property
    def band_high(self) -> int:
        return min(100, self.score + self.band_half_width)

    @property
    def label(self) -> str:
        return placement_label(self.score)


def _verified(field: ParsedField | None) -> bool:
    return field is not None and field.status == "verified" and field.value is not None


def _round5(value: float) -> int:
    """Round to the nearest 5, ties toward zero, clamped to [0, 100].

    Tie handling is load-bearing: the DIS-10 reachability table is only
    self-consistent under round-half-toward-zero. Raw 0 contracts to 7.5 and
    must round to 5 (reachable per the table); raw 100 contracts to 92.5 and
    must round to 90 (95 unreachable per the table). Python's banker's
    rounding and round-half-up both break one side of that table.
    """
    import math

    return max(0, min(100, math.ceil(value / 5 - 0.5) * 5))


def band_half_width(confidence_combined: float) -> int:
    """FR-029: band width proportional to 1 - CC, clamped to [5, 20]."""
    import math

    raw = (1.0 - confidence_combined) * 20
    return max(5, min(20, math.ceil(raw / 5 - 0.5) * 5))


def placement_bin(score: int) -> str:
    """DIS-10 widened bins (placements are multiples of 5)."""
    if score <= 20:
        return "strongly-sativa"
    if score <= 40:
        return "sativa"
    if score <= 55:
        return "balanced"
    if score <= 75:
        return "indica"
    return "strongly-indica"


def placement_label(score: int) -> str:
    b = placement_bin(score)
    if b.startswith("strongly-"):
        return b.replace("strongly-", "strongly ") + "-leaning"
    return b + "-leaning"


def readable_terpenes(chemistry: COAChemistry) -> int:
    return sum(1 for f in chemistry.terpenes.values() if _verified(f))


def apply_sufficiency_gate(chemistry: COAChemistry) -> str:
    """FR-006 / DIS-6 four-outcome gate.

    Returns "full" | "degraded" | "refusal". Raises NoUsableChemistryError for
    the complete-refusal outcome (zero readable chemistry of any kind), which
    surfaces as a typed S3 error rather than a result page.
    """
    any_chemistry = any(_verified(f) for f in chemistry.cannabinoids.values()) or any(
        _verified(f) for f in chemistry.terpenes.values()
    )
    if not any_chemistry:
        raise NoUsableChemistryError()

    forced = getattr(chemistry, "forced_refusal_reason", None)
    cannabinoids_verified = sum(
        1 for name in EXPECTED_CANNABINOIDS if _verified(chemistry.cannabinoids.get(name))
    )
    readable_terps = readable_terpenes(chemistry)

    if readable_terps == 0:
        return "refusal"
    if cannabinoids_verified == 0:
        # No cannabinoid anchor: neither full (needs >= 1 cannabinoid) nor
        # degraded (cannabinoid-ratio mode by definition) is computable.
        return "refusal"

    total_reported = chemistry.total_reported_terpenes
    if total_reported is None:
        terp_fraction_ok = True  # absolute >= 3 governs when undeterminable
    else:
        terp_fraction_ok = total_reported > 0 and (readable_terps / total_reported) >= 0.60
    if cannabinoids_verified >= 1 and readable_terps >= 3 and terp_fraction_ok and not forced:
        return "full"
    if forced:
        return "refusal"
    return "degraded"


def _contributions(
    chemistry: COAChemistry, participants: dict[str, dict]
) -> tuple[list[tuple[str, float, str]], float, float, list[str]]:
    """Directional sums (FR-007 Steps 1-2).

    Returns (contribution rows, indica_pull, sativa_pull, present_but_unscored).
    Compounds absent from the COA contribute 0; present compounds that are not
    in the weight table are named for the rationale but never scored.
    """
    rows: list[tuple[str, float, str]] = []
    indica_pull = 0.0
    sativa_pull = 0.0
    all_fields: dict[str, ParsedField] = {**chemistry.cannabinoids, **chemistry.terpenes}
    for name, spec in participants.items():
        f = all_fields.get(name)
        if not _verified(f):
            continue  # absent or unreadable: contributes 0, penalized in confidence
        # ``f.value`` has already been normalized to percentage units by the
        # parser.  FR-007 applies the reference-max ratio without clipping:
        # values above an operator-informed reference maximum must retain
        # their full directional contribution (and are separately surfaced by
        # the plausibility system when appropriate).
        reference_ratio = f.value / spec["reference_max"]
        contribution = spec["weight"] * reference_ratio
        if spec["direction"] == "indica":
            indica_pull += contribution
        elif spec["direction"] == "sativa":
            sativa_pull += contribution
        if contribution > 0:
            rows.append((name, contribution, spec["direction"]))
    rows.sort(key=lambda r: r[1], reverse=True)
    present_unscored = sorted(name for name, f in all_fields.items() if _verified(f) and name not in WEIGHTS)
    return rows, indica_pull, sativa_pull, present_unscored


def compute_confidence(chemistry: COAChemistry, mode: str) -> float:
    """FR-009 data-completeness component (DC). Penalty constants are tuning
    parameters documented in docs/algorithm.md."""
    # A missing expected field is incomplete just as an explicitly unreadable
    # field is.  Counting only objects the parser happened to emit would reward
    # silent extraction misses with a higher confidence score.
    unreadable_cannabinoids = sum(
        1 for name in EXPECTED_CANNABINOIDS if not _verified(chemistry.cannabinoids.get(name))
    )
    total_reported = chemistry.total_reported_terpenes
    if total_reported is None:
        unreadable_terpenes = sum(1 for f in chemistry.terpenes.values() if not _verified(f))
    else:
        # The denominator comes from independently observed source rows.  It
        # therefore includes rows whose value extraction failed or whose
        # compound was omitted from the structured result.
        unreadable_terpenes = max(0, total_reported - readable_terpenes(chemistry))
    dc = 1.0
    dc -= 0.15 * min(2, unreadable_cannabinoids)
    dc -= 0.10 * min(5, unreadable_terpenes)
    if readable_terpenes(chemistry) < 5:
        dc -= 0.20
    ocr_mean = chemistry.ocr_mean_confidence
    if ocr_mean is not None and 60.0 <= ocr_mean < 75.0:
        dc -= 0.15
    if mode == "degraded":
        dc -= 0.30
    return max(0.0, dc)


def _gate_refusal_reason(chemistry: COAChemistry) -> str:
    """Return the exact sufficiency failure instead of a generic explanation."""
    forced = getattr(chemistry, "forced_refusal_reason", None)
    if forced:
        return forced
    if readable_terpenes(chemistry) == 0:
        return (
            "No terpene values were readable on this certificate, so no placement can be computed. "
            "The chemotype summary below shows what was readable."
        )
    cannabinoid_anchors = sum(
        1 for name in EXPECTED_CANNABINOIDS if _verified(chemistry.cannabinoids.get(name))
    )
    if cannabinoid_anchors == 0:
        return (
            "No Total THC or Total CBD value was readable on this certificate. At least one "
            "cannabinoid anchor is required for a placement, even when terpene values are readable. "
            "The chemotype summary below shows what was readable."
        )
    # Defensive fallback for a future sufficiency gate. Every current refusal
    # route is handled above and should retain its own user-facing reason.
    return (
        "The readable chemistry did not meet the placement requirements. "
        "The chemotype summary below shows what was readable."
    )


def score_chemistry(chemistry: COAChemistry) -> PlacementResult:
    """Full FR-006 -> FR-009 pipeline for one parsed COA."""
    mode = apply_sufficiency_gate(chemistry)

    if mode == "refusal":
        reason = _gate_refusal_reason(chemistry)
        dc = compute_confidence(chemistry, "refusal")
        return PlacementResult(
            score=-1,
            raw_score=50.0,
            confidence_data=dc,
            confidence_model=MODEL_CONFIDENCE,
            confidence_combined=dc * MODEL_CONFIDENCE,
            completeness="refusal",
            rationale=[reason],
            driving_compounds=[],
            band_half_width=5,
            refusal_reason=reason,
        )

    participants = (
        {k: WEIGHTS[k] for k in DEGRADED_PARTICIPANTS}
        if mode == "degraded"
        else {k: v for k, v in WEIGHTS.items() if not v.get("monitored")}
    )
    contributions, indica_pull, sativa_pull, _ = _contributions(chemistry, participants)

    # Step 3: raw score. Step 4: model-uncertainty contraction. Step 5: round.
    # A zero signed sum is a valid midpoint, including when every readable
    # field is neutral/unscored or has a reported value of zero. Sufficiency
    # and confidence refusals are handled by the explicit gates above/below.
    raw_score = 50.0 + (indica_pull - sativa_pull) * 50.0
    contraction = CONTRACTION_FULL if mode == "full" else CONTRACTION_DEGRADED
    contracted = 50.0 + (raw_score - 50.0) * contraction
    placement = _round5(contracted)

    dc = compute_confidence(chemistry, mode)
    combined = dc * MODEL_CONFIDENCE
    if mode == "degraded" and combined < CONFIDENCE_FLOOR_DEGRADED:
        reason = (
            "Only cannabinoid data was usable and the combined confidence fell below the "
            f"{CONFIDENCE_FLOOR_DEGRADED:.2f} floor for cannabinoid-only placements, so no placement "
            "is shown. The chemotype summary below shows what was readable."
        )
        return PlacementResult(
            score=-1,
            raw_score=raw_score,
            confidence_data=dc,
            confidence_model=MODEL_CONFIDENCE,
            confidence_combined=combined,
            completeness="refusal",
            rationale=[reason],
            driving_compounds=[],
            band_half_width=5,
            refusal_reason=reason,
        )

    driving = [(name, round(contrib, 4), direction) for name, contrib, direction in contributions[:3]]
    return PlacementResult(
        score=placement,
        raw_score=raw_score,
        confidence_data=dc,
        confidence_model=MODEL_CONFIDENCE,
        confidence_combined=combined,
        completeness=mode,
        rationale=[],  # filled by scorer.__init__.score via build_rationale
        driving_compounds=driving,
        band_half_width=band_half_width(combined),
    )
