# Examples

Five runnable examples covering the most common uses of the COA Effect-Spectrum
Profiler. Run all commands from the repository root. Examples 1–3 and 5 need no
server; example 4 drives a running server over HTTP.

Each script was executed against this tree during documentation and produced
the output shown below.

| # | Example | Demonstrates | Run |
|---|---|---|---|
| 1 | `01_parse_a_coa.py` | Cite-and-verify parsing of one COA file | `PYTHONPATH=src python3 docs/examples/01_parse_a_coa.py` |
| 2 | `02_score_and_explain.py` | Placement, uncertainty band, confidence, rationale | `PYTHONPATH=src python3 docs/examples/02_score_and_explain.py` |
| 3 | `03_render_pdf.py` | One-page PDF profile, byte-identical re-render | `PYTHONPATH=src python3 docs/examples/03_render_pdf.py` |
| 4 | `04_http_journey.sh` | Full web journey over HTTP with `curl` | `bash docs/examples/04_http_journey.sh` (server required) |
| 5 | `05_operator_clis.sh` | The three operator CLIs: batch, evaluate, copy-lint | `bash docs/examples/05_operator_clis.sh` |

## Prerequisites

- The package installed (`pip install -e ".[dev]"`) or `PYTHONPATH=src` on
  every command.
- System dependencies from [../OPERATIONS.md](../OPERATIONS.md#prerequisites)
  (Tesseract, poppler, libheif, OpenCV libraries). Examples 1–3 run without
  Tesseract when the fixture has a real text layer (the shipped PDFs do).

## Verified output (this tree)

Example 2 on `fixtures/fl_coa_sample.pdf`:

```text
completeness:  full
placement:     70/100 (indica-leaning)
uncertainty:   band 65–75 (±5)
confidence:    data 100% × model 75% = combined 75%
```

Example 2 on `fixtures/cannabinoids_only.pdf` (degraded path):

```text
completeness:  degraded
placement:     80/100 (strongly indica-leaning)
confidence:    data 50% × model 75% = combined 38%
```

Example 3: `wrote /tmp/example_profile.pdf (64842 bytes)` and
`byte-identical on re-render: True`.

Example 4 (against a local server): `/upload -> 303`, `Placement: 70 of 100`,
PDF downloaded, `/result after teardown -> 410 (expected 410)`,
`PASS: full upload-to-PDF journey over HTTP`.

Example 5: batch `4/4 succeeded (1 skipped) -> exit 0`; evaluation
`binned concordance: 100.0% (20/20)`, `spearman rank correlation: 1.000`,
`Concordance 100.0% meets the 80% gate.`; copy-lint
`clean (scope=templates+rationale)`.

## Fixtures you can point at

- `fixtures/fl_coa_sample.pdf` — full Confident Cannabis-style COA (score 70).
- `fixtures/cannabinoids_only.pdf` — no terpenes; degraded placement.
- `fixtures/no_chemistry.pdf` — certificate with no readable chemistry; refusal.
- `fixtures/not_a_coa.txt` — not a certificate; typed rejection.
- `fixtures/unreadable_coa.jpg` — blurred photo; typed rejection.
- `fixtures/formats/` — one COA per supported lab-format family.
- `fixtures/eval/` — 20 held-out COAs plus `labels.json` for the evaluation CLI.
- `fixtures/batch/` — four COAs plus one corrupt file for the batch CLI.

Regenerate the whole fixture set deterministically with
`PYTHONPATH=src python3 scripts/make_fixtures.py` (or `make fixtures`).
