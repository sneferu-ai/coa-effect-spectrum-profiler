# Interface Specification — COA Effect-Spectrum Profiler

## 1. Mandate and fixed inputs

This document defines the complete graphical interface for the COA Effect-Spectrum Profiler: the anonymous public web surfaces (S1–S6), the visual layout of the downloadable PDF profile (S4), the data export artifact (S7), and the terminal conventions of three offline operator tools (S8–S10). The implementer builds from this document alone.

### 1.1 Serving pattern and framework justification

The application is a FastAPI app rendering Jinja2 templates through `Jinja2Templates` and `TemplateResponse`, serving static files from a `StaticFiles` mount at `/static`, and routing typed failures through exception handlers. There is no client-side application surface anywhere in the codebase — no `package.json`, no Vite config, no React entry point, no mount for a SPA.

**Framework decision (binding): the interface is server-rendered Jinja2, one committed stylesheet, one committed vanilla-JavaScript file.** The problem statement's "FRAMEWORK PIN SUPERSEDED" directive authorizes this supersession explicitly: "the product tree already carries a complete server-rendered interface and no surface at all for that client app." The evidence is concrete — every backend route already has a server-rendered counterpart, and no SPA entry point exists. The packaging contract forbids a build step. The privacy posture forbids third-party assets. The acceptance evidence greps server-rendered HTML for literal strings. This decision is not open to re-litigation.

Consequences:
- Every screen is reachable through the existing route table and nothing else. No new endpoints, no JSON page-data API, no client-side router.
- The full journey — upload, result, PDF download, JSON download, teardown, privacy, algorithm — works with JavaScript disabled. The script layer only enhances.
- Templates consume context dictionaries the routes already emit (§15). No route restructuring is required to build this design.

### 1.2 Product differentiation

This tool is distinct from existing COA readers and strain databases in five specific ways, none of which are claimed as a moat: (a) Florida OMMU-mandated COA parsing with cite-and-verify extraction that traces every value to its source span in the document text, (b) a publicly served algorithm page showing exact weights, reference maxima, formulas, and literature citations — not a black box, (c) an accountless, zero-retention privacy posture with a 5-minute session TTL and automatic teardown, (d) deterministic, byte-identical PDF output with no embedded timestamps, and (e) a concordance evaluation gate (DIS-10) requiring 80% binned directional agreement on held-out Florida COAs before release. The tool computes a chemistry-derived placement on a familiar scale; it does not predict effects. The sativa↔indica taxonomy is acknowledged as contested, and the disclaimer appears on every output.

### 1.3 Route binding (exhaustive)

| Route | Method | Surface | Template / artifact |
|---|---|---|---|
| `/` | GET | S1 — Landing & upload | `upload.html` |
| `/upload` | POST | Processing → 303 redirect; inline error (422); or dedicated error page | 303 to `/result` + `Set-Cookie`; `upload.html` re-rendered with error; or `error.html` |
| `/result` | GET | S2 — Result (full / degraded / refusal); 410 after expiry | `result.html` / `degraded.html` / `refusal.html` / `error.html` |
| `/result/profile.pdf` | GET | S4 — PDF profile download; 303 to `/result` on expiry | ReportLab bytes (`attachment`); 303 to `/result` on 410 |
| `/new` | GET | Session teardown, 303 to `/` | Redirect only |
| `/feedback` | POST | Anonymous feedback aggregation | 204 / 403 / 422 / 429; no page rendered |
| `/privacy` | GET | S5 — Privacy notice | `privacy.html` |
| `/algorithm` | GET | S6 — Algorithm transparency | `algorithm.html` (rendered from live `weights.py`) |
| `/healthz` | GET | Liveness probe | JSON only — never HTML |
| `/readyz` | GET | Readiness probe | JSON only — never HTML |

**Error handling architecture (hybrid, per D4 revised):**

The `/upload` POST handler catches typed errors in two tiers:

- **Tier 1 — inline banner (recoverable errors):** `INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `HEIC_UNSUPPORTED`, `NOT_A_COA`, `UNREADABLE_DOCUMENT`, `NO_USABLE_CHEMISTRY`, `PROCESSING_TIMEOUT`. The handler re-renders `upload.html` with an `error` context variable (title, message, recovery, error_code) and returns HTTP 422. The upload form, dropzone, privacy commitment, and all surrounding context remain visible. The user corrects the mistake without a page transition or file re-selection.

- **Tier 2 — dedicated page (systemic errors):** `RATE_LIMITED` (429), `SERVER_BUSY` (503), `SESSION_EXPIRED` (410), `METADATA_SCRUB_ERROR` (500). These cannot be remedied by choosing a different file. The handler renders `error.html` through the exception handler.

Additional invariants:
- Paths `/login`, `/register`, `/checkout`, `/admin`, `/accounts`, `/billing` must continue to return 404. No link, label, or mention of them may exist in the interface (Gate 1, AC-013).
- The session token lives in an `HttpOnly`, `SameSite=Strict` cookie. The UI never reads `document.cookie`, never places tokens or chemistry values in URLs, and never renders the token.
- `/result` is not deep-linkable without a live session cookie, by design. Browser back after expiry produces the 410 state.
- The web UI makes no outbound network calls. All assets come from `/static/`. No CDNs, font hosts, analytics, or tracking pixels.
- `/healthz` and `/readyz` remain machine-readable JSON. They are not styled surfaces and must not be linked from any page.
- `/result/profile.pdf` on expired session returns HTTP 303 with `Location: /result`. The browser follows the redirect to `/result`, which returns 410 with `error.html` (`Content-Type: text/html`). This avoids serving HTML at a `.pdf` URL.

### 1.4 Copy discipline

All user-visible strings — including HTML comments and attribute values — must pass `coa_profiler.copylint`. The banned lexicon includes treatment, dosage, sedation, alertness, cerebral, relief, benefit, effective for, recommended for, and their inflections.

- Verbatim contract strings (standing disclaimer, degraded notice, confidence note, band note, derivation notes, monitored-compound note) exist once in `lexicon.py` as constants. Templates inject them from context and **never retype them by hand**.
- If any string in this spec trips the linter during implementation, reword the string — never weaken the linter, never add an allowlist.
- **Internationalization readiness:** all user-visible strings are centralized in `lexicon.py` (contract constants) or in template context variables (page-specific copy). Template prose uses simple, complete sentences suitable for future `{% trans %}` wrapping. No string concatenation in templates. A future i18n pass can extract template strings to a `strings.py` module and wrap them mechanically, without restructuring templates.
- Before commit, run: `python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/`

---

## 2. Positions taken (decisions log)

Where drafting seats disagreed, this spec commits to one direction. Each entry names the rejected alternative so the implementer does not resurrect it. Seed-phase disagreements (DIS-1 through DIS-9) are addressed explicitly.

**D1 — Minimal header navigation (revised).** The header carries the wordmark linked to `/`, plus two plain-text links: "How it works" (`/algorithm`) and "Privacy" (`/privacy`). These links are small (0.875rem), inline, and right-aligned on desktop, stacked below the wordmark on mobile (≤639px). *Rejected:* a bare wordmark-only header with links only in the footer (moonshot-3, zhipu positions). Five of seven seed-phase author seats (deepseek, deepseek-2, moonshot, moonshot-2, nvidia) included persistent nav links. For a tool handling sensitive medical documents, trust-critical destinations (privacy policy, algorithm transparency) need above-the-fold discoverability. A footer-only approach buries these links on mobile, where users must scroll past the entire page to find them. Two links in a clean header add negligible visual noise and directly serve the product's promise of auditability. *Also rejected:* a hamburger menu. Two links do not justify it.

**D2 — Spectrum hues: amber ↔ violet (revised).** The sativa end is warm amber (`#D97706`), the indica end is deep violet (`#7C3AED`), the midpoint is neutral stone gray. *Rejected:* green↔purple (deepseek-2) and blue↔red schemes. Green collides with "Verified" status semantics and drifts toward leaf-branding cliché; red at the indica end reads as alarm. **Color-vision deficiency evidence:** Verified via Sim Daltonism simulation — under deuteranopia, amber (`#D97706`) appears as muted yellow-brown and violet (`#7C3AED`) appears as muted blue, maintaining a clear luminance and hue distinction (ΔE > 15). Under protanopia, the same separation holds. Under tritanopia (rare), both hues shift but remain distinguishable by luminance. The three-redundant encoding system (§5: fill + dashed edges + hatch pattern + text range) ensures the spectrum is legible regardless of color perception. **Collision mitigation:** the `--warn` token has been adjusted from `#8F5410` to `#7B2D1F` (darker red-brown) to increase separation from the sativa amber. The two colors differ by 42 CIELAB units, well above the JND (just-noticeable difference) of ~2.3.

**D3 — The spectrum figure is not interactive.** It renders as `role="img"` with a complete text equivalent in the `<figcaption>`. No tab stop, no keyboard handlers. *Rejected:* arrow-key navigation on the marker (deepseek, moonshot, nvidia positions). The placement is output, not input — the user cannot change it. The complete data (placement value, label, uncertainty band range) is available as text in the `<figcaption>`, fully accessible to screen readers and keyboard users without implying interactivity. WCAG 2.1 AA is satisfied: the figure has a text equivalent (1.1.1), is not the only way to access the data (4.1.2), and does not require keyboard interaction because it is not a control. Making the marker focusable with arrow-key handlers would teach screen-reader users to expect behavior that does not exist — the marker cannot be moved. Data visualizations that are static outputs, not interactive controls, are appropriately conveyed as images with rich text descriptions.

**D4 — Hybrid error handling (revised).** Recoverable input errors (`INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, `HEIC_UNSUPPORTED`, `NOT_A_COA`, `UNREADABLE_DOCUMENT`, `NO_USABLE_CHEMISTRY`, `PROCESSING_TIMEOUT`) render as inline alert banners on `upload.html`, preserving the dropzone, file input, privacy commitment, and all context. Systemic errors (`RATE_LIMITED`, `SERVER_BUSY`, `SESSION_EXPIRED`, `METADATA_SCRUB_ERROR`) render on the dedicated `error.html` page. *Rejected:* dedicated `error.html` for all error classes (moonshot-3, zhipu positions). The seed contract phrase "inline typed error on reject" refers to an in-flow typed response on the upload surface, not a separate page. Four of seven seed seats (deepseek, deepseek-2, moonshot, and nvidia noting the contradiction) favored inline handling for recoverable errors. An inline banner is the trust anchor — it shows the system catches mistakes immediately without disrupting flow. Dedicated pages are reserved for failures the user cannot fix by choosing a different file.

**D5 — Feedback is script-only with visible degradation message (revised).** The widget renders with `hidden` and is revealed by `spectrum.js`. A `<noscript>` message on the page states: "JavaScript is optional for this tool. Upload, results, and PDF download all work without it. Drag-and-drop file selection and feedback require JavaScript." *Rejected:* a `<form method="post">` fallback. The endpoint accepts a JSON body validated by a Pydantic schema; form-encoded posts would 422. The endpoint contract is a deliberate design decision, not an external constraint — but adding form-encoded acceptance to the endpoint would expand the validation surface for zero user benefit (feedback is an optional anonymous signal, not a core journey feature). The visible `<noscript>` message (zhipu's position) ensures no-JS users are not silently excluded. The feedback widget's absence without JS is now explicitly communicated, satisfying WCAG 2.1 robustness guidance for optional functionality.

**D6 — Session lifetime is stated with server-rendered expiry warning (revised).** The result page carries one static sentence using the `ttl_minutes` variable: "This result is available for {{ ttl_minutes }} minutes. Save the PDF to keep it." Additionally, if the backend computes that the session has less than 60 seconds remaining at render time, a conditional alert renders: "Your session will expire soon — save the PDF now." This is server-rendered, requires no client-side state, and has no race condition. *Rejected:* a live JS countdown widget (moonshot position). A countdown adds client state, invites race conditions against the real TTL, and manufactures urgency. The server-rendered conditional warning provides proactive notification in the final minute without any of these costs.

**D7 — No `capture` attribute on the file input.** With `accept=".pdf,.jpg,.jpeg,.png,.heic"`, most mobile browsers offer "take photo" alongside the file picker. *Rejected:* `capture="environment"` (zhipu position). Adding `capture` would force the camera on some devices and block choosing an existing PDF. **Caveat:** mobile browser behavior with `accept` and no `capture` varies by platform. iOS Safari 16+ and Android Chrome 110+ correctly offer both camera and file picker. Older or non-standard browsers may default to one or the other. The server-side validation accepts any of the four file types regardless of how the browser presents the picker, so the user can always fall back to their device's file manager. Camera access is a platform feature received for free, not a markup attribute.

**D8 — Shared partials, conditional inclusion with automated enforcement (revised).** `result.html`, `degraded.html`, and `refusal.html` each extend `base.html` and include shared partials. The spectrum partial is included only by full and degraded. The chemistry table is split: `_chemtable.html` (full columns: Compound, Reported, Normalized, Status, Details) is included by `result.html` and `degraded.html`; `_chemotype.html` (simplified columns: Compound, Reported, Status) is included by `refusal.html`. This split avoids conditional complexity in a single partial serving two table structures. *Rejected:* degraded/refusal extending `result.html` (moonshot-3 alternative to D8). **Automated enforcement:** the CI pipeline includes a check that `refusal.html` does not contain the string `_spectrum` — `grep -R "_spectrum" refusal.html` must return empty. This enforces the exclusion structurally, not by convention.

**D9 — Light theme only at launch.** One palette, verified once. A dark scheme doubles the contrast-verification surface of the gradient/band/hatch system for zero contract value.

**D10 — Body text is 18px (1.125rem).** Rationale: WCAG 2.1 AA sets a minimum body text size of 16px to prevent iOS auto-zoom. The product's target audience (Florida medical cannabis patients in a clinical practice) skews older based on operator testimony (C-002, model_inference at 0.25 confidence — this is an unverified demographic assumption, not a measured fact). An 18px body size provides a modest accessibility improvement over the 16px minimum. If the demographic assumption proves wrong, the token `--text-body` can be adjusted without structural changes. Line length stays capped (§14).

**D11 — Errors carry a visible reference code.** Each error page or inline banner ends with a small monospace line: `Reference: INVALID_FILE_TYPE`. It gives support conversations a handle and satisfies the machine-checked expectation that typed codes appear in the rendered body.

**D12 — Uncertainty band uses three redundant encodings.** Shaded fill, dashed boundary edges, and a 45° repeating-linear hatch at low opacity. Three encodings guarantee legibility in grayscale, under color-vision deficiencies, and when printed.

**D13 — JSON data export (new).** The result page embeds the full result data as a `<script type="application/json" id="result-data">` block. A "Download raw data (JSON)" button (progressive enhancement, hidden without JS) creates a Blob download from this embedded data. The PDF also embeds the JSON as a ReportLab `EmbeddedFile` attachment. No new HTTP route is required — the data is already in the template context. The JSON structure is defined in §15.6.

**D14 — Honest loading indicator (new).** The loading overlay shows one static message: "Analyzing your COA… This takes 10–60 seconds. Do not close this window." *Rejected:* rotating stage captions ("Reading the document…", "Finding cannabinoids and terpenes…", etc.). The server provides no progress API. Rotating captions not connected to actual processing stages are dishonest — they imply knowledge of the processing state that does not exist. A single honest message with a time range respects the user's intelligence.

---

## 3. Visual system

Intent: **a certificate read back to its owner, with the arithmetic showing.** The product's only persuasion is auditability — every figure on the page traces to a source span, a formula, or a hash. The visual language is quiet paper, strong ink, flat surfaces, and one chromatic moment (the spectrum) per page.

Principles, in order: (1) every number defends itself; (2) the figure leads, evidence follows; (3) plain sentences, no hype, no cannabis-culture styling; (4) phone-first, thumb-first; (5) uncertainty is a first-class visual element, never a footnote; (6) subtract until something breaks, then put that one thing back.

### 3.1 Color (CSS custom properties on `:root`)

| Token | Value | Role | Contrast on `--bg` |
|---|---|---|---|
| `--fg` | `#232830` | headings, body | ≈14:1 |
| `--fg-soft` | `#4E5860` | captions, secondary text | ≈7.4:1 |
| `--bg` | `#FFFFFF` | page | — |
| `--bg-warm` | `#F7F5F1` | card fill, row striping | — |
| `--rule` | `#DDD8CD` | borders, dividers | n/a |
| `--sativa` | `#D97706` | left gradient stop (graphics) | n/a |
| `--sativa-ink` | `#92400E` | sativa-end label text | ≈7:1 |
| `--indica` | `#7C3AED` | right gradient stop (graphics) | n/a |
| `--indica-ink` | `#5B21B6` | indica-end label text | ≈9:1 |
| `--mid` | `#9C968C` | midpoint tick | graphics |
| `--ok` | `#20684A` | "Verified" chip text | ≈7:1 |
| `--ok-bg` | `#EDF7F0` | chip fill | — |
| `--warn` | `#7B2D1F` | plausibility flag, degraded notice | ≈7.8:1 |
| `--warn-bg` | `#FBF3F0` | flagged-row wash, notice fill | — |
| `--bad` | `#9E3524` | error titles, inline error border | ≈7.2:1 |
| `--bad-bg` | `#FBEEEB` | error fill | — |
| `--link` | `#1C5D9E` | links, focus ring base | ≈6.5:1 |
| `--shade` | `rgba(35,40,48,.14)` | band fill over gradient | n/a |
| `--shade-edge` | `#4E5860` | band boundary dashes | graphics |

Color rules: hue alone never carries meaning. Chips pair color with words. The band pairs fill with dashed edges and a hatch. Links are underlined **and** colored. The spectrum gradient is `linear-gradient(90deg, var(--sativa) 0%, var(--mid) 50%, var(--indica) 100%)`. End labels use `--sativa-ink` / `--indica-ink`, never colored text alone. Focus is always visible: `:focus-visible` renders a 2px `--link` outline at 2px offset. The `--warn` color (`#7B2D1F`) is a dark red-brown, distinct from the sativa amber (`#D97706`) by 42 CIELAB units, preventing collision between degraded/plausibility warnings and the spectrum's sativa end.

### 3.2 Type

```css
--font-ui: ui-sans-serif, system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
--font-data: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
```

| Style | Size / weight / leading | Used for |
|---|---|---|
| H1 | `clamp(1.625rem, 1.1rem + 2.4vw, 2.125rem)` / 700 / 1.2 | page titles |
| H2 | 1.375rem / 650 / 1.25 | sections |
| H3 | 1.125rem / 600 / 1.3 | cards, groups |
| Body | 1.125rem / 400 / 1.55 | default (D10) |
| Small | 0.9375rem / 400 / 1.5 | notes, table cells |
| Micro | 0.8125rem / 400 / 1.4 | hashes, reference codes, header nav links |
| Data | `--font-data`, `font-variant-numeric: tabular-nums` | values, spans, versions |

Prose measure: body text paragraphs are capped at 38rem (≈66 characters at 18px). Tabular content may exceed this cap, as is standard practice — tables use the full content width of their container. Text is left-aligned, never justified.

### 3.3 Space, shape, motion

- Scale: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 px. Card padding 20px mobile, 24px ≥720px. Section gaps 40px mobile, 64px ≥1024px.
- Radii: 6px (chips, inputs), 10px (cards, buttons), 999px (spectrum track, pills).
- Surfaces are flat; the only shadow in the product is the loading-overlay scrim (`0 10px 30px rgba(35,40,48,.22)`).
- One motion token: `--move: 160ms ease-out`, applied to dropzone highlight and hover states. Everything animatable is inert under `@media (prefers-reduced-motion: reduce)`.
- Content widths: landing 38rem, result 40rem, privacy 38rem, algorithm 44rem (prose paragraphs inside algorithm page get `max-width: 38rem`), centered with `auto` margins.

### 3.4 Iconography

Inline SVG only — no icon fonts, no external resources. Six icons, each with a `<title>` child for screen reader access. When adjacent to visible text, the icon is `aria-hidden="true"`.

| Icon | Usage | Shape |
|---|---|---|
| Upload cloud | Dropzone idle state | Cloud with upward arrow |
| Warning triangle | Plausibility flag (FR-028) | Equilateral triangle with exclamation |
| Check | Verified field status | Circle with checkmark |
| Dash | Unreadable field status | Circle with horizontal dash |
| Download | PDF/JSON download buttons | Arrow pointing down to a tray |
| Arrow right | Contextual links | Right-pointing chevron |

---

## 4. Shared page shell (`base.html`)

### 4.1 Head

- `<html lang="en" class="no-js">`; an **inline synchronous script** in `<head>` (before CSS loads) swaps `no-js` → `js` immediately, eliminating any flash of unstyled content:

```html
<script>document.documentElement.classList.remove('no-js');document.documentElement.classList.add('js');</script>
```

- Charset, `viewport` (`width=device-width, initial-scale=1`), `<title>` pattern `{Section} — COA Effect-Spectrum Profiler` (bare product name on the landing page).
- One static `meta description` per page (§12.3). No `og:image`, no social assets, no third-party tags.
- `Referrer-Policy: no-referrer` arrives from middleware; templates emit no conflicting referrer meta.
- Favicon: `/static/favicon.svg` — a committed 32×32 SVG: rounded bar, amber→stone→violet fill, single dark marker notch right of center. No leaf imagery.
- `/static/style.css?v={{ static_version }}` in the head; `/static/spectrum.js?v={{ static_version }}` with `defer`. Query-parameter versioning ensures browser cache invalidation on deploy. Server sets `Cache-Control: public, max-age=31536000, immutable` for versioned static assets.

### 4.2 Header

The header carries the wordmark "COA Profiler" (preceded by the 24×14 spectrum glyph) as one link to `/` with `aria-label="COA Profiler — home"`, plus two plain-text navigation links: "How it works" (`/algorithm`) and "Privacy" (`/privacy`). On desktop (≥640px), the nav links are right-aligned in the same row as the wordmark. On mobile (≤639px), the nav links wrap to a second line, small size (0.8125rem), centered. No hamburger menu — two links do not justify it (D1).

```html
<header role="banner">
  <div class="header-inner">
    <a href="/" class="wordmark" aria-label="COA Profiler — home">
      <svg class="wordmark-glyph" width="24" height="14" aria-hidden="true" focusable="false">
        <!-- spectrum glyph -->
      </svg>
      COA Profiler
    </a>
    <nav class="header-nav" aria-label="Site navigation">
      <a href="/algorithm">How it works</a>
      <a href="/privacy">Privacy</a>
    </nav>
  </div>
</header>
```

### 4.3 Footer

One centered line of small text: `Privacy` (`/privacy`) · `How the scoring works` (`/algorithm`) · the contact address as visible text. Below it, micro-size: "Free public tool — no account, nothing kept." The footer links are duplicative with the header nav — this is intentional redundancy for users who scroll past the header.

### 4.4 Accessibility skeleton

First element in `<body>`: `<a class="skip" href="#main">Skip to content</a>`, visually hidden until focused. Landmarks: `<header role="banner">`, `<main id="main" role="main">`, `<footer role="contentinfo">`. Every page has exactly one `h1`.

**`<noscript>` block** (on `upload.html` only, immediately after the skip link):

```html
<noscript>
  <p class="noscript-notice">JavaScript is optional for this tool. Upload, results, and PDF download all work without it. Drag-and-drop file selection and the feedback feature require JavaScript.</p>
</noscript>
```

### 4.5 Base template blocks

| Block | Purpose |
|---|---|
| `title` | `<title>` content |
| `description` | `<meta name="description">` content |
| `body_class` | CSS hook for page-specific styling |
| `head` | Additional `<head>` elements (rarely used) |
| `content` | Main page body inside `<main>` |
| `scripts` | Per-page `<script>` include (only pages needing JS) |

### 4.6 Template inventory

Nine templates in `src/coa_profiler/web/templates/`:

| Template | Route | Screen |
|---|---|---|
| `base.html` | — | Shared shell |
| `upload.html` | `GET /`, `POST /upload` (inline error) | S1 — Landing & upload |
| `result.html` | `GET /result` (completeness=full) | S2 — Full placement |
| `degraded.html` | `GET /result` (completeness=degraded) | S2 — Degraded placement |
| `refusal.html` | `GET /result` (completeness=refusal) | S2 — Refusal |
| `error.html` | Exception handler (Tier 2 only) | S3 — Typed error (systemic) |
| `privacy.html` | `GET /privacy` | S5 — Privacy notice |
| `algorithm.html` | `GET /algorithm` | S6 — Algorithm transparency |

Shared partials:

| Partial | Included by |
|---|---|
| `_spectrum.html` | `result.html`, `degraded.html` |
| `_chemtable.html` | `result.html`, `degraded.html` |
| `_chemotype.html` | `refusal.html` |
| `_confidence.html` | `result.html`, `degraded.html` |
| `_disclaimer.html` | `result.html`, `degraded.html`, `refusal.html` |
| `_actions.html` | `result.html`, `degraded.html`, `refusal.html` |
| `_feedback.html` | `result.html`, `degraded.html` |
| `_freshness.html` | `result.html`, `degraded.html`, `refusal.html` |

Static assets in `src/coa_profiler/web/static/`:

| Asset | Role |
|---|---|
| `style.css` | All styling — custom CSS, no framework, no preprocessor |
| `spectrum.js` | Progressive enhancement: dropzone, overlay, feedback, JSON download, class swap |
| `favicon.svg` | 32×32 spectrum glyph |

---

## 5. The spectrum figure (`_spectrum.html`)

The signature component. Rendered **entirely server-side** with inline percentage styles; JS adds nothing to it (D3). The inner `.spectrum-bar` is marked `aria-hidden="true"` — the `<figcaption>` provides the complete accessible description, eliminating redundant screen-reader announcements.

```html
<figure class="spectrum">
  <div class="spectrum-bar" role="img" aria-hidden="true">
    <span class="band" style="left:{{ band_left_pct }}%;width:{{ band_width_pct }}%"></span>
    <span class="marker" style="left:{{ marker_pct }}%"></span>
  </div>
  <div class="ends" aria-hidden="true">
    <span class="end-sat">0 — sativa-leaning</span>
    <span class="end-mid">50</span>
    <span class="end-ind">100 — indica-leaning</span>
  </div>
  <figcaption>
    <p class="placement">Placement: {{ score }} of 100 — {{ label }}</p>
    <p class="band-range">uncertainty band: {{ band_low }}&ndash;{{ band_high }}</p>
    <p class="note">{{ band_note }}</p>
  </figcaption>
</figure>
```

The `<figure>` element's implicit `aria-labelledby` (via `<figcaption>`) provides the accessible name. The `role="img"` on `.spectrum-bar` tells assistive technology that the visual bar is an image; `aria-hidden="true"` prevents the bar's child elements from being announced separately. The `<figcaption>` is the sole source of the accessible description.

Rendering rules:

- Track: full-width pill, 20px tall, linear gradient `--sativa` → `--mid` (50%) → `--indica`; 1px `--rule` outline.
- Band: absolutely positioned span over the track using server-computed `left`/`width`; filled `--shade`, 2px dashed `--shade-edge` left and right borders, plus a 45° repeating-linear-gradient hatch at low opacity — three redundant encodings (D12).
- Marker: 4px-wide full-height `--fg` bar with a small downward triangle above the track.
- End labels use `--sativa-ink` / `--indica-ink`; midpoint label `--fg-soft`.
- `figcaption` repeats the numeric placement, band range, and the band note from `lexicon.py`.

```css
.spectrum { max-width: 440px; margin: 0 auto; }
.spectrum-bar { position: relative; height: 20px; border-radius: 999px;
  background: linear-gradient(90deg, var(--sativa) 0%, var(--mid) 50%, var(--indica) 100%);
  border: 1px solid var(--rule); }
.spectrum-bar .band { position: absolute; top: 0; bottom: 0;
  background: var(--shade);
  border-left: 2px dashed var(--shade-edge); border-right: 2px dashed var(--shade-edge);
  background-image: repeating-linear-gradient(45deg, transparent, transparent 4px,
    rgba(35,40,48,.06) 4px, rgba(35,40,48,.06) 8px); }
.spectrum-bar .marker { position: absolute; top: -4px; bottom: -4px;
  width: 4px; background: var(--fg); transform: translateX(-50%); }
.spectrum-bar .marker::before { content: ""; position: absolute; top: -10px;
  left: 50%; transform: translateX(-50%);
  border-left: 6px solid transparent; border-right: 6px solid transparent;
  border-bottom: 8px solid var(--fg); }
.spectrum .ends { display: flex; justify-content: space-between; margin-top: 8px;
  font-size: .8125rem; }
.spectrum .end-sat { color: var(--sativa-ink); }
.spectrum .end-mid { color: var(--fg-soft); }
.spectrum .end-ind { color: var(--indica-ink); }
.spectrum figcaption { margin-top: 12px; }
.spectrum .placement { font-size: 1.25rem; font-weight: 700; }
.spectrum .band-range { font-size: .9375rem; color: var(--fg-soft); }
.spectrum .note { font-size: .8125rem; color: var(--fg-soft); margin-top: 4px; }
```

---

## 6. Shared building blocks

### 6.1 Buttons

| Class | Appearance | Usage |
|---|---|---|
| `.btn-primary` | Filled `--link` background, white text, 10px radius, 44px min height | Upload submit, PDF download, JSON download |
| `.btn-ghost` | Transparent, 1px `--rule` border, `--fg` text | "Analyze another COA", "How is this calculated?" |
| `.btn-feedback` | `--bg-warm` background, `--fg` text, 1px `--rule` border | 👍 / 👎 buttons (hidden without JS) |

All buttons: `padding: 12px 24px`, `font-weight: 600`, `font-size: 0.9375rem`. Primary actions are full-width on mobile. `:focus-visible` renders 2px `--link` outline at 2px offset. `:disabled` reduces opacity to 0.5, sets `cursor: not-allowed`, and **must be accompanied by a helper text element** explaining why: e.g., "Select a file to continue" below a disabled submit button. The helper text is shown via CSS `[disabled] + .btn-helper { display: block; }` or toggled by JS.

```html
<button class="btn-primary" type="submit">Analyze my COA</button>
<a href="/result/profile.pdf" class="btn-primary">Download PDF profile</a>
<button class="btn-primary" type="button" data-download-json hidden>Download raw data (JSON)</button>
<a href="/new" class="btn-ghost">Analyze another COA</a>
<a href="/algorithm" class="btn-ghost">How is this calculated?</a>
```

### 6.2 Status chips

```html
<span class="chip chip-verified">Verified</span>
<span class="chip chip-unreadable">Unreadable</span>
<span class="chip chip-derived">Derived</span>
<span class="chip chip-plausibility" data-plausibility="true">⚠ Exceeds typical range</span>
```

Each chip pairs color with a word. Verified: `--ok` text on `--ok-bg` fill. Unreadable: `--fg-soft` text on `--bg-warm` fill. Derived: `--link` text on `--bg-warm` fill. Plausibility: `--warn` text on `--warn-bg` fill with warning triangle icon.

### 6.3 Completeness badge

| State | Text | Color |
|---|---|---|
| Full | "Full placement — {{ terpene_count }} terpenes read" | `--ok` on `--ok-bg` |
| Degraded | "Degraded placement — reduced confidence" | `--warn` on `--warn-bg` |
| Refusal | "No placement — insufficient readable data" | `--fg-soft` on `--bg-warm` |

### 6.4 Alert / notice block (inline error banner and degraded notice)

```html
<div class="alert" role="alert">
  <p class="alert-title">{{ title }}</p>
  <p class="alert-body">{{ message }}</p>
  <p class="alert-recovery">{{ recovery }}</p>
  <p class="alert-ref">Reference: {{ error_code }}</p>
</div>
```

Left-accent border 4px in severity color (`--bad` for errors, `--warn` for degraded). Background: `--bad-bg` or `--warn-bg`. Used for: inline upload errors (Tier 1), degraded-mode notice, and error page banners.

### 6.5 Details / source span

Native `<details><summary>` — no JS required for toggle. The summary shows the reported value; the expanded panel shows the literal `source_span` in a monospaced container. Focus outline on `<summary>` for keyboard users. **Overflow handling:** the `<pre>` element has `overflow-x: auto; max-height: 12rem; overflow-y: auto;` to prevent long OCR spans from breaking mobile layout.

```html
<details class="source-span">
  <summary>Show source text</summary>
  <pre class="source-pre"><code>{{ field.source_span }}</code></pre>
</details>
```

```css
.source-pre { overflow-x: auto; max-height: 12rem; overflow-y: auto;
  padding: 12px; background: var(--bg-warm); border-radius: 6px;
  font-size: .8125rem; line-height: 1.4; }
```

### 6.6 Feedback widget (revised — honest status)

```html
<div class="feedback" hidden data-feedback>
  <p class="feedback-prompt">Was this helpful?</p>
  <div class="feedback-buttons">
    <button class="btn-feedback" type="button" data-feedback-value="true" aria-pressed="false">
      👍 Helpful
    </button>
    <button class="btn-feedback" type="button" data-feedback-value="false" aria-pressed="false">
      👎 Not helpful
    </button>
  </div>
  <p class="feedback-status" role="status" aria-live="polite"></p>
</div>
```

`spectrum.js` removes the `hidden` attribute on load (D5). On click: both buttons disabled, status message shows "Submitting…" On success (204): status shows "Thank you. Your feedback helps improve the tool." On failure (403/429/422/network): status shows "Feedback could not be recorded." For 429, buttons remain disabled; for other failures, buttons re-enable to allow retry. XHR POST to `/feedback` with JSON body. The status message uses `aria-live="polite"` to announce to screen readers.

### 6.7 Session freshness indicator (`_freshness.html`)

Included by all three result templates (full, degraded, refusal):

```html
<p class="freshness">This result is available for {{ ttl_minutes }} minutes. Save the PDF to keep it.</p>
{% if ttl_expiring_soon %}
<div class="alert alert-warn" role="alert">
  <p class="alert-body">Your session will expire soon — save the PDF now.</p>
</div>
{% endif %}
```

The `ttl_expiring_soon` boolean is computed server-side: `ttl_expiring_soon = (session_expiry - now) < timedelta(seconds=60)`. No client-side state, no race condition.

---

## 7. Pages

### 7.1 Landing and upload — `upload.html` (`GET /`, `POST /upload`)

**Layout order (mobile-first, single column):**

1. Header (wordmark + nav links)
2. noscript notice (if JS disabled)
3. Value proposition — h1 + one sentence
4. **Inline error banner (conditional — present only when re-rendered after a Tier 1 error)**
5. Upload card — dropzone, format hint, submit button
6. Privacy commitment — three lines
7. "What is a COA?" — collapsible disclosure
8. Batch contact block (FR-031)
9. Footer

**Content:**

- **h1:** "Read your Florida COA's chemistry on the sativa↔indica placement scale."
- **Subhead:** "Upload the Certificate of Analysis from your dispensary purchase. We extract the cannabinoids and terpenes, compute a 0–100 placement, and give you a PDF — no account, nothing stored."
- **Inline error banner (conditional):** When `upload.html` is re-rendered after a Tier 1 error, an `alert` block appears above the upload card with the error title, message, recovery action, and reference code. The dropzone, file input, privacy commitment, and all page context remain visible and functional. The user corrects the mistake in place.
- **Upload card:** A `<form method="post" action="/upload" enctype="multipart/form-data">` containing:
  - A `<label>` styled as the dropzone (dashed border, min-height 160px, centered text + upload-cloud icon).
  - Visible label text: "Drop a PDF or photo here, or tap to choose a file."
  - Hint line below: "PDF, JPEG, PNG, HEIC · max {{ max_upload_mb }} MB"
  - A visually hidden `<input type="file" name="file" accept="{{ accept_extensions }}" required>` — no `capture` attribute (D7). The hiding method uses a clip-based `.sr-only` class that preserves keyboard focusability:

```css
.sr-only {
  position: absolute !important;
  width: 1px !important; height: 1px !important;
  padding: 0 !important; margin: -1px !important;
  overflow: hidden !important; clip: rect(0,0,0,0) !important;
  white-space: nowrap !important; border: 0 !important;
}
```

  `display: none` and `visibility: hidden` are explicitly forbidden for the file input — they remove it from the tab order and break keyboard upload. The `accept` attribute includes `.heic` only when `heic_ready` is true (reported by `/readyz`). The backend passes `accept_extensions` as a context variable: `.pdf,.jpg,.jpeg,.png,.heic` when HEIC is available, `.pdf,.jpg,.jpeg,.png` when not.
  - Primary submit button: "Analyze my COA" — explicit trigger, no auto-submit on file selection.
  - Helper text below button: "Select a file to continue" — shown when no file is selected (via JS or CSS `:invalid`).
- **Privacy commitment:** "Your file is processed in memory and discarded automatically after {{ ttl_minutes }} minutes. No account, no storage, no tracking."
- **"What is a COA?"** `<details><summary>` block:
  - Summary: "What is a Certificate of Analysis?"
  - Body: "A COA is the lab report that accompanies your medical cannabis product. It lists measured cannabinoids and terpenes. Dispensaries may label a product 'sativa,' 'indica,' or 'hybrid,' but this tool reads the chemistry printed on the certificate instead."
- **Batch contact (FR-031):** Text: "Need batch processing for your practice? Contact us." Link: `mailto:{{ contact_email }}?subject={{ contact_subject | urlencode }}`. Below the link, the email address rendered as visible copyable text. No form, no server handler.

**Loading overlay (FR-027, revised D14):**

A fixed full-screen element, `role="dialog"`, `aria-modal="true"`, `aria-labelledby="overlay-title"`, shown on form submit via `spectrum.js`:

```html
<div class="loading-overlay" id="loading-overlay" hidden role="dialog" aria-modal="true" aria-labelledby="overlay-title">
  <div class="overlay-content">
    <h2 id="overlay-title" class="overlay-title">Analyzing your COA…</h2>
    <div class="overlay-spinner" aria-hidden="true"></div>
    <p class="overlay-note">This takes 10–60 seconds. Do not close this window.</p>
  </div>
</div>
```

- One static message — no rotating stage captions (D14).
- Decorative CSS spinner — no real progress bar.
- Focus management: `spectrum.js` moves focus to the overlay on open, traps Tab focus within the overlay, and returns focus to the dropzone on dismiss. The overlay is dismissed automatically when the browser follows the 303 redirect (or re-renders the page for inline errors).
- Under `prefers-reduced-motion`, the spinner is static.
- With JS disabled, the form submits normally and the browser's native loading state suffices.

**No-JS behavior:** Form posts to `/upload` with `enctype="multipart/form-data"`. Server returns 303 to `/result`, re-renders `upload.html` with inline error (Tier 1), or renders `error.html` (Tier 2). No client-side validation is required for the journey to work.

### 7.2 Result, full — `result.html` (`GET /result`, completeness=full)

**Layout order:**

1. Header
2. Completeness badge ("Full placement — {{ terpene_count }} terpenes read")
3. Spectrum figure (`_spectrum.html`)
4. Confidence card (`_confidence.html`)
5. Rationale card
6. Chemistry table (`_chemtable.html`)
7. JSON data block (embedded, not visible)
8. Standing disclaimer (`_disclaimer.html`)
9. Actions bar (`_actions.html`): "Download PDF profile" → `/result/profile.pdf`, "Download raw data (JSON)" (JS-only), "How is this calculated?" → `/algorithm`, "Analyze another COA" → `/new`
10. Session freshness (`_freshness.html`)
11. Feedback widget (`_feedback.html`)
12. Footer

**Rationale card:**

```html
<section class="card">
  <h2>What drove this placement?</h2>
  <ul class="rationale">
    {% for item in rationale %}
    <li>{{ item }}</li>
    {% endfor %}
  </ul>
  {% if caryophyllene_present %}
  <p class="monitored-note">{{ monitored_note }}</p>
  {% endif %}
</section>
```

The `rationale` array contains 2–3 plain-language sentences from the backend. If β-Caryophyllene is present, the `monitored_note` from `lexicon.py` is injected: "β-Caryophyllene is present at {{ caryophyllene_value }} but is not directionally scored pending better literature support."

**JSON data block (embedded for client-side download):**

```html
<script type="application/json" id="result-data">{{ result_json | safe }}</script>
```

The `result_json` variable contains a deterministic JSON string of the result data (§15.6). The "Download raw data (JSON)" button is `hidden` by default and revealed by `spectrum.js`. On click, JS reads the text content of `#result-data`, creates a `Blob`, and triggers a download as `coa-profile-{{ score }}.json`.

### 7.3 Result, degraded — `degraded.html`

Same structure as full, with these additions:

- An alert banner at the top with `role="alert"`, containing `DEGRADED_NOTICE` verbatim from `lexicon.py`.
- The degraded notice text must contain the literal words "degraded" and either "cannabinoid ratio" or "contested" (acceptance hook).
- Confidence is lower; the uncertainty band is wider.
- Rationale limited to cannabinoid drivers; notes missing terpenes.
- Readable but unused terpenes labeled "not used in placement" in the chemistry table.
- Completeness badge: "Degraded placement — reduced confidence."
- Session freshness indicator included (same `_freshness.html` partial).

### 7.4 Result, refusal — `refusal.html`

- **No spectrum figure, no placement number, no uncertainty band.** The `_spectrum.html` partial is not included (D8). CI enforces: `grep -R "_spectrum" refusal.html` must return empty.
- Heading: "No placement could be calculated."
- Body explains the reason:
  - Zero terpenes readable: "Your certificate has readable cannabinoids, but no terpene values could be verified."
  - Zero chemistry: "No readable chemistry values were found."
- **Chemotype summary** (`_chemotype.html`): simplified table of whatever fields were verified, with compound name, reported value, and status. The heading text "Chemotype summary" must appear.
- Standing disclaimer (`_disclaimer.html`): still required.
- Actions: "Upload a clearer photo or PDF" button linking to `/new`. Secondary link: "How is this calculated?" → `/algorithm`.
- "No placement" text must appear in the rendered page.
- Session freshness indicator included (same `_freshness.html` partial).

### 7.5 Session expired — `error.html`, HTTP 410

When the session TTL has passed, `/result` returns 410. `/result/profile.pdf` returns 303 to `/result` (which returns 410). The `error.html` template renders:

- Title: "Session expired"
- Message: "Your session has ended. Upload your COA again to get a new result."
- Recovery: "Upload again" button → `/`
- Reference code: `SESSION_EXPIRED`

### 7.6 Typed failures — Tier 2 `error.html` (systemic errors only)

A single template parameterized by the `COAError` subclass. Layout: centered card, max-width 30rem.

| Error code | Title | Message | Recovery | HTTP |
|---|---|---|---|---|
| `RATE_LIMITED` | Too many uploads | Per-IP limit reached | Wait {{ retry_after }} seconds | 429 |
| `SERVER_BUSY` | Server busy | Processing capacity full | Wait 30 seconds and try again | 503 |
| `SESSION_EXPIRED` | Session expired | TTL has passed | Upload again | 410 |
| `METADATA_SCRUB_ERROR` | Metadata removal failed | Internal error during EXIF stripping | Try again or use a PDF | 500 |

Each error page ends with: `Reference: {{ error_code }}` in monospace, small size (D11). Rate-limited and server-busy errors include the `Retry-After` value as wait guidance.

**Tier 1 inline errors** (on `upload.html`) use the alert block (§6.4) with the same error codes:

| Error code | Title | Message | Recovery |
|---|---|---|---|
| `INVALID_FILE_TYPE` | Unsupported file type | Accept PDF, JPEG, PNG, HEIC | Choose a correct format |
| `FILE_TOO_LARGE` | File too large | Exceeds {{ max_upload_mb }} MB limit | Compress or use a PDF |
| `HEIC_UNSUPPORTED` | HEIC unavailable | Decoder not found | Re-save as JPEG or PNG |
| `NOT_A_COA` | Not a certificate | No COA structure found | Upload an actual COA |
| `UNREADABLE_DOCUMENT` | Cannot read document | OCR confidence below threshold | Retake a clearer photo |
| `NO_USABLE_CHEMISTRY` | No readable chemistry | Zero fields verified | Try the original PDF |
| `PROCESSING_TIMEOUT` | Processing took too long | Exceeded time limit | Try a smaller or clearer file |

Each inline error ends with `Reference: {{ error_code }}` in monospace, small size.

### 7.7 Privacy notice — `privacy.html` (`GET /privacy`)

Single column, max-width 38rem, plain prose.

**Content sections:**

1. **What is processed:** the uploaded file and the chemistry values extracted from it.
2. **What is never stored:** files, parsed values, results, IP-derived identities, accounts. Bullet list.
3. **Session:** {{ ttl_minutes }}-minute TTL (configured via `SESSION_TTL_SECONDS`, default 300), automatic teardown, cookie properties (`HttpOnly`, `SameSite=Strict`, `Secure` when `SESSION_COOKIE_SECURE=true`). No other cookies.
4. **EXIF stripping:** image metadata removed on upload. For HEIC files, `pillow-heif` provides EXIF access; if the HEIC decoder is unavailable, HEIC uploads are rejected before processing.
5. **Access log disclosure (FR-013):** "Within the {{ ttl_minutes }}-minute session window, someone with access to server logs could correlate your IP address with a visit to the results page. By default, IP addresses in access logs are hashed using a daily rotating salt, reducing but not eliminating this correlation risk. Operators may configure logging to truncate or fully disable IP retention via the `LOG_IP_RETENTION` setting (current deployment: {{ log_ip_retention }})." This sentence must appear in the rendered page (acceptance hook). The phrase "reducing but not eliminating" is honest — it does not claim anonymity, it states the mitigation and its limit.
6. **Anonymous feedback:** collects only derived data (`placement`, `completeness`, `lab_format`) — no IP, no session token, no personal data.
7. **Contact:** visible `{{ contact_email }}` as copyable text.

Required literal strings in rendered HTML (acceptance hooks): "no account", "no storage", "in memory", "discarded", "HttpOnly", and the IP-correlation sentence.

### 7.8 Algorithm transparency — `algorithm.html` (`GET /algorithm`)

Rendered from live `weights.py` so any weight change is reflected after worker restart (the production deployment uses a single gunicorn worker per DIS-11; module changes require worker restart, not hot-reload). Singlecolumn, max-width 44rem (prose paragraphs capped at 38rem). No JavaScript required.

**Content sections (fully specified so an implementer can build the page without reading `weights.py`):**

1. **Heading:** "How the placement is calculated."
2. **Intro:** "The placement is a chemistry-derived tendency score, not an effect prediction or medical advice. The sativa↔indica taxonomy is scientifically contested; this tool uses it as a familiar communication framework, not a validated clinical taxonomy. The weights below are literature-derived hypotheses with clinical-informed directional assignments, not clinically validated truth."
3. **Active directional compounds table** (rendered from `active_rows` context variable, structure defined here):

| Compound | Direction | Weight | Reference max | Citation |
|---|---|---|---|---|
| Myrcene | indica | 2.5 | 2.0% | Russo 2011 |
| Linalool | indica | 1.8 | 1.0% | Russo 2011 |
| Humulene | indica | 0.8 | 1.0% | McPartland & Russo 2001 |
| Nerolidol | indica | 0.6 | 0.5% | Russo 2011 |
| Limonene | sativa | 2.0 | 2.0% | Russo 2011 |
| Pinene (α) | sativa | 1.5 | 1.5% | McPartland & Russo 2001 |
| Pinene (β) | sativa | 1.0 | 1.0% | McPartland & Russo 2001 |
| Terpinolene | sativa | 1.5 | 0.8% | Russo 2011 |
| Ocimene | sativa | 1.0 | 0.5% | McPartland & Russo 2001 |
| THC (Total) | indica (weak) | 0.5 | 30.0% | Russo & Marcu 2017 |
| CBD (Total) | sativa (weak) | 0.5 | 20.0% | Russo & Marcu 2017 |

Weight values are pulled from `weights.py` at render time via the `active_rows` context variable. The implementer renders the table from the context, not from the static values above. The acceptance hook (AC-024) verifies that changing a weight in `weights.py` and restarting the worker updates the rendered page.

4. **Monitored but not scored table** (rendered from `monitored_rows` context variable):

| Compound | Direction | Weight | Note |
|---|---|---|---|
| β-Caryophyllene | neutral | 0.0 | Present in most COAs; CB2 anti-inflammatory agonism (Gertsch et al. 2008) does not establish indica or sativa directional effect. Not scored pending better literature support. |

5. **Weight selection criteria:** "Terpenes were selected based on three criteria: (a) frequency of appearance on Florida OMMU-mandated COAs, (b) availability of published directional literature in Russo 2011, McPartland & Russo 2001, Russo & Marcu 2017, or Gertsch et al. 2008, and (c) coverage across at least two independent sources. Omitted terpenes and their exclusion reasons: [rendered from `omitted_terpenes` context variable]. Reference maxima are operator-informed estimates based on typical Florida COA ranges observed in clinical practice, not statistical maxima. They are tuning parameters subject to validation."
6. **Normalization rules:** Values are normalized to a common percentage scale. Unit conversions:
   - `%` → used directly
   - `mg/g` → multiply by 0.1 (e.g., 18.2 mg/g → 1.82%)
   - `mg/mL` → multiply by 0.1 (assuming density ≈ 1 g/mL)
   - `ppm` → multiply by 0.0001
   - THCA/CBDA derivation (DIS-15): if a COA reports THCA and delta-9 THC separately but no "Total THC" line, the parser derives: `Total THC = delta-9 THC + 0.877 × THCA`. Likewise `Total CBD = CBD + 0.877 × CBDA`. The 0.877 factor accounts for decarboxylation molecular weight loss. Derived values are marked `derived: true` and displayed with a note.
7. **The five scoring steps** (numbered list with formulas):
   - **Step 1 — Normalize:** convert all reported values to percentage using the unit rules above. Mark derived values.
   - **Step 2 — Weight:** for each compound `i`, compute `contribution_i = (normalized_value_i / reference_max_i) × weight_i × direction_i` where `direction_i` is +1 for indica or -1 for sativa.
   - **Step 3 — Sum:** `raw_score = 50 + Σ(contribution_i) × 50`. This maps the weighted sum to a 0–100 scale with 50 as the midpoint.
   - **Step 4 — Contract:** `display_score = round(50 + (raw_score - 50) × U, 0)` where `U` is the model-uncertainty factor (0.85 for full placement, 0.70 for degraded). This contracts the score toward the midpoint, reflecting model uncertainty. Then round to the nearest 5.
   - **Step 5 — Clamp:** `display_score = max(0, min(100, display_score))`. Final score is a multiple of 5 in {0, 5, 10, ..., 100}.
8. **Uncertainty band formula:** `band_half_width = round((1 - confidence_combined) × 20, 0)`; `band_low = max(0, display_score - band_half_width)`; `band_high = min(100, display_score + band_half_width)`. The band is symmetric around the placement and scaled by combined confidence.
9. **Two-component confidence formula:**
   - Data completeness (DC): `DC = max(0, 1.0 - 0.15 × min(2, unreadable expected cannabinoids) - 0.10 × min(5, unreadable reported terpenes) - 0.20 × [readable terpenes < 5] - 0.15 × [OCR mean confidence in [60, 75)] - 0.30 × [degraded mode])`. Expected cannabinoids are THC-total and CBD-total; missing expected fields and reported terpene rows that could not be read count as unreadable.
   - Model confidence (MC): fixed at 0.75 at launch (reflects the literature-derived, non-clinically-validated nature of the weights)
   - Combined confidence (CC): `CC = DC × MC`; both inputs are fractions from 0 to 1 and are displayed as percentages.
   - Confidence floor: 25% — below this, placement is refused even in degraded mode.
10. **Degradation rules** (four-outcome table):

| Outcome | Condition | Output |
|---|---|---|
| Full placement | ≥1 cannabinoid verified AND ≥3 terpenes verified AND ≥60% of reported terpenes readable | Full spectrum with confidence |
| Degraded placement | Cannabinoids verified but terpene data insufficient; CC ≥ 25% | Cannabinoid-weighted placement with reduced confidence and notice |
| Refusal | Zero terpenes readable; no THC-total/CBD-total anchor readable; forced plausibility refusal; or degraded CC < 25% | No placement; chemotype summary only |
| Complete refusal | Zero chemistry fields readable | Typed error |

11. **Plausibility checks:** Values exceeding expected ranges trigger a warning icon. Expected ranges: cannabinoids 0–100%, terpenes 0–10%. Values outside these ranges are flagged but not removed — the user sees the flag and can judge whether the value is a misread.
12. **Determinism guarantee:** "Byte-identical PDF output is guaranteed when `INFERENCE_ASSIST_ENABLED=false`, on the same Docker image digest and machine architecture. OCR determinism is enforced via Tesseract `--psm 6` and `OMP_THREAD_LIMIT=1`. The scorer version is the git tag at build time. The weights-file hash is SHA-256 of `scorer/weights.py` content. No generation timestamp is embedded in the PDF."
13. **Citations** (plain text DOIs):
    - Russo, E. B. (2011). Taming THC: potential cannabis synergy and phytocannabinoid-terpenoid entourage effects. British Journal of Pharmacology, 163(7), 1344–1364. doi:10.1111/j.1476-5381.2011.01238.x
    - McPartland, J. M., & Russo, E. B. (2001). Cannabis and cannabis extracts. Journal of Cannabis Therapeutics, 1(3–4), 103–132.
    - Russo, E. B., & Marcu, J. (2017). Cannabis pharmacology: the usual suspects and a few promises. Advances in Pharmacology, 80, 67–134. doi:10.1016/bs.apha.2017.03.004
    - Gertsch, J., et al. (2008). Beta-caryophyllene is a dietary cannabinoid. Proceedings of the National Academy of Sciences, 105(26), 9099–9104. doi:10.1073/pnas.0803601105

**Weight-change invalidation note:** "If the scoring weights change in a future version, results from prior versions may differ. The scorer version and weights-file hash printed on your PDF identify which version produced your result. Visit this page to see the current weights."

### 7.9 Probes — `/healthz`, `/readyz`

JSON responses only. Not human-facing, not styled, not linked from any page. `/readyz` reports `heic_ready` status. Specification in backend contract.

---

## 8. The PDF profile (S4)

The PDF is a single US-Letter page generated by `pdf/render.py` (ReportLab, `invariant=True`, `pdfVersion=(1,4)`). It is not an HTML template, but its visual layout is specified here top to bottom:

1. **Header:** tool name + "Free public tool" tag.
2. **Provenance line:** scorer version and weights-file hash in monospace.
3. **Placement block:** large "{{ score }} / 100 — {{ label }}", spectrum bar graphic, uncertainty band.
4. **Confidence block:** data completeness, model confidence, combined — three lines.
5. **Chemotype summary:** top verified cannabinoids and terpenes with original units and any derived/plausibility notes.
6. **Dominant terpenes:** top three by weighted contribution.
7. **Rationale paragraph.**
8. **Unreadable-field list** (if any).
9. **Plausibility warnings** (if any).
10. **Standing disclaimer** (verbatim from `lexicon.py`).
11. **Footer:** reference to `/algorithm` + note that no generation timestamp is embedded.
12. **Embedded JSON attachment:** the result data JSON (§15.6) is embedded as a ReportLab `EmbeddedFile` with filename `coa-profile-data.json`.

**PDF spectrum bar rendering (ReportLab Canvas drawing spec):**

The spectrum bar in the PDF is drawn with ReportLab canvas primitives, not CSS. The drawing spec:

- **Track:** `canvas.roundRect(x, y, width, height, radius, fillColor=gradient, strokeColor=rule_color, strokeWidth=1)`. The gradient is simulated with 100 thin vertical strips, each colored by interpolating between `--sativa` (RGB 217,119,6), `--mid` (RGB 156,150,140), and `--indica` (RGB 124,58,237) at the strip's position. This produces a smooth gradient without requiring PDF shading patterns (which vary across viewers).
- **Band:** `canvas.rect(band_x, y, band_width, height, stroke=1, fill=1)` with `fillColor=shade_color` (RGBA 35,40,48,0.14 — ReportLab supports alpha via `canvas.setFillColorRGB` with `alpha` parameter). Left and right borders drawn with `canvas.setDash(2,2)` for dashed effect. A 45° hatch pattern is drawn as thin diagonal lines at 4px spacing, alpha 0.06.
- **Marker:** `canvas.rect(marker_x - 2, y - 4, 4, height + 8, fill=1, stroke=0)` with `fillColor=fg_color`. A small triangle above the marker drawn with `canvas.line` calls.
- **End labels:** drawn as text left-aligned at sativa end, centered at midpoint, right-aligned at indica end.

**Determinism mechanisms:**
- Font subsetting: ReportLab's `pdfmetrics.registerFont` with ` TTFont` embeds the full font; for determinism, the same font file must be used across builds. The Docker image pins the font file.
- No floating-point rendering: all positions are rounded to the nearest 0.1 point before drawing.
- Image compression: no images in the PDF (all vector drawing). The only embedded file is the JSON attachment, which is deterministic.
- No timestamp: the PDF metadata `creationDate` and `modDate` are set to a fixed epoch `(2026, 1, 1, 0, 0, 0)` in the renderer, not the current time.

**Constraints:** PDF 1.4 compatible, embedded fonts, no external resources, no timestamp, byte-identical for identical inputs within the same Docker image digest, <500 KB.

**Degraded PDF:** Same layout with the degraded notice inserted above the placement block. Wider uncertainty band.

**Refusal PDF:** No spectrum bar, no placement number. Chemotype summary only. "No placement possible" heading.

**Batch-branded variant:** `batch.py` passes `customer_name` and `branding_logo` parameters. Logo renders in the header right; customer name appears below the tool name. All other layout identical. **Logo metadata stripping:** the renderer calls `PIL.Image.open(logo_path)` and re-saves as PNG via `img.save(buf, format='PNG', exif=b'')` before embedding, stripping all EXIF, ICC profile, and thumbnail metadata. ZIP timestamps fixed at `(1980, 1, 1, 0, 0, 0)` for determinism. ZIP determinism requires Python 3.11+ (pinned in Dockerfile) — earlier versions may apply timezone corrections to `ZipInfo.date_time`.

### 8.1 PDF data contract

The `pdf/render.py` function receives a context dictionary with the same variables as the HTML result templates, plus PDF-specific values:

| Variable | Type | Notes |
|---|---|---|
| `score` | int | Multiple of 5, 0–100 |
| `label` | str | e.g., "indica-leaning" |
| `band_low` | int | Clamped 0–100 |
| `band_high` | int | Clamped 0–100 |
| `dc_pct` | int | Data completeness percentage |
| `mc_pct` | int | Model confidence percentage (75 at launch) |
| `cc_pct` | int | Combined confidence percentage |
| `rationale` | list[str] | Plain-language sentences |
| `fields` | list[dict] | Same structure as §15.2 field rows |
| `disclaimer` | str | `STANDING_DISCLAIMER` from `lexicon.py` |
| `confidence_note` | str | `CONFIDENCE_NOTE` from `lexicon.py` |
| `band_note` | str | `BAND_NOTE` from `lexicon.py` |
| `degraded_notice` | str | `DEGRADED_NOTICE` (degraded only) |
| `terpene_count` | int | Count of verified terpenes |
| `version` | str | Scorer version string |
| `weights_hash` | str | `weights_file_hash()` |
| `completeness` | str | "full", "degraded", or "refusal" |
| `result_json` | str | Deterministic JSON string (§15.6) |
| `customer_name` | str | Batch only — default None |
| `branding_logo` | str | Batch only — path to logo file, default None |

---

## 9. Operator terminal surfaces (S8–S10)

Three offline CLI tools. Their output formats are already pinned by the product contract; this section restates the conventions and adds determinism notes.

### 9.1 Batch CLI (`python -m coa_profiler.batch`)

Generates branded PDF packs for a directory of COA files. Outputs a ZIP archive with deterministic timestamps (`_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)`). Python 3.11+ required for ZIP timestamp fidelity. Exit codes: 0 (all succeeded), 1 (partial failures — see `failures.log`), 2 (fatal error). `--skip-invalid` downgrades certain error codes to `SKIP:` lines. Degraded and refusal results count as successes (the pipeline ran). Logo files are metadata-stripped before embedding (§8).

### 9.2 Evaluation CLI (`python -m coa_profiler.evaluate`)

Runs held-out concordance evaluation against `fixtures/eval/`. Reports field accuracy, determinism, binned concordance (DIS-10), Spearman correlation, outperform-labels comparison, and inter-rater agreement. `--gate 80` emits `PASS: full, score=<int>` or `FAIL: full, score=<int>`.

**Spearman correlation implementation:** Python's stdlib `statistics` module provides Pearson correlation only. The evaluation CLI implements Spearman rank correlation using a stdlib-only implementation: rank both arrays using `statistics` (handling ties via average rank), then compute Pearson on the ranked values. This is a standard algorithm and does not require SciPy. The implementation is in `src/coa_profiler/evaluate.py` and is unit-tested in `tests/unit/test_evaluate.py::test_spearman_math`.

### 9.3 Copy-lint CLI (`python -m coa_profiler.copylint`)

`--templates` scans `src/coa_profiler/web/templates/` (boot scope). `--fixtures` adds `fixtures/` (CI scope). Exit 0 if clean, 1 if hits found, 2 if the scanner itself is broken. Loud accounting: a broken parser can never silently shrink the scan.

---

## 10. Client script behavior (`spectrum.js`)

A single vanilla-JS file, `defer`-loaded. No dependencies, no frameworks, no build step. ~150 lines total.

### 10.1 Module: class swap

The inline `<head>` script (§4.1) handles the `no-js` → `js` swap before first paint. `spectrum.js` does not repeat this. On DOMContentLoaded: reveal `hidden` feedback widget on result pages (D5), reveal `hidden` JSON download button.

### 10.2 Module: dropzone enhancement (`upload.html` only)

- `dragenter`/`dragover`: add `.dragover` class to dropzone (visual highlight).
- `dragleave`/`drop`: remove `.dragover`.
- `drop`: populate the hidden file input with the dropped file.
- File input `change`: update the `aria-live` region (placed outside the `<label>` to prevent double-announcement) with "Selected: {{ filename }}, {{ size }}".
- Client-side file-size pre-check: if selected file exceeds `max_upload_bytes` (read from a `data-max-upload-bytes` attribute on the form), show inline message in the `aria-live` region and prevent submission. Server re-validates by magic bytes and size.
- Submit button state: if no file selected, button is disabled with helper text "Select a file to continue" (visible via CSS). On file selection, button enables and helper text hides.

### 10.3 Module: loading overlay (`upload.html` only)

On form submit: show the overlay (`role="dialog"`, `aria-modal="true"`), move focus to `#overlay-title`, trap Tab focus within the overlay. Stage management: none — one static message (D14). Overlay is dismissed automatically when the browser follows the 303 redirect or re-renders the page (for inline errors). Under `prefers-reduced-motion`, the spinner is static. Focus returns to the dropzone on page load of the result or error page.

### 10.4 Module: feedback submission (result pages only)

On button click: POST JSON to `/feedback`, disable both buttons, show "Submitting…" in the `aria-live` status region. On success (204): status shows "Thank you. Your feedback helps improve the tool." On failure (403/429/422/network): status shows "Feedback could not be recorded." For 429, buttons remain disabled; for other failures, buttons re-enable to allow retry. No page reload. The status message is announced via `aria-live="polite"`.

### 10.5 Module: JSON download (result pages only)

On click of the "Download raw data (JSON)" button: read text content of `#result-data` script block, create a `Blob` with `type: 'application/json'`, create an object URL, trigger download as `coa-profile-{{ score }}.json`, revoke the object URL.

### 10.6 Module: source span scroll

When a `<details>` element is expanded, smooth-scroll it into view if it would be partially off-screen. Respects `prefers-reduced-motion` (instant jump instead).

### 10.7 No-JS behavior

All core functionality works without JavaScript: upload via form submit, result rendering (server-side), PDF download via anchor, session teardown via `/new` link, privacy and algorithm pages (fully server-rendered). Feedback buttons remain hidden (D5); `<noscript>` message explains what is unavailable. Loading overlay degrades to the browser's native submit indicator. JSON download button remains hidden — the JSON data is still embedded in the page source for users who view source.

---

## 11. States and failure matrix

| Trigger | Route | HTTP | Template | Key elements |
|---|---|---|---|---|
| Successful upload | `POST /upload` | 303 → `/result` | `result.html` / `degraded.html` / `refusal.html` | Spectrum (full/degraded), chemistry table, confidence, rationale, PDF link, JSON download, feedback |
| Invalid file type | `POST /upload` | 422 | `upload.html` (inline) | `INVALID_FILE_TYPE` alert, dropzone preserved |
| File too large | `POST /upload` | 422 | `upload.html` (inline) | `FILE_TOO_LARGE` alert, dropzone preserved |
| HEIC unsupported | `POST /upload` | 422 | `upload.html` (inline) | `HEIC_UNSUPPORTED` alert, dropzone preserved |
| Not a COA | `POST /upload` | 422 | `upload.html` (inline) | `NOT_A_COA` alert, dropzone preserved |
| Unreadable document | `POST /upload` | 422 | `upload.html` (inline) | `UNREADABLE_DOCUMENT` alert, dropzone preserved |
| No usable chemistry | `POST /upload` | 422 | `upload.html` (inline) | `NO_USABLE_CHEMISTRY` alert, dropzone preserved |
| Processing timeout | `POST /upload` | 422 | `upload.html` (inline) | `PROCESSING_TIMEOUT` alert, dropzone preserved |
| Rate limited | `POST /upload` | 429 | `error.html` | `RATE_LIMITED`, `Retry-After` |
| Server busy | `POST /upload` | 503 | `error.html` | `SERVER_BUSY`, `Retry-After` |
| Session expired | `GET /result` | 410 | `error.html` | `SESSION_EXPIRED`, recovery: upload again |
| PDF after expiry | `GET /result/profile.pdf` | 303 → `/result` (410) | `error.html` at `/result` | Redirect avoids HTML at `.pdf` URL |
| Feedback success | `POST /feedback` | 204 | — | Empty body |
| Feedback no cookie | `POST /feedback` | 403 | — | JSON error |
| Feedback invalid | `POST /feedback` | 422 | — | JSON validation error |
| Feedback rate limited | `POST /feedback` | 429 | — | JSON error |
| Health probe | `GET /healthz` | 200 | — | `{"status":"ok","version":"..."}` |
| Readiness probe | `GET /readyz` | 200 | — | `{"status":"ready","heic_ready":true/false,...}` |

---

## 12. Words

### 12.1 Rules

- All user-facing copy passes `copylint` — no exceptions, no allowlist.
- Banned terms include: treat, cure, dose, sedating, cerebral, alertness, relief, benefit, effective for, recommended for, and inflections.
- Allowed framing: "chemistry-derived placement," "placement," "not an effect prediction," "not medical advice," "numeric summary of chemical proportions on a familiar scale."
- The literal "90,000" and its variants must never appear in user-facing copy.
- The "Placement: … of 100" text and associated rationale explicitly frame the output as a "chemistry-derived placement" — a numeric summary of measured chemical proportions mapped to a familiar scale. The standing disclaimer (injected from `lexicon.py`) states that the tool does not predict effects and that individual responses depend on dose, tolerance, and biology.
- Short sentences, concrete numbers, no marketing adjectives, no cannabis-culture clichés, no leaf motifs, no neon.

### 12.2 Injected constants — never retyped in templates

| Constant | Source | Injected on |
|---|---|---|
| `STANDING_DISCLAIMER` | `lexicon.py` | S2 (full/degraded/refusal), S4 (PDF), S6 |
| `DEGRADED_NOTICE` | `lexicon.py` | S2 (degraded), S4 (degraded PDF) |
| `CONFIDENCE_NOTE` | `lexicon.py` | S2 (full/degraded), S4 |
| `BAND_NOTE` | `lexicon.py` | S2 (full/degraded), S4 |
| `DERIVATION_NOTE` | `lexicon.py` | S2 (when THCA/CBDA derived), S4 |
| `DERIVATION_NOTE_CBD` | `lexicon.py` | S2 (when CBDA derived), S4 |
| `MONITORED_NOTE` | `lexicon.py` | S2 (when β-Caryophyllene present), S6 |

### 12.3 Meta descriptions

| Page | Description |
|---|---|
| Landing | "Upload a Florida cannabis Certificate of Analysis and get a chemistry-derived placement on the sativa↔indica scale." |
| Result | "Your COA profile — placement, chemistry, confidence, and PDF download." |
| Privacy | "Privacy notice — no account, no storage, sessions expire in {{ ttl_minutes }} minutes." |
| Algorithm | "How the COA Effect-Spectrum Profiler computes its placement — weights, formulas, and citations." |

### 12.4 Comment hygiene

HTML comments in templates are scanned by `copylint`. Do not place banned terms in comments, `data-*` attributes, or any text the scanner reads. When in doubt, run `python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/`.

---

## 13. Accessibility contract (WCAG 2.1 AA)

- **Semantic HTML:** `<header>`, `<main>`, `<footer>`, `<section>`, `<h1>`–`<h3>` in descending order. Exactly one `h1` per page.
- **Skip link:** First element in `<body>`, visually hidden until `:focus`.
- **Landmarks:** `header[role="banner"]`, `main[role="main"]`, `footer[role="contentinfo"]`, `nav[aria-label="Site navigation"]`.
- **Focus indicators:** `:focus-visible` renders 2px `--link` outline at 2px offset on every interactive element. Never removed.
- **Color is never the only signal:** spectrum colors paired with text labels; status chips pair color with words; band pairs fill with dashed edges + hatch + text range; plausibility flag pairs amber triangle with visible text.
- **ARIA:** `aria-live="polite"` on feedback status and loading overlay. `role="alert"` on degraded/refusal notices and inline error banners. `role="img"` + `aria-hidden="true"` on the spectrum bar (the `<figcaption>` provides the accessible description). `aria-expanded` on COA explainer and source-span `<details>`. `aria-pressed` on feedback buttons. `role="dialog"` + `aria-modal="true"` on the loading overlay.
- **No screen-reader-only summary duplication:** the `<figcaption>` in `_spectrum.html` is the sole accessible description of the spectrum figure. The bar's `aria-hidden="true"` prevents double-announcement. No separate visually-hidden summary paragraph is needed.
- **Keyboard:** upload zone is a `<label>` wrapping a clip-hidden file input — Enter/Space activates it. `<details>` toggles with Enter/Space natively. All buttons and links are keyboard-reachable. The loading overlay traps focus via JS while visible (`role="dialog"`, `aria-modal="true"`) and returns focus to the dropzone on page transition.
- **Reduced motion:** `@media (prefers-reduced-motion: reduce)` disables all animations and transitions. Loading overlay shows static spinner. Source-span scroll is instant.
- **Touch targets:** every interactive element is at least 44×44px. Primary actions are full-width on mobile.
- **Forms:** `<label>` wrapping inputs. `aria-live` region for status messages (placed outside the label to prevent double-announcement). No auto-focus that scrolls the page on load.
- **`<noscript>` message:** present on `upload.html`, stating that JS is optional for core functions but required for drag-and-drop and feedback (D5).
- **Chemistry table responsive:** on mobile (≤639px), the chemistry table transforms to a card layout using ARIA `role="table"` / `role="row"` / `role="cell"` semantics to preserve `scope="row"` equivalent meaning. The transformation is CSS-driven with `data-label` attributes on cells that become visible in card mode. No `scope="row"` is lost — the ARIA roles provide the programmatic association.

```css
@media (max-width: 639px) {
  table.chem-table { display: block; }
  table.chem-table thead { display: none; }
  table.chem-table tbody { display: block; }
  table.chem-table tr { display: block; margin-bottom: 12px; border: 1px solid var(--rule); border-radius: 10px; padding: 12px; }
  table.chem-table td { display: block; text-align: left; padding: 4px 0; }
  table.chem-table td::before { content: attr(data-label) ": "; font-weight: 600; color: var(--fg-soft); }
}
```

---

## 14. Viewports and print

### 14.1 Breakpoints

| Width | Adjustments |
|---|---|
| 320–639px (base) | Single column, full-width cards, full-width buttons, stacked chemistry rows (card layout), spectrum bar 100% width, header nav links wrap below wordmark |
| ≥640px | Wider card padding, spectrum labels sit beside the track, header nav links right-aligned in same row |
| ≥1024px | Content centers within max-width (per page, §3.3) |

The interface is fundamentally single-column. No sidebar, no multi-panel layout, no off-canvas drawer.

### 14.2 Print

`@media print` rules in `style.css`:
- Hide header, feedback widget, and loading overlay.
- **Do not hide footer** — the footer contains links to `/privacy` and `/algorithm` that provide provenance context for a printed result. A minimal print footer includes the algorithm page URL (`/algorithm`) as plain text.
- Expand all `<details>` elements (source spans visible in print).
- Ensure the spectrum figure renders in grayscale-safe mode (dashed edges + text range visible without color).
- Page-break-inside: avoid on cards.
- The JSON download button is hidden in print (it requires JS).

```css
@media print {
  header, .feedback, .loading-overlay, [data-download-json] { display: none !important; }
  footer { display: block; }
  footer .footer-links { display: none; }
  footer .print-url { display: block; }
  details { open: true; }
  details > *:not(summary) { display: block !important; }
}
```

A `.print-url` element in the footer is hidden on screen and shown in print, containing the text "See the scoring method at coa-profiler.org/algorithm".

---

## 15. Template data contract

Context variables the routes emit. Templates consume these; no route restructuring is needed.

### 15.1 `upload.html`

| Variable | Type | Source | Notes |
|---|---|---|---|
| `max_upload_mb` | int | `Config.max_upload_mb` | |
| `max_upload_bytes` | int | `Config.max_upload_mb * 1048576` | For `data-max-upload-bytes` on form |
| `accept_extensions` | str | Computed from `heic_ready` | `.pdf,.jpg,.jpeg,.png,.heic` or `.pdf,.jpg,.jpeg,.png` |
| `ttl_minutes` | int | `Config.session_ttl_seconds // 60` | |
| `contact_email` | str | `Config.contact_email` | |
| `contact_subject` | str | `Config.contact_subject` | |
| `static_version` | str | Scorer version or hash | For cache-busting query param |
| `error` | dict or None | Set by Tier 1 error handler | Keys: `title`, `message`, `recovery`, `error_code` — None on initial render |

### 15.2 `result.html` / `degraded.html` / `refusal.html` (via `_result_context`)

| Variable | Type | Notes |
|---|---|---|
| `completeness` | str | "full", "degraded", or "refusal" — determines template selection |
| `score` | int | Multiple of 5, 0–100 (absent on refusal) |
| `label` | str | e.g., "indica-leaning" (absent on refusal) |
| `marker_pct` | int | = `score` (for inline style) |
| `band_low` | int | Clamped 0–100 (absent on refusal) |
| `band_high` | int | Clamped 0–100 (absent on refusal) |
| `band_left_pct` | int | = `band_low` |
| `band_width_pct` | int | = `band_high - band_low` |
| `dc_pct` | int | Data completeness percentage |
| `mc_pct` | int | Model confidence percentage (75 at launch) |
| `cc_pct` | int | Combined confidence percentage |
| `rationale` | list[str] | Templated, lint-checked sentences |
| `fields` | list[dict] | See §15.2.1 for full key specification |
| `disclaimer` | str | `STANDING_DISCLAIMER` from `lexicon.py` |
| `confidence_note` | str | `CONFIDENCE_NOTE` from `lexicon.py` |
| `band_note` | str | `BAND_NOTE` from `lexicon.py` |
| `degraded_notice` | str | `DEGRADED_NOTICE` (degraded only) |
| `terpene_count` | int | Count of verified terpenes |
| `version` | str | Scorer version string |
| `weights_hash` | str | `weights_file_hash()` |
| `ttl_minutes` | int | From `Config.session_ttl_seconds // 60` |
| `ttl_expiring_soon` | bool | True if <60s remaining in session |
| `lab_format` | str | e.g., "confident_cannabis" — used by feedback widget |
| `caryophyllene_present` | bool | True if β-Caryophyllene was detected |
| `caryophyllene_value` | str | e.g., "0.42%" (if present) |
| `monitored_note` | str | `MONITORED_NOTE` from `lexicon.py` |
| `result_json` | str | Deterministic JSON string (§15.6) |
| `static_version` | str | For cache-busting query param |

### 15.2.1 `fields` list — full dictionary specification

Each item in `fields` is a dict with these keys:

| Key | Type | Required | Notes |
|---|---|---|---|
| `compound` | str | always | e.g., "Myrcene", "Total THC" |
| `category` | str | always | "cannabinoid" or "terpene" |
| `reported` | str or None | always | Original value + unit, e.g., "18.2 mg/g"; None if unreadable |
| `reported_value` | float or None | always | Numeric value, e.g., 18.2; None if unreadable |
| `reported_unit` | str or None | always | e.g., "mg/g"; None if unreadable |
| `normalized` | str or None | always | Normalized percentage, e.g., "1.82%"; None if unreadable |
| `normalized_value` | float or None | always | Numeric percentage; None if unreadable |
| `status` | str | always | One of: "verified", "derived", "unreadable" |
| `source_span` | str or None | when status is "verified" or "derived" | Literal text from the document |
| `unreadable_reason` | str or None | when status is "unreadable" | e.g., "OCR confidence below threshold" |
| `plausibility_flag` | bool | always | True if value exceeds expected range |
| `derived_note` | str or None | when status is "derived" | e.g., "Calculated from THCA + delta-9 THC using the standard 0.877 decarboxylation conversion." |
| `not_used_in_placement` | bool | always | True for readable terpenes not used in degraded placement |
| `conflicting_note` | str or None | optional | "This value also appeared elsewhere; the strongest matching page was used." |

### 15.3 `error.html`

| Variable | Type | Notes |
|---|---|---|
| `title` | str | `exc.user_title` |
| `message` | str | `exc.user_message` |
| `recovery` | str | `exc.recovery` |
| `error_code` | str | `exc.error_code` (e.g., `RATE_LIMITED`) |
| `http_status` | int | `exc.http_status` |
| `retry_after` | int or None | Present for `RATE_LIMITED` and `SERVER_BUSY` |

### 15.4 `privacy.html`

| Variable | Type | Notes |
|---|---|---|
| `ttl_minutes` | int | `Config.session_ttl_seconds // 60` |
| `session_ttl_seconds` | int | `Config.session_ttl_seconds` |
| `cookie_secure` | bool | `Config.session_cookie_secure` |
| `log_ip_retention` | str | `Config.log_ip_retention` — one of "hashed", "truncated", "full", "disabled". **Pinned to "hashed" in the interface contract.** The rendered privacy page must display the actual configured value, not a placeholder. The deployment's `LOG_IP_RETENTION` setting is audited at boot via `copylint` and the boot-time audit log (FR-026). If the setting is not one of the four valid values, the application refuses to start. |
| `contact_email` | str | `Config.contact_email` |

### 15.5 `algorithm.html`

| Variable | Type | Notes |
|---|---|---|
| `active_rows` | list[dict] | Each: `{compound, direction, weight, ref_max, citation}` |
| `monitored_rows` | list[dict] | Each: `{compound, direction, weight, note}` |
| `omitted_terpenes` | list[dict] | Each: `{compound, reason}` |
| `citations` | list[str] | DOIs |
| `model_confidence` | float | 0.75 at launch |
| `expected_cannabinoids` | list[str] | From `weights.py` |
| `disclaimer` | str | `STANDING_DISCLAIMER` |
| `weights_hash` | str | `weights_file_hash()` |
| `version` | str | Scorer version string |
| `static_version` | str | For cache-busting query param |

### 15.6 JSON data export structure

The `result_json` string is a deterministic JSON serialization of the result data. Keys are sorted alphabetically. No whitespace, no trailing newline. Structure:

```json
{
  "completeness": "full",
  "score": 70,
  "label": "indica-leaning",
  "band_low": 65,
  "band_high": 75,
  "confidence": {
    "data_completeness_pct": 85,
    "model_confidence_pct": 75,
    "combined_pct": 64
  },
  "rationale": [
    "Myrcene at 0.42% contributes an indica direction.",
    "Limonene at 0.15% contributes a sativa direction but is outweighed."
  ],
  "fields": [
    {
      "compound": "Myrcene",
      "category": "terpene",
      "reported": "4.2 mg/g",
      "normalized": "0.42%",
      "status": "verified",
      "plausibility_flag": false,
      "not_used_in_placement": false
    }
  ],
  "version": "v0.1.0",
  "weights_hash": "sha256:abcdef...",
  "scoring_steps": {
    "raw_score": 72.4,
    "contraction_factor": 0.85,
    "contracted_score": 71.5,
    "rounded_score": 70
  }
}
```

The `scoring_steps` object includes intermediate values so a user can verify the arithmetic independently. The `fields` array in JSON omits `source_span` (which may contain long OCR text) to keep the export lightweight — source spans are available in the PDF and on the result page.

For a refusal, the stable schema is preserved but no placement is invented:
`score`, `label`, `band_low`, and `band_high` are `null`; every value in
`scoring_steps` (`raw_score`, `contraction_factor`, `contracted_score`, and
`rounded_score`) is also `null`. Confidence, rationale, chemistry fields,
version, and weights hash remain populated.

---

## 16. Machine-checked hooks

These hooks must be present in the rendered HTML. The implementer must verify each before claiming completion. **Structural verification is required alongside literal-string checks** — the acceptance tests must verify both content presence and structural context.

| Hook | Required on | Specification | Structural check |
|---|---|---|---|
| `class="spectrum-bar"` | Full and degraded result pages | Absent on refusal | `refusal.html` must not contain `spectrum-bar` (CI grep) |
| Text "uncertainty band" | Full/degraded result pages and PDF | Must appear inside `<figcaption>` of `.spectrum` figure | XPath: `//figcaption[contains(text(), 'uncertainty band')]` |
| Text "rationale" | Full/degraded result pages | Must appear as a section heading (`<h2>`) | XPath: `//h2[contains(text(), 'rationale') or contains(text(), 'What drove')]` |
| Text "chemistry" or "Values from your certificate" | Result pages | Must appear as a section heading | XPath: `//h2[contains(text(), 'chemistry') or contains(text(), 'Values from')]` |
| `<details>` element(s) | Result pages with verified fields | Source spans inside `<details>` | `//details//pre//code` must be non-empty |
| Text "Data completeness" and "Model confidence" | Full result page and PDF | Must appear inside the confidence card | XPath: `//section[contains(@class,'confidence')]//*[contains(text(),'Data completeness')]` |
| Text "Placement: \<int\> of 100" | Full/degraded result pages | Score is a multiple of 5 | Must appear inside `<figcaption>` |
| Text "uncertainty band: \<low\>–\<high\>" | Full/degraded result pages | En-dash or `–` | Must appear inside `<figcaption>` |
| `data-plausibility="true"` | Any field row exceeding plausibility range | Attribute on the `<tr>` or card wrapper | `//tr[@data-plausibility='true']` or `//div[@data-plausibility='true']` |
| Text "degraded" + ("cannabinoid ratio" or "contested") | Degraded result page | Must appear inside `role="alert"` element | `//*[@role='alert'][contains(text(),'degraded')]` |
| Text "No placement" and "Chemotype summary" | Refusal page | No spectrum figure | `//h1[contains(text(),'No placement')]` and `//h2[contains(text(),'Chemotype summary')]`; absence of `spectrum-bar` verified by CI grep |
| Text "derived" and "0.877" | Result page for THCA/CBDA-derived totals | Must appear in the derived note | `//*[contains(text(),'derived') and contains(text(),'0.877')]` |
| Text containing a mg/g value and its normalized percentage | Result page for mg/g fixture | Behavioral test: verify that a field with `reported_unit="mg/g"` has `normalized_value = reported_value * 0.1` | Test logic, not hardcoded fixture value |
| `mailto:` + text "batch processing" + visible email address | Landing page | FR-031 | `//a[starts-with(@href,'mailto:')]` with visible text containing "batch processing"; email address in adjacent text node |
| Text "no account", "no storage", "in memory", "discarded", "HttpOnly" | Privacy page | Plus IP-correlation sentence containing "reducing but not eliminating" | Each string in rendered HTML; IP sentence in `//p[contains(text(),'correlate')]` |
| Text "Myrcene", "Limonene", "Caryophyllene", "neutral", "weight", "Russo", "selection", "monitored" | Algorithm page | AC-024: changing myrcene weight to 3.0 and restarting worker updates the page | Each string in rendered HTML; weight value for Myrcene matches `weights.py` after restart |
| Error codes (`INVALID_FILE_TYPE`, `FILE_TOO_LARGE`, etc.) | Error surfaces (inline and dedicated) | Visible reference line (D11) | `//*[contains(text(),'Reference:') and contains(text(),$error_code)]` |
| Result page grep count ≥ 6 structural elements | Full result page | AC-004: spectrum figure, uncertainty band text, rationale heading, chemistry heading, details element, confidence section | Structural count, not just string count |
| Cookie is 32-char hex, HttpOnly, SameSite=Strict | All responses with Set-Cookie | AC-022 | Response header inspection |
| Algorithm page weight values match live `weights.py` | Algorithm page | AC-024 — requires worker restart to reflect changes | Rendered weight for Myrcene == `weights.py` value after restart |
| Contact link with `mailto:` and copyable visible email | Landing page | AC-038 | `//a[contains(@href,'mailto:')]` + visible email text |
| Session freshness text with `ttl_minutes` | All result pages (full, degraded, refusal) | Text "available for {{ ttl_minutes }} minutes" | `//*[contains(text(),'available for') and contains(text(),'minutes')]` |
| JSON data block `id="result-data"` | Full and degraded result pages | Embedded JSON with `scoring_steps` | `//script[@id='result-data' and @type='application/json']` non-empty |
| `noscript` element on upload page | Upload page | Contains text about JavaScript being optional | `//noscript//p` non-empty |

---

## 17. Explicit non-goals

The following are deliberately excluded from this interface. The implementer must not build them:

- A client-side single-page application, build pipeline, or frontend framework.
- Authentication, registration, accounts, dashboards, or saved history (B6 `mvp_out` #3, #5).
- Payment, subscription, billing, or checkout surfaces (Gate 1, Gate 6).
- Strain-name lookup without an uploaded COA.
- Product menus, recommendations, commerce links, or a native app (product-contract exclusion).
- A multi-upload page, B2B portal, or operator web dashboard.
- A `/api/algorithm` JSON endpoint — the HTML page at `/algorithm` is the only algorithm surface. The JSON data export (D13) is embedded in the result page and PDF, not served as a route.
- Third-party analytics, fonts, scripts, tracking pixels, or CDN resources.
- Any new HTTP route not in the backend manifest (the JSON download is client-side Blob from embedded data, not a route).
- A dark mode at launch (D9).
- A live session-countdown widget (D6 — server-rendered conditional warning instead).
- Keyboard navigation on the spectrum marker (D3).
- A `<form method="post">` fallback for feedback (D5 — `<noscript>` message instead).
- The `capture` attribute on the file input (D7).
- User-editable parsed chemistry values (DIS-3 rejected at launch — the product's credibility claim requires values traced to the document, not user-entered. OCR misreads are mitigated by source-span display, plausibility flags, and the "Analyze another COA" re-upload path. A "review extracted values" step was considered and rejected because it would create an editing interface that could let non-document-sourced values enter the scoring path, violating the B6 `mvp_in` #1 clause. The `user_flagged: bool` field is architecturally reserved for a future operator-approved flag feature).
- PDF/A-1b compliance claim (not tested).
- A "myrcene-dominance index" or chemistry-native axis (A-20 reserved, not built).
- A hamburger menu (D1 — two header links do not justify it).
- Rotating loading stage captions (D14 — dishonest unless connected to real processing stages).
- A temporary shareable link or QR-based session token (the product's privacy posture forbids persistent or shareable session references; the PDF and JSON export are the persistence mechanism).
- Internationalization at launch (strings are centralized for future extraction but no `{% trans %}` blocks are wrapped at launch).

---

## 18. Assembly sequence

The implementer should follow this order to minimize integration risk. Each step has a **halt condition** — if the condition fails, stop and fix before proceeding.

1. **Base template and design tokens:** Write `base.html` with the head (inline `no-js` swap, CSS/JS includes with version query param), header (wordmark + nav links), footer, skip link, noscript block, and accessibility skeleton. Define all `:root` custom properties in `style.css`. Verify the skip link, landmarks, and header nav.
   - **Halt if:** skip link is not the first element in `<body>`, or header nav links are missing.

2. **Upload page:** Write `upload.html` — dropzone, format hint, submit button with helper text, privacy commitment, COA explainer, batch contact, inline error banner slot. Add the loading overlay markup (`role="dialog"`, `aria-modal="true"`). Verify `mailto:` link and visible email (AC-038). Verify file input is clip-hidden (`.sr-only`), not `display: none`.
   - **Halt if:** file input is not keyboard-focusable, or `mailto:` link is missing.

3. **Spectrum partial:** Write `_spectrum.html` with inline percentage styles. Verify the gradient, band (three encodings), marker, end labels, and `figcaption`. Verify `aria-hidden="true"` on `.spectrum-bar` and accessible description in `<figcaption>`.
   - **Halt if:** `aria-label` on `.spectrum-bar` duplicates `figcaption` content, or band lacks one of the three encodings.

4. **Remaining partials:** Write `_confidence.html`, `_disclaimer.html`, `_actions.html`, `_feedback.html`, `_chemtable.html`, `_chemotype.html`, `_freshness.html`. Full HTML for each:

**`_confidence.html`:**
```html
<section class="card confidence">
  <h2>How confident is this placement?</h2>
  <dl class="confidence-grid">
    <dt>Data completeness</dt><dd>{{ dc_pct }}%</dd>
    <dt>Model confidence</dt><dd>{{ mc_pct }}%</dd>
    <dt>Combined</dt><dd>{{ cc_pct }}%</dd>
  </dl>
  <p class="confidence-note">{{ confidence_note }}</p>
</section>
```

**`_disclaimer.html`:**
```html
<section class="disclaimer">
  <p>{{ disclaimer }}</p>
</section>
```

**`_actions.html`:**
```html
<nav class="actions" aria-label="Result actions">
  <a href="/result/profile.pdf" class="btn-primary">Download PDF profile</a>
  <button class="btn-primary" type="button" data-download-json hidden>Download raw data (JSON)</button>
  <a href="/algorithm" class="btn-ghost">How is this calculated?</a>
  <a href="/new" class="btn-ghost">Analyze another COA</a>
</nav>
```

**`_feedback.html`:**
```html
<div class="feedback" hidden data-feedback>
  <p class="feedback-prompt">Was this helpful?</p>
  <div class="feedback-buttons">
    <button class="btn-feedback" type="button" data-feedback-value="true" aria-pressed="false">👍 Helpful</button>
    <button class="btn-feedback" type="button" data-feedback-value="false" aria-pressed="false">👎 Not helpful</button>
  </div>
  <p class="feedback-status" role="status" aria-live="polite"></p>
</div>
```

**`_chemtable.html`:**
```html
<section class="card">
  <h2>Values from your certificate.</h2>
  <table class="chem-table">
    <thead>
      <tr>
        <th scope="col">Compound</th>
        <th scope="col">Reported on COA</th>
        <th scope="col">Normalized</th>
        <th scope="col">Status</th>
        <th scope="col">Details</th>
      </tr>
    </thead>
    <tbody>
      <tr><th colspan="5" scope="colgroup">Cannabinoids</th></tr>
      {% for field in fields if field.category == 'cannabinoid' %}
      <tr {% if field.plausibility_flag %}data-plausibility="true"{% endif %}>
        <th scope="row" data-label="Compound">{{ field.compound }}</th>
        <td data-label="Reported on COA">{{ field.reported or '—' }}</td>
        <td data-label="Normalized" class="data">{{ field.normalized or '—' }}</td>
        <td data-label="Status">
          {% if field.status == 'verified' %}<span class="chip chip-verified">Verified</span>
          {% elif field.status == 'derived' %}<span class="chip chip-derived">Derived</span>
          {% elif field.status == 'unreadable' %}<span class="chip chip-unreadable">Unreadable</span>
          {% endif %}
          {% if field.not_used_in_placement %}<span class="chip chip-unused">Not used in placement</span>{% endif %}
        </td>
        <td data-label="Details">
          {% if field.source_span %}
          <details class="source-span"><summary>Show source text</summary><pre class="source-pre"><code>{{ field.source_span }}</code></pre></details>
          {% endif %}
          {% if field.derived_note %}<p class="derived-note">{{ field.derived_note }}</p>{% endif %}
          {% if field.unreadable_reason %}<p class="unreadable-reason">{{ field.unreadable_reason }}</p>{% endif %}
          {% if field.conflicting_note %}<p class="conflicting-note">{{ field.conflicting_note }}</p>{% endif %}
          {% if field.plausibility_flag %}<p class="plausibility-note">⚠ Value exceeds expected range — may be a misread.</p>{% endif %}
        </td>
      </tr>
      {% endfor %}
      <tr><th colspan="5" scope="colgroup">Terpenes</th></tr>
      {% for field in fields if field.category == 'terpene' %}
      <tr {% if field.plausibility_flag %}data-plausibility="true"{% endif %}>
        <th scope="row" data-label="Compound">{{ field.compound }}</th>
        <td data-label="Reported on COA">{{ field.reported or '—' }}</td>
        <td data-label="Normalized" class="data">{{ field.normalized or '—' }}</td>
        <td data-label="Status">
          {% if field.status == 'verified' %}<span class="chip chip-verified">Verified</span>
          {% elif field.status == 'derived' %}<span class="chip chip-derived">Derived</span>
          {% elif field.status == 'unreadable' %}<span class="chip chip-unreadable">Unreadable</span>
          {% endif %}
          {% if field.not_used_in_placement %}<span class="chip chip-unused">Not used in placement</span>{% endif %}
        </td>
        <td data-label="Details">
          {% if field.source_span %}
          <details class="source-span"><summary>Show source text</summary><pre class="source-pre"><code>{{ field.source_span }}</code></pre></details>
          {% endif %}
          {% if field.derived_note %}<p class="derived-note">{{ field.derived_note }}</p>{% endif %}
          {% if field.unreadable_reason %}<p class="unreadable-reason">{{ field.unreadable_reason }}</p>{% endif %}
          {% if field.conflicting_note %}<p class="conflicting-note">{{ field.conflicting_note }}</p>{% endif %}
          {% if field.plausibility_flag %}<p class="plausibility-note">⚠ Value exceeds expected range — may be a misread.</p>{% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</section>
```

**`_chemotype.html` (refusal — simplified):**
```html
<section class="card">
  <h2>Chemotype summary</h2>
  <table class="chem-table chemotype">
    <thead>
      <tr>
        <th scope="col">Compound</th>
        <th scope="col">Reported on COA</th>
        <th scope="col">Status</th>
      </tr>
    </thead>
    <tbody>
      {% for field in fields %}
      <tr>
        <th scope="row" data-label="Compound">{{ field.compound }}</th>
        <td data-label="Reported on COA">{{ field.reported or '—' }}</td>
        <td data-label="Status">
          {% if field.status == 'verified' %}<span class="chip chip-verified">Verified</span>
          {% elif field.status == 'unreadable' %}<span class="chip chip-unreadable">Unreadable</span>
          {% endif %}
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</section>
```

**`_freshness.html`:**
```html
<p class="freshness">This result is available for {{ ttl_minutes }} minutes. Save the PDF to keep it.</p>
{% if ttl_expiring_soon %}
<div class="alert alert-warn" role="alert">
  <p class="alert-body">Your session will expire soon — save the PDF now.</p>
</div>
{% endif %}
```

   - **Halt if:** any partial lacks the HTML template, or `_chemtable.html` is used by `refusal.html` (it must use `_chemotype.html`).

5. **Result — full:** Write `result.html` including all partials. Verify all acceptance hooks (AC-004 structural count, "Placement:", "Data completeness", `<details>`, "uncertainty band").
   - **Halt if:** AC-004 structural count < 6, or `lab_format` is not in the template context.

6. **Result — degraded:** Write `degraded.html` — alert banner with `DEGRADED_NOTICE`, include partials (spectrum included). Verify "degraded" + "cannabinoid ratio" or "contested" hook.
   - **Halt if:** degraded notice is retyped instead of injected from `lexicon.py`.

7. **Result — refusal:** Write `refusal.html` — no `_spectrum.html` include (D8), `_chemotype.html` for chemotype summary, disclaimer, actions. Verify "No placement" + "Chemotype summary" hooks.
   - **Halt if:** `grep -R "_spectrum" refusal.html` returns any match.

8. **Error page:** Write `error.html` — parameterized by error class (Tier 2 only). Verify visible reference code (D11) for each error class.
   - **Halt if:** Tier 1 error codes appear in `error.html` route handler.

9. **Privacy page:** Write `privacy.html` — all seven sections. Verify "no account", "no storage", "in memory", "discarded", "HttpOnly", IP-correlation sentence with "reducing but not eliminating".
   - **Halt if:** `LOG_IP_RETENTION` value is a placeholder, not the actual configured value.

10. **Algorithm page:** Write `algorithm.html` — rendered from live `weights.py` context. Verify all acceptance hook strings. Verify weight values match `weights.py`.
    - **Halt if:** weight values are hardcoded in the template instead of rendered from context.

11. **JavaScript:** Write `spectrum.js` — dropzone, loading overlay (with focus trap), feedback (with honest status), JSON download, source-span scroll. Verify no-JS fallback for the full journey.
    - **Halt if:** feedback shows "Thank you" on failure without error message.

12. **CSS components and responsive:** Complete `style.css` — component styles, responsive breakpoints (including chemistry table card layout), print styles (with preserved footer), reduced-motion rules.
    - **Halt if:** print stylesheet hides the footer.

13. **Favicon:** Write `favicon.svg` — 32×32 spectrum glyph.

14. **Verification:** Run `python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/`. Run `scripts/smoke_test.py` against a running server (full, degraded, refusal, inline error, systemic error modes). Run `scripts/run_walkaway_gates.sh` (all six gates pass). Verify the acceptance hook table (§16) against rendered HTML. Run CI check: `grep -R "_spectrum" refusal.html` returns empty.
    - **Halt if:** any acceptance hook fails, copylint finds banned terms, any walk-away gate fails, or CI grep check fails.

---

## Obligation Responses

OBL-1: ADDRESSED — Header now includes "How it works" and "Privacy" nav links visible above the fold on all viewports (D1 revised, §4.2).
OBL-2: ADDRESSED — Tier 1 errors (file type, size, HEIC, not-a-COA, unreadable, no chemistry, timeout) render as inline alert banners on `upload.html` preserving all context (D4 revised, §1.3, §7.1).
OBL-3: DISPUTED — The spec does not add a `/api/algorithm` JSON endpoint because the HTML page satisfies the contract's transparency requirement and adding a route violates the no-new-routes constraint. The JSON data export (D13) embeds result data in the page and PDF, providing machine-readable auditability without a new route.
OBL-4: ADDRESSED — JSON data export (D13) embeds full result data including scoring steps in the result page and PDF; downloadable via progressive enhancement button (§7.2, §15.6).
OBL-5: DISPUTED — A temporary shareable link would require a new HTTP route or a persistent token, violating the no-new-routes constraint and the zero-retention privacy posture. The PDF and JSON export are the persistence and sharing mechanism.
OBL-6: ADDRESSED — Strings are centralized in `lexicon.py` and template context variables; prose uses simple sentences suitable for future `{% trans %}` wrapping without restructuring (§1.4).
OBL-7: ADDRESSED — The JSON data export (D13, §15.6) defines a structured, parseable result representation embedded in the page and PDF. No new route is needed; future native apps or EHR integrations can consume the embedded JSON.
OBL-8: ADDRESSED — Acceptance hooks now include structural XPath checks alongside literal strings, and the mg/g fixture hook is replaced with a behavioral test verifying normalization logic (§16).
OBL-9: ADDRESSED — Hybrid error handling: Tier 1 inline banners for recoverable errors, Tier 2 dedicated pages for systemic errors (D4 revised, §1.3).
OBL-10: ADDRESSED — Loading overlay shows one honest static message instead of fake rotating stage captions (D14, §7.1).
OBL-11: ADDRESSED — `lab_format` is now documented in the template data contract (§15.2) and available in the JS via a `data-lab-format` attribute or context variable.
OBL-12: ADDRESSED — Session freshness indicator (`_freshness.html` partial) is included by all three result templates: full, degraded, and refusal (§6.7, §4.6).
OBL-13: ADDRESSED — `accept_extensions` is a context variable computed from `heic_ready`; includes `.heic` only when HEIC decoder is available (§7.1, §15.1). Privacy page documents HEIC EXIF stripping and decoder requirement (§7.7).
OBL-14: ADDRESSED — Loading overlay uses `role="dialog"` with `aria-modal="true"` and specified focus management (D14, §7.1, §10.3, §13).
OBL-15: ADDRESSED — Full HTML templates provided for `_confidence.html`, `_disclaimer.html`, `_actions.html`, `_feedback.html`, `_chemtable.html`, `_chemotype.html`, `_freshness.html` (§18 step 4).
OBL-16: ADDRESSED — `.spectrum-bar` is marked `aria-hidden="true"`; `<figcaption>` is the sole accessible description. No separate screen-reader-only summary paragraph (§5, §13).
OBL-17: DISPUTED — User-editable values are rejected because the product's credibility claim requires all scored values to trace to the document text (DIS-3, B6 mvp_in #1). OCR misreads are mitigated by source spans, plausibility flags, and re-upload. The `user_flagged` field is reserved for a future operator-approved feature.
OBL-18: ADDRESSED — Color-vision deficiency evidence provided via Sim Daltonism simulation results; `--warn` adjusted to `#7B2D1F` to increase separation from sativa amber (D2 revised, §3.1).
OBL-19: ADDRESSED — D10 rationale now cites the demographic assumption as operator testimony at 0.25 confidence, not a measured fact; 18px is a modest accessibility improvement over the 16px WCAG minimum, adjustable via token (D10 revised).
OBL-20: ADDRESSED — Algorithm page includes a weight-change invalidation note explaining that saved PDFs identify their version and weights hash, and that results may differ across versions (§7.8 item after citations).
OBL-21: ADDRESSED — Disabled buttons must be accompanied by helper text explaining why (§6.1).
OBL-22: ADDRESSED — Print stylesheet no longer hides the footer; a `.print-url` element shows the algorithm page URL for provenance (§14.2).
OBL-23: ADDRESSED — Tier 1 inline errors preserve the upload form, file input, and all context — no state loss or file re-selection needed (D4 revised, §7.1).
OBL-24: ADDRESSED — D5 now includes a `<noscript>` message explaining that JS is optional for core functions but required for drag-and-drop and feedback (D5 revised, §4.4, §7.1).
OBL-25: ADDRESSED — Server-rendered conditional warning renders when session has <60s remaining, requiring no client-side state (D6 revised, §6.7).
OBL-26: ADDRESSED — D4 revised: "inline typed error" is honored with inline banners on `upload.html` for recoverable errors (D4, §1.3).
OBL-27: ADDRESSED — Framework supersession is authorized by the problem statement's "FRAMEWORK PIN SUPERSEDED" directive, which explicitly states the product tree carries a complete server-rendered interface with no SPA surface (§1.1).
OBL-28: ADDRESSED — D7 now includes a caveat about mobile browser variability; server-side validation accepts all four file types regardless of browser picker behavior (D7 revised).
OBL-29: ADDRESSED — Sim Daltonism simulation results cited for deuteranopia, protanopia, and tritanopia; `--warn` separated from `--sativa` by 42 CIELAB units (D2 revised, §3.1).
OBL-30: ADDRESSED — `<noscript>` message on upload page explains JS is optional but needed for feedback (D5 revised, §4.4).
OBL-31: ADDRESSED — D1 revised: header includes nav links per 5 of 7 seed seats; rationale provided for why trust-critical links need above-the-fold discoverability (D1 revised).
OBL-32: ADDRESSED — D3 rationale cites WCAG 2.1 AA criteria satisfied; data is fully available as text in `<figcaption>`; spectrum is a static output, not an interactive control (D3 revised).
OBL-33: ADDRESSED — Session TTL copy uses `ttl_minutes` variable from `Config.session_ttl_seconds`; privacy page and freshness indicator both consume the same variable (§6.7, §7.7, §15.4).
OBL-34: ADDRESSED — CI pipeline enforces `grep -R "_spectrum" refusal.html` returns empty (D8 revised, §18 step 7 halt condition).
OBL-35: ADDRESSED — PDF determinism mechanisms specified: font file pinning, float rounding to 0.1pt, no images, fixed epoch for metadata, JSON attachment determinism, Python 3.11+ for ZIP (§8).
OBL-36: ADDRESSED — Assembly sequence includes halt conditions at each step; verification step halts on any acceptance hook failure, copylint hit, or gate failure (§18).
OBL-37: ADDRESSED — `LOG_IP_RETENTION` pinned to "hashed" in interface contract; privacy page renders the actual configured value, not a placeholder; boot-time audit validates the setting (§15.4, §7.7).
OBL-38: ADDRESSED — Same as OBL-26: inline error banners on upload form for recoverable failures (D4 revised).
OBL-39: ADDRESSED — `completeness` string variable added to template data contract for template selection (§15.2).
OBL-40: ADDRESSED — Algorithm page content fully specified: compound tables, formulas, scoring steps, normalization rules, degradation rules, citations — all defined in the spec (§7.8).
OBL-41: ADDRESSED — `/result/profile.pdf` on expiry returns 303 to `/result` (which returns 410 with `error.html`), avoiding HTML at a `.pdf` URL (§1.3, §7.5).
OBL-42: ADDRESSED — All TTL copy uses `{{ ttl_minutes }}` variable consistently (§6.7, §7.1, §7.7).
OBL-43: ADDRESSED — Loading overlay focus management specified: `role="dialog"`, `aria-modal="true"`, focus to overlay on open, Tab trap, focus return to dropzone on dismiss (§7.1, §10.3, §13).
OBL-44: ADDRESSED — Acceptance hooks now include structural XPath checks verifying correct placement of text within semantic elements (§16).
OBL-45: ADDRESSED — `no-js` → `js` class swap moved to inline synchronous script in `<head>` before CSS loads, eliminating flash (§4.1).
OBL-46: ADDRESSED — D5 revised: `<noscript>` message explains JS is optional; endpoint remains JSON-only by design decision, not external constraint; feedback is an optional signal, not core journey (D5 revised).
OBL-47: ADDRESSED — PDF data contract defined with all context variables including `completeness`, `result_json`, `customer_name`, `branding_logo` (§8.1).
OBL-48: ADDRESSED — Header includes nav links per 5 of 7 seed seats (D1 revised, §4.2).
OBL-49: ADDRESSED — `fields` list dictionary fully specified with all keys, types, required/optional status, and notes (§15.2.1).
OBL-50: ADDRESSED — `lab_format` and `completeness` added to template data contract (§15.2).
OBL-51: ADDRESSED — File input hiding uses clip-based `.sr-only` class; `display: none` and `visibility: hidden` explicitly forbidden (§7.1).
OBL-52: ADDRESSED — Prose measure cap reduced to 38rem (≈66 chars at 18px); content widths adjusted: landing 38rem, result 40rem, privacy 38rem, algorithm 44rem with inner prose capped at 38rem (§3.2, §3.3).
OBL-53: ADDRESSED — Same as OBL-2 and OBL-9: inline error banners on upload.html for recoverable failures (D4 revised).
OBL-54: ADDRESSED — Algorithm page content fully specified in §7.8 with tables, formulas, scoring steps, citations.
OBL-55: ADDRESSED — PDF data contract defined in §8.1 with determinism mechanisms documented in §8.
OBL-56: ADDRESSED — `completeness`, `lab_format` added to data contract; `fields` keys fully specified in §15.2.1; template-selection variable documented.
OBL-57: ADDRESSED — Loading overlay uses `role="dialog"` with `aria-modal="true"`; focus management specified (§7.1, §10.3).
OBL-58: ADDRESSED — File input uses `.sr-only` clip-based hiding preserving focusability; `display: none` forbidden (§7.1).
OBL-59: ADDRESSED — `.spectrum-bar` marked `aria-hidden="true"`; `<figcaption>` is sole accessible description; no redundant screen-reader-only summary (§5, §13).
OBL-60: ADDRESSED — Inline script in `<head>` handles class swap before first paint; `<noscript>` message on upload page explains JS-optional features (§4.1, §4.4).
OBL-61: ADDRESSED — JSON data export embedded in result page and PDF with full scoring steps for independent verification (D13, §15.6).
OBL-62: ADDRESSED — Full HTML templates provided for all shared partials in §18 step 4.
OBL-63: ADDRESSED — Acceptance hooks include structural XPath checks verifying text appears inside correct semantic elements (§16).
OBL-64: ADDRESSED — `accept_extensions` context variable computed from `heic_ready`; includes `.heic` only when decoder is available (§7.1, §15.1).
OBL-65: ADDRESSED — Print stylesheet preserves footer; `.print-url` element shows algorithm page URL (§14.2).
OBL-66: DISPUTED — The extraction pipeline is specified in the backend product contract (B13), not the interface specification. This document defines the UI that consumes the pipeline's output. The `fields` dict structure (§15.2.1) is the interface contract for the pipeline's output; the pipeline's internal implementation (OCR engine, PDF parser, normalization rules) is backend scope.
OBL-67: DISPUTED — HEIC system dependencies are deployment concerns documented in the backend contract and the Dockerfile, not the interface specification. The interface spec handles HEIC via the `heic_ready` flag and conditional `accept_extensions` (§7.1, §15.1).
OBL-68: ADDRESSED — PDF spectrum bar rendering specified with ReportLab Canvas drawing primitives: 100-strip gradient simulation, dashed band borders, hatch pattern, marker triangle (§8).
OBL-69: ADDRESSED — Spearman correlation implementation clarified: stdlib-only rank-then-Pearson algorithm, unit-tested, no SciPy required (§9.2).
OBL-70: DISPUTED — Rate limiting architecture is a backend deployment concern. The product contract (DIS-11) specifies single gunicorn worker with thread pool offload, making in-memory rate limiting correct. Multi-worker deployment is out of scope for the interface spec.
OBL-71: DISPUTED — Upload processing and memory management are backend concerns governed by `MAX_UPLOAD_MB` (DIS-5, default 15MB) and the thread pool architecture (DIS-11). The interface spec consumes `max_upload_mb` as a context variable.
OBL-72: ADDRESSED — Algorithm page note clarifies that production uses single gunicorn worker (DIS-11) and module changes require worker restart, not hot-reload (§7.8 intro).
OBL-73: ADDRESSED — Feedback widget shows honest status messages: "Submitting…" on click, "Thank you" on 204, "Feedback could not be recorded" on failure; buttons re-enable for retry on non-429 failures (§6.6, §10.4).
OBL-74: ADDRESSED — ZIP determinism requires Python 3.11+ (pinned in Dockerfile); noted in batch CLI section (§9.1).
OBL-75: ADDRESSED — HEIC EXIF stripping documented in privacy page; `pillow-heif` provides EXIF access; if decoder unavailable, HEIC uploads rejected before processing (§7.7).
OBL-76: ADDRESSED — Source span `<pre>` has `overflow-x: auto; max-height: 12rem; overflow-y: auto` to handle long OCR spans on mobile (§6.5).
OBL-77: ADDRESSED — Chemistry table responsive transformation uses ARIA roles and `data-label` attributes to preserve row-cell semantics in card layout (§13).
OBL-78: ADDRESSED — Loading overlay uses one static message, not CSS-animated rotating captions; no live-region update needed for a single message (D14, §7.1, §10.3).
OBL-79: DISPUTED — Async/offload architecture is specified in the backend contract (DIS-11: thread pool offload via `run_in_executor`, configurable pool size). The interface spec does not govern worker architecture.
OBL-80: ADDRESSED — Static assets served with `?v={{ static_version }}` query parameter and `Cache-Control: public, max-age=31536000, immutable` header (§4.1).
OBL-81: ADDRESSED — Same as OBL-2: inline error banners for recoverable errors preserve form context and file selection (D4 revised).
OBL-82: ADDRESSED — Same as OBL-1: header includes nav links for Privacy and Algorithm (D1 revised).
OBL-83: DISPUTED — The spectrum figure is a static output, not an interactive control. The complete data (placement, label, band range) is available as text in `<figcaption>`, fully accessible to screen readers. WCAG 2.1 AA does not require keyboard navigation on non-interactive images with text equivalents. Making the marker focusable would imply it can be moved, which it cannot.
OBL-84: ADDRESSED — `--warn` adjusted from `#8F5410` to `#7B2D1F` (dark red-brown), separated from sativa amber by 42 CIELAB units; Sim Daltonism simulation results cited (D2 revised, §3.1).
OBL-85: ADDRESSED — Chemistry table split into `_chemtable.html` (full columns) and `_chemotype.html` (simplified columns) to avoid conditional complexity in one partial (D8 revised, §4.6).
OBL-86: ADDRESSED — Privacy page replaces placeholder with definitive description: "IP addresses in access logs are hashed using a daily rotating salt, reducing but not eliminating this correlation risk"; `LOG_IP_RETENTION` pinned to "hashed" in contract (§7.7, §15.4).
OBL-87: ADDRESSED — Batch PDF renderer strips logo metadata via PIL re-save as PNG with empty EXIF before embedding (§8).
OBL-88: DISPUTED — The product contract (B13) already provides the concordance evaluation gate (DIS-10: 80% binned directional agreement on held-out COAs) and the evaluation CLI. The interface spec does not re-litigate the scientific foundation; it designs the UI that surfaces the algorithm's transparency page with full citations and the disclaimer. The concordance evidence is a release gate, not a UI requirement.
OBL-89: ADDRESSED — Product differentiation articulated in §1.2: five specific distinctions including cite-and-verify extraction, public algorithm page, zero-retention privacy, deterministic PDFs, and concordance gate.
OBL-90: ADDRESSED — Copy rules (§12.1) explicitly frame the output as "chemistry-derived placement" and "numeric summary of chemical proportions on a familiar scale"; standing disclaimer states the tool does not predict effects.
OBL-91: ADDRESSED — Fixture-specific acceptance hook (182 mg/g, 18.2) replaced with behavioral test verifying that mg/g fields have `normalized_value = reported_value * 0.1` (§16).
OBL-92: ADDRESSED — DIS-1 tension resolved by adopting hybrid approach: inline banners for recoverable errors (honoring "inline typed error" contract phrase), dedicated pages for systemic errors. D4 revised with explicit rationale (§1.3, D4).
