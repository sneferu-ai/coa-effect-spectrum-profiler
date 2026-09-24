#!/usr/bin/env python3
"""Example 1 — parse one Certificate of Analysis and print what was extracted.

Uses the same ``parse_coa`` entry point the web upload route calls
(src/coa_profiler/parser/__init__.py). Every printed field traces to a
literal text span in the document; anything unverifiable is ``unreadable``.

Run from the repository root:

    PYTHONPATH=src python3 docs/examples/01_parse_a_coa.py
    PYTHONPATH=src python3 docs/examples/01_parse_a_coa.py fixtures/ppm_coa.pdf

Expected: the lab format, then one line per compound with its status.
"""

from __future__ import annotations

import sys
from pathlib import Path

from coa_profiler.parser import parse_coa

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "fl_coa_sample.pdf"


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FIXTURE
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2

    chemistry = parse_coa(path)
    print(f"file:            {path.name}")
    print(f"lab format:      {chemistry.lab_format}")
    if chemistry.ocr_mean_confidence is not None:
        print(f"OCR confidence:  {chemistry.ocr_mean_confidence:.1f} (0-100)")

    for category, table in (("cannabinoid", chemistry.cannabinoids),
                            ("terpene", chemistry.terpenes)):
        print(f"\n{category}s:")
        for name, f in sorted(table.items()):
            if f.status in ("verified", "derived") and f.value is not None:
                reported = (f"{f.original_value:g} {f.original_unit}"
                            if f.original_unit else f"{f.value:g}%")
                tag = " (derived)" if f.derived else ""
                flag = " [plausibility-flagged]" if f.plausibility_flag else ""
                print(f"  {name:<22} {reported:<14} -> {f.value:g}% w/w{tag}{flag}")
            else:
                reason = f" — {f.unreadable_reason}" if f.unreadable_reason else ""
                print(f"  {name:<22} unreadable{reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
