"""AC-023 code-side checks: the weight table is the real one used by the scorer."""

import hashlib
import re
from pathlib import Path

from coa_profiler.scorer.weights import (
    CITATIONS,
    MODEL_CONFIDENCE,
    WEIGHTS,
    active_weights,
    monitored_compounds,
    weights_file_hash,
)


def test_authoritative_values():
    assert WEIGHTS["myrcene"]["weight"] == 2.5
    assert WEIGHTS["myrcene"]["direction"] == "indica"
    assert WEIGHTS["limonene"]["weight"] == 2.0
    assert WEIGHTS["beta_caryophyllene"]["weight"] == 0.0
    assert WEIGHTS["beta_caryophyllene"]["direction"] == "neutral"
    assert WEIGHTS["thc_total"]["weight"] == 0.5
    assert WEIGHTS["cbd_total"]["direction"] == "sativa"


def test_monitored_partition():
    assert "beta_caryophyllene" in monitored_compounds()
    assert "beta_caryophyllene" not in active_weights()
    assert len(active_weights()) == len(WEIGHTS) - 1


def test_weights_hash_matches_file_bytes():
    path = Path(__import__("coa_profiler.scorer.weights", fromlist=["x"]).__file__)
    assert weights_file_hash() == hashlib.sha256(path.read_bytes()).hexdigest()


def test_citations_have_dois():
    dois = [c["doi"] for c in CITATIONS.values()]
    assert len(dois) >= 4
    for doi in dois:
        assert re.match(r"10\.\d{4,}/\S+", doi), doi


def test_model_confidence_is_documented_constant():
    assert MODEL_CONFIDENCE == 0.75
