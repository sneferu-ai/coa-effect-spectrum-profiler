#!/usr/bin/env python3
"""Example 2 — parse a COA and compute its spectrum placement + rationale.

Uses the public ``score`` entry point (src/coa_profiler/scorer/__init__.py):
the same deterministic function the web app runs. No randomness, no clocks —
identical input always produces the identical placement (FR-022).

Run from the repository root:

    PYTHONPATH=src python3 docs/examples/02_score_and_explain.py
    PYTHONPATH=src python3 docs/examples/02_score_and_explain.py fixtures/cannabinoids_only.pdf
    PYTHONPATH=src python3 docs/examples/02_score_and_explain.py fixtures/no_chemistry.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

from coa_profiler.errors import COAError
from coa_profiler.parser import parse_coa
from coa_profiler.scorer import score

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "fl_coa_sample.pdf"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FIXTURE
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2

    try:
        chemistry = parse_coa(path)
        result = score(chemistry)
    except COAError as err:
        # Typed errors carry a stable code, e.g. NO_USABLE_CHEMISTRY.
        print(f"{err.error_code}: {err.user_message}")
        print(f"recovery: {err.recovery}")
        return 1

    print(f"file:          {path.name}")
    print(f"completeness:  {result.completeness}")
    if result.completeness == "refusal":
        print(f"refusal:       {result.refusal_reason}")
        return 0
    print(f"placement:     {result.score}/100 ({result.label})")
    print(f"uncertainty:   band {result.band_low}–{result.band_high} "
          f"(±{result.band_half_width})")
    print(f"confidence:    data {result.confidence_data:.0%} × "
          f"model {result.confidence_model:.0%} = "
          f"combined {result.confidence_combined:.0%}")
    print("rationale:")
    for sentence in result.rationale:
        print(f"  - {sentence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
