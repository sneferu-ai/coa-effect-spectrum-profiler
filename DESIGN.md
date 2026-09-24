# DESIGN — COA Effect-Spectrum Profiler

## 0. Soul

A certificate read back to its owner, with the arithmetic showing — quiet paper, strong ink, flat surfaces, and one chromatic moment (the spectrum) per page. See `SOUL.md`: Maria, 61, Sarasota, iPhone, 9:40pm, suspicious of every tool in this space. Channeled product: **GOV.UK**. Forbidden cliches: dispensary/strain-culture styling, SaaS marketing landing, pastel health-app, dark AI cockpit.

## 1. Reference anchor

- **Reference**: https://www.gov.uk/check-state-pension — the GOV.UK service-page pattern ("Check your State Pension"), the world's most-tested plain-trust interface. One product, one URL: the GOV.UK service journey, not the GOV.UK homepage.
- **Why this one**: Maria does not need to be delighted; she needs to believe. GOV.UK is the strongest shipping proof that flat paper, one accent used sparingly, oversized readable type, native HTML controls, and brutally plain sentences produce trust in high-stakes, low-literacy-to-expert mixed audiences. This product's only persuasion is auditability — GOV.UK's entire design language is auditability.

**Five pixel-level patterns we mirror:**

1. **GOV.UK error summary / alert block.** Left border 4px in the severity color, tinted background, title + body + recovery sentence, all left-aligned, no icon dependency. We mirror this in `.alert` (§6.4 of the spec): 4px left accent `--bad`/`--warn`, `--bad-bg`/`--warn-bg` fill, reference code in micro mono at the foot.
2. **GOV.UK `<details>` disclosure component.** A small marker + underlined summary text that reads as a link, content indented with a left border when open, keyboard-native, zero JS. We mirror in "What is a Certificate of Analysis?" and every source-span row (`_chemtable.html`), with a visible focus outline on `<summary>`.
3. **GOV.UK table discipline.** No zebra striping inside the header row, thin bottom rules only (`1px solid var(--rule)`), left-aligned text, numerals in a tabular data face, and a transform to stacked cards under 640px with `data-label` pseudo-headers. Mirrored in `.chem-table` and the algorithm weight tables.
4. **GOV.UK phase-tag / status chip.** A short uppercase-free word on a tinted fill, color paired with the word always — never hue alone. Mirrored in `.chip-verified` (`--ok` on `--ok-bg`), `.chip-derived`, `.chip-unreadable`, `.chip-plausibility`.
5. **GOV.UK button geometry.** One filled primary action per screen, min-height 44px, generous horizontal padding (12×24), single radius scale, and a visible 2px focus outline offset 2px on every interactive element. Mirrored in `.btn-primary` / `.btn-ghost` with `:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; }`.

**Three deliberate divergences:**

1. **Serif display voice.** GOV.UK is sans-only (GDS Transport). Our launch-frozen brand direction (`BRAND_ASSETS/brand-direction.png`) specifies "an editorial serif voice paired with a neutral interface sans," so headings use a system serif stack (`--font-display`) while body/UI stays sans (`--font-ui`). A certificate read back to its owner is a printed document; the serif heading is the letterhead.
2. **The spectrum figure.** GOV.UK has no data-viz analog; our signature component is a gradient track with a hatched uncertainty band and marker (spec §5), three redundant encodings (fill + dashed edges + 45° hatch) so it survives grayscale, CVD, and print.
3. **No GOV.UK yellow focus ring / crown black.** Focus uses `--link` blue (spec §3.1) because the palette is already verified for AA against our warm paper tones; introducing GOV.UK yellow would collide with the sativa amber at the spectrum's left stop.

## Brand direction implementation

Board: `BRAND_ASSETS/brand-direction.png` (SHA-256 `d227f51c…16aa03b`); mark: `BRAND_ASSETS/brand-mark.png`, copied byte-exact (SHA-256 `053fd097…` verified identical) to `src/coa_profiler/web/static/brand-mark.png` and referenced from the page footer on every surface.

- **Shape** ("three converging field lines with one unmistakable center"): translated as the spectrum track itself — the amber→stone→violet field with a single decisive marker — and as the single-column layout where every section converges on one focal lane. No sidebars, no panels competing for attention.
- **Layout** ("instrument-panel density with quiet grouping and one decisive focal lane"): card sections separated by 1px `--rule` borders, tight 4/8/12/16/24/32/48/64 spacing scale, labels in small caps-ish soft ink, values in tabular mono. Density is *balanced*: rows are close, sections breathe.
- **Surface** ("matte, tactile surfaces with restrained edge contrast"): flat fills, no shadows anywhere except the loading-overlay scrim (the product's only shadow, spec §3.3). Borders do the work shadows usually do.
- **Typography** ("editorial serif + neutral sans"): `--font-display` serif stack for h1/h2; `--font-ui` system sans for body; `--font-data` mono for values, hashes, reference codes.
- **Motion** ("near-instant state changes with one slower orientation transition"): a single motion token `--move: 160ms ease-out` on dropzone/hover; the slower orientation transition is the page change itself (server-rendered, no fake progress).
- **Color**: the six launch-frozen brand tokens (`--brand-background #1C2328`, `--brand-foreground #D6D2C2`, `--brand-muted #97968E`, `--brand-primary #D6D2C2`, `--brand-secondary #888C7D`, `--brand-surface #2D3538`) are adopted verbatim in `style.css` and applied to the footer brand band — a matte dark strip carrying the mark, the "Free public tool" line, and the contact address. The main reading surfaces stay on the spec's verified light palette (D9: light theme only at launch); the dark band is a brand element, not a dark theme.

## 2. Density

**Balanced.** Instrument-panel grouping inside cards; generous section rhythm between them (40px mobile / 64px desktop). Not Linear-dense (Maria is not triaging), not Stripe.com-spacious (this is a tool, not a landing).

## 3. Color tokens

Light theme only (D9). Full table lives in `style.css :root`; roles per spec §3.1:

- Ink/paper: `--fg #232830` (≈14:1), `--fg-soft #4E5860` (≈7.4:1), `--bg #FFFFFF`, `--bg-warm #F7F5F1`, `--rule #DDD8CD`.
- Spectrum (graphics only): `--sativa #D97706` / `--sativa-ink #92400E`, `--indica #7C3AED` / `--indica-ink #5B21B6`, `--mid #9C968C`, `--shade rgba(35,40,48,.14)`, `--shade-edge #4E5860`.
- Status (always hue + word + icon): `--ok #20684A` / `--ok-bg #EDF7F0`; `--warn #7B2D1F` / `--warn-bg #FBF3F0`; `--bad #9E3524` / `--bad-bg #FBEEEB`.
- Action: `--link #1C5D9E` (links underlined AND colored; focus ring base).
- Brand (frozen, §BRAND_IDENTITY): `--brand-background #1C2328`, `--brand-foreground #D6D2C2`, `--brand-muted #97968E`, `--brand-primary #D6D2C2`, `--brand-secondary #888C7D`, `--brand-surface #2D3538` — footer brand band only.

## 4. Type tokens

- `--font-display: "Iowan Old Style", "Palatino Linotype", Palatino, Charter, Georgia, serif` (brand serif voice; system fonts only — privacy posture forbids third-party font hosts).
- `--font-ui: ui-sans-serif, system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`.
- `--font-data: "SF Mono", ui-monospace, Menlo, Consolas, monospace` + `font-variant-numeric: tabular-nums` for values/hashes/codes.
- Scale: H1 `clamp(1.625rem, 1.1rem + 2.4vw, 2.125rem)`/700/1.2 · H2 1.375rem/650/1.25 · H3 1.125rem/600/1.3 · Body 1.125rem/400/1.55 (D10) · Small .9375rem · Micro .8125rem. Prose measure ≤38rem.

## 5. Spacing tokens

`--space-1…8` = 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 px. Card padding 20px mobile / 24px ≥720px. Section gaps 40px / 64px. Radii: `--radius-sm 6px` (chips, inputs), `--radius-md 10px` (cards, buttons), `--radius-pill 999px` (spectrum track).

## 6. Component states

- **Button** (`.btn-primary` filled `--link`; `.btn-ghost` transparent + 1px `--rule`; `.btn-feedback` `--bg-warm`): default → hover (darken 6% via `--link-hover`) → focus-visible (2px `--link` outline, 2px offset) → active (`translateY(1px)`) → disabled (opacity .5, `cursor:not-allowed`, **plus visible helper text** — "Select a file to continue") → loading (button disabled + overlay with static honest message, D14).
- **Input/dropzone**: default (dashed `--rule`, `--bg-warm` wash) → hover/dragover (border `--link`, background `--ok-bg`-neutral wash, 160ms) → focus-within (2px ring) → error (border `--bad`, inline `.alert` above, form preserved).
- **Card**: flat `--bg-warm` fill, 1px `--rule` border, `--radius-md`. No shadow ever.
- **Modal (loading overlay)**: `role="dialog" aria-modal="true"`, scrim `0 10px 30px rgba(35,40,48,.22)` (the one shadow), focus trapped, static spinner, inert under reduced-motion.
- **Nav**: wordmark left, two plain links right (stacked centered ≤639px). No hamburger (D1).
- **Table**: rules-only; ≤639px transforms to stacked cards with `data-label` pseudo-headers and ARIA table roles (spec §13).
- **Badge/chip**: hue + word always; plausibility chip adds ⚠ triangle icon.
- **Toast/status**: `role="status" aria-live="polite"` inline status line in the feedback widget — "Submitting…" → "Thank you…" / "Feedback could not be recorded." No floating toasts.

## 7. Motion

One token: `--move: 160ms ease-out` (dropzone highlight, hover states). Choreographed entrance: none — server-rendered pages arrive complete; manufacturing stagger would be decoration. Loading state: the upload journey's layout is not known in advance (10–60s server processing), so an honest overlay with a static message beats a skeleton of a page that doesn't exist yet; the skeleton rule applies to content areas, and this product has no client-loaded content areas. Under `prefers-reduced-motion: reduce`, all transitions off and the spinner is static.

## 8. Voice & copy

Voice: **a careful lab technician writing to the person who owns the document** — plain sentences, exact numbers, stated limits, zero hype.

- Empty/next-action states: "Select a file to continue." · "Upload a clearer photo or PDF." · "Your certificate has readable cannabinoids, but no terpene values could be verified."
- Errors: "Unsupported file type — choose a PDF, JPEG, PNG, or HEIC. Reference: INVALID_FILE_TYPE" · "Too many uploads. Wait {n} seconds and try again. Reference: RATE_LIMITED" · "Your session has ended. Upload your COA again to get a new result. Reference: SESSION_EXPIRED"
- Buttons: "Analyze my COA" · "Download PDF profile" · "Analyze another COA"

## 9. Anti-defaults forbidden in this project

1. Dispensary/strain-culture styling: no leaf imagery (favicon is a spectrum bar), no neon green, no strain-review stars, no "kush" voice.
2. SaaS landing: no hero gradient, no KPI card row, no "Welcome back", no signup CTA, no social proof.
3. Pastel health-app: no teal/mint palette, no empathy emoji copy, no wellness illustrations.
4. Dark cockpit: no dark mode (D9), no glass blur decoration (blur is for nothing — even the overlay scrim is flat alpha), no glow.
5. Inter/Roboto as the voice; seven-color status rainbow (three status hues + one link blue, that's it); soft Tailwind drop shadows on cards (zero card shadows); rotating loading captions (D14 — dishonest); `capture` attribute forcing the camera (D7); spinner-only waits where copy can say the truth.
6. Magic values: every color/px/duration lives in `style.css :root` tokens; components consume `var(--*)` only.

## 10. Audit

Automated: `python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/` (copy lint), `pytest` (integration journey incl. acceptance hooks), `grep -R "_spectrum" templates/refusal.html` must be empty (D8), plus manual six-category walk per screen. No browser automation stack exists in this repo — manual check documented in the round summary.
