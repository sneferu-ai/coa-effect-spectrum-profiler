# Runtime test plan — browser smoke (Playwright)

Target surface: `browser_ui` — the public web application served by
`packaging.json`'s `runtime_test_command` (uvicorn on the assigned `{port}`).

## Flow under test (the section-3 primary journey)

1. **Land on `/`** — the upload page renders: dropzone, one-line privacy
   commitment, and "What is a COA?" expand-collapse. When `CONTACT_EMAIL`
   is configured, also assert the batch-contact `mailto:` link; when it is
   empty, assert that no placeholder address is rendered.
2. **Upload `fixtures/fl_coa_sample.pdf`** through the real form
   (multipart POST `/upload`) — the loading overlay appears
   ("Analyzing your COA…") and the browser follows the 303 to `/result`.
3. **Assert the value moment on `/result`**:
   - the spectrum bar (`#spectrum-bar`) with the marker and the shaded
     uncertainty band, and the text equivalent
     "Placement: 70 of 100, indica-leaning (uncertainty band: 65–75)"
   - the two-component confidence line ("Data completeness … Model
     confidence … Combined …")
   - the rationale list naming Myrcene and Limonene
   - the extracted-chemistry table with at least one expandable
     `<details>` source span
   - the standing disclaimer and the "How is this calculated?" link
4. **Download `/result/profile.pdf`** — assert a 1-page PDF under 500 KB
   containing the placement, version, and weights hash.
5. **Keyboard/a11y pass** — the file input is keyboard-operable; the
   degraded/refusal notices use `role="alert"`; color is never the sole
   carrier of state.
6. **Negative pass** — uploading `fixtures/not_a_coa.txt` renamed to
   `.pdf` returns the typed 422 inline alert on the upload page
   (magic-byte rejection), with the dropzone and form preserved.
7. **Teardown & fresh-context recovery** — `GET /new` tears the session
   down (303 → `/`); in a fresh browser context (no cookie) `GET /result`
   returns 410 `error.html` with `Reference: SESSION_EXPIRED`, and
   `GET /result/profile.pdf` answers 303 → `/result` (never HTML at a
   `.pdf` URL). Re-uploading from the landing page starts a new session —
   there is no account or login surface to re-authenticate against; the
   saved PDF from step 4 is the recovery artifact.

## Round-1 UI verification record (2026-08-12, manual + curl against uvicorn)

Walked live on `uvicorn coa_profiler.app:app` (port 8934): landing
(dropzone, `accept=".pdf,.jpg,.jpeg,.png"`, `data-max-upload-bytes`, skip
link, noscript notice, brand mark in footer) → upload `fl_coa_sample.pdf`
(303) → `/result` full placement (spectrum-bar, `Placement: 95 of 100 —
strongly indica-leaning`, `uncertainty band: 90–100` in `<figcaption>`, "Full
placement — 6 terpenes read", "Data completeness", "What drove this
placement?", "Values from your certificate", 10 `<details class=
"source-span">`, parseable `#result-data` JSON with `scoring_steps`,
β-Caryophyllene monitored note, JSON-download button, feedback widget) →
PDF 200 (1 page, 64 KB, PDF 1.4) → feedback 204 → `/new` 303 → `/result`
410 with `SESSION_EXPIRED` reference → degraded journey via
`cannabinoids_only.pdf` ("Degraded placement — reduced confidence",
`role="alert"` with "weighted THC-total"/"contested", "Not used in
placement" chip, spectrum present) → refusal journey via
`no_chemistry.pdf` ("No placement could be calculated.", "Chemotype
summary", zero `spectrum-bar` occurrences) → Tier-1 inline 422
(`INVALID_FILE_TYPE` alert with dropzone preserved) → privacy page (all
six required literals + "reducing but not eliminating" + live
`log_ip_retention` value) → algorithm page (all eight hook strings +
"0.877"). `grep -c "_spectrum" templates/refusal.html` = 0. Keyboard:
file input is clip-hidden (`.sr-only`), not `display:none`; dropzone is a
`<label>`; `<details>` toggles natively; overlay traps Tab and is
`role="dialog" aria-modal="true"`. Mobile states are CSS-driven (640px
breakpoint, card-transform table, full-width buttons); 375px layout
verified by inspection of the card-layout transform rules, not by a
device run.

## Environment notes

- `HEIC_ENABLED=false` in the runtime command because the Playwright sandbox
  image does not ship libheif; the HEIC path is covered by AC-026 on the
  deployment machine where the decoder is present (its absence is fatal at
  boot by design, DIS-9).
- `SESSION_COOKIE_SECURE=false` because the harness serves plain HTTP on
  loopback.
