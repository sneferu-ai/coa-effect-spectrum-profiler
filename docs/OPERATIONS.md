# Operations — COA Effect-Spectrum Profiler

Run, deploy, monitor, and debug the profiler. Audience: the operator keeping
the service up. End-user recovery steps live in
[USER_GUIDE.md](USER_GUIDE.md#common-errors-and-exactly-what-to-do); interface
details live in [API.md](API.md).

## Prerequisites

| Requirement | Version | Check command |
|---|---|---|
| Python | 3.11+ (3.12 verified) | `python3 --version` |
| Tesseract OCR | 5.3.x (Docker pins `tesseract-ocr=5.3.4-1`) | `tesseract --version` |
| poppler-utils | any current | `pdftoppm --version` |
| libheif (dev) | any current | `brew install libheif` / `apt install libheif-dev` |
| OpenCV system libs | `libgl1`, `libglib2.0-0` (Debian/Ubuntu) | — |
| Docker | optional (containerized run) | `docker --version` |

The Python package itself is pure Python (`pyproject.toml`, `src/` layout,
setuptools). Runtime dependencies: fastapi, uvicorn, gunicorn, pdfplumber,
pdf2image, PyMuPDF, pytesseract, Pillow, pillow-heif, opencv-python-headless,
reportlab, jinja2, pydantic.

## Configuration — environment variables

All configuration is environment-based (`src/coa_profiler/config.py`); a
`.env` file in the working directory is honored, and the process environment
wins over the file. **No secret is required at default configuration.** Every
row below is read in `load_config()`; `.env.example` is the template.

| Variable | Default | Required | Purpose |
|---|---|---|---|
| `MAX_UPLOAD_MB` | `15` | optional | Upload size cap; over-limit uploads get `422 FILE_TOO_LARGE` |
| `SESSION_TTL_SECONDS` | `300` | optional | In-memory session TTL; cookie `Max-Age` matches |
| `SESSION_COOKIE_SECURE` | `true` | optional | `Secure` flag on the session cookie. **Set `false` for HTTP development** — browsers drop Secure cookies on HTTP and every upload looks expired |
| `RATE_LIMIT_PER_MINUTE` | `20` | optional | Per-IP upload limit (sliding window, in-memory) |
| `FEEDBACK_RATE_LIMIT_PER_MINUTE` | `10` | optional | Per-IP feedback limit |
| `PORT` | `8080` | optional | Listen port used by `python -m coa_profiler` and the startup log line |
| `INFERENCE_ASSIST_ENABLED` | `false` | optional | Enable the optional LLM layout-classification fallback (DIS-2). **Leave `false`** — determinism (FR-022) and the no-data-transfer guarantee hold only while disabled |
| `INFERENCE_ASSIST_URL` | empty | only if the above is true | OpenAI-compatible endpoint base URL |
| `INFERENCE_ASSIST_API_KEY` | empty | optional | Bearer credential for that endpoint; never logged |
| `TRUSTED_PROXY_HEADER` | empty | production | Header carrying the real client IP (e.g. `X-Forwarded-For`). **Required behind Nginx** — otherwise every client is `127.0.0.1` and shares one rate-limit bucket |
| `LOG_IP_RETENTION` | `hashed` | optional | Access-log IP mode: `hashed` (SHA-256, daily salt) / `full` / `truncated` / `disabled` |
| `PROCESSING_THREAD_POOL_SIZE` | `4` | optional | Upload-processing thread pool; saturation → `503` + `Retry-After: 30` and `thread_pool_available:false` in `/readyz` |
| `COPYLINT_SOFT_FAIL` | `false` | optional | `true` downgrades a boot copy-lint failure from fatal to a loud warning. Emergency use only |
| `HEIC_ENABLED` | `true` | optional | `false` drops HEIC support (the A-04 reversible fallback). With `true`, a missing decoder is **fatal at boot** |
| `COA_PROFILER_TMP_DIR` | `/tmp/coa_profiler_sessions` | optional | Session working-copy root (test/dev override) |
| `COA_PROFILER_VERSION` | unset | optional | Scorer version override (used by Docker builds); default is the git tag or `dev-<short_hash>` |

Build/runtime hygiene set by the Dockerfile (set them on bare metal too):
`OMP_THREAD_LIMIT=1` (OCR determinism, FR-022 — also defaulted in
`parser/ocr.py`), `PYTHONUNBUFFERED=1`, `PIP_NO_CACHE_DIR=1`.

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# HTTP development: set SESSION_COOKIE_SECURE=false in .env
uvicorn coa_profiler.app:app --reload --port 8080     # or: make dev
```

Success looks like:

- boot log shows `copy-lint: clean (16 templates)`,
  `heic_enabled=… heic_decoder=…`, `INFERENCE_ASSIST_ACTIVE: false`, and
  `coa_profiler <version> ready`;
- `curl -sf http://localhost:8080/readyz` →
  `{"status":"ready","parser_ready":true,"ocr_ready":true,"heic_ready":true,"thread_pool_available":true}`;
- `python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf
  --base-url http://localhost:8080 --check full` → `PASS: full, score=70`.

Tests: `pytest` (full suite), `make test-unit` / `test-integration` /
`test-acceptance` (integration needs Tesseract), `ruff check src/`,
`python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/`,
`./scripts/run_walkaway_gates.sh` (all six release gates). Last verification
in this tree: **165 tests passed**, all six gates PASS.

## Production

### Bare metal (the contract target: Mac Studio node behind Nginx)

```bash
pip install .
OMP_THREAD_LIMIT=1 gunicorn coa_profiler.app:app -w 1 -k uvicorn.workers.UvicornWorker \
  -b 127.0.0.1:8080 --timeout 120          # or: make prod
```

Nginx terminates TLS and proxies with `proxy_read_timeout 120s`,
`proxy_set_header X-Forwarded-For $remote_addr;` — and
`TRUSTED_PROXY_HEADER=X-Forwarded-For` in `.env` so rate limiting sees real
IPs. TLS via Let's Encrypt/certbot. **Single worker only** (DIS-11): sessions
and rate limits are in-process memory; a second worker would split them.

### Docker

```bash
docker build -t coa_profiler:latest .
docker run -p 127.0.0.1:8080:8080 --env-file .env coa_profiler:latest
# or: docker compose up -d   (read-only root fs, /tmp tmpfs, healthcheck baked in)
```

The Dockerfile pins `python:3.11-slim-bookworm` and `tesseract-ocr=5.3.4-1`
and installs poppler-utils, libheif-dev, and the OpenCV libraries. The image
has a `HEALTHCHECK` hitting `/healthz` every 30 s.

### Smallest verified deploy procedure

```bash
git pull && pip install .
OMP_THREAD_LIMIT=1 gunicorn coa_profiler.app:app -w 1 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 --timeout 120 &
sleep 2
curl -sf http://localhost:8080/healthz     # {"status":"ok","version":"..."}
python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf \
  --base-url http://localhost:8080 --check full   # PASS: full, score=<int>
```

### Rollback

```bash
# Docker
docker stop coa_profiler && docker run -d --name coa_profiler \
  -p 127.0.0.1:8080:8080 --env-file .env coa_profiler:{previous_tag}
# Bare metal
git checkout {previous_tag} && pip install .
OMP_THREAD_LIMIT=1 gunicorn coa_profiler.app:app -w 1 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 --timeout 120
```

Backup/restore: not applicable — no durable user data exists. Deploy-time
files are git-tracked; recovery is `git checkout`.

## Observability

There is no metrics/tracing stack at launch; the contract's minimum is a cron
job curling `/healthz` every 5 minutes with an alert on non-200.

- **Health:** `GET /healthz` → `{"status":"ok","version":…}`;
  `GET /readyz` → per-subsystem booleans, `503` when anything is down
  (field meanings in [API.md](API.md#get-readyz--readiness)).
- **Logs:** everything to stdout/stderr (systemd journal or `docker logs`).
  No log files. Lines to know:
  - `access ip=<hashed> method=… path=… status=… ms=…` — per request; cookie
    headers are never logged; IP form per `LOG_IP_RETENTION`;
  - `copy-lint: clean (N templates)` / `copy-lint: banned term …` — boot gate;
  - `INFERENCE_ASSIST_ACTIVE: false` — boot audit (FR-026);
  - `heic_enabled=… heic_decoder=…` — boot decoder check;
  - `session_sweeper: cleaned=<N>, remaining=<M>` — every 60 s;
  - `startup sweep removed N stale session dir(s)`;
  - `rate_limit hit bucket=upload` / `thread pool saturated (N in flight)`;
  - `feedback_summary: …` — at shutdown and every 100 feedback posts;
  - `unhandled error on <path>` — the sanitized 500 path; this is the line to
    search first when a user reports a generic error page.
- **State on disk:** only per-session working copies under
  `$COA_PROFILER_TMP_DIR/coa_profiler_session_*`, deleted at teardown/expiry
  and swept at startup. A healthy steady state is an empty directory:
  `ls /tmp/coa_profiler_sessions/ | wc -l` → `0`.

## Troubleshooting

**1. The server refuses to start: `RuntimeError: HEIC decoder … unavailable`**
The boot check is fatal by design (DIS-9). Diagnose:
`python -c "import pillow_heif; print(pillow_heif.__version__)"` and confirm
the system lib (`brew install libheif` / `apt install libheif-dev`). Fix:
install both, or set `HEIC_ENABLED=false` to drop HEIC (the documented
reversible fallback).

**2. The server refuses to start: `copy-lint found N banned term(s)`**
A template gained banned medical vocabulary (walk-away gate 4). The log names
the term and file. Fix the copy; do not ship around it.
`COPYLINT_SOFT_FAIL=true` starts anyway with a loud warning — emergency only.

**3. Every upload fails with `SESSION_EXPIRED` (410) right after upload**
Almost always `SESSION_COOKIE_SECURE=true` over plain HTTP: the browser drops
the Secure cookie, so `/result` has no session. Set
`SESSION_COOKIE_SECURE=false` for HTTP development. In production behind TLS,
leave it `true`.

**4. Rate-limit (429) hits that make no sense, or one user's limit consumed by
others** Behind Nginx the socket peer is always `127.0.0.1`, so all clients
share one bucket. Set `TRUSTED_PROXY_HEADER=X-Forwarded-For` and confirm Nginx
sends `proxy_set_header X-Forwarded-For $remote_addr;`.

**5. `UNREADABLE_DOCUMENT` on good-looking photos, or `/readyz` shows
`ocr_ready:false`** Tesseract missing or broken. Check
`tesseract --version` on the host; in Docker it is pinned by the image. OCR
mean confidence below 60 rejects the document; 60–75 processes with a
confidence penalty. A user-side blurry photo produces the same error — that
path is working as intended.

**6. `503 SERVER_BUSY` under load** The processing pool is saturated
(`PROCESSING_THREAD_POOL_SIZE`, default 4 concurrent uploads). Confirm in
`/readyz` (`thread_pool_available:false`) and the `thread pool saturated` log
line. Raise the pool size for the host's cores, and keep it single-worker.

**7. Slow uploads timing out (`PROCESSING_TIMEOUT`)** The in-route bound is
110 s, below the 120 s gunicorn/Nginx timeout. Large multi-page scans under
OCR are the slow path. Check per-request `ms=` values in the access log; a
smaller/clearer file is the user-side fix.

**8. The startup log says `ready (port 8080)` but the server answers on
another port** The log line prints the configured `PORT`; a `--port` flag (or
gunicorn `-b`) overrides the bind without updating that line. Cosmetic only —
trust the socket.

**9. Docker build fails on the Tesseract pin** `tesseract-ocr=5.3.4-1` is
pinned against `python:3.11-slim-bookworm`; if the base image's apt index
moved, check `docker run --rm python:3.11-slim-bookworm apt-cache policy
tesseract-ocr` (after `apt-get update`) and re-pin deliberately — Tesseract's
version is part of the OCR-determinism contract, so do not float it silently.
