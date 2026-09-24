#!/usr/bin/env python3
"""Deterministic fixture generator for the COA Effect-Spectrum Profiler.

Generates every fixture in ``fixtures/`` with ReportLab in invariant mode
(byte-stable output), then computes expected scores with the REAL scorer and
writes the ``*_expected.json`` / ``labels.json`` / ``expected_results.json``
files from those computed values. Re-run after any intentional scorer or
weight change to regenerate the ground truth:

    PYTHONPATH=src python3 scripts/make_fixtures.py

The generator asserts every evaluation fixture lands in its intended DIS-10
bin, so a scoring change that moves a fixture fails loudly here first.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from coa_profiler.parser import extract_chemistry
from coa_profiler.scorer import placement_bin, score

FIXTURES = ROOT / "fixtures"


# --- COA text construction ----------------------------------------------------

_BRAND_HEADERS = {
    "confident_cannabis": [
        "Confident Cannabis",
        "confidentcannabis.com",
        "Analysis ID: CC-{sample}",
        "Certificate of Analysis",
    ],
    "sc_labs": [
        "SC Labs",
        "PhytoFacts",
        "sclabs.com",
        "Certificate of Analysis",
    ],
    "generic_ommu": [
        "Certificate of Analysis",
        "Florida OMMU Licensed Testing Laboratory",
    ],
}


def coa_pages(
    fmt: str, cannabinoids: list[str], terpenes: list[str], sample: str, multipage: bool = False
) -> list[list[str]]:
    """Build COA page text lines. Returns a list of pages (lists of lines)."""
    header = [line.format(sample=sample) for line in _BRAND_HEADERS[fmt]]
    header += [
        f"Sample ID: {sample}",
        "Product: Flower",
        "Serving Size: 1 g",
        "",
        "Cannabinoid Profile",
    ]
    cann = cannabinoids + ["", "Terpene Profile"]
    if multipage:
        return [header + cann, terpenes]
    return [header + cann + terpenes]


def write_pdf(path: Path, pages: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=letter, invariant=True, pdfVersion=(1, 4))
    c.setTitle("Certificate of Analysis")
    for lines in pages:
        y = letter[1] - 72
        for line in lines:
            c.setFont("Helvetica", 10)
            c.drawString(72, y, line)
            y -= 14
        c.showPage()
    c.save()


def pct(name: str, value: float) -> str:
    return f"{name}  {value:g} %"


def mgg(name: str, value: float) -> str:
    return f"{name}  {value:g} mg/g"


def mgml(name: str, value: float) -> str:
    return f"{name}  {value:g} mg/mL"


def ppm(name: str, value: float) -> str:
    return f"{name}  {value:g} ppm"


def score_of(pages: list[list[str]]) -> tuple[int, str, str]:
    """Compute the real placement for generated page text."""
    chem = extract_chemistry(["\n".join(p) for p in pages])
    result = score(chem)
    return result.score, placement_bin(result.score) if result.score >= 0 else "refusal", chem.lab_format


# --- Named chemistry profiles --------------------------------------------------
# (cannabinoid lines, terpene lines) tuned so each profile lands in its bin.


def profile_strong_sativa(v: float = 1.0):
    # Net signed contribution at v=1 is about -0.89 (robustly in the
    # strongly-sativa bin after the full-mode contraction).
    cann = [pct("Total THC", 20 * v), pct("Total CBD", 1 * v)]
    terps = [
        pct("Limonene", round(0.8 * v, 3)),
        pct("Terpinolene", round(0.16 * v, 3)),
        pct("alpha-Pinene", round(0.3 * v, 3)),
        pct("Myrcene", round(0.16 * v, 3)),
        pct("beta-Caryophyllene", round(0.5 * v, 3)),
    ]
    return cann, terps


def profile_sativa(v: float = 1.0):
    cann = [pct("Total THC", 20 * v), pct("Total CBD", 1 * v)]
    terps = [
        pct("Limonene", round(0.5 * v, 3)),
        pct("Terpinolene", round(0.16 * v, 3)),
        pct("alpha-Pinene", round(0.2 * v, 3)),
        pct("Myrcene", round(0.16 * v, 3)),
        pct("Linalool", round(0.05 * v, 3)),
        pct("beta-Caryophyllene", round(0.4 * v, 3)),
    ]
    return cann, terps


def profile_balanced(v: float = 1.0):
    cann = [pct("Total THC", 20 * v), pct("Total CBD", 1 * v)]
    terps = [
        pct("Myrcene", round(0.16 * v, 3)),
        pct("Limonene", round(0.3 * v, 3)),
        pct("Linalool", round(0.1 * v, 3)),
        pct("alpha-Pinene", round(0.15 * v, 3)),
        pct("Humulene", round(0.078 * v, 3)),
        pct("Terpinolene", round(0.16 * v, 3)),
        pct("beta-Caryophyllene", round(0.5 * v, 3)),
    ]
    return cann, terps


def profile_indica(v: float = 1.0):
    cann = [pct("Total THC", 20 * v), pct("Total CBD", 1 * v)]
    terps = [
        pct("Myrcene", round(0.2 * v, 3)),
        pct("Linalool", round(0.1 * v, 3)),
        pct("Humulene", round(0.078 * v, 3)),
        pct("Limonene", round(0.3 * v, 3)),
        pct("alpha-Pinene", round(0.1 * v, 3)),
        pct("beta-Caryophyllene", round(0.7 * v, 3)),
    ]
    return cann, terps


def profile_strong_indica(v: float = 1.0):
    cann = [pct("Total THC", 20 * v), pct("Total CBD", 1 * v)]
    terps = [
        pct("Myrcene", round(0.5 * v, 3)),
        pct("Linalool", round(0.15 * v, 3)),
        pct("Humulene", round(0.059 * v, 3)),
        pct("Limonene", round(0.25 * v, 3)),
        pct("alpha-Pinene", round(0.1 * v, 3)),
        pct("beta-Caryophyllene", round(0.9 * v, 3)),
    ]
    return cann, terps


def main() -> int:
    random.seed(20260812)
    written: list[str] = []

    # --- Core fixtures ---------------------------------------------------------
    sample_pages = coa_pages(
        "confident_cannabis",
        [pct("Total THC", 18.2), pct("Total CBD", 0.5), pct("THCA", 20.1)],
        [
            pct("Myrcene", 0.85),
            pct("Limonene", 0.42),
            pct("beta-Caryophyllene", 0.66),
            pct("Linalool", 0.21),
            pct("alpha-Pinene", 0.33),
            pct("Humulene", 0.12),
        ],
        "FL-2026-0001",
    )
    write_pdf(FIXTURES / "fl_coa_sample.pdf", sample_pages)
    s, b, fmt = score_of(sample_pages)
    assert fmt == "confident_cannabis", fmt
    (FIXTURES / "fl_coa_sample_expected.json").write_text(
        json.dumps(
            {
                "lab_format": fmt,
                "score": s,
                "placement_bin": b,
                "fields": {
                    "thc_total": {"value": 18.2, "unit": "%"},
                    "cbd_total": {"value": 0.5, "unit": "%"},
                    "myrcene": {"value": 0.85, "unit": "%"},
                    "limonene": {"value": 0.42, "unit": "%"},
                    "beta_caryophyllene": {"value": 0.66, "unit": "%"},
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    written += ["fl_coa_sample.pdf", "fl_coa_sample_expected.json"]

    # Degraded: cannabinoids verified, exactly one terpene (partial terpene data).
    write_pdf(
        FIXTURES / "cannabinoids_only.pdf",
        coa_pages(
            "generic_ommu",
            [pct("Total THC", 22.4), pct("Total CBD", 1.1)],
            [pct("Myrcene", 0.55)],
            "FL-2026-0002",
        ),
    )
    written.append("cannabinoids_only.pdf")

    # Refusal: cannabinoids present, zero terpenes.
    write_pdf(
        FIXTURES / "no_chemistry.pdf",
        coa_pages("generic_ommu", [pct("Total THC", 19.0), pct("Total CBD", 0.3)], [], "FL-2026-0003"),
    )
    written.append("no_chemistry.pdf")

    # Multi-page: cannabinoids page 1, terpenes page 2.
    write_pdf(
        FIXTURES / "multi_page_coa.pdf",
        coa_pages(
            "generic_ommu",
            [pct("Total THC", 21.6), pct("Total CBD", 0.4)],
            [
                pct("Myrcene", 0.95),
                pct("Limonene", 0.38),
                pct("Linalool", 0.25),
                pct("alpha-Pinene", 0.29),
                pct("beta-Caryophyllene", 0.71),
            ],
            "FL-2026-0004",
            multipage=True,
        ),
    )
    written.append("multi_page_coa.pdf")

    # Unit conversions.
    write_pdf(
        FIXTURES / "unit_mgg_coa.pdf",
        coa_pages(
            "generic_ommu",
            [mgg("Total THC", 182), mgg("Total CBD", 5)],
            [
                mgg("Myrcene", 8.5),
                mgg("Limonene", 4.2),
                mgg("Linalool", 2.1),
                mgg("alpha-Pinene", 3.3),
                mgg("Humulene", 1.2),
                mgg("beta-Caryophyllene", 6.6),
            ],
            "FL-2026-0005",
        ),
    )
    write_pdf(
        FIXTURES / "mg_ml_coa.pdf",
        coa_pages(
            "generic_ommu",
            [mgml("Total THC", 195), mgml("Total CBD", 4)],
            [
                mgml("Myrcene", 9.0),
                mgml("Limonene", 3.9),
                mgml("Linalool", 2.4),
                mgml("alpha-Pinene", 3.0),
                mgml("Humulene", 1.5),
                mgml("beta-Caryophyllene", 7.1),
            ],
            "FL-2026-0006",
        ),
    )
    write_pdf(
        FIXTURES / "ppm_coa.pdf",
        coa_pages(
            "generic_ommu",
            [pct("Total THC", 18.2), pct("Total CBD", 0.5)],
            [
                ppm("Myrcene", 8500),
                ppm("Limonene", 4200),
                ppm("Linalool", 2100),
                ppm("alpha-Pinene", 3300),
                ppm("Humulene", 1200),
                ppm("beta-Caryophyllene", 6600),
            ],
            "FL-2026-0007",
        ),
    )
    written += ["unit_mgg_coa.pdf", "mg_ml_coa.pdf", "ppm_coa.pdf"]

    # DIS-15 derivation: THCA + delta-9 THC separately, no Total THC line.
    write_pdf(
        FIXTURES / "thca_cbda_coa.pdf",
        coa_pages(
            "generic_ommu",
            [pct("THCA", 20.0), pct("delta-9 THC", 1.2), pct("CBDA", 0.8), pct("CBD", 0.1)],
            [
                pct("Myrcene", 0.85),
                pct("Limonene", 0.42),
                pct("Linalool", 0.21),
                pct("alpha-Pinene", 0.33),
                pct("Humulene", 0.12),
                pct("beta-Caryophyllene", 0.66),
            ],
            "FL-2026-0008",
        ),
    )
    written.append("thca_cbda_coa.pdf")

    # Plausibility flag: THC 45% > 40% threshold (FR-028).
    write_pdf(
        FIXTURES / "plausibility_high_coa.pdf",
        coa_pages(
            "generic_ommu",
            [pct("Total THC", 45.0), pct("Total CBD", 0.4)],
            [
                pct("Myrcene", 0.9),
                pct("Limonene", 0.4),
                pct("Linalool", 0.2),
                pct("alpha-Pinene", 0.3),
                pct("Humulene", 0.15),
                pct("beta-Caryophyllene", 0.6),
            ],
            "FL-2026-0009",
        ),
    )
    written.append("plausibility_high_coa.pdf")

    # Format family fixtures (AC-032: detected by content, not filename).
    for fmt in ("confident_cannabis", "sc_labs", "generic_ommu"):
        cann, terps = profile_balanced()
        pages = coa_pages(fmt, cann, terps, f"FMT-{fmt[:4].upper()}-01")
        write_pdf(FIXTURES / "formats" / f"{fmt}_coa.pdf", pages)
        got = score_of(pages)[2]
        assert got == fmt, (fmt, got)
        written.append(f"formats/{fmt}_coa.pdf")

    # Batch fixtures: four valid COAs with distinct placements + one corrupt.
    batch_profiles = [profile_strong_sativa(), profile_sativa(), profile_indica(), profile_strong_indica()]
    batch_scores: list[int] = []
    for i, (cann, terps) in enumerate(batch_profiles, start=1):
        pages = coa_pages("generic_ommu", cann, terps, f"BAT-2026-{i:04d}")
        write_pdf(FIXTURES / "batch" / f"coa_{i:02d}.pdf", pages)
        batch_scores.append(score_of(pages)[0])
        written.append(f"batch/coa_{i:02d}.pdf")
    assert len(set(batch_scores)) >= 2, batch_scores  # AC-016 input sensitivity
    (FIXTURES / "batch" / "corrupt.pdf").write_bytes(b"this is not a pdf, just garbage bytes")
    written.append("batch/corrupt.pdf")

    # Evaluation set: 20 COAs spanning all five DIS-10 bins.
    eval_plan = (
        [("strongly-sativa", profile_strong_sativa)] * 4
        + [("sativa", profile_sativa)] * 5
        + [("balanced", profile_balanced)] * 3
        + [("indica", profile_indica)] * 5
        + [("strongly-indica", profile_strong_indica)] * 3
    )
    invert = {
        "strongly-sativa": "strongly-indica",
        "sativa": "indica",
        "balanced": "balanced",
        "indica": "sativa",
        "strongly-indica": "strongly-sativa",
    }
    labels: list[dict] = []
    labels_fail: list[dict] = []
    expected: dict = {}
    formats_cycle = ["confident_cannabis", "sc_labs", "generic_ommu"]
    dispensary_labels = {
        "strongly-sativa": "sativa",
        "sativa": "sativa",
        "balanced": "hybrid",
        "indica": "indica",
        "strongly-indica": "indica",
    }
    for idx, (bin_name, profile_fn) in enumerate(eval_plan, start=1):
        v = 0.9 + (idx % 4) * 0.05  # mild variation within a profile
        fmt = formats_cycle[idx % len(formats_cycle)]
        cann, terps = profile_fn(v)
        fid = f"eval_{idx:02d}"
        pages = coa_pages(fmt, cann, terps, f"EVL-{idx:04d}")
        write_pdf(FIXTURES / "eval" / f"{fid}.pdf", pages)
        score_val, computed_bin, _ = score_of(pages)
        assert computed_bin == bin_name, (fid, bin_name, computed_bin, score_val)
        written.append(f"eval/{fid}.pdf")

        # Synthetic agreement labels test the evaluation math only. They are
        # explicitly ineligible for the independent real-COA release gate.
        second = computed_bin
        if idx == 7:  # one deliberately inconsistent pair for AC-039 (gap >= 2 bins)
            # eval_07 is in the 'sativa' profile group; 'indica' is 2 bins away.
            second = "indica"
        # Dispensary labels: mostly right, deliberately wrong on some so the
        # outperform comparison has signal.
        if idx in {3, 8, 14}:
            dispen = {
                "strongly-sativa": "indica",
                "sativa": "indica",
                "balanced": "sativa",
                "indica": "sativa",
                "strongly-indica": "sativa",
            }[computed_bin]
        else:
            dispen = dispensary_labels[computed_bin]
        labels.append(
            {
                "fixture_id": fid,
                "drs_rating": computed_bin,
                "second_rater_rating": second,
                "dispensary_label": dispen,
                "notes": "fixture-generated",
            }
        )
        labels_fail.append(
            {
                "fixture_id": fid,
                "drs_rating": invert[computed_bin],
                "dispensary_label": dispen,
                "notes": "inverted fixture rating",
            }
        )

        fields = {}
        for line in cann + terps:
            parts = line.split()
            value = float(parts[-2])
            unit = parts[-1]
            name = " ".join(parts[:-2])
            key = (
                name.lower()
                .replace("total thc", "thc_total")
                .replace("total cbd", "cbd_total")
                .replace("delta-9 thc", "delta9_thc")
                .replace("thca", "thca")
                .replace("cbda", "cbda")
                .replace("cbd", "cbd")
                .replace("myrcene", "myrcene")
                .replace("limonene", "limonene")
                .replace("linalool", "linalool")
                .replace("humulene", "humulene")
                .replace("nerolidol", "nerolidol")
                .replace("ocimene", "ocimene")
                .replace("terpinolene", "terpinolene")
                .replace("alpha-pinene", "alpha_pinene")
                .replace("beta-pinene", "beta_pinene")
                .replace("beta-caryophyllene", "beta_caryophyllene")
            )
            factor = {"%": 1.0, "mg/g": 0.1, "mg/mL": 0.1, "ppm": 0.0001}[unit]
            fields[key] = {"value": round(value * factor, 6), "unit": unit}
        expected[fid] = {"lab_format": fmt, "fields": fields}

    synthetic_provenance = {
        "kind": "synthetic-self-consistency",
        "generated_by": "scripts/make_fixtures.py",
        "labels_created_without_tool_output": False,
        "documents_are_deidentified": False,
        "rater": "",
        "purpose": "test evaluation calculations; never release qualification",
    }
    (FIXTURES / "eval" / "labels.json").write_text(
        json.dumps({"provenance": synthetic_provenance, "ratings": labels}, indent=2),
        encoding="utf-8",
    )
    (FIXTURES / "eval" / "labels_fail.json").write_text(
        json.dumps({"provenance": synthetic_provenance, "ratings": labels_fail}, indent=2),
        encoding="utf-8",
    )
    (FIXTURES / "eval" / "expected_results.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True), encoding="utf-8"
    )
    written += ["eval/labels.json", "eval/labels_fail.json", "eval/expected_results.json"]

    # not_a_coa.txt + unreadable_coa.jpg + heic_sample.heic --------------------
    (FIXTURES / "not_a_coa.txt").write_text(
        "Dear patient,\n\nThank you for your visit last week. This letter confirms your "
        "appointment. It is not a certificate of analysis and contains no laboratory data.\n",
        encoding="utf-8",
    )
    written.append("not_a_coa.txt")

    from PIL import Image, ImageFilter

    noise = Image.effect_noise((640, 480), 64).convert("RGB")
    blurred = noise.filter(ImageFilter.GaussianBlur(6))
    blurred.save(FIXTURES / "unreadable_coa.jpg", format="JPEG", quality=70)
    written.append("unreadable_coa.jpg")

    # HEIC magic bytes (decoder presence is an environment property, AC-026).
    (FIXTURES / "heic_sample.heic").write_bytes(
        b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 128
    )
    written.append("heic_sample.heic")

    print(f"wrote {len(written)} fixtures under {FIXTURES}")
    for name in written:
        print(" -", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
