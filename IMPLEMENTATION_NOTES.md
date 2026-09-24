# IMPLEMENTATION_NOTES — Round 1 (initial implementation)

> **Scoring/evaluation evidence superseded (2026-08-12).** The Round 1/2
> placement and concordance numbers below were produced by a ratio formula
> that did not match the binding signed-sum formula in `spec.md`. They are
> historical implementation notes, not current release evidence. The checked-in
> evaluation corpus is synthetic self-consistency data and is explicitly
> ineligible for release qualification. After the formula correction, release
> qualification requires a fresh run over at least 20 distinct, deidentified
> real documents with independently authored ratings; no such evidence is
> claimed by this repository.

---

## Round 2 — reviewer all-clear; verification pass, no code changes

The round-1 review returned **zero blockers and zero questions** (all clear).
No source edits were required or made this round. What was done instead:

- Re-ran the full suite: **165 passed** (`python3 -m pytest tests/`, exit 0) —
  includes every file on the orchestrator's impact list (test_ocr, test_app,
  test_batch, test_config, test_copylint, test_evaluate, test_fields,
  test_layout, test_lexicon, test_placement, test_rate_limit, test_rationale,
  test_session, test_weights).
- Re-ran `scripts/run_walkaway_gates.sh`: **ALL GATES PASS** (1–6, incl. the
  negative-injection proof on a temp copy).
- Re-ran the evaluate CLI with `--gate`: concordance 100% (20/20), Spearman
  1.000, determinism True, exit 0.
- Self-review findings checked and cleared:
  - Boot copy-lint **is** wired in `app.py` (imports `scan_templates` at
    startup; fatal default, `COPYLINT_SOFT_FAIL` override). A mid-round grep
    false-negative briefly suggested otherwise — confirmed by direct read.
  - Copy-lint CLI requires `--templates`/`--fixtures`, which exactly matches
    the spec's own AC-012/AC-043 invocation forms; the Makefile and gate
    script call it that way.
  - FR-007 `_round5` ties-toward-zero verified against both DIS-10 table
    edges (7.5→5, 92.5→90); FR-029 band clamps verified ([5, 20]).
  - No TODO/FIXME markers anywhere in shipped code or docs
    (docs-anti-patterns sweep).
  - Single canonical layout `src/coa_profiler/` confirmed; `spec.md`
    untouched.
- The two round-1 open questions (FR-028 re-run reading; batch sheet
  pagination) were not answered by the reviewer; the documented judgment
  calls stand as-is under the all-clear.

---

## What was built

The complete B13 product contract, from scratch, in the canonical
`src/coa_profiler/` layout (no parallel trees):

- **Parser** (`parser/`): magic-byte sniffing (FR-001), text-layer extraction
  with OCR fallback (FR-003), three-family layout detection + generic OMMU
  fallback + per-page sub-formats (FR-004), cite-and-verify extraction with
  unit normalization (`%`, `mg/g`, `mg/mL`, `ppm`), THCA/CBDA derivation
  (DIS-15), multi-page conflict resolution, plausibility flags + the >50%
  re-run/refusal rule (FR-028), ND/<LOQ → verified 0.0. Typed errors for
  every S3 failure class (`errors.py`).
- **Scorer** (`scorer/`): the FR-007 weight table as a literal dict
  (β-Caryophyllene monitored at 0.0 per DIS-14), the four-outcome sufficiency
  gate (FR-006/DIS-6), five-step scoring with U=0.85/0.70 contraction,
  two-component confidence with the 0.25 degraded floor (FR-009), uncertainty
  band (FR-029), templated lint-checked rationale (FR-008/FR-010).
- **PDF** (`pdf/render.py`): one-page US-Letter ReportLab profile in invariant
  mode — **no timestamp anywhere**, embedded Vera TTFs (bundled with
  ReportLab), version + weights-hash provenance, byte-identical across runs
  (proven by test + `cmp`), optional `customer_name`/`branding_logo` for the
  batch CLI (FR-017).
- **Web** (`app.py`, `web/`): FastAPI, Jinja2 templates, cookie sessions
  (128-bit HttpOnly/SameSite=Strict, 5-min TTL) with lazy expiry + throttled
  per-request sweep + 60 s logging sweeper + startup sweep (FR-012),
  per-IP sliding-window rate limits with `TRUSTED_PROXY_HEADER` support
  (FR-014), bounded thread pool with 503+Retry-After saturation (FR-030),
  access log with `LOG_IP_RETENTION` modes and no cookie logging (FR-013),
  anonymous feedback aggregate with shutdown/every-100 logging (FR-024),
  `/privacy`, `/algorithm` (rendered dynamically from `weights.py`, AC-024
  verified), `/healthz`, `/readyz` with thread-pool truth, boot-time
  copy-lint (fatal / `COPYLINT_SOFT_FAIL` emergency override) and HEIC-fatal
  check, `INFERENCE_ASSIST_ACTIVE` audit lines (FR-026).
- **CLIs**: `batch.py` (branded PDFs, alphabetically-sorted reference sheet,
  deterministic ZIP with fixed entry timestamps, `--skip-invalid`, exit
  codes 0/1/2), `evaluate.py` (field accuracy vs `expected_results.json`,
  determinism check, binned concordance, Spearman with the DIS-10 numeric
  mapping implemented from scratch in stdlib, outperform-the-labels,
  inter-rater flagging as a *warning* per OBL-23, `--gate` with the exact
  "Concordance below threshold: release blocked." message + 3-bin fallback
  recommendation), `copylint.py` (boot scope = templates, CI scope =
  templates + dynamic rationale over all fixtures).
- **Ops**: `Dockerfile` (pinned tesseract, `OMP_THREAD_LIMIT=1`, single
  gunicorn Uvicorn worker), `docker-compose.yml`, `Makefile`, `.env.example`,
  `packaging.json` (runtime_test_mode=playwright + `{port}` command),
  `test_plan.md`, `docs/algorithm.md` (weight table reproduced exactly, 4 real
  DOIs), `scripts/smoke_test.py` (all four modes verified against a live
  uvicorn server), `scripts/run_walkaway_gates.sh` (all six gates PASS,
  including the temp-copy negative-injection proof).
- **Fixtures**: `scripts/make_fixtures.py` generates all 44 fixtures
  deterministically (ReportLab invariant mode) and *computes* the expected
  scores/labels with the real scorer — `fl_coa_sample_expected.json`,
  `eval/labels.json` (concordance 100%), `labels_fail.json` (15%: inverted),
  `expected_results.json`, 20 eval COAs spanning all five DIS-10 bins
  (asserted at generation time), 4 batch COAs with distinct placements,
  corrupt/unreadable/not-a-COA/HEIC-magic negatives.

## Verification actually run (this environment, macOS, Python 3.12)

- `python3 -m pytest` → **148 passed** (unit + integration + acceptance).
- `./scripts/run_walkaway_gates.sh` → **ALL GATES PASS** (boots a real
  uvicorn for Gate 5, smoke `full` PASS, evaluate `--gate` both directions).
- `python -m coa_profiler.batch` on fixtures → exit 0 (4/5), sorted sheet,
  ZIP + failures.log.
- `python -m coa_profiler.evaluate --gate` → exit 0 on labels.json (100%),
  exit 1 on labels_fail.json (15%) with the contingency line.
- `python -m coa_profiler.copylint` → clean in both scopes; boot scan 0.01 s
  (AC-043 budget 5 s).
- Smoke CLI against live uvicorn: PASS full (score=70) / degraded (80) /
  refusal / reject; AC-004 grep count 10 ≥ 6 via the Netscape cookie jar.
- Byte-identical PDFs across runs (`cmp`-equivalent test), one page, <500 KB.

## Judgment calls (documented, all reversible)

1. **PDF engine fallback**: the sandbox lacks `pdfplumber`/`pdf2image`
   (no network). `text_extract.py`/`pdf_rasterize.py` prefer the spec'd
   libraries and fall back to PyMuPDF (`fitz`), which provides the identical
   capability (text layer + rasterization) with no system binary. Both are
   declared in `pyproject.toml`; the fallback is a lazy import seam, and the
   primary path activates automatically when the spec'd libs are installed.
2. **Rounding**: FR-007's "round to nearest 5" is implemented as
   round-half-toward-zero — the only rule consistent with DIS-10's
   reachability table (raw 0 → contracted 7.5 must reach 5; raw 100 → 92.5
   must reach 90). Banker's rounding and half-up each break one side.
3. **`HEIC_ENABLED=false`** is the reversible A-04 fallback for platforms
   without libheif; default remains `true` with fatal-at-boot enforcement
   (DIS-9). Tests run with it disabled because this sandbox lacks
   pillow-heif; AC-026 runs on the deployment machine.
4. **Zero-verified-cannabinoids case**: not addressable by DIS-6 (a) or (b);
   routed to refusal. Stated here for the reviewer.
5. **Session temp root** defaults to `/tmp/coa_profiler_sessions/` (AC-006);
   `COA_PROFILER_TMP_DIR` overrides for tests (documented, additive).
6. **Cookie `max-age` = TTL**: browsers drop the expired cookie, so the
   middleware runs a throttled (1/s) opportunistic sweep per request — the
   60 s logging sweeper alone cannot see a token that never arrives (AC-006).
7. **Batch reference sheet** is one page by construction; a very large batch
   (hundreds of files) would overflow the single page — acceptable for the
   $250-pack operator use case; pagination is a trivial follow-up.

## Not verified here (environment limits — honest remainder)

- `gunicorn`, `pdfplumber`, `pdf2image`, `pillow-heif`, `ruff`, `build` are
  not installed in this sandbox (no network). Code paths that need them are
  lazy-imported and covered by fallback or skip logic; the acceptance items
  that require them (AC-017/018/019 Docker runs, AC-020 wheel build,
  AC-026 real HEIC decode, AC-037 70-second sweeper watch, AC-021 25-request
  burst, AC-036 real concurrency, `ruff check`) must run on the Mac Studio.
- OCR path is covered by tests against the real Tesseract 5.5.2 binary here;
  determinism across *machines* requires the Docker image pin (DIS-12).
- `docs/algorithm.md` DOIs are the real, well-known identifiers for the four
  cited papers; operator manual resolution is the A-22 pre-release step.

## Open questions for the reviewer

- Is the FR-028 "re-run layout detection" reading acceptable (we re-extract
  under the generic fallback rules — the signatures are content-derived, so
  re-running *detection* on identical text cannot change the outcome)?
- Should the batch reference sheet paginate for very large input dirs?
