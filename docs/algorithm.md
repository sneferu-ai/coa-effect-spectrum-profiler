# Algorithm — COA Effect-Spectrum Profiler

This document is the authoritative human-readable reference for the scoring
function (FR-020). The same content is rendered publicly at `/algorithm`
(FR-023) from the live weight table in `src/coa_profiler/scorer/weights.py`.

## What the score is — and is not

The placement is a **chemistry-derived tendency** on the sativa↔indica axis:
an integer 0–100, rounded to the nearest 5 (21 distinct values), where 0 is
sativa-leaning and 100 is indica-leaning. It is a deterministic function of
the measured chemistry on one certificate of analysis (COA) and nothing else:
no strain name, dispensary label, crowdsourced rating, or external dataset
participates.

The sativa↔indica taxonomy is **morphological, not chemical**, and is
scientifically contested; published studies suggest strain labels often
correlate poorly with chemical composition. This tool uses the axis as a
familiar communication framework for patients who already encounter it at
dispensaries — not as a validated clinical taxonomy. The weights below are
**literature-derived hypotheses with clinical-informed directional
assignments**, not outputs of a quantitative model or clinical trial, and the
weights inherit the taxonomy's weakness.

## Weight table (active directional compounds)

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

## Monitored but not scored

| Compound | Direction | Weight | Reference max | Citation | Note |
|---|---|---|---|---|---|
| β-Caryophyllene | neutral | 0.0 | — | Gertsch et al. 2008 | CB2 agonism; no directional evidence on the tendency axis |

β-Caryophyllene is abundant on most COAs, but its cited literature (Gertsch
et al. 2008) addresses anti-inflammatory CB2 agonism — not directional
placement on the tendency axis. Assigning it a direction would systematically
bias most COAs toward indica without literature support (DIS-14). It is
extracted, displayed in the chemotype summary, and named in the rationale as
"present but not directionally scored pending better literature support."

## Weight selection criteria

Terpenes were selected based on (a) frequency of appearance on Florida COAs,
(b) availability of published directional literature in Russo 2011 or
McPartland & Russo 2001, and (c) coverage across at least two independent
sources. Omitted terpenes (bisabolol, eucalyptol, camphene, farnesene,
valencene, geraniol) lack published directional assignments in the cited
literature; they are extracted, displayed in the chemotype summary, and
listed in the rationale as "additional compounds present on your COA not
included in the current model." THC/CBD directions are explicitly labeled
weak priors and tuning parameters.

Reference maxima are **operator-informed estimates** based on typical Florida
COA ranges observed in Dr. S's practice — not statistical maxima. They are
tuning parameters subject to validation (assumption A-01).

## Normalization and unit conversion

All values are normalized to percent weight/weight before scoring:

| Unit | Conversion |
|---|---|
| `%` | used directly |
| `mg/g` | × 0.1 |
| `mg/mL` | × 0.1 (assumes density ≈ 1.0 g/mL; assumption A-17) |
| `ppm` | × 0.0001 |

The original value and unit are preserved and displayed beside the normalized
value. Every extracted value must trace to a literal text span in the
extracted document text (cite-and-verify); anything that cannot be verified
is recorded as **unreadable** — never interpolated, defaulted, or estimated.

**THCA/CBDA derivation (DIS-15):** when a COA reports THCA and delta-9 THC
separately but no "Total THC" line, the total is derived:

```
Total THC = delta-9 THC + 0.877 × THCA
Total CBD = CBD + 0.877 × CBDA
```

The 0.877 factor accounts for decarboxylation molecular-weight loss. Derived
values are marked `derived: true` and displayed with a conversion note.

## The five scoring steps

1. **Normalize units:** convert every reported value to percentage using the
   unit rules above and mark derived values. This step does not cap values at
   a reference maximum.
2. **Weight signed contributions:** for each verified scored compound `i`,
   `contribution_i = (normalized_value_i / reference_max_i) × weight_i × direction_i`,
   where direction is +1 for indica and −1 for sativa. Compounds absent from
   the COA contribute 0. Compounds present but not in the weight table are
   excluded from computation and named in the rationale.
3. **Raw score:** `raw_score = 50 + Σ(contribution_i) × 50`. A signed sum
   of zero is a valid midpoint score of 50, including when readable compounds
   are neutral or report zero. It is not a reason to refuse placement.
4. **Model-uncertainty contraction:**
   `contracted = 50 + (raw_score − 50) × U`, with **U = 0.85** for full
   placements and **U = 0.70** in degraded mode. U is a tuning parameter
   representing the hypothesis that literature-derived terpene-effect
   assignments carry substantial uncertainty. It is not a Bayesian posterior
   or a frequentist confidence interval.
5. **Round:** round `contracted` to the nearest multiple of 5, with an exact
   half-step tie rounded toward zero, then clamp to [0, 100].

## Uncertainty band (FR-029)

```
band_half_width = round_to_5((1 − combined_confidence) × 20), clamped to [5, 20]
band = [max(0, placement − half), min(100, placement + half)]
```

Band width reflects combined confidence (data completeness and model
confidence assumptions), not measurement precision.

## Two-component confidence (FR-009)

**Data completeness (DC):**

```
DC = max(0, 1.0
     − 0.15 × min(2, unreadable expected cannabinoids)   # expected: THC-total, CBD-total
     − 0.10 × min(5, unreadable reported terpenes)
     − 0.20 × [readable terpenes < 5]
     − 0.15 × [OCR mean confidence in [60, 75)]
     − 0.30 × [degraded mode])
```

The penalty constants are tuning parameters selected to produce meaningful
confidence variation across realistic data-quality scenarios; they are
subject to recalibration (assumption A-12).

**Model confidence (MC):** a tuning parameter fixed at **0.75** at launch —
an operator judgment that the literature-derived weights carry moderate but
not high reliability. MC is decoupled from the contraction factor U and is
not a statistical quantity. MC may be raised to 0.85 only after the held-out
evaluation shows concordance ≥ 90%, and any change requires updating this
document and `/algorithm`.

**Combined confidence:** `CC = DC × MC`. Below **CC = 0.25**, placement is
refused even in degraded mode.

## Degradation rules (DIS-6)

- **Full placement:** ≥ 1 cannabinoid verified AND ≥ 3 terpenes verified AND
  ≥ 60% of reported terpenes readable (the absolute ≥3 rule governs when the
  reported total is undeterminable).
- **Degraded placement:** cannabinoids verified but terpene data
  insufficient. Only the signed, weighted THC-total and CBD-total
  contributions participate (weights 0.5 each), U = 0.70, an additional 0.30
  data-completeness penalty, a visible notice that cannabinoid-only
  directional placement is particularly contested, and the CC ≥ 0.25 floor.
- **Refusal:** zero terpenes readable, no THC-total/CBD-total anchor readable,
  forced plausibility refusal, or degraded combined confidence below 0.25 — no
  placement; chemotype-only summary. Each output states the applicable reason.
- **Complete refusal:** zero chemistry fields readable — a typed error at
  upload time.

## Plausibility checks (FR-028)

Values exceeding expected ranges — THC-total > 40%, CBD-total > 25%, any
single terpene > 10%, any cannabinoid < 0% — are flagged with a warning on
the results page and in the PDF. Flagged values are still used (they trace to
the document). If more than half of the extracted values are implausible, the
document is re-parsed with the generic fallback parser; if the result is
still mostly implausible, placement is refused as inconsistent.

## Determinism (FR-022, DIS-12)

The same input COA processed by the same code version, weights, pinned
Tesseract version, `OMP_THREAD_LIMIT=1`, `--psm 6`, and the same Docker image
digest on the same machine architecture produces an identical placement, an
identical rationale, and a byte-identical PDF. The PDF embeds no generation
timestamp; provenance is the scorer version string (git tag, fixed at build
time) and the SHA-256 of `scorer/weights.py`. The guarantee applies only when
`INFERENCE_ASSIST_ENABLED=false`.

## Citations

- Russo EB. *Taming THC: potential cannabis synergy and
  phytocannabinoid-terpenoid entourage effects.* British Journal of
  Pharmacology, 2011. DOI: 10.1111/j.1476-5381.2011.01238.x
- McPartland JM, Russo EB. *Cannabis and Cannabis Extracts: Greater Than the
  Sum of Their Parts?* Journal of Cannabis Therapeutics, 2001.
  DOI: 10.1300/J175v01n03_08
- Russo EB, Marcu J. *Cannabis Pharmacology: The Usual Suspects and a Few
  Promising Leads.* Advances in Pharmacology, 2017.
  DOI: 10.1016/bs.apha.2017.03.004
- Gertsch J, et al. *Beta-caryophyllene is a dietary cannabinoid.*
  Proceedings of the National Academy of Sciences, 2008.
  DOI: 10.1073/pnas.0803601105

DOI resolution is verified by the operator before release (assumption A-22);
the automated gate checks only that the DOI patterns are present.
