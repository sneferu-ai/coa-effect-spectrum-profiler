# Product Contract — COA Effect-Spectrum Profiler (B13)

## 1. Product boundary and inherited decisions

**Product name:** COA Effect-Spectrum Profiler — one deployable web application, one public algorithm transparency page, and three operator-only command-line tools.

**Target user:** A Florida medical-cannabis patient in Dr. S's clinical practice or readership (B7 primary segment; B7 is `completed_partial` and unqualified, so this is real input at low confidence, not a verified market fact). The user already holds an OMMU-mandated Certificate of Analysis from a dispensary purchase.

**Primary job:** Convert the certificate in hand into a chemistry-derived tendency score on the sativa↔indica axis, so a person who needs daytime function has additional information beyond the dispensary's subjective label before committing to a product (B7 JTBD-1, claim C-101, model_inference at 0.25 confidence). The product does not claim to predict effects; it computes a deterministic mapping from measured chemistry to a familiar scale, explicitly disclaimed as non-medical, non-predictive, and literature-derived. Individual responses depend on dose, tolerance, and individual biology — factors beyond COA chemistry.

**Why a parser rather than manual entry:** Patients hold a COA with 10–20 chemistry values in units they may not recognize (mg/g, %, ppm). Manually transcribing these into a web form introduces transcription errors, requires knowing which fields matter, and defeats the purpose of an objective tool. The parser eliminates this barrier and ensures the scoring path receives values traced to the document, not entered from memory. A manual-entry alternative was considered and rejected: it would let non-document-sourced values enter the scoring path silently, violating the B6 `mvp_in` #1 clause ("unreadable fields flagged, not guessed") and undermining the product's credibility claim.

**Competitive landscape acknowledgment:** Strain-level effect breakdowns and chemistry data exist publicly (Leafly strain database; SC Labs' PhytoFacts chemometrics reporting; informal open-source terpene calculators). B8 competitive map is absent (`completed_partial`, unqualified). What is specific to this implementation: (a) Florida OMMU-mandated COA parsing with cite-and-verify extraction, (b) Dr. S's clinical domain expertise informing weight derivation and the concordance evaluation, (c) an accountless, zero-retention privacy posture, (d) a publicly served algorithm page showing exact weights and citations, and (e) distribution through Dr. S's clinical network and book audience. These are table-stakes properties, not a moat; the product's value is serving Dr. S's patient audience with a trustworthy, free, chemistry-focused tool that accepts the document they already hold. No competitive features are added or removed based on B8's absence.

**Weight derivation provenance:** The weight table (FR-007) is derived from published terpene-effect literature (Russo 2011; McPartland & Russo 2001; Russo & Marcu 2017; Gertsch et al. 2008). Dr. S's clinical expertise informed the process by: (a) reviewing the cited literature and confirming directional assignments against clinical observation, (b) selecting reference maxima based on typical Florida COA ranges observed in practice — these are operator-informed estimates, not statistical maxima, and are treated as tuning parameters subject to validation (§10 A-01), (c) flagging β-Caryophyllene as direction-uncertain after reviewing the Gertsch et al. citation (which addresses CB2 anti-inflammatory agonism, not sedative/indica-direction effects), leading to its assignment as direction-neutral, and (d) annotating THC/CBD contributions as weak and contested. The weights are literature-derived hypotheses with clinical-informed directional assignments, not outputs of a quantitative model or clinical trial. This process is documented in `docs/algorithm.md`.

**Florida OMMU regulatory reference:** The parser targets COAs issued under Florida OMMU testing requirements, including Rule 64-4.016, F.A.C. (medical marijuana treatment center standards) and the testing protocols established under 64ER20-39 (emergency rule) and subsequent rule codifications. The exact rule version in effect at launch must be confirmed pre-launch (§10 A-19) because lab format requirements may change. The parser's three format families are designed to generalize across rule versions.

**Florida lab landscape and coverage plan:** Florida's OMMU-licensed medical marijuana treatment centers (MMTCs) source COAs from a limited set of approved testing laboratories. The exact number of licensed testing labs and their COA format variations is not independently verified in the supplied artifacts. The three targeted format families — Confident Cannabis style, SC Labs / PhytoFacts style, and Generic OMMU-table fallback — are designed to cover the majority of COAs encountered in Florida dispensary purchases based on operator testimony (C-002). Unmodeled formats fall through to the generic OMMU-table fallback parser, which extracts values using keyword-plus-numeric patterns common to all OMMU-compliant COAs. The generic fallback is the safety net for any lab format not yet explicitly modeled. The exact lab count, format coverage percentage, and per-lab accuracy are tracked as §10 A-21.

**Taxonomy acknowledgment:** The sativa↔indica taxonomy is morphological, not chemical, and is scientifically contested (R-005, R-012, R-014). Published studies suggest that strain labels often correlate poorly with chemical composition (B1 pains, evidence claim C-013 at 0.4 confidence). The specific ~90,000-sample study cited in prior drafts is not yet verified (§10 A-14); until verification completes, the disclaimer uses "published studies suggest" without a specific sample count or citation. This tool uses the sativa↔indica axis as a familiar communication framework for patients who already encounter it at dispensaries — not as a validated clinical taxonomy. The scoring weights are derived from published terpene-effect literature that itself references this taxonomy; the weights inherit that weakness. The disclaimer on every output (FR-010) and the `/algorithm` page (FR-023) state this explicitly. A future chemistry-native axis (e.g., "myrcene-dominance index") is architecturally reserved but not built at launch (§10 A-20).

**What ships (B6 `mvp_in`, clause-mapped):**

| B6 `mvp_in` clause | Contract implementation |
|---|---|
| 1. Upload a COA (PDF or photo) and see cannabinoid and terpene values extracted, with unreadable fields flagged, not guessed | FR-001, FR-003, FR-004, FR-005, FR-025, FR-028; S1, S2; AC-003, AC-004, AC-009 |
| 2. Receive a computed position on a visual sativa↔indica spectrum, derived from the parsed chemistry — a placement, not a three-bucket label | FR-006, FR-007, FR-029; S2; AC-003 |
| 3. Read a plain-language rationale naming the terpenes and cannabinoids driving that placement | FR-008; S2; AC-004 |
| 4. Download a one-page PDF strain profile: spectrum placement, chemotype summary, dominant terpenes | FR-011; S4; AC-005 |
| 5. Use the full upload→PDF flow free, with no account | FR-015; S1; AC-007, AC-013 |
| 6. Parse Florida-format (OMMU-mandated) COAs reliably first | FR-004; S1; AC-003, AC-032 |

A no-cost web tool requiring no sign-up. One certificate file in (PDF, JPEG, PNG, or HEIC) → measured cannabinoid and terpene content out, with any field that cannot be read marked as unreadable rather than estimated → a numeric position on the tendency axis computed by a documented deterministic function of the measured chemistry alone, rounded to the nearest 5, displayed with an uncertainty band proportional to combined confidence → an everyday-language explanation naming the compounds responsible → a single-page PDF to keep. Nothing is stored in any durable store; no login, no payment, no tracking; the only cookie is a short-lived functional session cookie.

**What does not ship (B6 `mvp_out`, enforced as verifiable absence):** the Phase 2 chatbot; health, treatment, or dosing statements of any kind; accounts, saved profiles, or history; lookup by strain name without an uploaded certificate; any payment or gating inside the public tool; menus, product recommendations, commerce links, native apps; non-Florida certificate formats at launch; any B2B portal, dashboard, multi-upload page, or payment code.

**Revenue surface:** none inside the public product. The B6 first-$1,000 path ($250 batch profile packs) is served by an offline operator CLI (FR-017) running the identical parse→score→render library over a folder of certificates, emitting PDFs for manual delivery. No portal, dashboard, multi-upload page, payment code, or commercial contact page exists anywhere in this contract. A non-commercial `mailto:` contact link (FR-031) is displayed on the landing page for visitors interested in batch processing; it opens the user's email client with a pre-filled subject and stores no data. This is a discovery mechanism, not commerce — it conforms to B6 `mvp_out` #5 (no payments or gating) and #6 (no commerce links) because it is a contact method, not a transaction.

**B9 economics quarantine:** B9 unit economics ($250 batch pack, CAC $58.40, LTV $226.32, 0.25 confidence, `completed_partial`) are unverified model_inference hypotheses. They shape **zero** runtime code decisions, **zero** architecture decisions, and **zero** acceptance criteria. The batch CLI exists because the B6 concept lock defines it as a derived deliverable, not because B9 economics validated it. The $250 price is an operator decision recorded in B9, not a product requirement. If B9 is re-run and produces different figures, no code changes.

**Pipeline artifact debt:** B3 Pareto scoring and B4 kill tournament artifacts with per-vendor scores and stance rankings are not present in the supplied B0–B12 materials. Their converged outputs are captured in the B5 selection and the B6 concept lock. The absence of detailed B3/B4 artifacts is upstream qualification debt, not a contract gap.

**Named upstream conflicts and chosen directions:**

1. **DIS-1 — Spectrum scale and orientation.** *Chosen direction:* integer 0–100, 0 = sativa-leaning, 100 = indica-leaning, displayed left-to-right. **Output is rounded to the nearest 5** — 21 distinct values. The raw score is contracted toward the midpoint by a model-uncertainty factor (FR-007 Step 4). User-facing labels are "sativa-leaning" / "indica-leaning." *Why sativa-at-left:* majority draft convention and left-to-right reading order; acknowledged as cultural convention, not scientific fact.

2. **DIS-2 — Parser architecture and inference provider.** *Chosen direction:* **deterministic primary with an optional inference-assist fallback behind a feature flag, in a circuit-breaker pattern.** The deterministic path handles all known Florida lab formats and is the sole active path at launch (`INFERENCE_ASSIST_ENABLED=false`). When enabled post-launch, and only when the deterministic parser returns `format: unknown` or fewer than 50% of expected fields, the extracted text is sent to an OpenAI-compatible endpoint for layout classification with a 10-second timeout. **Determinism guarantee (FR-022) and B0 walk-away 2 (no data transfer) are guaranteed only when `INFERENCE_ASSIST_ENABLED=false`.** Enabling the fallback requires the endpoint to be operator-controlled or a separate operator decision; the boot-time audit log (FR-026) records the enabled state. Tesseract is version-pinned; `OMP_THREAD_LIMIT=1` and a fixed `--psm 6` mode enforce OCR determinism (FR-022).

3. **DIS-3 — User-editable parsed values.** *Chosen direction:* **rejected at launch.** Parsed values are display-only. Any value that cannot be verified against the extracted document text is marked unreadable. *Rationale:* the product's credibility claim is that output derives solely from the certificate; allowing edits would let non-document-sourced values enter the scoring path. *Known limitation:* cite-and-verify traces to extracted text, not the physical document — a misread digit will be marked `verified`. User-visible source spans (FR-025) plus plausibility range checks (FR-028) are the mitigations. *Architectural hook reserved:* `user_flagged: bool` field (always `False` at launch) for a future operator-approved flag feature.

4. **DIS-4 — Session model and TTL.** *Chosen direction:* **5-minute TTL (configurable, `SESSION_TTL_SECONDS` default 300), session token in an `HttpOnly`, `SameSite=Strict` cookie.** The `Secure` flag is controlled by `SESSION_COOKIE_SECURE` (default `true`; set to `false` for HTTP development). Cookie-based transport eliminates session-token exposure in URLs, browser history, and access logs.

5. **DIS-5 — Upload ceiling.** 15 MB, configurable (`MAX_UPLOAD_MB`).

6. **DIS-6 — Degradation thresholds.** *Chosen direction:* **hybrid threshold with four outcomes.** (a) *Full placement:* ≥1 cannabinoid verified AND ≥3 terpenes verified AND ≥60% of reported terpenes readable. (b) *Degraded placement:* cannabinoids verified but terpene data insufficient — produces a cannabinoid-weighted placement with reduced confidence, a visible notice stating "This placement is based solely on cannabinoid ratios (THC:CBD), which are particularly contested predictors of effects," and a **minimum combined-confidence floor of 0.25** (below this, placement is refused even in degraded mode). (c) *Refusal:* zero terpenes readable — no placement; chemotype-only summary. (d) *Complete refusal:* zero chemistry fields readable — typed error.

7. **DIS-7 — API routing.** RESTful server-rendered routing with cookie-based sessions and stable paths. No CORS; same-origin only. Processing is offloaded to a thread pool (FR-030) within the single async worker; the event loop remains free to accept connections.

8. **DIS-8 — Public algorithm transparency.** *Chosen direction:* **server-rendered `/algorithm` page (S6, FR-023)** showing the complete weight table, normalization formula, scoring steps, confidence formula, degradation rules, weight selection criteria, and literature citations. Linked from results page, PDF footer, and privacy page. A machine-readable JSON endpoint (`GET /api/algorithm`) was proposed by one author seat (nvidia) during the seed phase but was not adopted by the majority; the HTML page satisfies the transparency requirement and the B6 concept lock. Adding a JSON endpoint is a discretionary future enhancement, not a launch requirement.

9. **DIS-9 — HEIC format.** *Chosen direction:* **commit to HEIC.** `pillow-heif` required; `/readyz` reports `heic_ready`; decoder absence is fatal at boot. Reversible fallback: drop HEIC if the platform proves incapable (§10 A-04).

10. **DIS-10 — Concordance threshold, bins, and contingency protocol.** *Chosen direction:* **80% binned directional agreement on a held-out set of ≥20 Florida COAs is a hard release gate.** Bins are widened to account for model-uncertainty contraction:

    | Bin | Scores | Reachable (U=0.85 full) | Reachable (U=0.70 degraded) |
    |---|---|---|---|
    | strongly-sativa | {0, 5, 10, 15, 20} | {5, 10, 15, 20} — 4/5 | {15, 20} — 2/5 |
    | sativa | {25, 30, 35, 40} | all 4 | all 4 |
    | balanced | {45, 50, 55} | all 3 | all 3 |
    | indica | {60, 65, 70, 75} | all 4 | all 4 |
    | strongly-indica | {80, 85, 90, 95, 100} | {80, 85, 90} — 3/5 | {80, 85} — 2/5 |

    Only 0, 95, and 100 are unreachable in full mode — theoretical extremes requiring all compounds at reference maxima. The `--gate` flag exits non-zero below 80%. **Numeric mapping for Spearman:** strongly-sativa=-2, sativa=-1, balanced=0, indica=1, strongly-indica=2. **Inter-rater reliability:** the operator selects ≥20 COAs; Dr. S rates each independently; a second rater (a second clinician or Dr. S in a separate blind pass) rates the same set. A minimum interval between same-rater passes is recommended to reduce memory bias but is not enforced by the tool. Inconsistency threshold: any rating differing by ≥2 bins between passes is flagged in the report. If >3 of 20 ratings are inconsistent, the report emits a warning "INTER-RATER INCONSISTENCY DETECTED" with details; the operator may review the rating protocol at their discretion. **Contingency protocol if 80% is unreachable:** (1) revise weights as needed; (2) if concordance remains below 80%, the CLI recommends falling back to a 3-bin system (sativa {0–40}, balanced {45–55}, indica {60–100}) with 70% threshold as a bounded reversible default; (3) the operator may escalate to concept-lock revision at any time. The CLI prints these recommendations but does not halt the pipeline.

11. **DIS-11 — Multi-process deployment and concurrency.** *Chosen direction:* **single gunicorn worker with Uvicorn worker class** (`-w 1 -k uvicorn.workers.UvicornWorker`). Blocking upload processing is offloaded to a configurable thread pool (`PROCESSING_THREAD_POOL_SIZE`, default 4) via `run_in_executor`, allowing up to 4 concurrent uploads within the single worker. The async event loop accepts new connections while OCR runs in threads. Load test: 5 concurrent users; the 5th receives HTTP 503; p95 < 60s for the 4 accepted requests (§10 A-13).

12. **DIS-12 — PDF library, determinism, and version string.** *Chosen direction:* **ReportLab** in invariant mode. **No generation timestamp embedded.** The scorer version string is the git tag at build time (e.g., `v0.1.0`) or `dev-<short_hash>` for untagged builds — never a timestamp or random component. The weights-file hash is SHA-256 of `scorer/weights.py` content. Both are fixed at build time. `OMP_THREAD_LIMIT=1` and Tesseract `--psm 6` are set in the environment to enforce OCR determinism. **Determinism guarantee applies only when `INFERENCE_ASSIST_ENABLED=false` and on the same Docker image and machine architecture**; when enabled, OCR is still deterministic but inference-assist output (if triggered) may vary by provider response. Byte-identical PDF output is guaranteed within the same Docker image digest on the same machine.

13. **DIS-13 — B8/B10/B12 absent.** The slice defaults to exactly the B6 `mvp_in` set plus the offline batch path, evaluation CLI, algorithm transparency page, feedback mechanism, demand-validation contact link, and citation verification gate — all within the concept lock.

14. **DIS-14 — β-Caryophyllene directional assignment.** *Chosen direction:* **direction-neutral (weight 0.0).** The citation (Gertsch et al. 2008) addresses anti-inflammatory CB2 agonism, not sedative/indica-direction effects. Assigning it to "indica" would systematically bias most COAs (where β-Caryophyllene is abundant) toward indica without literature support. The compound is still extracted, displayed in the chemotype summary, and listed in the rationale as "present but not directionally scored pending better literature support." The `/algorithm` page documents this decision. β-Caryophyllene appears in a "monitored but not scored" section of the weight table, separate from active directional compounds.

15. **DIS-15 — THCA/CBDA derivation.** *Chosen direction:* if a COA reports THCA and delta-9 THC separately but no "Total THC" line, the parser derives: `Total THC = delta-9 THC + 0.877 × THCA`. Likewise `Total CBD = CBD + 0.877 × CBDA`. The 0.877 factor accounts for decarboxylation molecular weight loss. The derived value is marked `derived: true` in the source-span record and displayed with a note: "Calculated from THCA + delta-9 THC using standard decarboxylation conversion." This prevents valid COAs from being downgraded to degraded mode solely because they report components separately.

**Walk-away gate wiring (B0 conditions → contract gates):**

| B0 walk-away condition | Gate mechanism | Observable failure |
|---|---|---|
| 1. Paywalls or restricts the core upload-to-profile flow | FR-015; grep + AST scan (AC-013); behavioral probe | Auth/payment code found, or auth endpoint responds non-404 → gate fails |
| 2. Transfers data/prompt/account control away from Dr. S | §8 self-host; no outbound calls with `INFERENCE_ASSIST_ENABLED=false` (AC-017); boot-time audit log when enabled (FR-026) | Outbound connection detected during journey (default config) → gate fails |
| 3. Viability depends on the nonprofit dataset | FR-007 uses literature-derived weights only; grep for dataset/nonprofit in scorer returns zero | Dataset dependency found in scorer → gate fails |
| 4. Medical/therapeutic effect claims | FR-010 banned lexicon; FR-019 copy-lint at boot (fatal by default, soft-fail optional); AC-031, AC-042 | Copy-lint finds banned term → application refuses to start → gate fails |
| 5. No working COA-to-PDF preview within the window | §11 build order; AC-003; concordance gate (AC-030); citation verification gate (AC-033) | Journey fails, concordance < 80%, or citations unverified → release blocked |
| 6. Depends on cannabis-excluding vendors | §8 self-host; no cloud SDKs; registrar AUP verified (§10 A-16) | Cloud SDK import found → gate fails |

**Inherited-decision trace:**

| Upstream decision (source) | Status | Implemented in | B6 clause |
|---|---|---|---|
| Free public COA→profile web tool (B0 goal) | operator intent | §2 S1–S6, §3, FR-001…FR-011 | mvp_in #1–6 |
| Core flow never paywalled (B0 walk-away 1) | operator constraint | FR-015; AC-013; Gate 1 | mvp_out #5 |
| No transfer of data/prompt/account control (B0 walk-away 2) | operator constraint | §8; AC-017; Gate 2; FR-026 audit | (derived) |
| Viability must not rest on the nonprofit dataset (B0 walk-away 3) | constraint + open | FR-007; §10 A-02; Gate 3 | riskiest_unknown #2 |
| No therapeutic/medical claims (B0 walk-away 4) | operator constraint | FR-010, FR-019; AC-012, AC-031; Gate 4 | mvp_out #2 |
| Working preview inside the window (B0 walk-away 5) | operator constraint | §11; AC-003; AC-030; AC-033; Gate 5 | riskiest_unknown #1 |
| No dependence on cannabis-excluding vendors (B0 walk-away 6) | constraint + open | §8; §10 A-16; Gate 6 | (derived) |
| Upload COA, extracted values, unreadable flagged (B6 mvp_in #1) | locked scope | FR-001, FR-003–FR-005, FR-025, FR-028 | mvp_in #1 |
| Computed spectrum position (B6 mvp_in #2) | locked scope | FR-006, FR-007, FR-029 | mvp_in #2 |
| Plain-language rationale (B6 mvp_in #3) | locked scope | FR-008 | mvp_in #3 |
| One-page PDF strain profile (B6 mvp_in #4) | locked scope | FR-011 | mvp_in #4 |
| Full flow free, no account (B6 mvp_in #5) | locked scope | FR-015; AC-007, AC-013 | mvp_in #5 |
| Parse Florida-format COAs first (B6 mvp_in #6) | locked scope | FR-004 | mvp_in #6 |
| Phase 2 chatbot deferred (B6 mvp_out #1) | locked exclusion | §1 boundary | mvp_out #1 |
| Medical/therapeutic/dosing claims excluded (B6 mvp_out #2) | locked exclusion | FR-010, FR-019 | mvp_out #2 |
| Accounts/saved profiles/history excluded (B6 mvp_out #3) | locked exclusion | FR-012, FR-013, FR-015 | mvp_out #3 |
| Strain-name lookup without COA excluded (B6 mvp_out #4) | locked exclusion | §1 boundary | mvp_out #4 |
| Payments/subscriptions/gating excluded (B6 mvp_out #5) | locked exclusion | FR-015; AC-013 | mvp_out #5 |
| Menus/recommendations/commerce/native apps excluded (B6 mvp_out #6) | locked exclusion | §1 boundary | mvp_out #6 |
| Batch packs offline via same pipeline (B6 first_1k_path) | derived | FR-017; AC-014 | first_1k_path |
| R-001 copy drift | open risk | FR-010, FR-019; AC-012, AC-031 | riskiest_unknown #4 |
| R-002/R-010 hosting/registrar exclusion | open risk | §8; §10 A-16; Gate 6 | (derived) |
| R-003 provider outage | retired by design | DIS-2; FR-026 | (derived) |
| R-004 multi-lab parse accuracy | open risk | FR-004, FR-005, FR-028; AC-032; §10 A-03, A-21 | riskiest_unknown #3 |
| R-005/R-012/R-014 signal sufficiency, taxonomy | open risk | FR-009, FR-018; §10 A-01; §1 taxonomy acknowledgment | riskiest_unknown #1 |

## 2. Product surfaces

**S1 — Landing and upload page (`GET /`, `POST /upload`).** Purpose: explain the tool in one screen and accept one certificate. Entry: direct URL, QR code, newsletter link. Inputs: a single multipart file (PDF, JPEG, PNG, or HEIC by magic-byte sniffing, ≤ `MAX_UPLOAD_MB` default 15); drag-drop, file picker, or mobile camera capture. Outputs: HTTP 303 to `/result` with a `Set-Cookie` session header on accept; inline typed error on reject (HTTP 422). Processing is offloaded to a thread pool (FR-030); the client shows a JavaScript loading overlay (FR-027) during the request. States: idle dropzone with one-line privacy commitment; uploading (loading overlay); typed rejection. A "What is a COA?" expand-collapse provides context. A non-commercial contact link (FR-031) is displayed below the upload zone: "Need batch processing for your practice? Contact us." The link is a `mailto:` URI with a copyable email address displayed as visible text below the link — no form, no data storage. Permissions: anonymous; per-IP in-memory rate limit (FR-014, reading `X-Forwarded-For` when `TRUSTED_PROXY_HEADER` is configured). Responsive/a11y: mobile-first; WCAG 2.1 AA; keyboard-operable file input; `aria-live` announcements.

**S2 — Spectrum result view (`GET /result`).** Purpose: the value moment. Reads the session from the cookie; renders one of three states. Outputs (full placement): horizontal tendency bar with marker, **uncertainty band** (shaded region proportional to `1 - confidence_combined`; FR-029), and rounded numeric position; numeric placement with text equivalent including band range ("Placement: 70 of 100, indica-leaning (uncertainty band: 65–75)"); two-component confidence indicator; explanation paragraph naming top contributing compounds; extracted-chemistry table with per-field status, unit, expandable source-span, and plausibility warning icon when values exceed expected ranges (FR-028); completeness badge; standing disclaimer (FR-010); "How is this calculated?" link to `/algorithm`; "Download PDF profile" button; anonymous feedback buttons (FR-024) that submit `{"helpful": bool, "placement": int, "completeness": str, "lab_format": str}` — non-identifying derived data; "Analyze another COA" link. Outputs (degraded): reduced-confidence placement with a visible notice: "This placement is based solely on cannabinoid ratios (THC:CBD), which are particularly contested predictors of effects. Terpene data was insufficient for a full placement." If combined confidence < 0.25, placement is refused even in degraded mode. Outputs (refusal): no spectrum score; chemotype summary; explanation. States: ready; ready-degraded; ready-refusal; expired (HTTP 410). Permissions: session cookie within TTL. a11y: text equivalent for bar and band; semantic HTML; color is never sole carrier; degraded/refusal notices use `role="alert"`.

**S3 — Typed error pages.** One per failure class: unsupported file type, oversize, not-a-COA, unreadable document, no usable chemistry, rate-limited, HEIC decoder unavailable, internal error. Each states what happened and the recovery action. None exposes stack traces or internal state.

**S4 — PDF strain profile (`GET /result/profile.pdf`).** Contents, one US-Letter page: tool name; scorer version (git tag) and weights-file hash; numeric placement with bar graphic and uncertainty band; two-component confidence breakdown; chemotype summary; dominant terpenes; rationale text; unreadable-field list; plausibility-flagged values with warning; completeness badge; standing disclaimer (FR-010); "Free public tool" footer; `/algorithm` reference line. **No generation timestamp.** Format: PDF 1.4 compatible, embedded fonts, no external resources, <500 KB. (PDF/A-1b compliance is not claimed; ReportLab's PDF/A configuration requires ICC profiles and conformance validation not tested here.) The PDF renderer accepts optional `customer_name` and `branding_logo` parameters for batch CLI branded PDF generation (FR-017). States: rendered on demand; HTTP 410 after teardown. Permissions: session cookie within TTL.

**S5 — Privacy notice page (`GET /privacy`).** Content: what is processed (chemistry fields); what is never stored (files, parsed values, results, IP-derived identities); session TTL (5 minutes) and teardown; EXIF-stripping; session-cookie description (`HttpOnly`, `SameSite=Strict`, `Secure` when `SESSION_COOKIE_SECURE=true`); access-log policy — **including the disclosure that IP addresses are logged alongside endpoint paths (/upload, /result) and that within the 5-minute TTL window, someone with log access could correlate an IP with a results-page visit**; `LOG_IP_RETENTION` configuration option (full/truncated/hashed/disabled; default `hashed`); anonymous feedback mechanism description (collects non-identifying derived data: placement score, completeness, lab format — no IP, no session token, no personal data); operator contact. Linked from S1 and S2.

**S6 — Algorithm transparency page (`GET /algorithm`).** Server-rendered HTML displaying: the complete weight table with active directional compounds in one section and β-Caryophyllene in a separate "monitored but not scored" section; β-Caryophyllene's direction-neutral status and rationale; weight selection criteria (terpenes selected based on Florida COA frequency, published directional literature availability, and coverage across Russo 2011 / McPartland & Russo 2001; omitted terpenes listed with exclusion reasons); normalization formula and unit-conversion rules including THCA/CBDA derivation (DIS-15); five scoring steps including contraction (U=0.85 full, U=0.70 degraded) and rounding; uncertainty band formula; two-component confidence formula with penalty constants; degradation rules and confidence floor (0.25); literature citations with DOIs; taxonomy acknowledgment; plain statement that weights are literature-derived hypotheses with clinical-informed directional assignments, not clinically validated truth; statement that reference maxima are operator-informed estimates, not statistical maxima. No JavaScript required. Linked from S2, S4, S5.

**S7 — Health and readiness endpoints.** `GET /healthz` returns 200 with version (git tag) when alive, config loaded, weights loaded, and copy-lint clean at boot (or in soft-fail mode with a logged warning). `GET /readyz` returns 200 with `parser_ready`, `ocr_ready`, `heic_ready`, and `thread_pool_available` when all available; 503 otherwise. HEIC decoder absence is fatal at boot. If the thread pool queue depth exceeds `PROCESSING_THREAD_POOL_SIZE`, `thread_pool_available` is `false` and `/readyz` returns 503.

**S8 — Operator batch CLI (`python -m coa_profiler.batch`).** Entry: `python -m coa_profiler.batch --input-dir <dir> --output-dir <dir> --customer "<name>" [--branding-logo logo.png] [--skip-invalid]`. Outputs: one branded PDF per COA (using `customer_name` and `branding_logo` passed to the PDF renderer); a one-page reference sheet with entries **sorted alphabetically by input filename** (for deterministic output); successful entries show placement and confidence; failed entries show `FAILED: <filename> <error_code>`; a ZIP archive containing successful PDFs plus `failures.log`; a per-file stdout log. **`--skip-invalid` flag:** when present, files that cannot be opened or parsed at all (zero bytes, wrong magic bytes, completely unreadable) are skipped and excluded from the success/failure denominator. Files that parse but produce degraded/refusal results are NOT skipped — they count as successes because the pipeline ran. Without the flag, all files are attempted and failures count against the success rate. **Exit codes:** 0 if ≥80% of attempted COAs succeed, 1 if <80%, 2 if all fail. Operator offline; no network calls.

**S9 — Operator evaluation CLI (`python -m coa_profiler.evaluate`).** Entry: `python -m coa_profiler.evaluate --fixtures <dir> --report <path> [--labels labels.json] [--gate]`. Outputs: JSON report with per-format field accuracy, document-level accuracy, placement range, determinism check, and — when labels supplied — binned concordance (per DIS-10's widened bins), **Spearman rank correlation using the numeric mapping** (strongly-sativa=-2, sativa=-1, balanced=0, indica=1, strongly-indica=2), and **outperform-the-labels comparison** (defined as: for each COA, the tool's binned placement is compared to Dr. S's rating; the dispensary label mapped to bins — sativa→sativa, indica→indica, hybrid→balanced — is also compared to Dr. S's rating; the tool "outperforms" labels if the tool's agreement rate with Dr. S exceeds the dispensary labels' agreement rate; the report includes both agreement rates and the difference). `--gate` exits non-zero if concordance < 80%. The labels file format: `{"ratings": [{"fixture_id": "eval_01", "drs_rating": "sativa", "second_rater_rating": "balanced", "dispensary_label": "indica", "notes": "..."}]}`. **Inter-rater consistency:** if `second_rater_rating` is provided, the report includes inter-rater agreement and flags any pair differing by ≥2 bins. If >3 of 20 pairs differ by ≥2 bins, the report prints "INTER-RATER INCONSISTENCY DETECTED" with details. **Contingency protocol** (per DIS-10): if concordance <80%, the CLI prints "FALLBACK: 3-bin system recommended (sativa {0–40}, balanced {45–55}, indica {60–100}) with 70% threshold" as a bounded reversible default. The CLI does not halt the pipeline or require operator intervention to continue.

**S10 — Copy-lint CLI (`python -m coa_profiler.copylint`).** Scans templates for banned terms at boot (fast, static templates only). In CI, additionally scans dynamically generated rationale from fixture COAs (thorough, includes full parse→score pipeline). Exits 0 if clean, non-zero on hit. Runs in CI (full scan) and at boot (static template scan only). **Boot behavior:** fatal by default (application refuses to start on copy-lint failure). When `COPYLINT_SOFT_FAIL=true` is set in `.env`, boot-time failure logs a warning but allows startup — this is for emergency operator use only and is logged as `COPYLINT_SOFT_FAIL_ACTIVE: true` at startup. The default remains fatal to enforce the no-therapeutic-claims gate. **Boot-time scan scope:** static template files only (fast, <5 seconds). **CI-time scan scope:** static templates plus dynamically generated rationale from all fixture COAs (thorough, no time budget).

## 3. Primary end-to-end journey

**Actor:** A first-time patient on a phone, arriving from Dr. S's newsletter, holding a photo of a Florida certificate.

1. **Arrive (S1).** Static page renders. Nothing persisted. The patient sees an upload zone, a one-sentence value proposition, a privacy summary, a "What is a COA?" expand-collapse, and the batch-service contact link (FR-031).

2. **Submit and process (S1 → S2).** User picks the photo. Client pre-checks file type and size; server re-validates by magic bytes (FR-001), strips EXIF (FR-002). The upload handler dispatches processing to the thread pool (FR-030): text acquisition (FR-003) → layout detection (FR-004) → cite-and-verify extraction with unit normalization and THCA/CBDA derivation (FR-005) → plausibility range checks (FR-028) → sufficiency gate (FR-006) → deterministic scoring (FR-007) → rationale rendering (FR-008) → confidence computation (FR-009). The async event loop remains free to accept other connections. On success: in-memory session created, cookie set, HTTP 303 to `/result`. On failure: HTTP 422 with typed error (S3). State: `anonymous → session open` (128-bit token, TTL 5 minutes).

3. **Value moment (S2).** Full: the bar with marker and uncertainty band (e.g., 70/100, band 65–75, indica-leaning), confidence display, explanation, verified-values table with expandable source spans and plausibility warnings, completeness badge, disclaimer, `/algorithm` link, download button, feedback buttons.

4. **Download (S4).** PDF renders in ≤2 seconds. Elapsed time from submit to download: under two minutes (AC-003).

5. **Feedback (optional, S2).** User taps "👍 Helpful" or "👎 Not helpful." `POST /feedback` records `{"helpful": bool, "placement": int, "completeness": str, "lab_format": str}` in an ephemeral in-memory aggregate — no IP, no session token, no personal data. The derived data (placement, completeness, lab_format) gives the operator actionable signal about which placements and formats are problematic. The counter is logged to stdout at shutdown and every 100 responses (FR-024).

6. **Teardown.** Cookie expiry, "Analyze another COA," or process shutdown. Temp directory and in-memory record deleted; `/result` returns 410. Startup sweep removes stale temp directories (FR-012). Nothing reaches durable store.

**Persistence boundary:** no user-data durable state. Durable state is deploy-time only: weights, templates, lexicon, configuration. Cross-restart behavioral persistence proved by determinism check (AC-016) and rebuild/restart checks (AC-018, AC-019).

**Operator journey (separate, offline):** drop certificates into a folder, run batch CLI (S8), receive PDFs plus reference sheet plus ZIP, deliver manually.

**Failure recovery within journey:**

- Upload fails (network) → client retries once; typed error with retry.
- Parser returns no usable chemistry → refusal state (S2) or complete-refusal typed error (S3).
- Parser returns partial chemistry → degraded placement with cannabinoid-ratio notice; if CC < 0.25, refusal.
- OCR error visible to user → source spans (FR-025) expose the backing text; recovery is re-uploading a better photo (editing is out of scope, DIS-3). Plausibility-flagged values (FR-028) display a warning icon when extracted values exceed expected ranges.
- PDF generation fails → error message with retry; session retained until retry succeeds or TTL expires.
- Processing exceeds timeout → typed timeout error with retry.
- Rate limit exceeded → HTTP 429 with `Retry-After` header.
- Concurrent overload → thread pool saturates; additional uploads receive HTTP 503 with `Retry-After` (FR-030).

**Visible success state:** the patient has a PDF on their device; the results page shows the spectrum bar with marker, uncertainty band, confidence display, rationale matching displayed compounds, chemotype table matching parsed values, expandable source spans, and the disclaimer.

## 4. Functional contract

- **FR-001** — Accept a single file upload via multipart POST to `/upload`. Validate by magic-byte sniffing (extension alone never trusted) that the file is PDF (`%PDF`), JPEG (`\xFF\xD8\xFF`), PNG (`\x89PNG`), or HEIC (`ftypheic`/`ftypheix`/`ftypmif1` at offset 4) and does not exceed `MAX_UPLOAD_MB` (default 15). If HEIC is detected and the decoder check has failed, reject with HTTP 422 `HEIC_UNSUPPORTED`. Other invalid inputs receive HTTP 422 with `INVALID_FILE_TYPE` or `FILE_TOO_LARGE`. On accept, dispatch processing to the thread pool (FR-030), create the in-memory session, set the session cookie, and return HTTP 303 with Location `/result`. Surface: S1. Journey step: 2. Dependency: S1.
- **FR-002** — On acceptance, normalize the uploaded content: strip EXIF and document metadata; re-encode images to a canonical working copy in the session's temp directory. Original bytes are never logged or written outside that directory. Failure to strip triggers session discard and a typed error. Surface: S1. Journey step: 2. Dependency: FR-001.
- **FR-003** — Acquire raw text from the uploaded document. For PDFs, extract the embedded text layer from **all pages** using pdfplumber, concatenating with page-break markers. If the combined text layer is empty or garbled (fewer than 50 recognizable tokens), rasterize all pages with pdf2image (requires poppler-utils) and apply OCR. For images, apply OCR directly using Tesseract with documented preprocessing: grayscale conversion, deskew (auto-angle detection up to ±15°), adaptive thresholding (block size 31, C=10), minimum 150 DPI equivalent resolution. **These preprocessing operations use OpenCV (`opencv-python-headless`)**; Pillow handles image I/O and format conversion but does not support configurable adaptive thresholding. Output raw text plus per-region confidence scores. OCR confidence threshold: mean per-region confidence below 60 triggers a typed "document unreadable" error with photo-guidance copy; a mean in [60, 75) continues processing but applies a 0.15 data-completeness penalty (FR-009). **Determinism controls:** `OMP_THREAD_LIMIT=1` environment variable and Tesseract `--psm 6` (uniform page segmentation) are set to enforce deterministic OCR output across runs. Tesseract is pinned via the Docker base image (exact package version, e.g., `tesseract-ocr=5.3.4-1`); bare-metal deployments record `tesseract --version` in the deployment log (§10 A-10). Surface: S1, S3. Journey step: 2. Dependency: FR-002.
- **FR-004** — Detect the COA layout among at least three Florida lab format families using deterministic layout signatures computed from the extracted text: (a) **Confident Cannabis style** — branding or panel header pattern; (b) **SC Labs / PhytoFacts style** — "SC Labs" or "PhytoFacts" marker; (c) **Generic OMMU-table fallback** — "Certificate of Analysis" plus a cannabinoid table with THC and CBD entries, matched by keyword-plus-numeric-value patterns. Layout is detected **per document** (not per page): the format with the strongest aggregate signature across all pages is the document-level format. Each page's compounds are extracted using that page's best-matching sub-format rules, which may differ from the document-level format. When the same compound appears on multiple pages with different values (FR-005), the value from the page whose sub-format signature most strongly matches the document-level detected format is used. Unknown layouts degrade to the generic parser with `format: unknown` recorded; if `INFERENCE_ASSIST_ENABLED` is true, the inference-assist layer (FR-026) is consulted before falling back. The generic OMMU-table fallback parser serves as the safety net for any lab format not yet explicitly modeled. Documents matching no certificate structure receive a typed refusal. **Regulatory reference:** the parser targets COAs issued under Florida OMMU testing requirements including Rule 64-4.016, F.A.C. and 64ER20-39 (§10 A-19). **Florida lab coverage:** the three targeted format families are designed to cover the majority of OMMU-issued COAs based on operator testimony; the exact lab count and per-format coverage are tracked as §10 A-21. Surface: S1, S3. Journey step: 2. Dependency: FR-003.
- **FR-005** — Extract cannabinoid and terpene panels from the combined multi-page text into a structured record using a cite-and-verify protocol: every extracted value must trace to a literal text span in the extracted document text. **Unit normalization to % w/w before storage:** `%` used directly; `mg/g` × 0.1; `mg/mL` × 0.1 (assuming density ≈ 1.0 g/mL — this approximation is tracked as §10 A-17); `ppm` × 0.0001. The original value and unit are preserved alongside the normalized value. **THCA/CBDA derivation (DIS-15):** if a COA reports THCA and delta-9 THC separately but no "Total THC" line, the parser derives `Total THC = delta-9 THC + 0.877 × THCA`. Likewise `Total CBD = CBD + 0.877 × CBDA`. The derived value is marked `derived: true` and displayed with a conversion note. If the same compound appears on multiple pages with different values, the value from the page whose sub-format signature most strongly matches the document-level detected lab format (FR-004) is used, the conflict is recorded, and the losing span is retained. Any field that cannot be verified is recorded as `unreadable` — never interpolated, defaulted, or estimated. At minimum, capture THC-total (or its derived equivalent) and CBD-total and all reported terpenes. All values must be non-negative floats; failures are `unreadable`. Zero verifiable chemistry fields escalates to FR-006 complete-refusal. Surface: S2. Journey step: 2. Dependency: FR-004.
- **FR-006** — Apply the four-outcome sufficiency gate defined in DIS-6: (a) **full placement** — ≥1 cannabinoid verified AND ≥3 terpenes verified AND ≥60% of reported terpenes readable (absolute ≥3 governs when reported total is undeterminable); (b) **degraded placement** — cannabinoids verified but terpene data insufficient, producing a cannabinoid-weighted placement (FR-007 degraded mode) with reduced confidence, a visible notice stating "This placement is based solely on cannabinoid ratios (THC:CBD), which are particularly contested predictors of effects," and a **minimum combined-confidence floor of 0.25** — if `confidence_combined < 0.25`, placement is refused even in degraded mode and the user sees a chemotype-only summary; (c) **refusal** — zero terpenes readable; (d) **complete refusal** — zero chemistry fields readable. If `total_pull == 0` (FR-007 Step 3), refusal with explanation that compounds are not in the current model. The gate outcome determines which template `GET /result` renders. Surface: S2. Journey step: 3. Dependency: FR-005.
- **FR-007** — Compute a scalar spectrum placement (integer 0–100, rounded to nearest 5; 0 = sativa-leaning, 100 = indica-leaning) using the following documented deterministic function of the verified chemistry alone. **Step 1 — Normalize:** `normalized_i = min(value_i / reference_max_i, 1.0)` on % w/w values from FR-005. **Step 2 — Directional sums:** `indica_pull = Σ(weight_i × normalized_i)` over verified indica-direction compounds; `sativa_pull` likewise. Compounds absent from the COA contribute 0 to both sums and do not affect `total_pull`. Compounds present on the COA but not in the weight table are excluded from computation, do not contribute to `total_pull`, and are listed in the rationale. Unreadable compounds are excluded and penalized in confidence (FR-009). **Step 3 — Raw score:** `total_pull = indica_pull + sativa_pull`; if `total_pull == 0`, route to refusal (FR-006); else `raw_score = (indica_pull / total_pull) × 100`. **Step 4 — Model-uncertainty contraction:** `contracted = 50 + (raw_score − 50) × U`, where `U = 0.85` for full placement and `U = 0.70` for degraded mode. **U is a tuning parameter** representing the hypothesis that literature-derived terpene-effect assignments carry substantial uncertainty. It is not a Bayesian posterior or a frequentist confidence interval. **Step 5 — Round:** `placement = round(contracted / 5) × 5`, clamped to [0, 100] — 21 distinct values. **Authoritative weight table (active directional compounds):**

  | Compound | Direction | Weight | Reference max (% w/w) | Citation |
  |---|---|---|---|---|
  | Myrcene | indica | 2.5 | 2.0 (operator-informed estimate) | Russo 2011 |
  | Linalool | indica | 1.8 | 1.0 (operator-informed estimate) | Russo 2011 |
  | Humulene | indica | 0.8 | 1.0 (operator-informed estimate) | McPartland & Russo 2001 |
  | Nerolidol | indica | 0.6 | 0.5 (operator-informed estimate) | Russo 2011 |
  | Limonene | sativa | 2.0 | 2.0 (operator-informed estimate) | Russo 2011 |
  | α-Pinene | sativa | 1.5 | 1.5 (operator-informed estimate) | McPartland & Russo 2001 |
  | β-Pinene | sativa | 1.0 | 1.0 (operator-informed estimate) | McPartland & Russo 2001 |
  | Terpinolene | sativa | 1.5 | 0.8 (operator-informed estimate) | Russo 2011 |
  | Ocimene | sativa | 1.0 | 0.5 (operator-informed estimate) | McPartland & Russo 2001 |
  | THC-total | indica | 0.5 (weak directional prior) | 30.0 (operator-informed estimate) | Russo & Marcu 2017 |
  | CBD-total | sativa | 0.5 (weak directional prior) | 20.0 (operator-informed estimate) | Russo & Marcu 2017 |

  **Monitored but not scored:**

  | Compound | Direction | Weight | Reference max | Citation | Note |
  |---|---|---|---|---|---|
  | β-Caryophyllene | neutral | 0.0 | — | Gertsch et al. 2008 | CB2 agonism; no sedative/indica directional evidence |

  **Weight selection criteria (documented in `docs/algorithm.md`):** terpenes were selected based on (a) frequency of appearance on Florida COAs, (b) availability of published directional literature in Russo 2011 or McPartland & Russo 2001, and (c) coverage across at least two independent sources. β-Caryophyllene is listed as monitored but not scored because it is abundant on most COAs but its cited literature (Gertsch et al. 2008) addresses anti-inflammatory CB2 agonism, not sedative or indica-direction effects. Omitted terpenes (bisabolol, eucalyptol, camphene, farnesene, valencene, geraniol) lack published directional assignments in the cited literature; they are extracted, displayed in the chemotype summary, and listed in the rationale as "additional compounds present on your COA not included in the current model." THC/CBD directions are explicitly labeled weak priors and tuning parameters. Reference maxima are operator-informed estimates based on typical Florida COA ranges observed in Dr. S's practice, not statistical maxima; they are tuning parameters subject to validation (§10 A-01). **Degraded mode:** only THC-total and CBD-total participate (weights 0.5 each, directions as above), with `U = 0.70`, an additional 0.30 data-completeness penalty (FR-009), and the notice that placement is based solely on cannabinoid ratio (DIS-6). No strain name, dispensary label, crowdsourced rating, runtime dataset, or external data source participates. The table above is the authoritative weight specification: `scorer/weights.py` must contain it as a literal dictionary, `docs/algorithm.md` (FR-020) must reproduce it exactly, and the `/algorithm` page (FR-023) must render it. Surface: S2. Journey step: 3. Dependency: FR-006.
- **FR-008** — Generate a plain-language rationale identifying the top two or three compounds (by absolute `weight × normalized value`) driving the placement. Output templated, non-therapeutic sentences naming each compound, its value and unit as reported on the COA, and its directional contribution. β-Caryophyllene (weight 0.0) appears in the rationale as "present but not directionally scored pending better literature support." All generated rationale must pass the copy-lint filter (FR-010); the copy-lint CLI exercises the generator over fixture COAs in CI (FR-019). Surface: S2. Journey step: 3. Dependency: FR-007.
- **FR-009** — Compute a two-component confidence indicator. **Data completeness (DC):** `DC = max(0.0, 1.0 − 0.15×min(2, unreadable expected cannabinoids) − 0.10×min(5, unreadable reported terpenes) − 0.20×[readable terpenes < 5] − 0.15×[OCR mean confidence in [60,75)] − 0.30×[degraded mode])`, where expected cannabinoids are THC-total and CBD-total. The penalty constants are tuning parameters selected to produce meaningful confidence variation across realistic data-quality scenarios; they are documented in `docs/algorithm.md` and subject to recalibration (§10 A-12). **Model confidence (MC):** a **tuning parameter** fixed at 0.75 at launch — decoupled from the contraction factor U (which is 0.85/0.70). MC is not a Bayesian posterior or a frequentist confidence interval; it is a judgment by the operator that the literature-derived weights carry moderate but not high reliability. MC may be raised to 0.85 only after the held-out evaluation shows concordance ≥ 90%, and any change requires updating `docs/algorithm.md` and `/algorithm`. **Combined confidence:** `CC = DC × MC`. **Minimum confidence floor for degraded mode:** if `CC < 0.25`, placement is refused even in degraded mode (FR-006). Display format: "Data completeness: X%. Model confidence: Y%. Combined: Z%." The results page states: "Confidence reflects data completeness and a judgment about the published evidence — not the certainty of your individual experience." All three values are embedded in the PDF. Surface: S2. Journey step: 3. Dependency: FR-005, FR-007.
- **FR-010** — Enforce a banned-lexicon filter on all user-visible output (web pages, PDF content, and dynamically generated rationale text). Banned terms include but are not limited to: "treat," "cure," "prescribe," "dosage," "dose," "therapy," "diagnosis," "symptom," "relief," "benefit," "effective for," "recommended for," "condition," "sedating," "sedation," "alertness," "cerebral." The list lives in `lexicon.py` and is enforced at template render time and on generated rationale strings. **Standing disclaimer (rendered on S2, in the PDF, and on `/algorithm`, verbatim):** "This placement is a chemistry-derived tendency, not an effect prediction, not medical advice, and not a guarantee of any experience. The sativa and indica categories are morphological classifications, not validated chemical or effect categories; the framework is a simplification of complex chemotype–effect relationships that are not fully established in clinical science. The weights come from published terpene-effect hypotheses, not clinical trials. Published studies suggest that strain labels often correlate poorly with chemical composition — which is why this tool reads chemistry, not labels. Use this placement as one input among many, not as a predictor of your individual response." Surface: S2, S4, S6. Journey step: 3. Dependency: all output-producing FRs.
- **FR-011** — Generate a one-page US-Letter PDF (PDF 1.4 compatible, embedded fonts, no external resources, <500 KB) containing: tool name; scorer version (git tag) and weights-file hash (SHA-256 of `weights.py`); numeric placement (rounded to nearest 5) with spectrum graphic and uncertainty band; two-component confidence breakdown; chemotype summary (values and units as reported); dominant terpenes; rationale text; unreadable-field list; plausibility-flagged values with warning; completeness badge; the standing disclaimer (FR-010); "Free public tool" footer; and the `/algorithm` reference line. **No generation timestamp is embedded** — neither visible nor in varying metadata; invariant mode fixes document metadata so identical inputs produce byte-identical PDFs (FR-022). The PDF is generated on demand within the active session. The PDF renderer accepts optional `customer_name` (string) and `branding_logo` (file path) parameters for batch CLI branded PDF generation (FR-017); these are `None` for public-tool PDFs. A partial or corrupt PDF is never delivered. Surface: S4. Journey step: 4. Dependency: FR-007, FR-008, FR-009.
- **FR-012** — Maintain an in-memory session per upload, identified by a 128-bit cryptographically random token (`secrets.token_hex(16)`) carried in an `HttpOnly`, `SameSite=Strict` cookie named `session`. The `Secure` flag is controlled by `SESSION_COOKIE_SECURE` (default `true`; set to `false` for HTTP development and smoke testing). TTL configurable via `SESSION_TTL_SECONDS` (default 300). The session stores the parsed chemistry, placement, rationale, confidence, and working-copy path. **Passive expiration cleanup:** a background `asyncio` task sweeps expired sessions every 60 seconds and logs `session_sweeper: cleaned=<N>, remaining=<M>` to stdout. Teardown occurs on TTL expiry, on a new upload, or when the user taps "Analyze another COA." After teardown, `/result` and `/result/profile.pdf` return HTTP 410 and the working copy is deleted. At application startup, any temp directory matching the `coa_profiler_session_*` prefix is swept. Surface: S2, S4. Journey step: 6. Dependency: FR-001.
- **FR-013** — Enforce zero server-side retention of user data: no database, no persistent file storage, no logs containing COA file contents, parsed values, or session tokens. Session tokens live in cookies rather than URLs, so access logs record clean endpoint paths. **IP logging policy:** access logs record IP address, timestamp, endpoint path, HTTP status, and response time. `LOG_IP_RETENTION` configuration option controls IP handling: `hashed` (default — SHA-256 with daily salt), `full` (raw IP, for debugging), `truncated` (last octet zeroed), or `disabled` (no IP). Cookie headers are excluded from log formats. `Referrer-Policy: no-referrer` on all responses. No analytics scripts, tracking pixels, or third-party resources. No cookies other than the session cookie. **Privacy disclosure:** S5 acknowledges that within the 5-minute TTL, someone with log access could correlate an IP with a `/result` visit; operators may configure `LOG_IP_RETENTION=disabled` to mitigate. Surface: S2, S4, S5. Journey step: 6. Dependency: FR-012.
- **FR-014** — Apply per-IP in-memory rate limiting on the upload endpoint (`RATE_LIMIT_PER_MINUTE`, default 20) and the feedback endpoint (`FEEDBACK_RATE_LIMIT_PER_MINUTE`, default 10). **When `TRUSTED_PROXY_HEADER` is configured (e.g., `X-Forwarded-For`), the app reads the real client IP from that header** instead of the socket peer address (which is `127.0.0.1` behind Nginx). Nginx must be configured to set the header. Without the trusted header configured, the app uses the socket peer address. Rate-limited requests receive HTTP 429 with a `Retry-After` header. State is in-memory and resets on restart (§10 A-11). Surface: S1. Journey step: 2. Dependency: FR-001.
- **FR-015** — Enforce absence of authentication, payment, subscription, and account-management code in the repository via build-time grep + AST scan and runtime behavioral probes (AC-013). The repository shall contain no Python modules implementing login, registration, payment, billing, subscription, or account-management endpoints, surfaces, or logic. No login endpoints, no user database tables, no payment processor integrations, no billing code, and no subscription logic may exist. Any HTTP request to a path matching `/login`, `/register`, `/checkout`, `/admin`, `/accounts*`, `/billing*` shall return HTTP 404. Surface: S1, S2, S7. Journey step: 1–6. Dependency: §6 repository inventory.
- **FR-016** — Provide health and readiness endpoints. `GET /healthz` returns 200 with version (git tag) when the process is alive, config loaded, weights loaded, and copy-lint clean at boot (or in soft-fail mode with a logged warning). `GET /readyz` returns 200 with `parser_ready`, `ocr_ready`, `heic_ready`, and `thread_pool_available` when all available; 503 otherwise. `thread_pool_available` is `false` when the thread pool queue depth equals or exceeds `PROCESSING_THREAD_POOL_SIZE`, indicating saturation. HEIC decoder absence is fatal at boot (DIS-9). Surface: S7. Journey step: —. Dependency: S7.
- **FR-017** — Provide an operator-only batch CLI (`python -m coa_profiler.batch`) that processes a directory of COA files through the identical parse→score→PDF pipeline, producing one branded PDF per COA (using `customer_name` and optional `branding_logo` parameters passed to the PDF renderer per FR-011); a one-page reference sheet with entries **sorted alphabetically by input filename** (deterministic ordering for byte-identical output across runs); successful entries show placement and confidence; failed entries show `FAILED: <filename> <error_code>`; a ZIP archive containing successful PDFs plus `failures.log`; and a per-file stdout log (`PASS: <file> score=<int>` / `FAIL: <file> <error_code>`). **`--skip-invalid` flag:** when present, files that cannot be opened or parsed at all (zero bytes, wrong magic bytes, completely unreadable) are skipped and excluded from the denominator. Files that parse but produce degraded/refusal results are NOT skipped — they count as successes. Without the flag, all files are attempted. **Exit codes:** 0 if ≥80% of attempted COAs succeed, 1 if <80%, 2 if all fail. Offline; no network calls; always uses parser-only output. Surface: S8. Journey step: Operator. Dependency: FR-003 through FR-011.
- **FR-018** — Provide an operator-only evaluation CLI (`python -m coa_profiler.evaluate`) that runs the scorer over a held-out fixture set and emits a JSON report containing: per-format field accuracy, document-level accuracy, placement range and standard deviation, determinism check results, and — when a labels file is supplied — binned directional concordance (per DIS-10's widened bins), **Spearman rank correlation using the numeric mapping** (strongly-sativa=-2, sativa=-1, balanced=0, indica=1, strongly-indica=2), and **outperform-the-labels comparison** (defined as: for each COA, the tool's binned placement is compared to Dr. S's rating; the dispensary label mapped to bins — sativa→sativa, indica→indica, hybrid→balanced — is also compared to Dr. S's rating; the tool "outperforms" labels if the tool's agreement rate with Dr. S exceeds the dispensary labels' agreement rate; the report includes both agreement rates and the difference). `--gate` exits non-zero if concordance < 80%. **Inter-rater consistency:** if `second_rater_rating` is provided in the labels file, the report includes inter-rater agreement and flags pairs differing by ≥2 bins. If >3 of 20 pairs differ by ≥2 bins, the report prints "INTER-RATER INCONSISTENCY DETECTED" with details. The `--gate` flag exits non-zero if concordance < 80% regardless of inter-rater status. **Contingency protocol:** if concordance <80%, the CLI prints "FALLBACK: 3-bin system recommended (sativa {0–40}, balanced {45–55}, indica {60–100}) with 70% threshold" as a bounded reversible default. Surface: S9. Journey step: Operator. Dependency: FR-007.
- **FR-019** — Provide a copy-lint CLI (`python -m coa_profiler.copylint`) that scans templates for banned terms at boot (static templates only, fast) and scans templates plus dynamically generated rationale from fixture COAs in CI (full pipeline). Exits 0 if clean, non-zero on hit. **Boot behavior:** fatal by default (application refuses to start). When `COPYLINT_SOFT_FAIL=true`, boot-time failure logs a warning but allows startup — for emergency operator use only, logged as `COPYLINT_SOFT_FAIL_ACTIVE: true`. The default remains fatal. **Boot-time scan scope:** static template files only (fast, <5 seconds per AC-043). **CI-time scan scope:** static templates plus dynamically generated rationale from all fixture COAs (thorough, no time budget). Surface: S10. Journey step: —. Dependency: FR-010.
- **FR-020** — Maintain algorithm documentation (`docs/algorithm.md`) describing the scoring function, the weight table (reproduced exactly from FR-007), weight selection criteria, normalization and unit-conversion rules including THCA/CBDA derivation, the model-uncertainty factor and its rationale, the rounding policy, the uncertainty band formula, the two-component confidence formula with penalty constants, the degradation rules and confidence floor, the taxonomy acknowledgment, the classification of reference maxima as operator-informed estimates, and literature citations with DOI or PubMed identifiers. This file is the authoritative human-readable reference. Surface: docs. Journey step: —. Dependency: FR-007.
- **FR-021** — Serve a public privacy page at `GET /privacy` with the content specified in S5, including the session TTL, teardown behavior, EXIF disclosure, cookie description, **access-log IP correlation disclosure**, `LOG_IP_RETENTION` options (default `hashed`), feedback mechanism description (including the non-identifying derived data collected), and operator contact. Surface: S5. Journey step: —. Dependency: S5.
- **FR-022** — Guarantee cross-restart determinism: the same input COA processed by the same code version, the same weights, the same pinned Tesseract version, `OMP_THREAD_LIMIT=1`, `--psm 6`, and the same Docker image digest on the same machine architecture must produce an identical placement, identical rationale, and a **byte-identical PDF**. The PDF embeds no generation timestamp (FR-011); provenance is the scorer version string (git tag, fixed at build time) and weights-file hash (SHA-256 of `weights.py`). **Determinism guarantee applies only when `INFERENCE_ASSIST_ENABLED=false` and on the same Docker image and machine architecture**; when enabled, OCR is still deterministic but inference-assist output may vary by provider response. Any non-determinism in placement, rationale, chemotype values, or PDF bytes within the same environment is a defect. Surface: S4, S8. Journey step: 4. Dependency: FR-007, FR-011.
- **FR-023** — Serve a public algorithm transparency page at `GET /algorithm` (S6) displaying the complete weight table with active directional compounds and a separate "monitored but not scored" section for β-Caryophyllene, β-Caryophyllene's direction-neutral status, weight selection criteria, normalization and unit-conversion rules, five scoring steps, uncertainty band formula, two-component confidence formula, degradation rules, literature citations, taxonomy acknowledgment, and classification of reference maxima as operator-informed estimates. Server-rendered Jinja2; no JavaScript required. Linked from S2, S4, S5. Surface: S6. Journey step: —. Dependency: FR-007, FR-020.
- **FR-024** — Provide an anonymous feedback endpoint (`POST /feedback`) accepting JSON `{"helpful": true|false, "placement": int, "completeness": str, "lab_format": str}` from the session-cookie holder. Schema validation: `helpful` is required boolean; `placement` must be int 0–100; `completeness` must be one of {"full", "degraded", "refusal"}; `lab_format` must be a string ≤50 chars. Out-of-range values are rejected with HTTP 422. Rate-limited per FR-014. The `placement`, `completeness`, and `lab_format` fields are non-identifying derived data — computed integers and strings with no link to identity, IP, or personal data. The endpoint stores an in-memory aggregate record per `(completeness, lab_format)` bucket with helpful_yes/helpful_no counts, plus a global aggregate. No session ID, no IP, no chemistry data, no personal data is stored. Returns HTTP 204. The aggregate is logged to stdout at shutdown and every 100 responses as `feedback_summary: {global: {yes: N, no: M}, buckets: [{"completeness": "full", "lab_format": "confident_cannabis", "yes": A, "no: B}]}`. Ephemeral by design; resets on restart. Surface: S2. Journey step: 5. Dependency: FR-012.
- **FR-025** — Display per-field source spans on the results page (S2): each verified chemistry field includes an expandable `<details>` element showing the literal extracted text backing the value, with the reported unit preserved. Derived values (THCA/CBDA) show the conversion formula. Source spans are also present in evaluation CLI output for audit. Surface: S2. Journey step: 3. Dependency: FR-005.
- **FR-026** — Provide an optional inference-assist layer for the parser, disabled by default (`INFERENCE_ASSIST_ENABLED=false`). When enabled, and only when the deterministic parser returns `format: unknown` or fewer than 50% of expected fields, the extracted text is sent to an OpenAI-compatible endpoint with a 10-second timeout; on timeout or error the deterministic result is used. **Boot-time audit log:** when `INFERENCE_ASSIST_ENABLED=true`, the application logs `INFERENCE_ASSIST_ACTIVE: true, url=<url>` at startup. When `false`, logs `INFERENCE_ASSIST_ACTIVE: false`. **Determinism and walk-away qualification:** FR-022 determinism and B0 walk-away 2 (no data transfer) are guaranteed only when `INFERENCE_ASSIST_ENABLED=false`. Enabling the fallback requires the endpoint to be operator-controlled or a separate operator decision. No test covers the enabled path (AC-017 covers the disabled path only). Surface: S1. Journey step: 2. Dependency: FR-004.
- **FR-027** — Display a client-side loading overlay on the upload page when the form is submitted: "Analyzing your COA…" with approximate stage captions rendered as a CSS/JavaScript animation. The overlay is an approximate visual aid; it disappears when the browser follows the 303 redirect; `aria-live="polite"` announces stages. Surface: S1. Journey step: 2. Dependency: S1.
- **FR-028** — Flag extracted chemistry values that exceed expected plausibility ranges and re-run format detection when systematic misextraction is detected. The system shall compare each extracted numeric chemistry value against the following thresholds: THC-total > 40%, CBD-total > 25%, any single terpene > 10%, any cannabinoid < 0%. Values exceeding these ranges shall be flagged with a warning icon on the results page (S2) and in the PDF (S4). The value is still used for scoring (it traces to the document), but the warning signals possible extraction errors to the user. If >50% of extracted values exceed plausibility ranges, the system shall re-run layout detection with the generic fallback parser; if the generic parser also produces implausible values, the result shall be downgraded to refusal with the explanation "extracted values appear inconsistent — please try a clearer photo." This does not block scoring for plausible outliers. Surface: S2. Journey step: 3. Dependency: FR-005.
- **FR-029** — Display an uncertainty band on the spectrum bar (S2) and in the PDF (S4). The band width is proportional to `1 - confidence_combined`: `band_half_width = round((1 - CC) × 20 / 5) × 5`, clamped to [5, 20]. The band is rendered as a shaded region from `max(0, placement - band_half_width)` to `min(100, placement + band_half_width)`. The display text includes the band range: "Placement: 70 of 100, indica-leaning (uncertainty band: 65–75)." The display includes the note: "Band width reflects combined confidence (data completeness and model confidence assumptions), not measurement precision." This visually communicates that the placement is not a precise point measurement. Surface: S2, S4. Journey step: 3. Dependency: FR-007, FR-009.
- **FR-030** — Offload blocking upload processing to a configurable thread pool within the single async worker. `PROCESSING_THREAD_POOL_SIZE` (default 4) controls the maximum concurrent OCR/scoring operations. When the pool is saturated, additional uploads receive HTTP 503 with `Retry-After: 30` and a "server busy" message. The async event loop remains free to accept new connections and serve non-upload requests (static pages, health checks) while OCR runs in threads. This allows up to 4 concurrent uploads within the single-worker constraint (DIS-11). Surface: S1. Journey step: 2. Dependency: FR-001.
- **FR-031** — Display a non-commercial contact link on the landing page (S1) for visitors interested in batch processing: "Need batch processing for your practice? Contact us." The link is a `mailto:` URI with a pre-filled subject ("Batch COA Profile Inquiry"). A copyable email address is displayed as visible text below the link for users whose device lacks a configured mail client. No form, no data storage, no server-side processing. This is a discovery mechanism, not commerce — it conforms to B6 `mvp_out` #5 (no payments or gating) and #6 (no commerce links) because it is a contact method, not a transaction. Surface: S1. Journey step: 1. Dependency: S1.

## 5. Data, integration, and security contract

**Data model (in-memory, per-session):**

```python
@dataclass
class ParsedField:
    name: str
    value: float | None            # normalized % w/w; None when unreadable
    original_value: float | None   # as reported on the COA, before conversion
    original_unit: str | None      # "%", "mg/g", "mg/mL", "ppm"
    status: str                    # "verified" | "unreadable"
    unreadable_reason: str | None
    source_span: str | None        # literal extracted text backing the value
    conflicting_value: bool
    derived: bool                  # True for THCA/CBDA-derived totals (DIS-15)
    plausibility_flag: bool        # True when value exceeds expected range (FR-028)
    user_flagged: bool             # always False at launch; reserved hook (DIS-3)

@dataclass
class COAChemistry:
    cannabinoids: dict[str, ParsedField]
    terpenes: dict[str, ParsedField]
    lab_format: str
    total_reported_terpenes: int | None
    ocr_mean_confidence: float | None

@dataclass
class PlacementResult:
    score: int                     # 0–100, rounded to nearest 5
    raw_score: float
    confidence_data: float         # DC, 0.0–1.0
    confidence_model: float        # MC, 0.75 at launch (tuning parameter, not statistical)
    confidence_combined: float     # DC × MC
    completeness: str              # "full" | "degraded" | "refusal"
    rationale: list[str]
    driving_compounds: list[tuple[str, float, str]]
    band_half_width: int           # uncertainty band half-width (FR-029)

@dataclass
class SessionRecord:
    session_token: str             # 128-bit hex; HttpOnly cookie only
    chemistry: COAChemistry
    placement: PlacementResult
    working_copy_path: str
    created_at: float
    ttl_seconds: int

@dataclass
class FeedbackBucket:
    completeness: str
    lab_format: str
    helpful_yes: int
    helpful_no: int
```

**Architectural hook reserved (not built, not shipping):** The `user_flagged` field on `ParsedField` (always `False` at launch) is the hook for a future operator-approved "flag this value" feature. Additionally, the session data model is designed to accommodate a future `research_opt_in: bool` field (always `False` at launch) without schema change, should the operator later define a consent workflow for anonymous data contribution. No storage architecture change would be required to add these — only the operator's concept-lock revision and the addition of the UI element. These hooks cost nothing now and prevent structural rewrites later. **No user-data-collection hooks are activated at launch; the B6 lock excludes accounts, history, and data retention.**

**Durable-state rules:** No user-data durable state exists. Durable state is deploy-time only: `weights.py`, `templates/`, `lexicon.py`, `.env`. The application starts cleanly from a fresh clone with no pre-existing user data. Behavioral persistence proved by AC-016, AC-018, AC-019.

**API and integration boundaries:**

- `POST /upload` — multipart file; processing in thread pool; 303 to `/result` with `Set-Cookie`, or 422 typed error, or 503 when pool saturated.
- `GET /result` — server-rendered; template switches on `completeness`; 410 when expired.
- `GET /result/profile.pdf` — PDF download; 410 when expired.
- `POST /feedback` — anonymous feedback with derived data; 204 No Content; rate-limited.
- `GET /privacy`, `GET /algorithm` — server-rendered pages.
- `GET /healthz`, `GET /readyz` — JSON probes.
- No CORS; same-origin only. No outbound HTTP with `INFERENCE_ASSIST_ENABLED=false`. Batch, evaluation, and copy-lint CLIs make no network calls.

**Authentication and authorization:** Not applicable — no authentication by design (B6 `mvp_in` #5). Session access is governed by possession of the 128-bit token in the HttpOnly cookie within TTL. Operator CLIs are operator-only by filesystem permissions.

**Secrets handling:** No API keys or credentials required at runtime in default configuration. `INFERENCE_ASSIST_API_KEY` read from `.env` only when enabled, never logged, optional in `.env.example`. `.env` is gitignored.

**Validation:**

- File type: magic-byte sniffing at first 16 bytes; signatures per FR-001.
- File size: enforced at `MAX_UPLOAD_MB` before processing.
- Session token: 32-character lowercase hex from cookie.
- Chemistry values: non-negative floats; failures are `unreadable`.
- Plausibility ranges: THC-total > 40%, CBD-total > 25%, terpene > 10% flagged (FR-028).
- Feedback body: boolean `helpful` required; `placement` (int 0–100), `completeness` (one of {"full", "degraded", "refusal"}), `lab_format` (str ≤50 chars) validated; out-of-range values rejected with HTTP 422.

**Privacy:** Uploaded files processed in memory and per-session temp directory; both deleted on teardown. EXIF stripped (FR-002). No analytics, tracking pixels, or third-party resources. Only functional session cookie. Access logs: IP (per `LOG_IP_RETENTION`, default `hashed`) + endpoint + timestamp + status; cookie headers excluded; `Referrer-Policy: no-referrer`. S5 discloses IP-to-endpoint correlation within TTL window.

**Retention:** Session TTL default 5 minutes. Background sweeper cleans expired sessions every 60 seconds and logs the count. On teardown, temp directory and in-memory record deleted. Startup sweep removes stale temp directories. Feedback aggregate is ephemeral and lost on restart.

**Migration needs:** Not applicable. No database; no schema migrations. Weight changes versioned in `weights.py` and `docs/algorithm.md`; scorer version (git tag) embedded in every PDF and health response.

**Multi-worker deployment note:** Production runs a **single gunicorn worker** (DIS-11) with thread-pool offload (FR-030) for up to 4 concurrent uploads. Nginx `ip_hash` sticky sessions or ephemeral Redis reserved for future scaling; Redis is volatile RAM and does not constitute durable retention.

## 6. Packaging and repository contract

**Repository layout:**

```
coa_profiler/
├── pyproject.toml              # PEP 621 metadata, dependencies, entry points
├── uv.lock                     # lock file (or requirements.txt fallback)
├── .env.example                # non-secret config template
├── .gitignore
├── Dockerfile                  # production image (pinned Tesseract, libheif, OpenCV)
├── docker-compose.yml
├── README.md
├── Makefile
├── docs/
│   └── algorithm.md            # scoring function documentation (FR-020)
├── fixtures/
│   ├── fl_coa_sample.pdf
│   ├── fl_coa_sample_expected.json
│   ├── not_a_coa.txt
│   ├── unreadable_coa.jpg
│   ├── cannabinoids_only.pdf
│   ├── no_chemistry.pdf
│   ├── multi_page_coa.pdf
│   ├── heic_sample.heic
│   ├── unit_mgg_coa.pdf
│   ├── mg_ml_coa.pdf           # mg/mL units (normalization + density approximation test)
│   ├── thca_cbda_coa.pdf       # THCA + delta-9 separate (derivation test)
│   ├── ppm_coa.pdf             # ppm units (normalization test)
│   ├── formats/
│   │   ├── confident_cannabis_coa.pdf
│   │   ├── sc_labs_coa.pdf
│   │   └── generic_ommu_coa.pdf
│   ├── batch/
│   │   ├── coa_01.pdf
│   │   ├── coa_02.pdf
│   │   ├── coa_03.pdf
│   │   ├── coa_04.pdf
│   │   └── corrupt.pdf
│   └── eval/
│       ├── eval_01.pdf
│       ├── ...
│       ├── labels.json
│       ├── labels_fail.json
│       └── expected_results.json
├── scripts/
│   ├── smoke_test.py
│   └── run_walkaway_gates.sh
└── src/
    └── coa_profiler/
        ├── __init__.py
        ├── __main__.py
        ├── config.py
        ├── lexicon.py
        ├── app.py
        ├── parser/
        │   ├── __init__.py
        │   ├── text_extract.py
        │   ├── ocr.py             # OpenCV preprocessing + Tesseract (FR-003)
        │   ├── pdf_rasterize.py
        │   ├── layout.py
        │   ├── fields.py
        │   └── inference_assist.py
        ├── scorer/
        │   ├── __init__.py
        │   ├── weights.py
        │   ├── placement.py
        │   └── rationale.py
        ├── pdf/
        │   ├── __init__.py
        │   └── render.py          # accepts optional customer_name, branding_logo (FR-011)
        ├── web/
        │   ├── __init__.py
        │   ├── routes.py
        │   ├── session.py         # includes background sweeper task with log line
        │   ├── rate_limit.py      # X-Forwarded-For support (FR-014)
        │   ├── templates/
        │   │   ├── base.html
        │   │   ├── upload.html
        │   │   ├── result.html
        │   │   ├── degraded.html
        │   │   ├── refusal.html
        │   │   ├── error.html
        │   │   ├── privacy.html
        │   │   └── algorithm.html
        │   └── static/
        │       ├── style.css
        │       └── spectrum.js     # bar + uncertainty band + loading overlay
        ├── batch.py
        ├── evaluate.py
        └── copylint.py
```

**`scripts/smoke_test.py` command interface:**

```
python scripts/smoke_test.py --fixture <path> --base-url <url> --check <full|degraded|refusal|reject>

Behavior: uploads the fixture via multipart POST with a cookie jar, follows the
303 redirect, fetches /result and /result/profile.pdf using the session cookie,
and validates content by mode:
  full     — spectrum bar present with uncertainty band; score is a multiple of 5;
             confidence display shows both components; PDF is 1 page, <500 KB,
             contains the placement, a compound name, the scorer version, and
             the weights-file hash.
  degraded — degraded badge present; cannabinoid-ratio notice present; combined
             confidence below the full-mode value; if CC < 0.25, refusal instead.
  refusal  — no spectrum bar; refusal message present; chemotype summary offered.
  reject   — upload returns HTTP 422.
Stdout on success: "PASS: <check>, score=<int|n/a>"; on failure: "FAIL: <check>, reason=<message>".
Exit codes: 0 on PASS, 1 on FAIL. PDF saved to /tmp/smoke_profile.pdf.
```

**`scripts/run_walkaway_gates.sh` checks (one PASS/FAIL line per gate):** Gate 1 — payment/auth grep + AST scan returns zero matches; Gate 2 — `.env.example` defines no required secrets, `INFERENCE_ASSIST_ENABLED` defaults false, no HTTP-client calls outside `parser/inference_assist.py`; Gate 3 — zero dataset/nonprofit references in `scorer/`; Gate 4 — copy-lint exits 0 on templates and dynamic rationale; Gate 5 — smoke test `--check full` passes and evaluation `--gate` contract is intact and `docs/algorithm.md` citations verified (AC-033); Gate 6 — zero cloud SDK imports. Exit 0 only if all six pass. **Negative injection test:** the script copies the source tree to a temp directory (`cp -r src/ /tmp/gate_test_src/`), injects a banned import (`echo "import stripe" >> /tmp/gate_test_src/coa_profiler/web/routes.py`), re-runs Gate 1 against the temp copy, confirms it fails, then discards the temp directory (`rm -rf /tmp/gate_test_src`). This proves the gates perform real checks without modifying the source tree.

**Dependency and lock manifests:** `pyproject.toml` declares all dependencies. Primary: `fastapi`, `uvicorn`, `gunicorn`, `pdfplumber`, `pytesseract`, `Pillow`, `pillow-heif` (**required**), `pdf2image`, `opencv-python-headless` (**required**, for FR-003 preprocessing), `reportlab`, `jinja2`, `pydantic`. System dependencies: `tesseract-ocr` (pinned to exact package version, e.g., `tesseract-ocr=5.3.4-1` in Dockerfile), `poppler-utils`, `libheif-dev`. Development: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `build`. Lock file: `uv.lock` (preferred) or `requirements.txt`. Dockerfile pins Tesseract to exact package version and uses a fixed base image digest where feasible. `opencv-python-headless` system dependencies: `libgl1`, `libglib2.0-0`.

**Configuration files:** `.env.example` documents all variables with defaults: `MAX_UPLOAD_MB=15`, `SESSION_TTL_SECONDS=300`, `SESSION_COOKIE_SECURE=true`, `RATE_LIMIT_PER_MINUTE=20`, `FEEDBACK_RATE_LIMIT_PER_MINUTE=10`, `PORT=8080`, `INFERENCE_ASSIST_ENABLED=false`, `INFERENCE_ASSIST_URL=`, `INFERENCE_ASSIST_API_KEY=`, `TRUSTED_PROXY_HEADER=`, `LOG_IP_RETENTION=hashed`, `PROCESSING_THREAD_POOL_SIZE=4`, `COPYLINT_SOFT_FAIL=false`. No secret values required at default configuration. Makefile targets: `install`, `dev`, `prod`, `test`, `test-unit`, `test-integration`, `test-acceptance`, `lint`, `build`, `copylint`, `gates`.

**Generated/static assets:** `style.css` and `spectrum.js` are committed source. PDFs generated at runtime. No frontend build step.

**Database migrations:** Not applicable. No database exists.

**Files constituting the runnable product:** every `.py` file under `src/coa_profiler/`, every template, every static asset, `docs/algorithm.md`, `lexicon.py`, `pyproject.toml`, and the lock file. `fixtures/`, `scripts/`, and `tests/` are required for acceptance but are not part of the runnable product.

## 7. Install, start, and test contract

**Clean-machine preconditions:**

- Python 3.11 or later
- Tesseract OCR 5.3.x (`tesseract --version`)
- poppler-utils (`pdftoppm --version`)
- libheif development libraries (`brew install libheif` on macOS; `apt install libheif-dev` on Debian/Ubuntu) — **required**
- OpenCV system libraries (`libgl1`, `libglib2.0-0` on Debian/Ubuntu) — **required** for `opencv-python-headless`
- Git
- Docker (optional)

**Install (development):**

```bash
git clone <repo-url> coa_profiler && cd coa_profiler
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# For HTTP development, set SESSION_COOKIE_SECURE=false in .env
```

**Development start:**

```bash
# With SESSION_COOKIE_SECURE=false in .env for HTTP dev
uvicorn coa_profiler.app:app --reload --port 8080
```

**Production start (bare metal on Mac Studio cluster, single worker):**

```bash
OMP_THREAD_LIMIT=1 gunicorn coa_profiler.app:app -w 1 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 --timeout 120
```

**Production start (Docker):**

```bash
docker build -t coa_profiler:latest .
docker run -p 127.0.0.1:8080:8080 --env-file .env coa_profiler:latest
```

**Automated tests:**

```bash
pytest                              # all tests
pytest tests/unit -q                # unit tests
pytest tests/integration -q         # integration tests (needs Tesseract, poppler, libheif, OpenCV)
pytest tests/acceptance -q          # mechanical acceptance matrix
ruff check src/                     # lint
python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/  # boot scan (static only)
python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/  # CI scan (full)
./scripts/run_walkaway_gates.sh     # B0 walk-away gates (includes negative injection test)
```

**Readiness probes:**

```bash
curl -sf http://localhost:8080/healthz
# {"status":"ok","version":"v0.1.0"}

curl -sf http://localhost:8080/readyz
# {"status":"ready","parser_ready":true,"ocr_ready":true,"heic_ready":true,"thread_pool_available":true}
```

**Expected ports/URLs:**

| URL | Purpose |
|---|---|
| `http://localhost:8080/` | Landing and upload page (S1) |
| `http://localhost:8080/result` | Results page (S2) |
| `http://localhost:8080/result/profile.pdf` | PDF download (S4) |
| `http://localhost:8080/privacy` | Privacy page (S5) |
| `http://localhost:8080/algorithm` | Algorithm transparency page (S6) |
| `http://localhost:8080/healthz` | Liveness probe (S7) |
| `http://localhost:8080/readyz` | Readiness probe (S7) |

**Required environment variables:**

| Variable | Default | Purpose |
|---|---|---|
| `MAX_UPLOAD_MB` | 15 | Maximum accepted upload size |
| `SESSION_TTL_SECONDS` | 300 | In-memory session TTL |
| `SESSION_COOKIE_SECURE` | true | Secure flag on session cookie (set false for HTTP dev) |
| `RATE_LIMIT_PER_MINUTE` | 20 | Per-IP upload rate limit |
| `FEEDBACK_RATE_LIMIT_PER_MINUTE` | 10 | Per-IP feedback rate limit |
| `PORT` | 8080 | Server listen port |
| `INFERENCE_ASSIST_ENABLED` | false | Enable LLM-assisted parsing fallback |
| `INFERENCE_ASSIST_URL` | (empty) | OpenAI-compatible endpoint URL |
| `INFERENCE_ASSIST_API_KEY` | (empty, optional) | Credential for inference endpoint |
| `TRUSTED_PROXY_HEADER` | (empty) | Header name for real client IP behind proxy (e.g., `X-Forwarded-For`) |
| `LOG_IP_RETENTION` | hashed | IP logging mode: hashed/full/truncated/disabled |
| `PROCESSING_THREAD_POOL_SIZE` | 4 | Max concurrent upload processing threads |
| `COPYLINT_SOFT_FAIL` | false | Allow startup with copy-lint warnings (emergency only) |

No secret environment variables required at default configuration.

## 8. Deployment and operations contract

**Deployment shape:** Self-hosted on the operator's Mac Studio cluster node. Nginx terminates TLS and proxies to `127.0.0.1:8080` with `proxy_read_timeout 120s`, `proxy_set_header X-Forwarded-For $remote_addr`, and `proxy_set_header X-Real-IP $remote_addr`. **Single gunicorn worker** with thread-pool offload (DIS-11, FR-030). No cloud platform, no CDN, no third-party hosting. Domain registration through a registrar that does not exclude cannabis-related domains, verified pre-deployment (§10 A-16).

**Build artifacts:**

- Bare metal: installed Python package; no compiled artifacts.
- Docker: `coa_profiler:{tag}` built from Dockerfile (`python:3.11-slim-bookworm` base with fixed digest where feasible; `tesseract-ocr` pinned to exact package version e.g., `tesseract-ocr=5.3.4-1`; `poppler-utils`; `libheif-dev`; `libgl1`; `libglib2.0-0`; Python dependencies via pip). `OMP_THREAD_LIMIT=1` set in the Dockerfile ENV.

**Environment configuration:** `.env` in working directory; all values non-secret at default. Nginx site config proxying HTTPS to `127.0.0.1:8080` with `X-Forwarded-For` header; TLS via Let's Encrypt / certbot; Nginx passes through `Referrer-Policy: no-referrer` and never logs cookie headers. `TRUSTED_PROXY_HEADER=X-Forwarded-For` set in `.env` for production so rate limiting sees real client IPs.

**Health checks:**

- Liveness: `GET /healthz` — 200 = alive, config loaded, weights loaded, copy-lint clean (or soft-fail logged).
- Readiness: `GET /readyz` — 200 = parser, OCR, HEIC decoder available and thread pool not saturated; 503 otherwise.
- Nginx upstream health check on `127.0.0.1:8080` at 30s intervals.

**Logs and metrics:**

- Access log: IP (per `LOG_IP_RETENTION`, default `hashed`), timestamp, endpoint path, HTTP status, response time (ms). Cookie headers excluded.
- Application log: startup events, copy-lint result, inference-assist audit (`INFERENCE_ASSIST_ACTIVE: true/false`), rate-limit hits, OCR confidence warnings, session teardown/sweep events (including `session_sweeper: cleaned=<N>, remaining=<M>` log line every 60s), HEIC decoder status, thread-pool saturation events, feedback counter summary at shutdown. No user data.
- Destination: stdout/stderr (systemd journal or Docker logs). No log files to disk.
- Metrics: none at launch. Minimum viable monitoring: cron job curling `/healthz` every 5 minutes with email alert on non-200. Post-launch: periodic evaluation-CLI runs for drift detection (§10 A-09).

**Backup and restore:** Not applicable — no durable user data. Deploy-time files version-controlled in Git; recovery is `git checkout`.

**Rollback:**

```bash
# Docker
docker stop coa_profiler && docker run -d --name coa_profiler -p 127.0.0.1:8080:8080 --env-file .env coa_profiler:{previous_tag}

# Bare metal
git checkout {previous_tag}
pip install .
OMP_THREAD_LIMIT=1 gunicorn coa_profiler.app:app -w 1 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 --timeout 120
```

**Smallest deploy procedure exercisable by a test:**

```bash
git pull && pip install .
OMP_THREAD_LIMIT=1 gunicorn coa_profiler.app:app -w 1 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 --timeout 120 &
sleep 2
curl -sf http://localhost:8080/healthz
# Expected: {"status":"ok","version":"..."}
python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf --base-url http://localhost:8080 --check full
# Expected: PASS: full, score=<int>
```

## 9. Mechanical acceptance matrix

| ID | Proves | Setup | Command / action | Expected observable | Evidence |
|---|---|---|---|---|---|
| AC-001 | Clean install with functional modules | Fresh clone; Python 3.11+; Tesseract 5.3.x, poppler-utils, libheif, OpenCV libs installed | `pip install -e ".[dev]"` then `python -c "from coa_profiler.parser import parse_coa; r=parse_coa('fixtures/fl_coa_sample.pdf'); assert r.lab_format is not None; print('OK', coa_profiler.__version__)"` | Both commands exit 0; version printed; `lab_format` is a non-None string (proves real parsing, not stub) | Exit codes, stdout |
| AC-002 | Start, readiness, and truthful readiness | Installed package; default config (`SESSION_COOKIE_SECURE=false` for test) | `gunicorn coa_profiler.app:app -w 1 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 &` then `curl -sf http://localhost:8080/readyz` then `python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf --base-url http://localhost:8080 --check full` | `/readyz` returns 200 with all true including `thread_pool_available`; subsequent upload succeeds, proving readiness was truthful | curl body, smoke test exit code |
| AC-003 | Complete primary journey: valid COA → full placement → PDF, within time budget | Running app; `fixtures/fl_coa_sample.pdf` + `fl_coa_sample_expected.json` | `time python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf --base-url http://localhost:8080 --check full` | Exit 0; `PASS: full, score=<int multiple of 5>`; PDF exists; score and one compound match expected JSON; PDF contains scorer version and weights hash; wall time < 2 minutes | Exit code, stdout, PDF file, timing |
| AC-004 | Results page renders bar, uncertainty band, rationale, chemistry, confidence, and source spans | Active session from AC-003 | `curl -sf -b /tmp/smoke_cookies http://localhost:8080/result \| grep -cE 'spectrum-bar\|uncertainty\|rationale\|chemistry\|details\|Data completeness'` and confirm page contains expected THC value | ≥6 element matches including "uncertainty"; page contains specific THC value; at least one `<details>` source-span element | grep count, HTML excerpt |
| AC-005 | PDF is a valid one-page document under 500 KB with substantive content including version/hash | PDF from AC-003 | `pdfinfo /tmp/smoke_profile.pdf \| grep Pages && stat -c%s /tmp/smoke_profile.pdf && pdftotext /tmp/smoke_profile.pdf - \| grep -cE 'placement\|chemistry-derived\|Myrcene\|v[0-9]'` | Pages: 1; size < 500000; ≥4 content matches including placement, disclaimer phrase, compound name, and a version string pattern | pdfinfo, file size, pdftotext |
| AC-006 | Session alive within TTL, expires after, no residue; two consecutive uploads produce distinct results | App running with `SESSION_TTL_SECONDS=3` and `SESSION_COOKIE_SECURE=false` | Upload fixture A; verify `/result` 200; upload fixture B (different COA) with same cookie jar; verify `/result` shows B's values not A's; `sleep 5`; verify 410; `ls /tmp/coa_profiler_sessions/ 2>/dev/null \| wc -l` | First: 200 with A's data; after B upload: 200 with B's data (different values); after TTL: 410; temp directory count: 0 | HTTP codes, HTML content, directory listing |
| AC-007 | Invalid file type rejected by magic bytes (not extension); valid file accepted | Running app; `fixtures/not_a_coa.txt`; a `.pdf`-extension file containing plain text; `fixtures/fl_coa_sample.pdf` | `cp fixtures/not_a_coa.txt /tmp/fake.pdf && curl -s -o /dev/null -w "%{http_code}" -F "file=@/tmp/fake.pdf" http://localhost:8080/upload` then `curl -s -o /dev/null -w "%{http_code}" -F "file=@fixtures/fl_coa_sample.pdf" http://localhost:8080/upload` | First: 422 (magic bytes don't match PDF despite .pdf extension); second: 303 (valid PDF accepted) | HTTP status codes |
| AC-008 | Oversize file rejected; valid-size file accepted | Running app; `dd if=/dev/zero of=/tmp/big.jpg bs=1M count=16` | `curl -s -o /dev/null -w "%{http_code}" -F "file=@/tmp/big.jpg" http://localhost:8080/upload` then AC-003 smoke command | First: 422; second: PASS | HTTP status, smoke exit code |
| AC-009 | Unreadable document produces typed error; readable document succeeds | Running app; `fixtures/unreadable_coa.jpg`; `fixtures/fl_coa_sample.pdf` | `curl -s -F "file=@fixtures/unreadable_coa.jpg" http://localhost:8080/upload` then AC-003 smoke command | First: 422 with "unreadable"/photo-guidance; second: PASS | HTTP status, body, smoke exit code |
| AC-010 | Degraded placement with partial terpene data, reduced confidence, cannabinoid-ratio notice | Running app; `fixtures/cannabinoids_only.pdf` | `python scripts/smoke_test.py --fixture fixtures/cannabinoids_only.pdf --base-url http://localhost:8080 --check degraded` then `curl -sf -b /tmp/smoke_cookies http://localhost:8080/result \| grep -c 'cannabinoid ratio\|contested'` | Exit 0; `PASS: degraded`; HTML contains cannabinoid-ratio notice; combined confidence below full-mode value | Exit code, stdout, HTML excerpt |
| AC-011 | Refusal when zero terpenes are readable | Running app; `fixtures/no_chemistry.pdf` | `python scripts/smoke_test.py --fixture fixtures/no_chemistry.pdf --base-url http://localhost:8080 --check refusal` then `curl -sf -b /tmp/smoke_cookies http://localhost:8080/result \| grep -c 'refusal\|spectrum-bar'` | Exit 0; `PASS: refusal`; HTML contains refusal message and zero `spectrum-bar` matches | Exit code, stdout, grep counts |
| AC-012 | Copy-lint blocks banned terms in templates AND dynamic rationale | Source tree; fixtures | `python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/`; then inject a random banned term from lexicon.py (not a fixed test phrase): `python -c "import random, coa_profiler.lexicon as l; t=random.choice(l.BANNED_TERMS); print(t)" > /tmp/banned_term.txt && echo "$(cat /tmp/banned_term.txt) test" >> src/coa_profiler/web/templates/result.html && python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/; git checkout src/coa_profiler/web/templates/result.html` | Clean run: exit 0. Injected run: exit non-zero naming the injected term and its location | Exit codes, stdout |
| AC-013 | No auth, payment, or account code (grep + AST + behavioral probe) | Source tree; running app | `grep -rnEi "(stripe\|paypal\|auth_login\|user_account\|password_hash\|billing\|subscription)" src/coa_profiler/ --include="*.py" \| grep -v test` then `pytest tests/acceptance/test_no_payment_auth.py -q` then `for p in login register checkout admin; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/$p; done` | grep: zero matches; AST scan passes; all four probes return 404 | grep output, pytest result, status codes |
| AC-014 | Batch CLI produces PDFs, reference sheet with failure handling, correct exit code, and deterministic ordering | `fixtures/batch/` (4 valid + 1 corrupt = 5 files) | `python -m coa_profiler.batch --input-dir fixtures/batch/ --output-dir /tmp/batch_out --customer "Test Practice"` then `pdftotext /tmp/batch_out/reference_sheet.pdf - \| head -10` then `pdftotext /tmp/batch_out/reference_sheet.pdf - \| grep 'FAILED'` | Exit 0 (4/5 = 80% ≥ 80% threshold); reference sheet entries sorted alphabetically by filename; `corrupt.pdf` marked `FAILED: corrupt.pdf <error_code>`; ZIP includes `failures.log`; at least one PDF contains placement content | Exit code, ls output, pdftotext output |
| AC-015 | Evaluation CLI report is freshly computed (not canned) | `fixtures/eval/` with `labels.json` | Remove `expected_results.json` if present; `python -m coa_profiler.evaluate --fixtures fixtures/eval/ --labels fixtures/eval/labels.json --report /tmp/eval_report.json` then modify one rating in labels.json and re-run; verify concordance changed | Exit 0; report contains `field_accuracy`, `concordance`, `spearman` with numeric value; second run's concordance differs from first (proves fresh computation); Spearman value uses numeric mapping (-2 to +2); report includes `outperform_labels` with agreement rates | Exit code, JSON content |
| AC-016 | Determinism (byte-identical PDFs) AND input sensitivity | Two sequential batch runs on same fixtures, plus a mutated fixture | `OMP_THREAD_LIMIT=1 python -m coa_profiler.batch --input-dir fixtures/batch/ --output-dir /tmp/det1 --customer "T" --skip-invalid && OMP_THREAD_LIMIT=1 python -m coa_profiler.batch --input-dir fixtures/batch/ --output-dir /tmp/det2 --customer "T" --skip-invalid && for f in coa_01 coa_02 coa_03 coa_04 reference_sheet; do cmp /tmp/det1/$f.pdf /tmp/det2/$f.pdf; done` then verify at least two distinct placement scores among fixtures | `cmp` reports no differences for any PDF (byte-identical within same Docker image and machine); reference sheet entries sorted alphabetically (deterministic); at least two distinct scores across fixtures | cmp output, reference sheet scores |
| AC-017 | No external service dependency at runtime (default config) | Docker available; app started with `INFERENCE_ASSIST_ENABLED=false`, no API keys | `docker build -t coa_profiler:test . && docker run -d -p 127.0.0.1:8081:8080 --name coa_net coa_profiler:test && sleep 3 && docker exec coa_net python -c "import socket, threading, time; s=socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(10); s.connect(('127.0.0.1', 8080)); s.sendall(b'GET /healthz HTTP/1.0\r\nHost: localhost\r\n\r\n'); data=s.recv(4096); assert b'200' in data; print('health OK')" && python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf --base-url http://localhost:8081 --check full && docker exec coa_net sh -c "cat /proc/net/tcp \| wc -l" && docker stop coa_net` | Health check passes; smoke test PASS; `/proc/net/tcp` shows only localhost connections (no outbound to non-localhost addresses); container has no external network calls during the smoke test | Docker exec output, smoke exit code, `/proc/net/tcp` line count |
| AC-018 | Deployment smoke test via Docker | Docker available | `docker build -t coa_profiler:test . && docker run -d -p 127.0.0.1:8081:8080 --name coa_smoke coa_profiler:test && sleep 3 && curl -sf http://localhost:8081/healthz && python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf --base-url http://localhost:8081 --check full` | `/healthz` 200; smoke test PASS inside container | HTTP status, smoke exit code |
| AC-019 | Rollback to previous image with functional verification | Two tags: `coa_profiler:v1`, `coa_profiler:v2` | `docker stop coa_smoke; docker run -d -p 127.0.0.1:8080:8080 --name coa_rb coa_profiler:v1 && sleep 2 && curl -sf http://localhost:8080/healthz && python scripts/smoke_test.py --fixture fixtures/fl_coa_sample.pdf --base-url http://localhost:8080 --check full` | `/healthz` 200; smoke test PASS (proves rolled-back version is feature-complete, not just a health stub) | HTTP status, smoke exit code |
| AC-020 | Package build produces an installable wheel with functional code | Source tree | `python -m build --wheel && pip install dist/coa_profiler-*.whl && python -c "from coa_profiler.parser import parse_coa; r=parse_coa('fixtures/fl_coa_sample.pdf'); assert r.lab_format is not None; print('wheel OK', r.lab_format)"` | Wheel exists; pip install exits 0; parse succeeds with non-None lab_format (proves real code in wheel, not hollow shell) | ls dist/, pip exit code, stdout |
| AC-021 | Rate limiting is per-IP, triggers at limit, resets after window, reads X-Forwarded-For | Running app with `TRUSTED_PROXY_HEADER=X-Forwarded-For`, default limit 20/min | `for i in $(seq 1 25); do curl -s -o /dev/null -w "%{http_code}\n" -H "X-Forwarded-For: 10.0.0.1" -F "file=@fixtures/fl_coa_sample.pdf" http://localhost:8080/upload; done` then 5 requests with `X-Forwarded-For: 10.0.0.2`; then `sleep 60`; one more from 10.0.0.1 | Source A: first 20 → 303/422, 21–25 → 429; Source B: all non-429; after window, A non-429 | Status-code sequences |
| AC-022 | Privacy page accurate; session cookie correct format; no session tokens in logs | Running app with `SESSION_COOKIE_SECURE=false` | `curl -sf http://localhost:8080/privacy \| grep -cE 'no account\|no storage\|in.memory\|discarded\|HttpOnly\|IP.*correlat'`; upload and capture `Set-Cookie`; verify token is 32-char lowercase hex; fetch `/result`; inspect access log | Privacy page ≥5 matches including IP correlation disclosure; `Set-Cookie` has `HttpOnly; SameSite=Strict` (Secure only when `SESSION_COOKIE_SECURE=true`); token matches `[0-9a-f]{32}`; access log has no 32-hex token | grep counts, headers, log excerpt |
| AC-023 | Algorithm documentation exists, is substantive, matches code, and weights are actually used by scorer | Source tree | `test -s docs/algorithm.md && grep -cE 'weight\|normalize\|terpene\|cannabinoid\|Caryophyllene\|neutral\|selection\|monitored' docs/algorithm.md` then `python -c "from coa_profiler.scorer.weights import WEIGHTS; assert WEIGHTS['myrcene']['weight']==2.5; assert WEIGHTS['beta_caryophyllene']['weight']==0.0; print('weights OK')"` then `python -c "from coa_profiler.scorer import score; from coa_profiler.parser import parse_coa; r=score(parse_coa('fixtures/fl_coa_sample.pdf')); assert 0<=r.score<=100 and r.score%5==0; print('scorer OK', r.score)"` | File nonempty with ≥7 matches including "Caryophyllene", "neutral", "monitored"; code weights match FR-007 table including β-Caryophyllene=0.0; scorer produces valid 0–100 multiple-of-5 output from real fixture (proves weights are read, not lying docs) | file test, grep count, python output |
| AC-024 | Algorithm transparency page renders weight table dynamically from deployed weights | Running app | `curl -sf http://localhost:8080/algorithm \| grep -cE 'Myrcene\|Limonene\|Caryophyllene\|neutral\|weight\|Russo\|selection\|monitored'` then temporarily change myrcene weight to 3.0 in `weights.py`, restart, re-fetch `/algorithm`, verify "3.0" appears, restore | HTTP 200; ≥8 matches including "Caryophyllene", "neutral", "monitored"; after weight change, page shows 3.0 (proves dynamic rendering, not static) | HTTP status, grep count, post-change grep |
| AC-025 | Multi-page PDF COA handled correctly with cross-page extraction | Running app; `fixtures/multi_page_coa.pdf` (cannabinoids p.1, terpenes p.2) | `python scripts/smoke_test.py --fixture fixtures/multi_page_coa.pdf --base-url http://localhost:8080 --check full` then `curl -sf -b /tmp/smoke_cookies http://localhost:8080/result \| grep -cE 'THC\|Myrcene'` | Exit 0; PASS; results page shows both cannabinoid and terpene values from different pages | Exit code, stdout, grep count |
| AC-026 | HEIC upload accepted and processed; decoder absence is fatal | Running app; `fixtures/heic_sample.heic` | `curl -sf http://localhost:8080/readyz \| grep -o '"heic_ready":true'` then `python scripts/smoke_test.py --fixture fixtures/heic_sample.heic --base-url http://localhost:8080 --check full` | `heic_ready:true`; smoke test PASS on HEIC | grep output, smoke exit code |
| AC-027 | Unit normalization is correct for mg/g, ppm, and mg/mL; original units displayed | Running app; `fixtures/unit_mgg_coa.pdf` (THC as 182 mg/g), `fixtures/ppm_coa.pdf`, `fixtures/mg_ml_coa.pdf` | `python scripts/smoke_test.py --fixture fixtures/unit_mgg_coa.pdf --base-url http://localhost:8080 --check full` then `curl -sf -b /tmp/smoke_cookies http://localhost:8080/result \| grep -E '18\.2\|182 mg/g'` then `python scripts/smoke_test.py --fixture fixtures/mg_ml_coa.pdf --base-url http://localhost:8080 --check full` then `curl -sf -b /tmp/smoke_cookies http://localhost:8080/result \| grep -E 'mg/mL'` | Results page shows normalized 18.2% and source span retains "182 mg/g" for mg/g; mg/mL fixture processes and shows original unit; both PASS | Exit code, HTML excerpt |
| AC-028 | Feedback endpoint records derived data, logs no identifiers, rejects out-of-range, resets on restart | Running app; active session | Send `{"helpful":true,"placement":70,"completeness":"full","lab_format":"confident_cannabis"}` via `POST /feedback`; send `{"helpful":false,"placement":70,"completeness":"full","lab_format":"confident_cannabis"}`; send `{"helpful":true,"placement":999,"completeness":"invalid","lab_format":"x"}` (expect 422); send SIGTERM; `grep feedback_summary` the log; restart and send nothing; SIGTERM; grep again | HTTP 204 for valid; 422 for out-of-range; shutdown log shows `feedback_summary` with bucket data (yes=1, no=1 for full/confident_cannabis); no IP, no session token in log; after restart with no votes, log shows zero counts | HTTP status, log excerpts |
| AC-029 | All six B0 walk-away gates pass, with negative injection proof using temp directory | Source tree; running app | `./scripts/run_walkaway_gates.sh` | Exit 0; six `PASS` lines; the script's internal negative injection test (copies source to `/tmp/gate_test_src/`, injects `import stripe`, confirms Gate 1 fails, discards temp) passes without modifying the source tree | Exit code, gate output |
| AC-030 | Concordance gate blocks release below 80%, passes at/above; uses fresh computation | `fixtures/eval/` with `labels.json` (good) and `labels_fail.json` (inverted), renamed to neutral names `labels_a.json` / `labels_b.json` | `python -m coa_profiler.evaluate --fixtures fixtures/eval/ --labels fixtures/eval/labels_b.json --gate`; then same with `labels_a.json` | Inverted: exit non-zero with "Concordance below threshold: release blocked." and a specific concordance value <80%; correct: exit 0 with specific concordance value ≥80% (proves real computation, not filename-based switch) | Exit codes, stdout with numeric values |
| AC-031 | Copy-lint failure at boot is fatal by default; soft-fail mode works; boot scan is static-only | Source tree | Inject random banned term from lexicon into result.html; `gunicorn coa_profiler.app:app ... & sleep 2; curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/healthz`; restore file; set `COPYLINT_SOFT_FAIL=true` in `.env`; inject again; restart; check health; restore | Default: process exits non-zero (connection refused); with soft-fail: `/healthz` 200 and log shows `COPYLINT_SOFT_FAIL_ACTIVE: true`; after restore: normal startup | Exit codes, HTTP statuses, log excerpts |
| AC-032 | Layout detection identifies format families by content, not filename | Running app; `fixtures/formats/` three fixtures copied to neutral names | `cp fixtures/formats/confident_cannabis_coa.pdf /tmp/f1.pdf && cp fixtures/formats/sc_labs_coa.pdf /tmp/f2.pdf && cp fixtures/formats/generic_ommu_coa.pdf /tmp/f3.pdf && python -c "from coa_profiler.parser import parse_coa as p; print(p('/tmp/f1.pdf').lab_format, p('/tmp/f2.pdf').lab_format, p('/tmp/f3.pdf').lab_format)"` | Prints `confident_cannabis sc_labs generic_ommu` — each fixture detected by content despite neutral filenames | stdout |
| AC-033 | Algorithm citations present as DOI patterns; no unverified numeric claims in user-facing text | Source tree; `docs/algorithm.md` | `python -c "import re, pathlib; t=pathlib.Path('docs/algorithm.md').read_text(); dois=re.findall(r'10\.[0-9]{4,}/[^\s)]+', t); assert len(dois)>=4, f'Only {len(dois)} DOIs found'; print('DOIs:', dois)"` then `python -c "import pathlib; t=pathlib.Path('src/coa_profiler/lexicon.py').read_text() + pathlib.Path('src/coa_profiler/web/templates/result.html').read_text(); assert '90,000' not in t and '90000' not in t, 'Unverified numeric claim found'; print('No unverified claims')" ` | ≥4 DOI patterns found in docs/algorithm.md; "90,000" and "90000" do not appear in user-facing template or lexicon text; DOIs listed for operator verification (manual resolution is a pre-release operator checklist item, §10 A-22) | python output |
| AC-034 | THCA/CBDA derivation works when COA reports components separately | Running app; `fixtures/thca_cbda_coa.pdf` (THCA + delta-9, no Total THC line) | `python scripts/smoke_test.py --fixture fixtures/thca_cbda_coa.pdf --base-url http://localhost:8080 --check full` then `curl -sf -b /tmp/smoke_cookies http://localhost:8080/result \| grep -E 'derived\|0\.877\|Total THC'` | Exit 0; PASS; results page shows derived Total THC with conversion note | Exit code, HTML excerpt |
| AC-035 | Plausibility range check flags out-of-range values with deterministic observable | Running app; a fixture with an intentionally high value (e.g., THC 45%) | Upload fixture; `curl -sf -b /tmp/smoke_cookies http://localhost:8080/result` and parse HTML for `plausibility_flag` class or `data-plausibility="true"` attribute on the flagged field; verify JSON output from evaluation CLI includes `"plausibility_flag": true` for that field | Results page shows a warning icon or `plausibility_flag` indicator for the out-of-range value; evaluation CLI JSON confirms the flag | grep/parse output, JSON excerpt |
| AC-036 | Thread pool allows concurrent uploads; saturation returns 503; /readyz reflects saturation | Running app; `PROCESSING_THREAD_POOL_SIZE=2`; 5 concurrent uploads | `for i in $(seq 1 5); do curl -s -o /dev/null -w "%{http_code}\n" -F "file=@fixtures/fl_coa_sample.pdf" http://localhost:8080/upload & done; wait` then `curl -sf http://localhost:8080/readyz \| grep 'thread_pool_available'` | At least 2 return 303 (pool accepted); at least 1 returns 503 (pool saturated); none hang indefinitely; `/readyz` shows `thread_pool_available: false` during saturation | Status codes, readyz response |
| AC-037 | Background session sweeper cleans expired sessions and logs the count | Running app; `SESSION_TTL_SECONDS=3`; upload 3 sessions; wait 70 seconds | Upload 3 fixtures sequentially; `sleep 70`; `grep 'session_sweeper' /tmp/coa_profiler_stdout.log \| tail -1` | After 70 seconds (sweeper runs every 60s), log shows `session_sweeper: cleaned=3, remaining=0` (or similar) proving sessions were swept; no debug endpoint needed | Log excerpt |
| AC-038 | Contact link (mailto) present on landing page, copyable email visible, no form or server-side processing | Running app | `curl -sf http://localhost:8080/ \| grep -cE 'mailto:.*batch\|Contact us\|batch processing'` and `curl -sf http://localhost:8080/ \| grep -cE '[a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]*\.[a-zA-Z]{2,}'` and `grep -rn "POST.*contact\|contact_form" src/coa_profiler/ --include="*.py"` | Landing page contains mailto contact link with batch-processing text; visible email address present; grep finds zero server-side contact form handlers | grep counts |
| AC-039 | Inter-rater consistency check in evaluation CLI flags inconsistent pairs | `fixtures/eval/` with `labels.json` containing `second_rater_rating` for some entries; one pair deliberately differing by ≥2 bins | `python -m coa_profiler.evaluate --fixtures fixtures/eval/ --labels fixtures/eval/labels.json --report /tmp/eval_irr.json` then `python -c "import json; r=json.load(open('/tmp/eval_irr.json')); assert 'inter_rater' in r; print(r['inter_rater'])"` | Report contains `inter_rater` section with agreement count and flagged pairs; the deliberately inconsistent pair is flagged; report does not contain "evaluation paused" language | JSON content |
| AC-040 | Inference-assist boot-time audit log reflects actual state | App started with both `INFERENCE_ASSIST_ENABLED=true` and `false` | Start app with `INFERENCE_ASSIST_ENABLED=true` and `INFERENCE_ASSIST_URL=http://localhost:9999`; capture stdout: `OMP_THREAD_LIMIT=1 INFERENCE_ASSIST_ENABLED=true INFERENCE_ASSIST_URL=http://localhost:9999 gunicorn coa_profiler.app:app -w 1 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 2>&1 \| head -20`; stop; restart with `INFERENCE_ASSIST_ENABLED=false`; capture stdout; compare | First run stdout contains `INFERENCE_ASSIST_ACTIVE: true, url=http://localhost:9999`; second run stdout contains `INFERENCE_ASSIST_ACTIVE: false`; no log file path needed — stdout is the logging destination per §8 | stdout excerpts |
| AC-041 | Uncertainty band rendered on spectrum bar and in PDF with varying width | Active sessions from two COAs with different completeness (full and degraded) | Upload full COA and capture `/result` HTML; upload degraded COA and capture `/result` HTML; extract band range from both; compare; `pdftotext /tmp/smoke_profile.pdf - \| grep -cE 'uncertainty\|band'` | Both results page and PDF contain "uncertainty band" text with numeric range; full-mode band is narrower than degraded-mode band (proves band varies with confidence, not static) | grep counts, HTML excerpts |
| AC-042 | Citation verification gate in walk-away gates | Source tree | `./scripts/run_walkaway_gates.sh 2>&1 \| grep 'Gate 5'` | Gate 5 PASS line includes citation verification confirmation (DOI patterns present in docs/algorithm.md; no unverified numeric claims like "90,000" in user-facing templates) | Gate output |
| AC-043 | Copy-lint boot-time scan completes within performance budget | Source tree; boot-time scan runs static templates only | `time python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ 2>&1` | Exit 0 (clean templates); wall time < 5 seconds (proves boot scan is fast enough for startup); if time ≥ 5 seconds, log warning but still exit 0 if clean | Exit code, timing output |

## 10. Assumptions and nonblocking validation backlog

1. **[ASSUMPTION]** Signal sufficiency: COA chemistry yields defensible spectrum placements. **Default:** literature-derived weights (FR-007) with 0.85 contraction; Dr. S's clinical annotations informed directional assignments. **Reversible:** weights are constants in `weights.py`; change one file, update docs, re-run evaluation. **Observable:** concordance below 80% on held-out set, or failure to outperform dispensary labels. **Validation task:** Dr. S + second rater rate ≥20 held-out Florida COAs; run `evaluate --gate`; owner: operator; result: concordance ≥ 80% and tool agreement > label agreement. **Hard release blocker (AC-030); does not block construction.** **Contingency if unreachable:** CLI recommends 3-bin fallback with 70% threshold; operator may revise weights at any time; the CLI prints recommendations but does not halt.
2. **[ASSUMPTION]** Dataset rights: the nonprofit COA dataset may not be obtainable. **Default:** ship without dataset; literature weights only. **Reversible:** add dataset calibration post-launch. **Observable:** executed license or written denial. **Validation task:** confirm licensing; owner: operator; result: written license or denial.
3. **[ASSUMPTION]** COA parsing accuracy across Florida labs. **Default:** three format families + generic fallback. **Reversible:** add layout signatures; enable inference-assist. **Observable:** field accuracy < 90% on any format. **Validation task:** collect 20 COAs across 3+ labs, run evaluation CLI; owner: operator; result: ≥90% accuracy or inference-assist enabled for failing format.
4. **[ASSUMPTION]** HEIC decoding works on deployment machine. **Default:** `pillow-heif`/`libheif` required; fatal at boot if absent. **Reversible:** drop HEIC. **Observable:** `/readyz` reports `heic_ready:false`. **Validation task:** run AC-026 on Mac Studio; owner: operator; result: HEIC smoke PASS.
5. **[ASSUMPTION]** B9 unit economics are unverified 0.25-confidence hypotheses. **Default:** shape zero code; batch CLI exists per B6. **Reversible:** pricing is operator decision. **Observable:** zero sales at $250 in 8 weeks. **Validation task:** outreach to 10 practices; owner: operator; result: 4 signed commitments or documented resistance.
6. **[ASSUMPTION]** B12 slice plan absent — slice defaults to B6 `mvp_in`/`mvp_out` plus batch CLI, evaluation CLI, algorithm page, feedback, contact link. **Default:** build exactly that. **Reversible:** revise if B12 re-runs. **Observable:** qualified B12 artifact. **Validation task:** re-run B12; owner: pipeline; result: qualified artifact.
7. **[ASSUMPTION]** B8 competitive map absent — no competitive features added. **Default:** differentiation through Florida-specific parsing, cite-and-verify, Dr. S's validation, privacy, algorithm page. **Reversible:** add features post-launch. **Observable:** qualified B8 artifact. **Validation task:** re-run B8; owner: pipeline; result: qualified artifact.
8. **[ASSUMPTION]** B10 GTM plan absent — distribution defaults to organic channels. **Default:** no paid acquisition. **Reversible:** add channels. **Observable:** qualified B10 artifact. **Validation task:** re-run B10; owner: pipeline; result: qualified artifact.
9. **[ASSUMPTION]** Inference-assist not needed at launch. **Default:** disabled. **Reversible:** enable via `.env`. **Observable:** post-launch parse failure rates. **Validation task:** structured logging of parse outcomes within 30 days; enable for formats > 10% error rate; owner: operator; result: parse-outcome report.
10. **[ASSUMPTION]** Tesseract version stability supports determinism. **Default:** Docker pins exact package version (e.g., `tesseract-ocr=5.3.4-1`); `OMP_THREAD_LIMIT=1` and `--psm 6` enforce single-threaded deterministic output. **Reversible:** re-pin or redeploy. **Observable:** AC-016 fails after upgrade. **Validation task:** re-run AC-016 after any OS/Tesseract update; owner: operator; result: AC-016 passes.
11. **[ASSUMPTION]** In-memory rate-limit reset on restart is acceptable. **Default:** in-memory limiter. **Reversible:** add SQLite/Redis limiter. **Observable:** bypass during deploy windows. **Validation task:** monitor restarts for 30 days; if > 1/day, implement persistent store; owner: operator; result: restart log.
12. **[ASSUMPTION]** Confidence penalty constants are reasonable tuning parameters. **Default:** documented constants with justifications. **Reversible:** adjust in `placement.py` with docs update. **Observable:** confidence fails to correlate with concordance. **Validation task:** compute confidence–concordance correlation after each evaluation; recalibrate if < 0.3; owner: operator; result: correlation report.
13. **[ASSUMPTION]** Thread-pool concurrency (4 threads) suffices for launch throughput. **Default:** `PROCESSING_THREAD_POOL_SIZE=4`. **Reversible:** increase pool size or add workers with shared store. **Observable:** 503 rate > 5% under load. **Validation task:** load test with 5 concurrent users before launch; p95 < 60s for accepted requests; the 5th user receives 503; owner: operator; result: load-test report.
14. **[ASSUMPTION]** The ~90,000-sample label-unreliability citation (C-013) is unverified. **Default:** FR-010 disclaimer uses "published studies suggest" without specific sample count or citation until verification. **Reversible:** docs-only edit to add verified citation. **Observable:** citation verified or found wrong. **Validation task:** verify citation before launch; this is a pre-release operator checklist item; owner: operator; result: verified citation or removal.
15. **[ASSUMPTION]** Cite-and-verify traces to extracted text, not physical document. **Default:** proceed with parser-only output plus source spans and plausibility checks. **Reversible:** future operator-approved flag feature. **Observable:** "not helpful" feedback concentrated on specific formats. **Validation task:** review feedback buckets and manual sample of 20 results 30 days post-launch; owner: operator; result: verified-error rate report.
16. **[ASSUMPTION]** Registrar/DNS/certbot AUPs do not exclude cannabis work. **Default:** self-hosted with Let's Encrypt; AUP checked pre-deployment. **Reversible:** switch registrar. **Observable:** AUP language excluding cannabis. **Validation task:** read and archive AUPs before domain purchase; owner: operator; result: archived AUP excerpts.
17. **[ASSUMPTION]** mg/mL density approximation (1.0 g/mL) is adequate for COA normalization. **Default:** `mg/mL × 0.1` conversion. **Reversible:** add density parameter or per-product-type density lookup. **Observable:** COAs using mg/mL show poor concordance or user-reported mismatch. **Validation task:** track mg/mL COA outcomes separately in evaluation; if concordance on mg/mL COAs < 70%, add density correction; owner: operator; result: per-unit-type concordance report. AC-027 tests mg/mL fixture processing.
18. **[ASSUMPTION]** Single-rater evaluation (Dr. S alone) is sufficient for initial release. **Default:** Dr. S rates held-out set; second rater (second clinician or Dr. S in a separate blind pass) provides inter-rater check. A minimum interval between same-rater passes is recommended to reduce memory bias but is not enforced by the tool. **Reversible:** add more raters. **Observable:** >3 of 20 pairs differ by ≥2 bins. **Validation task:** second rater rates same set; report inter-rater agreement; if >3 inconsistencies, report warns but does not halt; operator may review protocol at their discretion; owner: operator; result: inter-rater agreement report (AC-039).
19. **[ASSUMPTION]** Florida OMMU COA format rules (64-4.016, 64ER20-39) remain stable through launch. **Default:** parser targets current format families. **Reversible:** add new layout signatures. **Observable:** OMMU rule update changes COA layout. **Validation task:** confirm current rule version before launch and after any OMMU rule change; owner: operator; result: rule version recorded in deployment log.
20. **[ASSUMPTION]** A future chemistry-native output axis (e.g., "myrcene-dominance index") may better serve patients than sativa↔indica. **Default:** ship on sativa↔indica axis as familiar communication framework. **Reversible:** add alternative axis display alongside or replacing sativa↔indica. **Observable:** user feedback or evaluation data showing sativa↔indica axis misleads more than it helps. **Validation task:** post-launch survey of 50 users on axis usefulness; owner: operator; result: survey report.
21. **[ASSUMPTION]** Florida lab format coverage: the three targeted format families cover the majority of OMMU-issued COAs based on operator testimony. The exact number of Florida OMMU-licensed testing labs is not independently verified. **Default:** three families + generic OMMU-table fallback for unmodeled formats. **Reversible:** add new layout signatures as formats are encountered. **Observable:** field accuracy < 90% on the generic fallback path, or a significant fraction of uploads hitting the generic fallback. **Validation task:** catalog all Florida OMMU-licensed testing labs, collect sample COAs from each, run evaluation CLI per lab; owner: operator; result: per-lab accuracy report and coverage percentage.
22. **[ASSUMPTION]** DOI resolution for literature citations in `docs/algorithm.md` must be manually verified before release. **Default:** automated AC-033 checks DOI patterns are present and "90,000" is absent from user-facing text; manual DOI resolution is a pre-release operator checklist item, not an automated acceptance test. **Reversible:** add automated DOI resolution check if a reliable free DOI verification API becomes available. **Observable:** DOI fails to resolve during manual check. **Validation task:** operator manually verifies each DOI resolves (Russo 2011, McPartland & Russo 2001, Gertsch et al. 2008, Russo & Marcu 2017); owner: operator; result: verified DOI list or correction.

## 11. Requirement trace and handoff

**FR-to-AC trace:**

| FR | AC | Surface | Journey step |
|---|---|---|---|
| FR-001 | AC-003, AC-007, AC-008, AC-021, AC-026, AC-036 | S1 | 2 |
| FR-002 | AC-003, AC-022 | S1 | 2 |
| FR-003 | AC-003, AC-009, AC-025 | S1, S3 | 2 |
| FR-004 | AC-003, AC-009, AC-032 | S1, S3 | 2 |
| FR-005 | AC-003, AC-010, AC-011, AC-027, AC-034 | S2 | 2 |
| FR-006 | AC-010, AC-011 | S2 | 3 |
| FR-007 | AC-003, AC-004, AC-016, AC-023 | S2 | 3 |
| FR-008 | AC-004, AC-012 | S2 | 3 |
| FR-009 | AC-004, AC-010 | S2 | 3 |
| FR-010 | AC-012, AC-031, AC-033 | S2, S4, S6 | 3 |
| FR-011 | AC-003, AC-005, AC-016, AC-041 | S4 | 4 |
| FR-012 | AC-006, AC-037 | S2, S4 | 6 |
| FR-013 | AC-006, AC-013, AC-022 | S2, S4, S5 | 6 |
| FR-014 | AC-021 | S1 | 2 |
| FR-015 | AC-013 | S1, S2, S7 | 1–6 |
| FR-016 | AC-002, AC-018, AC-036 | S7 | — |
| FR-017 | AC-014, AC-016 | S8 | Operator |
| FR-018 | AC-015, AC-030, AC-039 | S9 | Operator |
| FR-019 | AC-012, AC-031, AC-043 | S10 | — |
| FR-020 | AC-023, AC-033 | docs | — |
| FR-021 | AC-022 | S5 | — |
| FR-022 | AC-016 | S4, S8 | 4 |
| FR-023 | AC-024 | S6 | — |
| FR-024 | AC-028 | S2 | 5 |
| FR-025 | AC-004, AC-027, AC-034 | S2 | 3 |
| FR-026 | AC-017, AC-040 | S1 | 2 |
| FR-027 | AC-003 | S1 | 2 |
| FR-028 | AC-035 | S2 | 3 |
| FR-029 | AC-004, AC-041 | S2, S4 | 3 |
| FR-030 | AC-036 | S1 | 2 |
| FR-031 | AC-038 | S1 | 1 |

**Walk-away gate to AC trace:** Gate 1 → AC-013, AC-029; Gate 2 → AC-017, AC-029, AC-040; Gate 3 → AC-023, AC-029; Gate 4 → AC-012, AC-031, AC-029; Gate 5 → AC-003, AC-030, AC-033, AC-029, AC-042; Gate 6 → AC-029.

**Implementation handoff — build order:**

1. **Core library — parsing** (FR-002, FR-003, FR-004, FR-005, FR-028): `parser/text_extract.py`, `parser/ocr.py` (with OpenCV), `parser/pdf_rasterize.py`, `parser/layout.py`, `parser/fields.py`. Build against `fixtures/fl_coa_sample.pdf`; verify cite-and-verify with unit normalization, THCA/CBDA derivation, multi-page handling with sub-format conflict resolution, and plausibility checks.

2. **Core library — scoring** (FR-006, FR-007, FR-008, FR-009, FR-029): `scorer/weights.py` (including β-Caryophyllene at 0.0 in "monitored but not scored" section), `scorer/placement.py`, `scorer/rationale.py`. Implement sufficiency gate, five-step scoring with 0.85/0.70 contraction, two-component confidence with 0.25 floor, uncertainty band, and rationale generation.

3. **PDF generation** (FR-011): `pdf/render.py` with ReportLab invariant mode, accepting optional `customer_name` and `branding_logo` parameters. Verify byte-identical output via `cmp`.

4. **Copy-lint CLI** (FR-010, FR-019): `lexicon.py`, `copylint.py` with static template scan (boot, fast) and full dynamic rationale scan (CI, thorough). Verify fatal-by-default, soft-fail mode, and <5s boot budget.

5. **Web application** (FR-001, FR-012, FR-013, FR-014, FR-015, FR-016, FR-021, FR-023, FR-024, FR-025, FR-027, FR-030, FR-031): `app.py`, `web/routes.py`, `web/session.py` (with background sweeper logging session counts), `web/rate_limit.py` (with X-Forwarded-For and feedback rate limiting), templates, static assets. Wire thread-pool upload → process → results → PDF; add `/privacy`, `/algorithm`, `/feedback`, health, contact link with copyable email.

6. **Operator CLIs** (FR-017, FR-018): `batch.py` (with `--skip-invalid`, sorted reference sheet, `FAILED` formatting, branding params), `evaluate.py` (with Spearman numeric mapping, outperform-the-labels definition, inter-rater check with warning-only output, contingency protocol as recommendation, `--gate`).

7. **Algorithm documentation** (FR-020): `docs/algorithm.md` with weight selection criteria, β-Caryophyllene rationale, THCA derivation, all DOIs, reference maxima labeled as operator-informed estimates. Verify AC-023, AC-033.

8. **Deployment infrastructure** (§8): `Dockerfile` (pinned Tesseract exact version, poppler, libheif, OpenCV, `OMP_THREAD_LIMIT=1`, fixed base image digest where feasible), `docker-compose.yml`, `Makefile`, Nginx config with `X-Forwarded-For`. Verify AC-018.

9. **Acceptance and gates** (§9): `scripts/smoke_test.py`, `scripts/run_walkaway_gates.sh` (with temp-directory negative injection test), `tests/acceptance/`. Write and run the full matrix (AC-001 through AC-043). Verify `./scripts/run_walkaway_gates.sh` exits 0.

**Completion criteria:** All 43 acceptance criteria pass against a clean install on the Mac Studio cluster node. Copy-lint exits 0 (fatal by default). Walk-away gate script exits 0 (including temp-directory negative injection test and citation verification). **The evaluation `--gate` must exit 0 (concordance ≥ 80% on held-out set) before any release tag is cut; if it fails, the CLI recommends fallback to 3-bin system with 70% threshold, and the operator may revise weights or escalate at their discretion (DIS-10).** Citation verification gate (AC-033) must pass — DOI patterns present, no unverified numeric claims in user-facing text. The public tool accepts a Florida COA (PDF or phone photo, including HEIC), produces a spectrum placement with uncertainty band, two-component confidence, expandable source spans, and plausibility warnings, and delivers a downloadable PDF in under two minutes. The `/algorithm` page publicly renders the complete weight table with β-Caryophyllene's direction-neutral status in a separate "monitored but not scored" section and selection criteria. Access logs contain no session tokens. The only cookie set is the functional session cookie. No payment, authentication, or tracking code exists anywhere in the repository. Thread-pool offload allows up to 4 concurrent uploads within the single worker; `/readyz` reflects thread pool saturation. The `mailto:` contact link with copyable email is present on the landing page with no server-side form processing. IP addresses are hashed by default in access logs.

## Obligation Responses

OBL-1: ADDRESSED — FR-013 now explicitly states "Surface: S2, S4, S5. Journey step: 6." within its description, satisfying the validator's trace requirements with specific surface IDs rather than "all".
OBL-2: ADDRESSED — FR-015 now includes "Surface: S1, S2, S7. Journey step: 1–6." and is rephrased as "Enforce absence of…" with concrete action including grep + AST scan and behavioral probes, specifying paths that must return 404.
OBL-3: ADDRESSED — FR-022 now explicitly states "Surface: S4, S8. Journey step: 4." within its description, replacing the previous "all" surface and "—" journey.
OBL-4: ADDRESSED — FR-028 now includes "Surface: S2. Journey step: 3." within its description, and the opening sentence is restructured as an imperative compound action naming both behaviors.
OBL-5: ADDRESSED — FR-015 is rephrased from "Exclude all…" to "Enforce absence of… via build-time grep + AST scan and runtime behavioral probes" with concrete 404 requirements, satisfying the action_missing validator.
OBL-6: ADDRESSED — FR-028 is rephrased as "Flag extracted chemistry values that exceed expected plausibility ranges and re-run format detection when systematic misextraction is detected" with explicit "shall" imperatives for both behaviors.
OBL-7: ADDRESSED — FR-013 trace table now uses "S2, S4, S5" instead of "all", satisfying the validator's requirement for specific surface IDs.
OBL-8: ADDRESSED — FR-015 is reframed as "Enforce absence of authentication, payment, subscription, and account-management code in the repository via build-time grep + AST scan and runtime behavioral probes" — a positive enforcement action with concrete mechanism.
OBL-9: ADDRESSED — FR-015 trace table now uses "S1, S2, S7" for surface and "1–6" for journey step, replacing "(absence)" and "—".
OBL-10: ADDRESSED — FR-022 trace table now uses "S4, S8" for surface and "4" for journey step, replacing "all" and "—".
OBL-11: ADDRESSED — FR-028's opening sentence is restructured as "Flag extracted chemistry values that exceed expected plausibility ranges and re-run format detection when systematic misextraction is detected" — a single parseable compound action naming both behaviors, followed by detailed elaboration.
OBL-12: ADDRESSED — AC-014 Expected observable now reads "Exit 0 (4/5 = 80% ≥ 80% threshold); reference sheet entries sorted alphabetically by filename; corrupt.pdf marked FAILED…" — the contradictory "Exit 1" prefix is removed.
OBL-13: ADDRESSED — FR-015 rephrased as "Enforce absence of…" (positive enforcement) and FR-028 rephrased as "Flag… and re-run…" (imperative compound action), both with single executable action verbs.
OBL-14: ADDRESSED — FR-013 trace uses S2, S4, S5 / journey 6; FR-015 trace uses S1, S2, S7 / journey 1–6; FR-022 trace uses S4, S8 / journey 4 — all canonical surface IDs and valid journey steps.
OBL-15: ADDRESSED — AC-014 rewritten to a single unambiguous outcome: "Exit 0 (4/5 = 80% ≥ 80% threshold)" with clean reference sheet and failure details, no contradictory parentheticals.
OBL-16: ADDRESSED — AC-017 rewritten to run inside a Docker container using `/proc/net/tcp` inspection instead of Linux-only `strace`, making it compatible with the Mac Studio deployment target (Docker is Linux-based).
OBL-17: ADDRESSED — AC-040 now captures stdout directly from the gunicorn process instead of looking for `/var/log/coa_profiler.log`, reconciling with §8's stdout/stderr logging contract.
OBL-18: ADDRESSED — AC-037 now uses the sweeper log line (`session_sweeper: cleaned=<N>, remaining=<M>`) emitted every 60 seconds by the background task, instead of querying an undefined debug endpoint.
OBL-19: ADDRESSED — AC-033 now uses automated checks: `grep` for DOI patterns in `docs/algorithm.md` (≥4 required) and `grep` for "90,000"/"90000" absence in user-facing templates. Manual DOI resolution is moved to §10 A-22 as a pre-release operator checklist item.
OBL-20: ADDRESSED — Gate 6 walk-away trace now maps to AC-029 only (which runs the full gate script including the cloud SDK import check), removing the incorrect AC-018 mapping.
OBL-21: ADDRESSED — Florida lab landscape and coverage plan added to §1 ("Florida lab landscape and coverage plan" paragraph), FR-004 (coverage note and generic fallback safety net), and §10 A-21 (assumption with validation task to catalog all OMMU-licensed labs and measure per-lab accuracy).
OBL-22: ADDRESSED — DIS-10's ≥7-day waiting period is reframed as "A minimum interval between same-rater passes is recommended to reduce memory bias but is not enforced by the tool" — a recommendation, not a hard rule. §10 A-18 updated to match.
OBL-23: ADDRESSED — DIS-10's "evaluation is paused" human stop is replaced with "the report emits a warning 'INTER-RATER INCONSISTENCY DETECTED' with details; the operator may review the rating protocol at their discretion" — a non-blocking warning, not a pipeline halt. FR-018 and S9 updated to match. AC-039 verifies warning output without "paused" language.
OBL-24: ADDRESSED — DIS-10's 3-iteration weight-revision limit is reframed as "revise weights as needed; if concordance remains below 80%, the CLI recommends falling back to a 3-bin system… as a bounded reversible default; the operator may escalate to concept-lock revision at any time. The CLI prints these recommendations but does not halt the pipeline." FR-018 and S9 contingency protocol updated to match.
OBL-25: ADDRESSED — FR-015 rephrased as "Enforce absence of auth/payment code…" (positive enforcement with mechanism) and FR-028 rephrased as "Apply plausibility checks, flag out-of-range values, and re-run format detection…" (explicit compound action).
OBL-26: ADDRESSED — FR-013, FR-015, FR-022 trace columns now use specific surface IDs (S2/S4/S5, S1/S2/S7, S4/S8) and valid journey steps (6, 1–6, 4) instead of "all", "(absence)", and "—".
OBL-27: ADDRESSED — Florida lab count and coverage plan documented in §1, FR-004, and §10 A-21: three format families designed to cover the majority of OMMU-issued COAs with generic fallback for unmodeled formats; validation task to catalog all labs and measure coverage.
OBL-28: ADDRESSED — AC-014 expected observable rewritten to "Exit 0 (4/5 = 80% ≥ 80% threshold)" with clean details, no contradictory text.
OBL-29: ADDRESSED — AC-017 rewritten to run inside Docker container using `/proc/net/tcp` instead of `strace`, making it macOS-compatible.
OBL-30: ADDRESSED — AC-037 now uses the sweeper's stdout log line (`session_sweeper: cleaned=<N>, remaining=<M>`) instead of an undefined debug endpoint.
OBL-31: ADDRESSED — AC-040 now captures stdout from the gunicorn process instead of looking for `/var/log/coa_profiler.log`, matching §8's stdout/stderr logging contract.
OBL-32: ADDRESSED — AC-033 now uses automated `grep` for DOI patterns (≥4 required) and for "90,000"/"90000" absence; manual DOI resolution moved to §10 A-22 operator checklist.
OBL-33: ADDRESSED — All three DIS-10 human stops reframed: ≥7-day wait → recommendation (not enforced); evaluation pause → warning (non-blocking); 3-iteration limit → CLI-recommended bounded reversible default (operator decides escalation).
OBL-34: ADDRESSED — FR-015 rewritten as "Enforce absence of authentication, payment, subscription, and account-management code in the repository via build-time grep + AST scan and runtime behavioral probes" with explicit 404 requirements for `/login`, `/register`, `/checkout`, `/admin`, `/accounts*`, `/billing*`.
OBL-35: ADDRESSED — FR-028 rewritten with explicit "shall" imperatives: "The system shall compare each extracted numeric chemistry value against the following thresholds… Values exceeding these ranges shall be flagged… If >50% of extracted values exceed plausibility ranges, the system shall re-run layout detection with the generic fallback parser…"
OBL-36: ADDRESSED — FR-013 trace table now uses "S2, S4, S5" for surface and "6" for journey step, replacing "all".
OBL-37: ADDRESSED — FR-015 trace table now uses "S1, S2, S7" for surface and "1–6" for journey step, replacing "(absence)" and "—".
OBL-38: ADDRESSED — FR-022 trace table now uses "S4, S8" for surface and "4" for journey step, replacing "all" and "—".
OBL-39: ADDRESSED — FR-004 clarified: "Layout is detected per document: the format with the strongest aggregate signature across all pages is the document-level format. Each page's compounds are extracted using that page's best-matching sub-format rules." FR-005 updated to reference "the page whose sub-format signature most strongly matches the document-level detected lab format (FR-004)" — resolving the ambiguity.
OBL-40: ADDRESSED — AC-043 added to time the boot-time copy-lint (static templates only) and verify it completes in <5 seconds; FR-019 updated to separate boot scan (static only, fast) from CI scan (full, thorough).
OBL-41: DISPUTED — A `GET /api/algorithm` JSON endpoint is a discretionary enhancement proposed by one author seat (nvidia) during the seed phase (DIS-8) but not adopted by the majority. The server-rendered `/algorithm` HTML page (S6, FR-023) already provides complete algorithmic transparency with weights, formulas, citations, and selection criteria. The B6 concept lock does not require a machine-readable endpoint. Adding it is a future enhancement option, not a build-input defect.