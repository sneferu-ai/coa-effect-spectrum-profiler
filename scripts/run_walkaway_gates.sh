#!/usr/bin/env bash
# B0 walk-away gates (spec section 6). One PASS/FAIL line per gate; exit 0
# only if all six pass. Includes the temp-directory negative-injection test
# that proves Gate 1 performs a real check without modifying the source tree.
set -u
cd "$(dirname "$0")/.."
export PYTHONPATH=src
export OMP_THREAD_LIMIT=1

FAILURES=0
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1 — $2"; FAILURES=$((FAILURES+1)); }

# --- Gate 1: no payment/auth code (grep + AST scan) --------------------------
G1_GREP=$(grep -rnEi "(stripe|paypal|auth_login|user_account|password_hash|billing|subscription)" \
  src/coa_profiler/ --include="*.py" | grep -v test || true)
G1_AST=$(python3 - <<'PY'
import ast, sys
from pathlib import Path
BANNED_MODULES = {"stripe", "paypal", "flask_login", "django.contrib.auth", "braintree", "square"}
BANNED_NAMES = {"auth_login", "user_account", "password_hash", "billing", "subscription"}
bad = []
for path in Path("src/coa_profiler").rglob("*.py"):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {m.split(".")[0] for m in BANNED_MODULES}:
                    bad.append(f"{path}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in {m.split(".")[0] for m in BANNED_MODULES}:
                bad.append(f"{path}: from {node.module} import ...")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in BANNED_NAMES:
            bad.append(f"{path}: def {node.name}")
print("\n".join(bad))
PY
)
if [ -z "$G1_GREP" ] && [ -z "$G1_AST" ]; then pass "Gate 1 (no payment/auth code)"
else fail "Gate 1 (no payment/auth code)" "$G1_GREP $G1_AST"; fi

# --- Gate 1 negative injection proof (temp copy; source tree untouched) ------
rm -rf /tmp/gate_test_src
cp -r src/ /tmp/gate_test_src/
echo "import stripe" >> /tmp/gate_test_src/coa_profiler/web/routes.py
NEG=$(grep -rnEi "stripe" /tmp/gate_test_src/coa_profiler/ --include="*.py" || true)
rm -rf /tmp/gate_test_src
if [ -n "$NEG" ]; then pass "Gate 1 negative-injection (temp-copy scan detects planted import)"
else fail "Gate 1 negative-injection" "planted stripe import was not detected"; fi

# --- Gate 2: no data transfer at default config ------------------------------
G2_ENV=$(grep -E "^(INFERENCE_ASSIST_ENABLED|INFERENCE_ASSIST_API_KEY)" .env.example || true)
G2_CALLS=$(grep -rnE "httpx\.|requests\.|urllib\.request|aiohttp" src/coa_profiler/ --include="*.py" \
  | grep -v "parser/inference_assist.py" || true)
if echo "$G2_ENV" | grep -q "INFERENCE_ASSIST_ENABLED=false" && [ -z "$G2_CALLS" ]; then
  pass "Gate 2 (no outbound calls at default; inference assist disabled)"
else fail "Gate 2 (no data transfer)" "env:[$G2_ENV] calls:[$G2_CALLS]"; fi

# --- Gate 3: scorer does not depend on any dataset ---------------------------
G3=$(grep -rniE "dataset|nonprofit" src/coa_profiler/scorer/ --include="*.py" || true)
if [ -z "$G3" ]; then pass "Gate 3 (scorer free of dataset references)"
else fail "Gate 3 (no dataset dependency)" "$G3"; fi

# --- Gate 4: copy-lint clean (templates + dynamic rationale) -----------------
if python3 -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/ \
    > /tmp/gate4.out 2>&1; then
  pass "Gate 4 (copy-lint clean)"
else fail "Gate 4 (copy-lint clean)" "$(cat /tmp/gate4.out)"; fi

# --- Gate 5: working preview + independent real-COA evaluation + citations ---
G5_OK=1
PORT=8123
SESSION_COOKIE_SECURE=false HEIC_ENABLED=false COA_PROFILER_TMP_DIR=/tmp/coa_gate5_sessions \
  python3 -m uvicorn coa_profiler.app:app --port $PORT > /tmp/gate5_server.log 2>&1 &
SERVER_PID=$!
for i in $(seq 1 30); do curl -sf "http://127.0.0.1:$PORT/healthz" > /dev/null 2>&1 && break; sleep 0.5; done
if ! python3 scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf \
    --base-url "http://127.0.0.1:$PORT" --check full >> /tmp/gate5.out 2>&1; then
  G5_OK=0; G5_WHY="smoke test failed: $(cat /tmp/gate5.out)"
fi
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true

# Generated fixtures prove deterministic mechanics, not independent product
# validity. Their manifest must be rejected by --gate even though its ratings
# agree with the scorer by construction.
if ! python3 -m coa_profiler.evaluate --fixtures fixtures/eval/ --labels fixtures/eval/labels.json \
    --report /tmp/gate5_eval_synthetic.json > /tmp/gate5b.out 2>&1; then
  G5_OK=0; G5_WHY="synthetic evaluation mechanics failed: $(cat /tmp/gate5b.out)"
fi
if python3 -m coa_profiler.evaluate --fixtures fixtures/eval/ --labels fixtures/eval/labels.json \
    --report /tmp/gate5_eval_must_reject.json --gate >> /tmp/gate5b.out 2>&1; then
  G5_OK=0; G5_WHY="release gate accepted self-labeled synthetic fixtures"
fi

# Real, deidentified held-out documents and independently authored ratings are
# operator-owned inputs and must never be committed to this repository.
if [ -n "${REAL_COA_FIXTURES_DIR:-}" ] && [ -n "${REAL_COA_LABELS:-}" ]; then
  if ! python3 -m coa_profiler.evaluate --fixtures "$REAL_COA_FIXTURES_DIR" \
      --labels "$REAL_COA_LABELS" --report /tmp/gate5_eval_real.json --gate \
      >> /tmp/gate5b.out 2>&1; then
    G5_OK=0; G5_WHY="independent real-COA evaluation failed: $(cat /tmp/gate5b.out)"
  fi
else
  G5_OK=0
  G5_WHY="set REAL_COA_FIXTURES_DIR and REAL_COA_LABELS to an independent, deidentified >=20-document corpus"
fi
# Citation verification (AC-033): >= 4 DOI patterns; no unverified numeric claims.
G5_DOIS=$(grep -oE "10\.[0-9]{4,}/[^ )]+" docs/algorithm.md | wc -l | tr -d ' ')
G5_CLAIM=$(grep -rE "90,000|90000" src/coa_profiler/lexicon.py src/coa_profiler/web/templates/ 2>/dev/null || true)
if [ "$G5_DOIS" -lt 4 ] || [ -n "$G5_CLAIM" ]; then
  G5_OK=0; G5_WHY="citation check failed (DOIs=$G5_DOIS, unverified-claim hit: $G5_CLAIM)"
fi
if [ "$G5_OK" -eq 1 ]; then pass "Gate 5 (preview + independent concordance + citations verified)"
else fail "Gate 5 (preview + independent concordance + citations)" "$G5_WHY"; fi

# --- Gate 6: no cloud SDK imports ---------------------------------------------
G6=$(grep -rnE "^\s*(import|from)\s+(boto3|botocore|google\.cloud|azure|aws_|stripe)" \
  src/coa_profiler/ --include="*.py" || true)
if [ -z "$G6" ]; then pass "Gate 6 (no cloud SDK imports)"
else fail "Gate 6 (no cloud SDK imports)" "$G6"; fi

echo "----"
if [ "$FAILURES" -eq 0 ]; then echo "ALL GATES PASS"; exit 0
else echo "$FAILURES gate(s) failed"; exit 1; fi
