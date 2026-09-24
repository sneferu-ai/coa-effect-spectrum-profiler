# API reference — COA Effect-Spectrum Profiler

The public interface has three tiers, all documented here:

1. **HTTP routes** — the server-rendered web app (`src/coa_profiler/web/routes.py`).
2. **Python library API** — the deterministic core (`parser`, `scorer`, `pdf`).
3. **Operator CLIs and scripts** — offline tools (`batch`, `evaluate`,
   `copylint`, `smoke_test.py`, `run_walkaway_gates.sh`).

Everything below is grounded in the shipped source; no route or command is
invented, and none is omitted.

---

## 1. HTTP API

### Base URL and protocol shape

- Local development: `http://localhost:8080`
- Server-rendered HTML (Jinja2); the only JSON bodies are `/healthz`,
  `/readyz`, and the `/feedback` error replies. There is no REST JSON API for
  the analysis itself — results are pages and a PDF, with a machine-readable
  JSON copy embedded in the results page (`<script type="application/json"
  id="result-data">`, spec §15.6) and downloadable client-side.
- **Same-origin only: no CORS headers are emitted.** Cross-origin API
  consumption is not supported.
- **Authentication: none.** The product is accountless by contract. Requests
  to `/login`, `/register`, `/checkout`, `/admin`, `/accounts*`, `/billing*`
  return 404 by absence — enforced by build-time gates and acceptance probes.

### Sessions

`POST /upload` mints a 128-bit token (`secrets.token_hex(16)`) and returns it
as the `session` cookie: `HttpOnly`, `SameSite=Strict`, `Secure` by default
(`SESSION_COOKIE_SECURE=false` for HTTP development), `Max-Age` equal to the
TTL (`SESSION_TTL_SECONDS`, default 300). Session state is in-memory; expired
sessions answer **410 Gone**. `/result` and `/result/profile.pdf` require the
cookie; everything else is public.

### Rate limits

| Bucket | Limit (default) | Response on breach |
|---|---|---|
| `POST /upload` | `RATE_LIMIT_PER_MINUTE` = 20/min per IP | HTTP 429 + `Retry-After` |
| `POST /feedback` | `FEEDBACK_RATE_LIMIT_PER_MINUTE` = 10/min per IP | HTTP 429 JSON + `Retry-After` |

Per-IP sliding-window, in-memory (resets on restart). Behind a proxy, set
`TRUSTED_PROXY_HEADER=X-Forwarded-For` so the limiter sees the real client IP.

### Route reference

#### `GET /` — landing / upload page

Renders `upload.html`: the drop zone (accepts `.pdf,.jpg,.jpeg,.png,.heic` —
HEIC only when the decoder is ready), the privacy commitment, a "What is a
Certificate of Analysis?" explainer, and the batch-inquiry `mailto:` link.

- **Parameters:** none.
- **Response:** `200 text/html`.
- **Example:** `curl -s http://localhost:8080/ | head -5`

#### `POST /upload` — analyze a certificate

The core action. Body is `multipart/form-data` with one field, `file`.

Processing: rate-limit → size cap (`MAX_UPLOAD_MB`, default 15) → magic-byte
sniff (extension is never trusted) → metadata strip → thread-pool pipeline
(parse → score) → session minted → redirect.

- **Success:** `303 See Other` → `/result`, sets the `session` cookie.
- **Recoverable input errors** (`422`, re-rendered inline on the upload page):
  `INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `HEIC_UNSUPPORTED`, `NOT_A_COA`,
  `UNREADABLE_DOCUMENT`, `NO_USABLE_CHEMISTRY`, `PROCESSING_TIMEOUT`,
  `METADATA_SCRUB_FAILED`.
- **Other errors:** `429 RATE_LIMITED` (with `Retry-After`),
  `503 SERVER_BUSY` when the processing pool is saturated (with
  `Retry-After: 30`), `500 INTERNAL_ERROR` as a sanitized catch-all page.
- **Example:**

  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" -c /tmp/cookies.txt \
    -F "file=@fixtures/fl_coa_sample.pdf" http://localhost:8080/upload
  # 303
  ```

#### `GET /result` — the results page

Requires the session cookie. Renders one of three templates by outcome:
`result.html` (full placement), `degraded.html` (cannabinoid-ratio placement
with the contested-predictor notice), `refusal.html` (no placement; chemotype
summary). The page carries the spectrum bar with uncertainty band, the
two-component confidence readout, the rationale, the chemistry table with
per-field status and source spans, the standing disclaimer, the PDF/JSON
download actions, and the 👍/👎 feedback widget.

- **Response:** `200 text/html`; **410** `SESSION_EXPIRED` page when the
  session is gone.
- **Example:** `curl -sf -b /tmp/cookies.txt http://localhost:8080/result`

#### `GET /result/profile.pdf` — the one-page PDF profile

Requires the session cookie. One US-Letter page (PDF 1.4, embedded fonts,
<500 KB), byte-identical for identical inputs (no timestamps). Headers:
`Content-Type: application/pdf`, `Content-Disposition: attachment;
filename="coa_profile.pdf"`.

- **Response:** `200 application/pdf`; with an expired session it **redirects
  303 to `/result`** (which shows the 410 page) — an HTML error page is never
  served at a `.pdf` URL.
- **Example:**
  `curl -sf -b /tmp/cookies.txt -o profile.pdf http://localhost:8080/result/profile.pdf`

#### `GET /new` — "Analyze another COA"

Tears down the session (deletes the record and the temp working directory),
deletes the cookie, and redirects `303` to `/`.

#### `POST /feedback` — anonymous helpfulness vote

The only JSON-in route. Called by the results-page feedback widget.

- **Auth:** requires the session cookie's presence (`403 {"error":"session
  cookie required"}` otherwise). Rate-limited: `429 {"error":"rate_limited"}`
  with a `Retry-After` header.
- **Body:**

  ```json
  {"helpful": true, "placement": 70, "completeness": "full", "lab_format": "confident_cannabis"}
  ```

  `helpful`: boolean. `placement`: integer 0–100. `completeness`: one of
  `full`, `degraded`, `refusal`. `lab_format`: string, max 50 chars.
  Schema violations (out-of-range placement, unknown completeness) get FastAPI
  validation `422`.
- **Response:** `204 No Content`. The aggregate is in-memory only (bucketed by
  completeness × lab format; no IP, token, or chemistry) and is logged at
  shutdown and every 100 responses.
- **Example:**

  ```bash
  curl -s -o /dev/null -w "%{http_code}\n" -b /tmp/cookies.txt \
    -H "Content-Type: application/json" \
    -d '{"helpful":true,"placement":70,"completeness":"full","lab_format":"confident_cannabis"}' \
    http://localhost:8080/feedback
  # 204
  ```

#### `GET /privacy` — privacy notice

`200 text/html`. States the zero-retention posture, session TTL, cookie
flags, and the configured IP-logging mode.

#### `GET /algorithm` — algorithm transparency page

`200 text/html`. Renders the complete weight table, normalization and scoring
formulas, confidence rule, degradation rules, weight-selection criteria, and
literature citations **from the live `scorer/weights.py` module**, plus the
weights-file SHA-256 and scorer version — the page cannot drift from the
code.

#### `GET /healthz` — liveness

`200 application/json`: `{"status":"ok","version":"dev-5a45478"}` (version is
the git tag at build time, or `dev-<short_hash>`; `COA_PROFILER_VERSION`
overrides).

#### `GET /readyz` — readiness

`200` when all checks pass, `503` otherwise:

```json
{"status":"ready","parser_ready":true,"ocr_ready":true,"heic_ready":true,"thread_pool_available":true}
```

- `parser_ready` — a PDF text engine importable (PyMuPDF or pdfplumber).
- `ocr_ready` — Tesseract answers `pytesseract.get_tesseract_version()`.
- `heic_ready` — decoder probe; reported `true` when `HEIC_ENABLED=false`
  (HEIC not required).
- `thread_pool_available` — false when in-flight uploads equal
  `PROCESSING_THREAD_POOL_SIZE`.

### Error envelope

HTML routes render `error.html` with a title, plain-language message, recovery
action, and a stable `error_code` (table in
[USER_GUIDE.md](USER_GUIDE.md#common-errors-and-exactly-what-to-do)). No stack
traces or internal paths are ever served. The JSON-speaking error cases are
`/feedback` (`403`/`429` bodies above).

---

## 2. Python library API

Install with `pip install -e .` or run with `PYTHONPATH=src`. These are the
same entry points the web routes and CLIs call.

### `coa_profiler.parser`

```python
from coa_profiler.parser import parse_coa, sniff_file_type, COAChemistry, ParsedField

chemistry = parse_coa("fixtures/fl_coa_sample.pdf")   # path-like; optional config=
```

- `sniff_file_type(data: bytes) -> "pdf" | "jpeg" | "png" | "heic" | None` —
  magic-byte classification; extension is never consulted.
- `parse_coa(path, config=None) -> COAChemistry` — the full FR-001…FR-005,
  FR-028 pipeline. Raises typed `COAError` subclasses
  (`InvalidFileTypeError`, `NotACOAError`, `UnreadableDocumentError`, …) —
  never returns guessed values.
- `COAChemistry` — `cannabinoids`/`terpenes` dicts of `ParsedField`, plus
  `lab_format`, `total_reported_terpenes`, `ocr_mean_confidence`.
- `ParsedField` — `value` (normalized % w/w; `None` when unreadable),
  `original_value`/`original_unit` (as printed), `status`
  (`verified`/`unreadable`), `source_span` (the literal text the value was
  verified against), `derived`, `plausibility_flag`.

### `coa_profiler.scorer`

```python
from coa_profiler.scorer import score

placement = score(chemistry)   # -> PlacementResult
```

`PlacementResult`: `score` (0–100, multiple of 5; `-1` on refusal),
`raw_score`, `confidence_data`/`confidence_model`/`confidence_combined`
(0–1), `completeness` (`full`/`degraded`/`refusal`), `rationale` (list of
sentences), `band_low`/`band_high`, `label`, `refusal_reason`. The sufficiency
gate can raise `NoUsableChemistryError` (zero readable chemistry). Pure
functions: no I/O, no clocks, no randomness.

### `coa_profiler.pdf`

```python
from coa_profiler.pdf import render_profile_pdf
from coa_profiler.scorer.weights import weights_file_hash

pdf_bytes = render_profile_pdf(
    chemistry, placement,
    version="v0.1.0", weights_hash=weights_file_hash(),
    customer_name=None, branding_logo=None,   # batch-CLI branding only
)
```

Returns PDF bytes (US-Letter, PDF 1.4, embedded fonts, <500 KB, invariant
mode — byte-identical for identical inputs).

Runnable forms of all three calls are in [examples/](examples/README.md).

---

## 3. Operator CLIs and scripts

All CLIs are offline and local-only. Exit codes are part of the contract.

### `python -m coa_profiler.batch` — batch profile packs (FR-017)

```bash
python -m coa_profiler.batch --input-dir <dir> --output-dir <dir> \
    --customer "<name>" [--branding-logo <path>] [--skip-invalid]
```

Processes every file in `--input-dir` through the identical
parse → score → PDF pipeline. Writes one branded PDF per COA
(`<stem>.pdf`), a one-page `reference_sheet.pdf` (entries sorted
alphabetically by filename), `failures.log`, and `batch_profiles.zip`
(fixed entry timestamps — byte-deterministic). Degraded and refusal outcomes
count as successes (the pipeline ran). Exit codes: **0** when ≥80% of
attempted COAs succeed, **1** below 80%, **2** when none succeed.
`--skip-invalid` converts unreadable/non-COA inputs into `SKIP` lines instead
of failures.

### `python -m coa_profiler.evaluate` — held-out evaluation (FR-018)

```bash
python -m coa_profiler.evaluate --fixtures fixtures/eval/ \
    --labels fixtures/eval/labels.json --report /tmp/eval.json [--gate]
```

Runs the real parser + scorer over the fixture set and writes a freshly
computed JSON report: per-format field accuracy (against
`expected_results.json` when present), document-level accuracy, placement
range/std-dev, a determinism check, and — with `--labels` — binned directional
concordance (DIS-10 bins), Spearman rank correlation, the
outperform-the-labels comparison, and the inter-rater inconsistency warning.
`--gate` exits **1** below 80% concordance with `Concordance below threshold:
release blocked.` plus the printed 3-bin fallback recommendation (advisory;
the CLI never halts a pipeline). Verified here: 100% (20/20), Spearman 1.000,
exit 0.

### `python -m coa_profiler.copylint` — banned-lexicon scan (FR-019)

```bash
python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ [--fixtures fixtures/]
```

Boot scope (`--templates` only) scans static templates — the app runs this at
startup, fatal unless `COPYLINT_SOFT_FAIL=true`. CI scope (`--fixtures`) adds
the generated rationale of every parseable fixture and prints the loud
`scanned/len(paths)` accounting line. Exit **0** when clean, **1** on any hit.
Each hit prints `BANNED TERM '<term>' in <location>: …context…`.

### `scripts/smoke_test.py` — journey smoke against a running server

```bash
python scripts/smoke_test.py --fixture <path> --base-url <url> \
    --check full|degraded|refusal|reject
```

Uploads the fixture with a cookie jar, follows the 303, fetches `/result` and
`/result/profile.pdf`, and validates by mode. Prints `PASS: <check>,
score=<int|n/a>` / `FAIL: <check>, reason=<message>`; exit 0/1. Side effects:
PDF saved to `/tmp/smoke_profile.pdf`, Netscape cookie jar at
`/tmp/smoke_cookies`.

### `scripts/run_walkaway_gates.sh` — the six B0 release gates

```bash
./scripts/run_walkaway_gates.sh
```

One `PASS`/`FAIL` line per gate: (1) no payment/auth code (grep + AST),
including a temp-copy **negative-injection proof**; (2) no outbound HTTP calls
outside `parser/inference_assist.py` and inference-assist disabled by default;
(3) scorer free of dataset references; (4) copy-lint clean in CI scope;
(5) live smoke `full` + evaluation gate contract + algorithm citations;
(6) zero cloud-SDK imports. Exit **0** only if all six pass.

### `scripts/make_fixtures.py` — regenerate the test fixtures

```bash
PYTHONPATH=src python3 scripts/make_fixtures.py   # or: make fixtures
```

Regenerates all 44 fixtures deterministically (invariant ReportLab) and
computes the expected scores/labels with the real scorer.
