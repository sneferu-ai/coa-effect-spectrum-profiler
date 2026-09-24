#!/usr/bin/env bash
# Example 5 — the three operator-only CLIs (offline; no server needed).
#
# Run from the repository root:
#
#     bash docs/examples/05_operator_clis.sh
#
# 1. batch:     one branded PDF per COA + reference sheet + ZIP (FR-017)
# 2. evaluate:  held-out concordance report + 80% release gate (FR-018)
# 3. copylint:  banned-lexicon scan of templates + generated rationale (FR-019)
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH=src
export OMP_THREAD_LIMIT=1
OUT=/tmp/example_batch

echo "=== 1. batch CLI over fixtures/batch/ (contains one corrupt file) ==="
python3 -m coa_profiler.batch --input-dir fixtures/batch --output-dir "$OUT" \
  --customer "Example Dispensary" --skip-invalid || true
ls "$OUT"

echo
echo "=== 2. evaluation CLI with the 80% concordance gate ==="
python3 -m coa_profiler.evaluate --fixtures fixtures/eval/ \
  --labels fixtures/eval/labels.json --report /tmp/example_eval.json --gate

echo
echo "=== 3. copy-lint over templates + fixture-generated rationale ==="
python3 -m coa_profiler.copylint \
  --templates src/coa_profiler/web/templates/ --fixtures fixtures/

echo
echo "PASS: all three operator CLIs ran"
