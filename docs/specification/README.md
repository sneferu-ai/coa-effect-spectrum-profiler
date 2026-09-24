# The specification: the COA Effect-Spectrum Profiler

This folder holds the specification Sneferu built the COA Effect-Spectrum Profiler from. Every file here is copied byte for byte from Sneferu's own run records. Nothing was retyped or edited.

| File | What it is |
|---|---|
| [`SPECIFICATION.md`](SPECIFICATION.md) | the product contract, exactly as it stood at the spec-review gate |
| [`REQUEST.md`](REQUEST.md) | the original request the pipeline started from |
| [`REFINED_REQUEST.md`](REFINED_REQUEST.md) | the request after Sneferu refined it; the specification run worked from this |
| [`INTERFACE_SPECIFICATION.md`](INTERFACE_SPECIFICATION.md) | the `spec.md` that sat at the root of the finished product folder, titled *Interface Specification — COA Effect-Spectrum Profiler* |

## Where it came from

- **Business pipeline run:** `2026-08-11T19-39-44Z-pipeline-6ca86806`
- **Specification run:** `2026-08-11T21-59-48Z-spec-8466e6ba`
- **Spec-review gate:** Not approved. On Aug 12, 2026 Sneferu's autopilot let the build continue from it with recorded qualification debt, because the contract did not earn a clean approval.
- **What the coders received:** this file, plus one short section Sneferu appended at the end before coding. Everything above it is identical, so the line numbers the code and tests cite (as `spec.md`) match this file. The appended section read, in full:

```text
## Orchestrator build-readiness repair obligations

The approved specification above remains authoritative. Before calling the product complete, implement and test each missing delivery requirement detected immediately before CODE:

- runtime_test_command: command to spawn the app for browser smoke testing (must include {port})
- runtime_test_mode_playwright: runtime_test_mode must be 'playwright' for browser_ui (got 'http')
- browser_smoke_plan: test_plan.md or runtime_test_plan describing the user flow to verify
- packaging_strategy: packaging.{json,toml} or pyproject/MANIFEST.in entries that include built JS/CSS assets
```

## Checksums (SHA-256)

| File | SHA-256 |
|---|---|
| `INTERFACE_SPECIFICATION.md` | `580f4261065bde4ab201492d2920d5e1c52199198b0f7fe03e3b111a954561bd` |
| `REFINED_REQUEST.md` | `996ead83e2b64f8da3d59950e3fb7ed6b6b280b03f800b4a99635020a1c6d7b1` |
| `REQUEST.md` | `60c56fb377179803ebee43c4f68ff490322ea5d0a04ad9481f0b36e7cc4e2927` |
| `SPECIFICATION.md` | `4b93819f4ebdadc513b5b078abfcdf1362dea6fd05ce91ad8ccd7caaf47bd7b6` |
