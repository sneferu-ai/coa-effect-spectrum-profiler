# COA Effect-Spectrum Profiler — self-hosting and operator guide

A free, no-account web tool that reads a Florida medical-cannabis Certificate
of Analysis (COA) — PDF or phone photo — and places its measured chemistry on
a sativa↔indica tendency spectrum, with a plain-language rationale and a
one-page PDF profile.

The placement is a **chemistry-derived tendency, not an effect prediction**:
a deterministic mapping from measured cannabinoids and terpenes to a familiar
scale, computed from the document alone. Individual responses depend on dose,
tolerance, and individual biology — factors beyond COA chemistry. See
[algorithm.md](algorithm.md) for the full scoring function, weight
table, and citations.

## Quick start

Prerequisites: Python 3.11+, Tesseract OCR 5.3.x, poppler-utils, libheif, and
OpenCV system libraries (`libgl1`, `libglib2.0-0`). See section 7 of the
product contract for the full list.

```bash
python -m venv .venv && source .venv/bin/activate
pip install --constraint constraints-runtime.txt -e ".[dev]"
cp .env.example .env
# For HTTP development only: set SESSION_COOKIE_SECURE=false in .env
# HEIC needs pillow-heif + libheif; without them, set HEIC_ENABLED=false
uvicorn coa_profiler.app:app --reload --port 8080
```

- **Open:** http://localhost:8080/ — the upload page. The full journey is
  upload → result → PDF/JSON download → "Analyze another COA" (session
  teardown). No credentials exist or are needed — the product is accountless.
- **Logs/errors:** the app writes startup gates (copy-lint, HEIC decoder,
  `INFERENCE_ASSIST_ACTIVE`) and privacy-filtered application access events
  to stdout. The documented launch commands disable Uvicorn's separate raw-IP
  access log.
- **Stop:** Ctrl+C, or `docker compose down` for the containerized run.
- **Test:** `pytest` (full suite),
  `python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/`
  (copy lint),
  `REAL_COA_FIXTURES_DIR=/private/path REAL_COA_LABELS=/private/labels.json ./scripts/run_walkaway_gates.sh`
  (all six release gates, including independent held-out evidence),
  `python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf --base-url http://localhost:8080 --check full`
  (journey smoke against the running server).

## Hosted preview (Sneferu launcher)

When the product is opened through Sneferu's accepted-product launcher, the
launch wrapper authenticates the operator at the edge (access cookie plus an
injected `Authorization` header) and plants a versioned handoff record at
`localStorage["sneferu.preview.bootstrap.v1"]` before redirecting to `/`.
`src/coa_profiler/web/static/preview-bootstrap.js` — loaded on every page —
reads, validates, and removes that one-time record (`schema ===
"sneferu.preview.bootstrap/v1"`),
ignores any credential fields (authentication stays at the launcher edge),
and stamps `data-preview-session="authenticated"` on `<html>` so
the hosted browser journey can assert the handoff. Direct runs carry no
record and behave identically: no account, no added UI, no extra requests.

## What it does

1. **Upload** a Florida COA (PDF, JPEG, PNG, or HEIC, ≤ 15 MB). EXIF/document
   metadata is stripped in an owner-only temporary directory; the original is
   removed immediately and the working copy is deleted with the session.
   Configurable page, dimension, and decoded-pixel limits bound OCR memory.
2. **Cite-and-verify extraction** of cannabinoid and terpene values with unit
   normalization (`%`, `mg/g`, `mg/mL`, `ppm`), THCA/CBDA total derivation,
   and plausibility flags. Anything unreadable is flagged — never estimated.
3. **Placement** on a 0–100 spectrum (multiples of 5) with an uncertainty
   band and a two-component confidence readout.
4. **PDF profile** — one page, byte-identical for identical inputs.
5. **Privacy**: no accounts, no durable storage, sessions expire in 5
   minutes, the only cookie is the functional session cookie.

Public surfaces: `/` (upload), `/result`, `/result/profile.pdf`, `/privacy`,
`/algorithm`, `/healthz`, `/readyz`, `/feedback`.

## Operator tools (offline)

```bash
# Batch profile packs (FR-017)
python -m coa_profiler.batch --input-dir <dir> --output-dir <dir> --customer "<name>" [--skip-invalid]

# Synthetic self-consistency report (mechanics only; never release evidence)
python -m coa_profiler.evaluate --fixtures fixtures/eval/ --labels fixtures/eval/labels.json \
    --report /tmp/eval-synthetic.json

# Held-out evaluation with the 80% concordance release gate (FR-018, DIS-10)
python -m coa_profiler.evaluate --fixtures /private/deidentified-real-coas \
    --labels /private/independent-labels.json --report /tmp/eval.json --gate

# Banned-lexicon copy lint (FR-019; boot scope = templates only, CI scope adds fixtures)
python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/

# B0 walk-away gates (real evaluation inputs stay outside the repository)
REAL_COA_FIXTURES_DIR=/private/deidentified-real-coas \
REAL_COA_LABELS=/private/independent-labels.json \
./scripts/run_walkaway_gates.sh

# Smoke test against a running server
python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf --base-url http://localhost:8080 --check full
```

## Tests

```bash
pytest                    # full suite
pytest tests/unit -q      # unit only
pytest tests/integration  # needs Tesseract for the OCR-path tests
```

## Deployment

Self-hosted, single gunicorn worker behind Nginx (see section 8 of the
contract). `Dockerfile` and `docker-compose.yml` are included.

The Compose topology publishes the application only on
`127.0.0.1:8080`. It sets Gunicorn's `FORWARDED_ALLOW_IPS=*` so Nginx is
trusted even when its Docker-bridge source address varies by platform. That
trust boundary is safe only while the application port remains loopback-only.
If the backend is reachable on another interface or shared network, replace
`*` with the exact proxy IP/CIDR before starting it. A bare `make prod` keeps
Gunicorn's loopback-only proxy default and also binds only to localhost.

Nginx must reject unknown hosts and overwrite (not append) all client-supplied
forwarding headers. This minimal location is the expected contract for the
default 15 MiB upload limit (raise `client_max_body_size` alongside
`MAX_UPLOAD_MB`, leaving room for multipart framing):

```nginx
server {
    listen 443 ssl;
    server_name coa-profiler.example;
    # The application emits the configured privacy-safe access log; never
    # duplicate raw client IPs in the edge proxy's default combined log.
    access_log off;
    client_max_body_size 16m;
    client_body_buffer_size 16m;
    client_body_timeout 15s;

    # Defense in depth for the tiny JSON feedback schema. The application
    # independently enforces the same cap before JSON/Pydantic parsing.
    location = /feedback {
        client_max_body_size 4k;
        proxy_read_timeout 115s;
        proxy_request_buffering on;
        proxy_set_header Host $server_name;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_pass http://127.0.0.1:8080;
    }

    location / {
        # 110s application guard < 115s proxy read < 120s Gunicorn timeout.
        proxy_read_timeout 115s;
        proxy_request_buffering on;
        proxy_set_header Host $server_name;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_pass http://127.0.0.1:8080;
    }
}
```

`client_body_buffer_size` matches the accepted request envelope, so ordinary
COA bodies remain in the edge proxy's memory instead of spilling to its
default on-disk client-body directory. Also mount Nginx's process temporary
directory on a size-bounded, owner-only tmpfs (for example
`tmpfs /var/lib/nginx/body 256m,mode=0700,uid=<nginx-uid>,gid=<nginx-gid>` and
set `client_body_temp_path /var/lib/nginx/body 1 2;`) as a fail-safe for
framing overhead or future limit changes. A deployment that cannot provide
that tmpfs must disclose proxy-host temporary storage in its privacy notice.
Keep `access_log off` unless the proxy uses a separately audited privacy-safe
format that omits raw client IPs, cookies, authorization, and query strings;
the application's `LOG_IP_RETENTION` setting cannot sanitize an edge log.

`client_body_timeout` limits the idle gap between client-body reads rather
than the upload's total duration. With request buffering left on, Nginx first
finishes that size- and idle-bounded upload, then forwards it over loopback;
the default 60-second `proxy_send_timeout` therefore applies only between
writes of the buffered request to the local upstream, not to the subsequent
analysis wait. If request buffering is disabled or the upstream stops being
local, reassess both request-body timeouts together.

Configure a separate default server that rejects unmatched `Host` values.
Keep `TRUSTED_PROXY_HEADER` empty for this topology: Uvicorn derives
`request.client` after verifying the proxy peer. HSTS and secure-cookie
behavior then follow the overwritten `X-Forwarded-Proto: https` value.

Production installation uses `constraints-runtime.txt`. It pins audited
direct runtime dependencies without freezing platform-specific transitive
wheels; refresh it deliberately after dependency and advisory review.

Compose refuses to configure or build until `COA_PROFILER_VERSION` is set to a
release-unique immutable identifier (tag plus commit is recommended), for
example `0.1.0+git.abc1234`. The same value is baked into the image and passed
at runtime, so result provenance and immutable static cache URLs cannot drift.
For a direct build, pass the required value explicitly:
`docker build --build-arg COA_PROFILER_VERSION=0.1.0+git.abc1234 .`.

The labels JSON for a qualifying evaluation contains at least 20 comparable
`ratings` plus this top-level provenance block:

```json
{
  "provenance": {
    "kind": "independent-real-coa",
    "labels_created_without_tool_output": true,
    "documents_are_deidentified": true,
    "rater": "operator name or independent rater role"
  },
  "ratings": []
}
```

Generated fixtures are deliberately marked `synthetic-self-consistency`, so
the release gate refuses them even when they agree perfectly with the scorer.
