"""Deterministic result JSON represents unavailable placement truthfully."""

import json

from coa_profiler.result_data import build_result_json, field_rows
from coa_profiler.scorer import score
from tests.conftest import make_chemistry


def test_refusal_serializes_placement_metrics_as_null():
    chemistry = make_chemistry(
        {"thc_total": (19.0, "%"), "cbd_total": (0.3, "%")},
        {},
        total_reported_terpenes=0,
    )
    placement = score(chemistry)

    payload = json.loads(
        build_result_json(
            placement,
            field_rows(chemistry, placement),
            version="v-test",
            weights_hash="abc123",
        )
    )

    assert placement.completeness == "refusal"
    assert {payload[key] for key in ("score", "label", "band_low", "band_high")} == {None}
    assert set(payload["scoring_steps"].values()) == {None}
    assert payload["confidence"]["model_confidence_pct"] == 75
    assert payload["rationale"] == placement.rationale
