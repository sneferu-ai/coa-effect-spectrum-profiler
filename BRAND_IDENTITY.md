# str — Brand Identity

This file is a launch-frozen product contract. Read `BRAND_DIRECTION.md` first. Use the exact selected brand-mark bytes; do not redraw, replace, recolor, or generate another logo during the UI pass.

- Identity ID: `232acb725ed03d9e6258319c119171b89530686c4a98a612f57f7a24d8279dd7`
- Direction asset: `BRAND_ASSETS/brand-direction.png`
- Selected mark: `BRAND_ASSETS/brand-mark.png`
- Mark source: `generated_from_direction`
- Board-to-mark lineage: `exact`

## Required semantic color tokens

- `--brand-background`: `#1C2328`
- `--brand-foreground`: `#D6D2C2`
- `--brand-muted`: `#97968E`
- `--brand-primary`: `#D6D2C2`
- `--brand-secondary`: `#888C7D`
- `--brand-surface`: `#2D3538`

Copy the exact selected mark into the framework's public/static asset directory and reference that copy in the primary visible product surface. Apply every semantic color through the product's token layer. The direction board remains a design reference and must not be mistaken for the shipped mark. The orchestrator verifies the copied mark bytes, source reference, complete palette, and direction acknowledgement before B16 may pass.
