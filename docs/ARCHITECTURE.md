# Architecture — COA Effect-Spectrum Profiler

This document describes the system as it exists in `src/coa_profiler/`, not an
aspirational design. Every module named here exists and is linked.

## Project shape

One deployable unit with three faces:

1. **A server-rendered web application** (FastAPI + Jinja2, no frontend build
   step) — the public product.
2. **A Python library** (`parser`, `scorer`, `pdf`) — the deterministic core
   the web app and the CLIs share.
3. **Three operator-only CLIs** (`batch`, `evaluate`, `copylint`) plus two
   scripts (`scripts/smoke_test.py`, `scripts/run_walkaway_gates.sh`) — run
   offline, never exposed over HTTP.

There is **no database, no cache, no queue, no object store**. The only state
is in-memory (sessions, rate-limit counters, the feedback aggregate) and
short-lived per-session temp directories under `/tmp/coa_profiler_sessions/`.

## C4 Context

```mermaid
flowchart TD
    patient["Patient<br/>(Florida medical-cannabis patient<br/>with a Certificate of Analysis)"]
    operator["Operator<br/>(runs batch packs,<br/>evaluation, copy-lint)"]
    nginx["Nginx<br/>(TLS termination,<br/>X-Forwarded-For)"]
    app["COA Effect-Spectrum Profiler<br/>(FastAPI, single process)"]
    tesseract["Tesseract OCR 5.3.x<br/>(local binary, via pytesseract)"]
    inference["OpenAI-compatible endpoint<br/>(OPTIONAL, disabled by default —<br/>INFERENCE_ASSIST_ENABLED=false)"]

    patient -->|"HTTPS: upload COA, view result,<br/>download PDF"| nginx
    nginx -->|"plain HTTP to 127.0.0.1:8080"| app
    operator -->|"offline CLI runs on the same host"| app
    app -->|"subprocess: OCR of photos/scans"| tesseract
    app -.->|"only if explicitly enabled AND deterministic<br/>parse is weak: layout classification"| inference
```

The system has exactly one optional network dependency, and it is off at
launch. Everything else is local computation.

## C4 Container

```mermaid
flowchart LR
    subgraph host["Single host (Mac Studio node) / Docker container"]
        subgraph proc["gunicorn process — 1 UvicornWorker"]
            web["web layer<br/>web/routes.py · web/session.py · web/rate_limit.py<br/>(async event loop)"]
            pool["ThreadPoolExecutor<br/>(PROCESSING_THREAD_POOL_SIZE, default 4)"]
            parser["parser package<br/>parser/__init__.py · layout.py · fields.py<br/>ocr.py · text_extract.py · pdf_rasterize.py"]
            scorer["scorer package<br/>scorer/placement.py · rationale.py · weights.py"]
            pdf["pdf package<br/>pdf/render.py (ReportLab, invariant mode)"]
            guardrails["lexicon.py · copylint.py · errors.py"]
            sessions["SessionStore<br/>(in-memory dict + sweeper task)"]
            tmpdir["/tmp/coa_profiler_sessions/<br/>coa_profiler_session_* (working copies)"]
        end
    end
    browser["Patient's browser"] -->|"HTTP, same-origin only, no CORS"| web
    web -->|"run_in_executor (FR-030)"| pool
    pool --> parser
    parser --> scorer
    scorer --> pdf
    web --> sessions
    sessions --> tmpdir
    parser -.->|"guarded by copy-lint at boot<br/>and in CI"| guardrails
```

Blocking work (OCR, PDF text extraction) never touches the event loop: the
upload route hands it to a bounded thread pool with
`asyncio.wait_for(..., timeout=110s)`. A saturated pool answers 503 with
`Retry-After: 30` instead of queueing unboundedly.

## Component view — the deterministic pipeline

```mermaid
flowchart TD
    A["POST /upload<br/>(rate limit → size cap → magic-byte sniff)"] --> B["FR-002 metadata strip<br/>PDF: rewrite without metadata<br/>image: re-encode to PNG (drops EXIF)"]
    B --> C["FR-003 text acquisition<br/>PDF text layer (pdfplumber, PyMuPDF fallback)<br/>empty/garbled (<50 tokens) → rasterize + OCR<br/>image → OCR directly"]
    C --> D["FR-004 layout detection<br/>confident_cannabis / sc_labs / generic_ommu<br/>per-document + per-page sub-formats"]
    D --> E["FR-005 cite-and-verify extraction<br/>unit normalization to % w/w<br/>THCA/CBDA total derivation<br/>multi-page conflict resolution"]
    E --> F["FR-028 plausibility flags<br/>>50% implausible → generic re-extract → refusal"]
    F --> G["FR-006 sufficiency gate<br/>full / degraded / refusal / complete refusal"]
    G --> H["FR-007 five-step scoring<br/>normalize → directional sums → raw score<br/>→ contraction (U=0.85/0.70) → round to 5"]
    G --> I["FR-009 confidence<br/>DC penalties × MC (0.75) = CC"]
    H --> J["FR-008 rationale<br/>top 2–3 driving compounds,<br/>templated + copy-linted"]
    I --> J
    J --> K["GET /result (Jinja2) +<br/>GET /result/profile.pdf (ReportLab, byte-deterministic)"]
```

## Sequence — the primary user flow

```mermaid
sequenceDiagram
    autonumber
    participant U as Patient browser
    participant W as FastAPI routes (web/routes.py)
    participant P as Thread pool worker
    participant S as SessionStore (in-memory)
    participant T as Temp dir (/tmp/coa_profiler_sessions/)

    U->>W: POST /upload (multipart file)
    W->>W: rate-limit check (per-IP sliding window)
    W->>W: size cap, magic-byte sniff
    W->>S: mint session token + create temp dir
    W->>P: process_upload (strip metadata → parse → score)
    P->>T: write original + working copy
    P-->>W: (COAChemistry, PlacementResult, working path)
    W->>S: create record (TTL 300 s)
    W-->>U: 303 /result + Set-Cookie: session (HttpOnly, SameSite=Strict)
    U->>W: GET /result (cookie)
    W->>S: lookup (lazy expiry on access)
    S-->>W: SessionRecord
    W-->>U: result.html (or degraded.html / refusal.html)
    U->>W: GET /result/profile.pdf (cookie)
    W-->>U: application/pdf (byte-deterministic)
    U->>W: GET /new ("Analyze another COA")
    W->>S: teardown → delete record
    S->>T: delete session temp dir
    W-->>U: 303 / + cookie deleted
    Note over S,T: Independently, a background task sweeps expired sessions<br/>every 60 s and logs "session_sweeper: cleaned=N, remaining=M"
```

## Data model

No durable entities exist. The working data structures (spec section 5) are:

```mermaid
classDiagram
    class ParsedField {
        str name
        float value          # normalized % w/w; None when unreadable
        float original_value # as printed on the COA
        str original_unit    # %, mg/g, mg/mL, ppm
        str status           # verified | unreadable (derived reported via flag)
        str source_span      # literal text the value was verified against
        bool derived         # THCA/CBDA total derivation (DIS-15)
        bool plausibility_flag
        bool user_flagged    # reserved, always False at launch (DIS-3)
    }
    class COAChemistry {
        dict cannabinoids
        dict terpenes
        str lab_format
        int total_reported_terpenes
        float ocr_mean_confidence
    }
    class PlacementResult {
        int score            # 0-100 in steps of 5; -1 sentinel on refusal
        float raw_score
        float confidence_data
        float confidence_model
        float confidence_combined
        str completeness     # full | degraded | refusal
        list rationale
        int band_half_width  # 5-20, from 1 - CC
    }
    class SessionRecord {
        str session_token    # 128-bit hex, cookie only
        COAChemistry chemistry
        PlacementResult placement
        str working_copy_path
        float created_at
        int ttl_seconds
    }
    COAChemistry "1" *-- "many" ParsedField
    SessionRecord "1" *-- "1" COAChemistry
    SessionRecord "1" *-- "1" PlacementResult
```

The only other state is the **feedback aggregate** (in-memory counters keyed by
`(completeness, lab_format)` — no IP, no token, no chemistry) and the
**rate limiter** (per-IP sliding-window deques, reset on restart).

## Key design decisions

- **Deterministic parsing is the only active path.** Layout detection is
  signature scoring over extracted text (`parser/layout.py`); extraction is
  regex-with-citation (`parser/fields.py`) — every value must trace to a
  literal text span or it is marked `unreadable`. An optional
  OpenAI-compatible inference fallback exists (`parser/inference_assist.py`)
  behind `INFERENCE_ASSIST_ENABLED=false`; it is the only module permitted to
  make a network call, and the walk-away gates audit exactly that boundary.
- **Determinism is a feature (FR-022).** Tesseract runs with
  `OMP_THREAD_LIMIT=1` and `--psm 6` and is version-pinned in the Dockerfile;
  the PDF renderer uses ReportLab invariant mode with no timestamps, so
  identical inputs produce byte-identical PDFs (test-proven); the batch ZIP
  uses a fixed entry timestamp. The scorer version is the git tag, never a
  timestamp (DIS-12).
- **Zero retention is structural.** No database imports, no auth/payment code
  (enforced by a grep + AST gate that fails the build), sessions in memory
  with a 5-minute TTL, working copies under a prefix-swept temp root, access
  logs with hashed IPs and no cookie headers.
- **Copy is a correctness surface.** `lexicon.py` bans medical/therapeutic
  vocabulary ("treat", "dosage", "relief", …). The scan runs at boot (fatal;
  `COPYLINT_SOFT_FAIL=true` is a logged emergency override) and in CI over the
  generated rationale of every parseable fixture.
- **The weight table is code.** `scorer/weights.py` is the authoritative
  specification; `docs/algorithm.md` reproduces it and `/algorithm` renders it
  from the live module, so the public transparency page cannot drift from the
  shipped behavior.
- **Degradation is explicit, never silent.** Four sufficiency outcomes
  (full / degraded / refusal / complete refusal), an OCR confidence ladder
  (reject < 60, penalize 60–75), plausibility flags, and a >50%-implausible
  forced-refusal rule. The scorer never interpolates missing values.
- **Single worker, thread-pool offload (DIS-11, FR-030).** One gunicorn
  UvicornWorker; CPU-bound OCR/PDF work runs in a bounded
  `ThreadPoolExecutor` (default 4) with a 110 s in-route timeout below the
  120 s proxy/server timeout.

## Deployment and runtime model

- **Bare metal:** `OMP_THREAD_LIMIT=1 gunicorn coa_profiler.app:app -w 1 -k
  uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 --timeout 120` behind Nginx
  (TLS, `X-Forwarded-For`, 120 s read timeout).
- **Docker:** `Dockerfile` pins the base (`python:3.11-slim-bookworm`) and
  Tesseract (`tesseract-ocr=5.3.4-1`), installs `poppler-utils`, `libheif-dev`,
  `libgl1`, `libglib2.0-0`, and runs the same gunicorn command.
  `docker-compose.yml` adds a read-only root filesystem with a `/tmp` tmpfs —
  matching the zero-retention design.
- **Boot gates (lifespan startup, `app.py`):** copy-lint (fatal) → HEIC decoder
  check (fatal when enabled) → `INFERENCE_ASSIST_ACTIVE` audit line → stale
  session-dir sweep → session sweeper task.
- **Probes:** `GET /healthz` (liveness + version), `GET /readyz`
  (`parser_ready`, `ocr_ready`, `heic_ready`, `thread_pool_available`; 503
  when any is false).
- **Packaging:** `pyproject.toml` (setuptools, `src/` layout);
  `packaging.json` declares the runtime smoke command used by the Sneferu
  product launcher.

## Where the boundaries are

| Concern | Location |
|---|---|
| HTTP surface | `src/coa_profiler/web/routes.py` |
| Sessions + sweeps | `src/coa_profiler/web/session.py` |
| Rate limiting | `src/coa_profiler/web/rate_limit.py` |
| Config / env | `src/coa_profiler/config.py` |
| Parsing pipeline | `src/coa_profiler/parser/` |
| Scoring + weights + rationale | `src/coa_profiler/scorer/` |
| PDF rendering | `src/coa_profiler/pdf/render.py` |
| Banned lexicon | `src/coa_profiler/lexicon.py` |
| Typed user errors | `src/coa_profiler/errors.py` |
| Operator CLIs | `src/coa_profiler/{batch,evaluate,copylint}.py` |
| Boot gates + app factory | `src/coa_profiler/app.py` |
