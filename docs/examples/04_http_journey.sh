#!/usr/bin/env bash
# Example 4 — drive the full web journey over HTTP with curl.
#
# Prerequisite: a server running locally with HTTP-friendly settings:
#
#     SESSION_COOKIE_SECURE=false HEIC_ENABLED=false \
#       uvicorn coa_profiler.app:app --port 8080
#
# Then, from the repository root:
#
#     bash docs/examples/04_http_journey.sh
#
# What it does: upload a fixture COA, follow the 303 redirect with the session
# cookie, check the results page, and download the PDF profile.
set -euo pipefail
cd "$(dirname "$0")/../.."

BASE_URL="${BASE_URL:-http://localhost:8080}"
JAR=/tmp/example_cookies.txt
OUT=/tmp/example_profile.pdf

echo "1. readiness probe"
curl -sf "$BASE_URL/readyz" && echo

echo "2. upload fixtures/fl_coa_sample.pdf (expect HTTP 303)"
code=$(curl -s -o /dev/null -w "%{http_code}" -c "$JAR" \
  -F "file=@fixtures/fl_coa_sample.pdf" "$BASE_URL/upload")
echo "   /upload -> $code"
[ "$code" = "303" ] || { echo "FAIL: expected 303, got $code"; exit 1; }

echo "3. fetch /result with the session cookie (expect 200 + placement line)"
curl -sf -b "$JAR" "$BASE_URL/result" | grep -oE "Placement: [0-9]+ of 100" | head -1

echo "4. download the PDF profile"
curl -sf -b "$JAR" -o "$OUT" "$BASE_URL/result/profile.pdf"
ls -l "$OUT"

echo "5. end the session ('Analyze another COA') and confirm /result is gone"
curl -s -o /dev/null -b "$JAR" -c "$JAR" "$BASE_URL/new"
code=$(curl -s -o /dev/null -w "%{http_code}" -b "$JAR" "$BASE_URL/result")
echo "   /result after teardown -> $code (expected 410)"
[ "$code" = "410" ] || { echo "FAIL: expected 410, got $code"; exit 1; }

echo "PASS: full upload-to-PDF journey over HTTP"
