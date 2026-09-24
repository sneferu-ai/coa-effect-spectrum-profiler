"""FR-006/FR-007/FR-009/FR-029 placement math, gate outcomes, bands."""

import pytest

from coa_profiler.errors import NoUsableChemistryError
from coa_profiler.scorer import score
from coa_profiler.scorer.placement import (
    PlacementResult,
    apply_sufficiency_gate,
    band_half_width,
    placement_bin,
    score_chemistry,
)
from tests.conftest import make_chemistry, make_field


def _full_chem():
    return make_chemistry(
        {"thc_total": (18.2, "%"), "cbd_total": (0.5, "%")},
        {
            "myrcene": (0.85, "%"),
            "limonene": (0.42, "%"),
            "linalool": (0.21, "%"),
            "alpha_pinene": (0.33, "%"),
            "humulene": (0.12, "%"),
            "beta_caryophyllene": (0.66, "%"),
        },
        total_reported_terpenes=6,
    )


class TestGate:
    def test_full(self):
        assert apply_sufficiency_gate(_full_chem()) == "full"

    def test_degraded_with_partial_terpenes(self):
        chem = make_chemistry(
            {"thc_total": (20.0, "%"), "cbd_total": (1.0, "%")},
            {"myrcene": (0.5, "%")},
            total_reported_terpenes=1,
        )
        assert apply_sufficiency_gate(chem) == "degraded"

    def test_refusal_with_zero_terpenes(self):
        chem = make_chemistry({"thc_total": (20.0, "%"), "cbd_total": (1.0, "%")}, {})
        assert apply_sufficiency_gate(chem) == "refusal"
        result = score_chemistry(chem)
        assert "No terpene values were readable" in result.refusal_reason
        assert "No Total THC or Total CBD" not in result.refusal_reason

    def test_refusal_with_zero_cannabinoids(self):
        chem = make_chemistry(
            {},
            {"myrcene": (0.5, "%"), "limonene": (0.5, "%"), "linalool": (0.2, "%")},
            total_reported_terpenes=3,
        )
        assert apply_sufficiency_gate(chem) == "refusal"

    def test_no_cannabinoid_anchor_has_truthful_refusal_reason(self):
        chem = make_chemistry(
            {},
            {"myrcene": (0.5, "%"), "limonene": (0.5, "%"), "linalool": (0.2, "%")},
            total_reported_terpenes=3,
        )

        result = score_chemistry(chem)

        assert result.completeness == "refusal"
        assert "No Total THC or Total CBD value was readable" in result.refusal_reason
        assert "even when terpene values are readable" in result.refusal_reason
        assert "No terpene values were readable" not in result.refusal_reason

    def test_complete_refusal_raises(self):
        with pytest.raises(NoUsableChemistryError):
            apply_sufficiency_gate(make_chemistry({}, {}))

    def test_unreadable_only_raises(self):
        chem = make_chemistry({"thc_total": (None,)}, {})
        with pytest.raises(NoUsableChemistryError):
            apply_sufficiency_gate(chem)

    def test_sixty_percent_rule(self):
        # 3 readable of 6 reported = 50% < 60% -> degraded, not full.
        terps = {
            "myrcene": (0.5, "%"),
            "limonene": (0.4, "%"),
            "linalool": (0.2, "%"),
            "humulene": (None,),
            "ocimene": (None,),
            "terpinolene": (None,),
        }
        chem = make_chemistry({"thc_total": (18.0, "%")}, terps, total_reported_terpenes=6)
        assert apply_sufficiency_gate(chem) == "degraded"

    def test_absolute_rule_when_total_unknown(self):
        terps = {"myrcene": (0.5, "%"), "limonene": (0.4, "%"), "linalool": (0.2, "%")}
        chem = make_chemistry({"thc_total": (18.0, "%")}, terps, total_reported_terpenes=None)
        assert apply_sufficiency_gate(chem) == "full"

    def test_forced_refusal(self):
        chem = _full_chem()
        chem.forced_refusal_reason = "inconsistent"
        assert apply_sufficiency_gate(chem) == "refusal"
        assert score_chemistry(chem).refusal_reason == "inconsistent"


class TestScoring:
    def test_known_arithmetic(self):
        chem = make_chemistry({"thc_total": (20.0, "%")}, {"myrcene": (1.0, "%")}, total_reported_terpenes=1)
        # Degraded mode scores cannabinoids only. Signed contribution is
        # +0.5*(20/30) = +1/3, so raw = 50 + (1/3)*50 = 66.6667.
        result = score_chemistry(chem)
        assert result.completeness == "degraded"
        assert result.raw_score == pytest.approx(66.6666667)
        assert result.score == 60  # 50 + (66.6667 - 50)*0.70 = 61.6667

    def test_rounding_matches_dis10_reachability(self):
        # Round-half-toward-zero: raw 100 -> contracted 92.5 -> 90 (95 is
        # unreachable in full mode per the DIS-10 table)...
        chem = make_chemistry(
            {"thc_total": (30.0, "%")},
            {"myrcene": (0.4, "%"), "beta_caryophyllene": (0.5, "%"), "bisabolol": (0.2, "%")},
            total_reported_terpenes=3,
        )
        result = score_chemistry(chem)
        assert result.completeness == "full"
        assert result.raw_score == pytest.approx(100.0)
        assert result.score == 90
        # ...and raw 0 -> contracted 7.5 -> 5 (5 IS reachable per the table).
        chem0 = make_chemistry(
            {"cbd_total": (20.0, "%")},
            {"limonene": (0.5, "%"), "beta_caryophyllene": (0.5, "%"), "bisabolol": (0.2, "%")},
            total_reported_terpenes=3,
        )
        result0 = score_chemistry(chem0)
        assert result0.raw_score == pytest.approx(0.0)
        assert result0.score == 5

    def test_score_is_multiple_of_5_in_range(self):
        for thc in (0.0, 5.0, 12.0, 18.2, 25.0, 30.0):
            chem = _full_chem()
            chem.cannabinoids["thc_total"] = make_field("thc_total", thc)
            result = score(chem)
            assert 0 <= result.score <= 100 and result.score % 5 == 0

    def test_zero_active_pull_is_valid_midpoint(self):
        # The chemistry/refusal gates are satisfied, but every readable value
        # is neutral, unscored, or zero. FR-007 defines this as a signed sum of
        # zero and therefore a midpoint placement, not a scorer refusal.
        chem = make_chemistry(
            {},
            {"bisabolol": (0.4, "%"), "geraniol": (0.2, "%"), "eucalyptol": (0.1, "%")},
            total_reported_terpenes=3,
        )
        chem.forced_refusal_reason = None
        chem.cannabinoids["thc_total"] = make_field("thc_total", 0.0)
        result = score_chemistry(chem)
        assert result.completeness == "full"
        assert result.raw_score == pytest.approx(50.0)
        assert result.score == 50
        assert result.refusal_reason is None
        assert result.driving_compounds == []

    def test_reference_max_ratio_is_not_capped(self):
        chem = make_chemistry(
            {"thc_total": (0.0, "%")},
            {"limonene": (4.0, "%"), "beta_caryophyllene": (0.5, "%"), "bisabolol": (0.2, "%")},
            total_reported_terpenes=3,
        )
        result = score_chemistry(chem)
        # Limonene is 2x its 2% reference max: 2.0 weight * 2.0 ratio
        # contributes -4.0. A capped implementation would report only -2.0.
        assert result.raw_score == pytest.approx(-150.0)
        assert result.driving_compounds[0] == ("limonene", 4.0, "sativa")
        assert result.score == 0

    def test_degraded_confidence_floor_refusal(self):
        # Degraded + one unreadable cannabinoid + marginal OCR + few terpenes:
        # DC = 1 - .15 - .20 - .15 - .30 = 0.20 -> CC = 0.15 < 0.25 -> refusal.
        chem = make_chemistry(
            {"thc_total": (20.0, "%"), "cbd_total": (None,)},
            {"myrcene": (0.5, "%")},
            total_reported_terpenes=1,
            ocr_mean_confidence=65.0,
        )
        result = score_chemistry(chem)
        assert result.completeness == "refusal"
        assert result.confidence_combined < 0.25

    def test_driving_compounds_ordered(self):
        result = score(_full_chem())
        assert result.completeness == "full"
        assert result.driving_compounds[0][0] == "myrcene"
        contributions = [c for _, c, _ in result.driving_compounds]
        assert contributions == sorted(contributions, reverse=True)


class TestConfidence:
    def test_clean_full(self):
        result = score(_full_chem())
        assert result.confidence_data == pytest.approx(1.0)
        assert result.confidence_model == pytest.approx(0.75)
        assert result.confidence_combined == pytest.approx(0.75)

    def test_penalties_stack(self):
        chem = _full_chem()
        chem.cannabinoids["cbd_total"] = make_field("cbd_total", None)  # unreadable
        chem.ocr_mean_confidence = 70.0
        result = score_chemistry(chem)
        # DC = 1 - .15 (cannabinoid) - .15 (OCR band) = 0.70
        assert result.confidence_data == pytest.approx(0.70)
        assert result.confidence_combined == pytest.approx(0.70 * 0.75)

    def test_degraded_penalty(self):
        chem = make_chemistry(
            {"thc_total": (20.0, "%"), "cbd_total": (1.0, "%")},
            {"myrcene": (0.5, "%")},
            total_reported_terpenes=1,
        )
        result = score_chemistry(chem)
        # DC = 1 - .20 (few terpenes) - .30 (degraded) = 0.50; CC = 0.375.
        assert result.confidence_data == pytest.approx(0.50)
        assert result.confidence_combined == pytest.approx(0.375)

    def test_missing_expected_cannabinoid_reduces_confidence(self):
        chem = make_chemistry(
            {"thc_total": (18.0, "%")},
            {
                "myrcene": (0.5, "%"),
                "limonene": (0.4, "%"),
                "linalool": (0.2, "%"),
                "humulene": (0.1, "%"),
                "alpha_pinene": (0.1, "%"),
            },
            total_reported_terpenes=5,
        )
        result = score_chemistry(chem)
        assert result.completeness == "full"
        assert result.confidence_data == pytest.approx(0.85)

    def test_reported_minus_readable_terpenes_reduces_confidence(self):
        chem = make_chemistry(
            {"thc_total": (18.0, "%"), "cbd_total": (0.5, "%")},
            {"myrcene": (0.5, "%"), "limonene": (0.4, "%"), "linalool": (0.2, "%")},
            total_reported_terpenes=5,
        )
        result = score_chemistry(chem)
        assert result.completeness == "full"  # 3/5 exactly meets the 60% gate
        # 0.20 for two unreadable reported rows + 0.20 for fewer than five readable.
        assert result.confidence_data == pytest.approx(0.60)


class TestBand:
    def test_formula(self):
        assert band_half_width(0.75) == 5
        assert band_half_width(0.5) == 10
        assert band_half_width(0.0) == 20
        assert band_half_width(1.0) == 5  # clamped floor

    def test_band_clamped_to_axis(self):
        chem = make_chemistry(
            {"thc_total": (0.0, "%"), "cbd_total": (30.0, "%")},
            {
                "limonene": (2.0, "%"),
                "terpinolene": (0.8, "%"),
                "alpha_pinene": (1.5, "%"),
                "ocimene": (0.5, "%"),
                "myrcene": (0.0, "%"),
            },
            total_reported_terpenes=5,
        )
        result = score_chemistry(chem)
        assert result.score <= 20
        assert result.band_low == 0


class TestBins:
    @pytest.mark.parametrize(
        "score_val,bin_name",
        [
            (0, "strongly-sativa"),
            (20, "strongly-sativa"),
            (25, "sativa"),
            (40, "sativa"),
            (45, "balanced"),
            (55, "balanced"),
            (60, "indica"),
            (75, "indica"),
            (80, "strongly-indica"),
            (100, "strongly-indica"),
        ],
    )
    def test_bin_edges(self, score_val, bin_name):
        assert placement_bin(score_val) == bin_name

    def test_label(self):
        result = PlacementResult(
            score=70,
            raw_score=70.0,
            confidence_data=1.0,
            confidence_model=0.75,
            confidence_combined=0.75,
            completeness="full",
        )
        assert result.label == "indica-leaning"
