**Run-first:** Parse the B6 Concept Lock and interrogation synthesis before spec.

**Goal:** Build a free, accountless web app for Florida medical cannabis patients — reached through Dr. S's practice and book audience — that turns an uploaded Florida-format COA into a one-page PDF placing the strain on a chemistry-derived sativa↔indica effect spectrum. Labels dispensaries assign today are subjective, with no objective basis; a patient needing daytime function who brings home a sedating chemotype wastes the purchase and loses confidence in the regimen. No credible tool does this today.

**Deliverables:**
- COA upload (PDF or photo) with cannabinoid and terpene values extracted from Florida OMMU-compliant COAs; unreadable fields flagged, not guessed.
- A documented, explainable spectrum-mapping algorithm that converts the extracted chemical profile into a continuous scalar sativa↔indica placement on a single axis — a position on a spectrum, not a three-bucket label — driven solely by the COA's chemistry. No strain name, dataset lookup, or user input feeds the placement at runtime. The output must vary meaningfully across different COA chemistries; a constant or near-constant placement regardless of input is a failure.
- Visual spectrum display with plain-language rationale naming the specific terpenes and cannabinoids driving the placement, using non-therapeutic language.
- One-page PDF strain profile: scalar spectrum placement, chemotype summary (cannabinoid ratios and dominant terpenes as reported on the COA), and dominant terpenes.
- Full upload→PDF flow in a single browser session — free, no account, no login, no payment, no storage of user data.
- Florida-format (OMMU) COA parsing reliable first, validated against at least three representative lab formats.
- Batch profile packs for the B2B commercial test: compiled PDFs produced by running the same mapping pipeline offline on multiple COAs and delivering to physician or dispensary customers — no B2B portal, dashboard, multi-upload web interface, or payment infrastructure in the public tool.

**Constraints:**
- Spectrum placement computes from the uploaded COA's chemistry alone — no dataset dependence at runtime. Any calibration using historical COAs must be done offline and never invoked at run time.
- The mapping must not use strain names, dispensary labels, or any non-chemistry metadata as input — neither at runtime nor in calibration. Offline calibration may use historical COA chemistry paired with effect annotations drawn from Dr. S's clinical observations or expert chemotype-effect literature — not from crowdsourced ratings, dispensary catalogs, or any source that encodes the subjective labels the tool replaces.
- The mapping algorithm must be a real chemistry-derived function, not a placeholder or static lookup. Its logic must be documented and explainable for expert review.
- No medical, therapeutic, or dosing claims — declared kill criterion. Effect-spectrum language must stay on the objective-chemistry side of the therapeutic-claim line under Florida regulatory scrutiny.
- Unreadable fields flagged, not silently inferred. If essential data (e.g., terpenes) is missing, the tool must either refuse placement with an explanation or produce a degraded placement with a clear notice that data is incomplete. Degraded placements must not become the default path for COAs that contain readable terpene data.
- Only Florida-format (OMMU) COAs are handled at launch; out-of-state COAs are deferred.
- B2B batch packs are produced offline using the same mapping pipeline; no shared infrastructure that compromises the public tool's no-account/no-payment constraints.

**Out of scope:**
- Phase 2 chatbot, interactive Q&A, or conversational features.
- Accounts, saved profiles, upload history.
- Strain-name lookup without COA.
- Payments, subscriptions, or gated features in the public tool.
- Dispensary menus, product recommendations, commerce links, native apps.
- Medical, therapeutic, or dosing claims.
- Non-Florida COAs.
- B2B portal, dashboard, multi-upload interface, or payment handling — batch packs are produced offline.

**Acceptance:**
- A Florida patient uploads a legible photo of a typical Florida COA and, within two minutes, receives a scalar spectrum placement and a downloadable PDF containing the placement, chemotype summary, and dominant terpenes — no account, no payment.
- On a held-out test set of 20 Florida COAs — strain names redacted, dispensary labels hidden from both the evaluator and the mapping, test set not used during calibration — Dr. S rates the scalar placement as directionally correct in at least 80% of cases. The test must verify that placements vary meaningfully across the test set: if the algorithm outputs the same or near-same placement for every COA, the test fails regardless of directional accuracy. The tool's placements must also agree with Dr. S's ratings more often than the redacted dispensary labels do — the tool must outperform the labels it replaces, not merely match them.
- Unreadable fields flagged on output; no value guessed or silently substituted. COAs with readable terpene data must produce full placements, not degraded ones.
- All output text reviewed and confirmed by Dr. S to avoid therapeutic, dosing, or medical language.
- The placement algorithm runs without any external data service at runtime — it is stateless and self-contained.
- Four physician or dispensary customers purchase $250 batch profile packs within eight weeks, produced via offline runs of the same validated mapping pipeline.

**Falsification:**
- If no reproducible chemistry→effect mapping can be constructed that outperforms subjective dispensary labels on the held-out test set — where outperform means the tool's placements agree with Dr. S's ratings at a higher rate than dispensary labels do — the core premise is false; halt.
- If the mapping is found to use strain names, dispensary labels, or calibration data derived from crowdsourced ratings or dispensary catalogs as input or training signal — halt and rebuild.
- If OMMU does not mandate terpene panels on a significant fraction of COAs and no cannabinoid-only fallback produces a defensible placement — halt or redefine.
- If effect-spectrum language cannot avoid regulatory classification as a therapeutic claim under Florida law, the kill criterion is triggered.
- If the tool cannot produce a full (non-degraded) placement for more than 20% of legible Florida COA uploads from representative lab formats due to parsing errors or missing chemistry — halt or redefine.
- If a confident placement is produced from silently corrupted data (e.g., OCR misread) without the field being flagged — halt and fix.
- If the placement algorithm requires any external dataset, account, or payment to function at runtime — halt.
- If the PDF profile fails to generate for a valid upload, or the download is not offered within two minutes under normal load — halt or fix.
- If the build introduces any form of user tracking, login, or data persistence tied to an individual — halt and remove.