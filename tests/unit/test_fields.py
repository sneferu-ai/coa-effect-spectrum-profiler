"""FR-005 extraction: units, derivation, cite-and-verify, conflicts, FR-028."""

import pytest

from coa_profiler.parser import extract_chemistry
from coa_profiler.parser.fields import (
    apply_plausibility,
    count_reported_terpenes,
    derive_totals,
    extract_page,
    implausible_fraction,
    normalize_unit,
)
from tests.conftest import make_chemistry, make_field


class TestUnitNormalization:
    @pytest.mark.parametrize(
        "value,unit,expected",
        [
            (18.2, "%", 18.2),
            (182.0, "mg/g", 18.2),
            (195.0, "mg/mL", 19.5),
            (8500.0, "ppm", 0.85),
        ],
    )
    def test_conversions(self, value, unit, expected):
        normalized, canonical = normalize_unit(value, unit)
        assert normalized == pytest.approx(expected)
        assert canonical == unit

    def test_unknown_unit(self):
        assert normalize_unit(1.0, "ng") is None


class TestExtraction:
    def test_cite_and_verify_span(self):
        page = extract_page(0, "Total THC 18.2 %\nMyrcene 0.85 %", "generic_ommu", 3.0)
        assert page.cannabinoids["thc_total"].value == 18.2
        assert "18.2" in page.cannabinoids["thc_total"].source_span
        assert page.terpenes["myrcene"].value == pytest.approx(0.85)

    def test_negative_value_unreadable(self):
        page = extract_page(0, "Total THC -3.5 %", "generic_ommu", 3.0)
        # The numeric pattern never captures a leading minus; a value that
        # fails non-negativity is recorded unreadable, never clamped.
        thc = page.cannabinoids.get("thc_total")
        assert thc is None or thc.status in {"verified", "unreadable"}

    def test_nd_is_verified_zero(self):
        page = extract_page(0, "Linalool ND", "generic_ommu", 3.0)
        lin = page.terpenes["linalool"]
        assert lin.status == "verified" and lin.value == 0.0
        assert "ND" in lin.source_span

    def test_no_match_no_field(self):
        page = extract_page(0, "nothing relevant here", "generic_ommu", 3.0)
        assert not page.cannabinoids and not page.terpenes


class TestACSLaboratoryRows:
    """Real Florida ACS Laboratory (Trulieve) row shapes.

    Regression suite for the 2026-08-12 field failure: a real Patient COA
    yielded only "CBD 0% verified" because every row keeps its unit in the
    column header (mg/g and % columns, dilution/LOD/LOQ columns in between)
    and pdfplumber merges the right-hand summary column into potency rows.
    """

    POTENCY_HEADER = "Potency - 11 Tested\nAnalyte Dilution LOD LOQ Result (%)\n(1:n) (%) (%) (mg/g)"

    def test_terpene_row_with_leading_mgg_column(self):
        page = extract_page(0, "beta-Myrcene 6.108 0.611%", "generic_ommu", 3.0)
        myr = page.terpenes["myrcene"]
        assert myr.status == "verified" and myr.value == pytest.approx(0.611)
        assert myr.original_unit == "%"

    def test_alpha_pinene_never_matches_inside_beta_pinene(self):
        text = "beta-Pinene 1.263 0.126%\nalpha-Pinene 0.961 0.096%"
        page = extract_page(0, text, "generic_ommu", 3.0)
        assert page.terpenes["beta_pinene"].value == pytest.approx(0.126)
        assert page.terpenes["alpha_pinene"].value == pytest.approx(0.096)

    def test_dual_column_cannabinoid_row_with_merged_prose_tail(self):
        # dilution, LOD, LOQ, mg/g, % — unit only in the header; the page's
        # right-hand column ("Total CBG Total CBN") merged into the line.
        page = extract_page(
            0,
            f"{self.POTENCY_HEADER}\nTHCA-A 15.000 3.20E-5 0.0015 307 30.7 Total CBG Total CBN",
            "generic_ommu",
            3.0,
        )
        thca = page.cannabinoids["thca"]
        assert thca.status == "verified" and thca.value == pytest.approx(30.7)
        assert "307 30.7" in thca.source_span
        assert "Total CBG" not in thca.source_span  # merged neighbor never cited

    def test_total_active_thc_with_merged_terpene_tail(self):
        page = extract_page(
            0,
            f"{self.POTENCY_HEADER}\nTotal Active THC 15.000 278 27.8 alpha-Bisabolol 1.445 0.144%",
            "generic_ommu",
            3.0,
        )
        assert page.cannabinoids["thc_total"].value == pytest.approx(27.8)
        assert page.terpenes["bisabolol"].value == pytest.approx(0.144)

    def test_dual_column_requires_ten_to_one_cross_check(self):
        # Two trailing numbers that do NOT verify at mg/g = 10 x % stay out.
        page = extract_page(
            0,
            f"{self.POTENCY_HEADER}\nTHCA-A 15.000 1.5 2.5",
            "generic_ommu",
            3.0,
        )
        assert "thca" not in page.cannabinoids

    def test_dual_column_requires_relevant_header(self):
        page = extract_page(0, "THCA-A 1 2 30 3", "generic_ommu", 3.0)
        assert "thca" not in page.cannabinoids

    def test_definitions_prose_never_extracts(self):
        text = "Total Active THC = THCA-A * 0.877 + Delta 9 THC, Total THCV = THCV"
        page = extract_page(0, text, "generic_ommu", 3.0)
        assert "thc_total" not in page.cannabinoids
        assert "thca" not in page.cannabinoids

    def test_loq_row_still_reads_as_verified_zero(self):
        page = extract_page(0, "CBD 15.000 5.40E-5 0.0015 <LOQ <LOQ", "generic_ommu", 3.0)
        cbd = page.cannabinoids["cbd"]
        assert cbd.status == "verified" and cbd.value == 0.0

    def test_inline_unit_grammar_unchanged(self):
        page = extract_page(0, "Total THC 24.1 %\nLinalool 0.30 mg/g", "generic_ommu", 3.0)
        assert page.cannabinoids["thc_total"].value == pytest.approx(24.1)
        assert page.terpenes["linalool"].value == pytest.approx(0.03)


class TestModernCannaRows:
    """Real Florida Modern Canna row shapes (Trulieve's other lab).

    Cannabinoids print as ``THCa 26.9 941.5`` (% then total mg for a 3.5 g
    package). Terpenes print as ``beta-Caryophyllene 0.491`` — ONE bare
    number whose unit exists only in the ``Analyte %`` column header.
    """

    HEADER = "POTENCY SUMMARY  TERPENES SUMMARY (Top Ten)\nAnalyte % mg Analyte %"

    def test_reversed_dual_column_order(self):
        page = extract_page(0, f"{self.HEADER}\nTHCa 26.9 269", "generic_ommu", 3.0)
        thca = page.cannabinoids["thca"]
        assert thca.status == "verified" and thca.value == pytest.approx(26.9)

    def test_total_mg_column_does_not_assume_one_gram_package(self):
        # For a 3.5 g package, total mg is 35x the reported percent.  The
        # explicit header makes the first value authoritative.
        page = extract_page(0, f"{self.HEADER}\nTHCa 26.9 941.5", "generic_ommu", 3.0)
        assert page.cannabinoids["thca"].value == pytest.approx(26.9)

    def test_single_number_terpene_reads_under_pct_header(self):
        text = f"{self.HEADER}\nbeta-Caryophyllene 0.491\ntrans-Nerolidol 0.0916"
        page = extract_page(0, text, "generic_ommu", 3.0)
        assert page.terpenes["beta_caryophyllene"].value == pytest.approx(0.491)
        assert page.terpenes["nerolidol"].value == pytest.approx(0.0916)
        assert "%" in (page.terpenes["nerolidol"].original_unit or "")

    def test_single_number_terpene_refused_without_header(self):
        page = extract_page(0, "beta-Caryophyllene 0.491", "generic_ommu", 3.0)
        assert "beta_caryophyllene" not in page.terpenes

    def test_unrelated_percent_header_never_lends_unit(self):
        text = "Analyte %\nMethods section\nLinalool 0.4"
        page = extract_page(0, text, "generic_ommu", 3.0)
        assert "linalool" not in page.terpenes

    def test_single_number_rule_never_reads_cannabinoids(self):
        # A lone bare number after a cannabinoid name stays unread even under
        # a % header (cannabinoid tables carry the 10:1 pair; a single number
        # there is a column fragment, not a verifiable value).
        page = extract_page(0, f"{self.HEADER}\nTHCa 26.9", "generic_ommu", 3.0)
        assert "thca" not in page.cannabinoids

    def test_single_number_above_terpene_ceiling_refused(self):
        page = extract_page(0, f"{self.HEADER}\nLinalool 22.5", "generic_ommu", 3.0)
        assert "linalool" not in page.terpenes

    def test_new_modern_canna_terpenes(self):
        text = f"{self.HEADER}\nFenchyl Alcohol 0.0717\nalpha-Terpineol 0.0659"
        page = extract_page(0, text, "generic_ommu", 3.0)
        assert page.terpenes["fenchyl_alcohol"].value == pytest.approx(0.0717)
        assert page.terpenes["alpha_terpineol"].value == pytest.approx(0.0659)


class TestReportedTerpeneDenominator:
    def test_exact_acs_header_counts_unknown_result_rows(self):
        text = """\
Certificate of Analysis
Cannabinoid Profile
Total THC 18.0 %
Total CBD 0.5 %
Terpenes Summary
Analyte Result (mg/g) (%)
beta-Myrcene 5.00 0.50%
(R)-(+)-Limonene 4.00 0.40%
Linalool 2.00 0.20%
Guaiol 1.00 0.10%
Borneol 0.80 0.08%
Sabinene 0.60 0.06%
Isopulegol 0.40 0.04%
Methods
Carrier Gas 1.00 0.10%
"""
        chemistry = extract_chemistry([text])

        assert chemistry.total_reported_terpenes == 7
        assert len(chemistry.terpenes) == 3

        from coa_profiler.scorer.placement import apply_sufficiency_gate

        assert apply_sufficiency_gate(chemistry) == "degraded"  # 3/7 < 60%

    def test_unknown_result_rows_reduce_completeness_without_counting_methods(self):
        text = """\
Certificate of Analysis
Cannabinoid Profile
Total THC 18.0 %
Total CBD 0.5 %
Terpene Profile
Analyte Result (%)
Myrcene 0.50
Limonene 0.40
Linalool 0.20
Guaiol 0.10
Borneol 0.08
Sabinene 0.06
Isopulegol 0.04
Methods
Carrier Gas 1.00
Limonene retention time 4.20 min
"""
        chemistry = extract_chemistry([text])

        assert chemistry.total_reported_terpenes == 7
        assert len(chemistry.terpenes) == 3

        from coa_profiler.scorer.placement import apply_sufficiency_gate, compute_confidence

        assert apply_sufficiency_gate(chemistry) == "degraded"  # 3/7 < 60%
        # Four reported-but-unreadable rows plus the fewer-than-five penalty.
        assert compute_confidence(chemistry, "full") == pytest.approx(0.40)

    def test_no_explicit_result_header_means_unknown_prose_is_not_a_denominator(self):
        text = "Terpene Profile\nMethods\nCarrier Gas 1.00 %\nUnknown Retention 2.00 %"
        assert count_reported_terpenes([text]) == 0


class TestDerivation:
    def test_thca_delta9_derivation(self):
        cann = {
            "thca": make_field("thca", 20.0),
            "delta9_thc": make_field("delta9_thc", 1.2),
        }
        derive_totals(cann)
        total = cann["thc_total"]
        assert total.derived is True
        assert total.value == pytest.approx(1.2 + 0.877 * 20.0)
        assert "0.877" in total.derivation_note

    def test_cbda_derivation(self):
        cann = {"cbda": make_field("cbda", 0.8), "cbd": make_field("cbd", 0.1)}
        derive_totals(cann)
        assert cann["cbd_total"].derived is True
        assert cann["cbd_total"].value == pytest.approx(0.1 + 0.877 * 0.8)

    def test_no_derivation_when_total_present(self):
        cann = {
            "thc_total": make_field("thc_total", 18.2),
            "thca": make_field("thca", 20.0),
            "delta9_thc": make_field("delta9_thc", 1.2),
        }
        derive_totals(cann)
        assert cann["thc_total"].value == 18.2
        assert cann["thc_total"].derived is False


class TestConflictResolution:
    def test_document_format_page_wins(self):
        from coa_profiler.parser.fields import merge_pages

        p0 = extract_page(0, "Total THC 10.0 %", "generic_ommu", 1.0)
        p1 = extract_page(1, "Total THC 22.0 %", "confident_cannabis", 6.0)
        cann, _ = merge_pages([p0, p1], "confident_cannabis")
        assert cann["thc_total"].value == 22.0
        assert cann["thc_total"].conflicting_value is True
        assert "10.0" in cann["thc_total"].conflict_span


class TestPlausibility:
    def test_flags(self):
        chem = make_chemistry({"thc_total": (45.0, "%"), "cbd_total": (0.5, "%")}, {"myrcene": (0.5, "%")})
        apply_plausibility(chem)
        assert chem.cannabinoids["thc_total"].plausibility_flag is True
        assert chem.cannabinoids["cbd_total"].plausibility_flag is False
        assert chem.terpenes["myrcene"].plausibility_flag is False

    def test_forced_refusal_after_generic_retry(self):
        # Every value implausible (>50% rule): generic re-extract still bad
        # -> forced refusal with the inconsistency explanation.
        pages = [
            (
                "Certificate of Analysis\nCannabinoid Profile\n"
                "Total THC 90 %\nTotal CBD 80 %\nMyrcene 55 %\nLimonene 60 %"
            )
        ]
        chem = extract_chemistry(pages)
        assert chem.forced_refusal_reason is not None
        assert "inconsistent" in chem.forced_refusal_reason

    def test_plausible_outlier_still_scores(self):
        chem = make_chemistry(
            {"thc_total": (41.0, "%"), "cbd_total": (0.5, "%")},
            {"myrcene": (0.5, "%"), "limonene": (0.4, "%"), "linalool": (0.2, "%")},
        )
        apply_plausibility(chem)
        assert implausible_fraction(chem) <= 0.5
