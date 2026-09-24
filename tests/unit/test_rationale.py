"""FR-008 rationale: top compounds named with as-reported values; lint clean."""

from coa_profiler.lexicon import is_clean
from coa_profiler.scorer import score
from coa_profiler.scorer.rationale import build_rationale
from tests.conftest import make_chemistry


def _chem():
    return make_chemistry(
        {"thc_total": (18.2, "%"), "cbd_total": (0.5, "%")},
        {
            "myrcene": (0.85, "%"),
            "limonene": (0.42, "%"),
            "linalool": (0.21, "%"),
            "beta_caryophyllene": (0.66, "%"),
            "bisabolol": (0.2, "%"),
        },
        total_reported_terpenes=5,
    )


def test_top_compounds_named_with_values():
    chem = _chem()
    result = score(chem)
    text = " ".join(result.rationale)
    assert "Myrcene" in text and "0.85%" in text
    assert "indica-leaning" in text
    # beta-Caryophyllene: monitored, named, never scored (DIS-14).
    assert "β-Caryophyllene" in text
    assert "not directionally scored" in text
    # Unscored-but-present terpenes are listed (FR-007 note).
    assert "Bisabolol" in text
    assert "not included in the current model" in text


def test_rationale_is_lint_clean():
    for sentence in score(_chem()).rationale:
        assert is_clean(sentence)


def test_refusal_has_no_rationale():
    chem = make_chemistry({"thc_total": (19.0, "%"), "cbd_total": (0.3, "%")}, {})
    result = score(chem)
    assert result.completeness == "refusal"
    assert build_rationale(chem, result.driving_compounds, "refusal") == []


def test_mg_g_unit_shown_as_reported():
    chem = make_chemistry(
        {"thc_total": (182.0, "mg/g")},
        {"myrcene": (8.5, "mg/g"), "limonene": (4.2, "mg/g"), "linalool": (2.1, "mg/g")},
        total_reported_terpenes=3,
    )
    result = score(chem)
    text = " ".join(result.rationale)
    assert "8.5 mg/g" in text and "0.85%" in text  # original + normalized both shown
