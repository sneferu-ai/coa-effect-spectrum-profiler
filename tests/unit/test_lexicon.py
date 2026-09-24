"""FR-010 banned lexicon: detection, boundaries, clean standing copy."""

from coa_profiler.lexicon import (
    BANNED_TERMS,
    DEGRADED_NOTICE,
    STANDING_DISCLAIMER,
    find_banned,
    is_clean,
)


def test_every_banned_term_is_detected_verbatim():
    # AC-012 picks random.choice(BANNED_TERMS); every entry must be catchable.
    for term in BANNED_TERMS:
        hits = find_banned(f"Some template copy containing {term} mid-sentence.")
        assert hits, f"term {term!r} not detected"
        assert any(h.term == term for h in hits), term


def test_inflections_caught():
    assert find_banned("the best treatments available")
    assert find_banned("your symptoms")
    assert find_banned("the doses are listed")
    assert find_banned("dosages")


def test_word_boundaries_prevent_false_positives():
    assert is_clean("The conditional rendering of this component is documented.")
    assert is_clean("Data completeness and model confidence.")


def test_standing_copy_is_clean():
    assert is_clean(STANDING_DISCLAIMER)
    assert is_clean(DEGRADED_NOTICE)


def test_case_insensitive():
    assert find_banned("DOSE")
    assert find_banned("Therapy")
