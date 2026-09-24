#!/usr/bin/env python3
"""Example 3 — render the one-page PDF profile for a COA, offline.

Uses ``render_profile_pdf`` (src/coa_profiler/pdf/render.py) — the same
renderer behind GET /result/profile.pdf and the batch CLI. Invariant mode is
on: no timestamp is embedded, so identical inputs produce byte-identical PDFs
(FR-022). ``customer_name``/``branding_logo`` are for the operator batch CLI;
leave them out for the public-tool layout.

Run from the repository root:

    PYTHONPATH=src python3 docs/examples/03_render_pdf.py
    # writes /tmp/example_profile.pdf and prints its SHA-256
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from coa_profiler.parser import parse_coa
from coa_profiler.pdf import render_profile_pdf
from coa_profiler.scorer import score
from coa_profiler.scorer.weights import weights_file_hash

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO_ROOT / "fixtures" / "fl_coa_sample.pdf"
OUT_PATH = Path("/tmp/example_profile.pdf")


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FIXTURE
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2

    chemistry = parse_coa(path)
    placement = score(chemistry)
    pdf_bytes = render_profile_pdf(
        chemistry, placement, version="example", weights_hash=weights_file_hash(),
    )
    OUT_PATH.write_bytes(pdf_bytes)
    print(f"wrote {OUT_PATH} ({len(pdf_bytes)} bytes)")
    print(f"sha256: {hashlib.sha256(pdf_bytes).hexdigest()}")
    # Re-render and prove determinism (FR-022).
    again = render_profile_pdf(
        chemistry, placement, version="example", weights_hash=weights_file_hash(),
    )
    print(f"byte-identical on re-render: {again == pdf_bytes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
