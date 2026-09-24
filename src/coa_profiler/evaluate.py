"""Operator evaluation CLI (FR-018, surface S9).

Runs the real parser + scorer over a held-out fixture set and emits a freshly
computed JSON report: per-format field accuracy, document-level accuracy,
placement range and standard deviation, a determinism check, and — when a
labels file is supplied — binned directional concordance (DIS-10 bins),
Spearman rank correlation on the numeric bin mapping, the
outperform-the-labels comparison, and the inter-rater consistency check.

``--gate`` exits non-zero below 80% concordance ("Concordance below
threshold: release blocked."). The DIS-10 contingency protocol is printed as
a recommendation; the CLI never halts a pipeline on its own.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

from coa_profiler.parser import parse_coa
from coa_profiler.scorer import score as score_chemistry
from coa_profiler.scorer.placement import placement_bin

GATE_THRESHOLD = 0.80
MIN_GATE_DOCUMENTS = 20

_QUALIFYING_PROVENANCE = "independent-real-coa"

#: DIS-10 numeric mapping for Spearman.
BIN_TO_NUMERIC = {
    "strongly-sativa": -2,
    "sativa": -1,
    "balanced": 0,
    "indica": 1,
    "strongly-indica": 2,
}

#: Dispensary label -> bin mapping for the outperform comparison.
_LABEL_TO_BIN = {"sativa": "sativa", "indica": "indica", "hybrid": "balanced"}

CONTINGENCY_MESSAGE = (
    "FALLBACK: 3-bin system recommended (sativa {0-40}, balanced {45-55}, indica {60-100}) with 70% threshold"
)


def _qualification_errors(
    labels: dict,
    compared_fixture_ids: set[str],
    compared_document_hashes: set[str],
    duplicate_fixture_ids: list[str],
    duplicate_content_groups: list[dict[str, object]],
) -> list[str]:
    """Explain why a labels manifest cannot serve as release evidence.

    Synthetic fixtures remain useful for repeatable parser/scorer tests, but
    their labels cannot independently validate the model that generated them.
    A release corpus must carry an explicit operator attestation and enough
    comparable documents to satisfy the product contract.
    """
    provenance = labels.get("provenance")
    if not isinstance(provenance, dict):
        return ["labels manifest has no provenance attestation"]

    errors: list[str] = []
    if provenance.get("kind") != _QUALIFYING_PROVENANCE:
        errors.append("documents are not declared as independent real COAs")
    if provenance.get("labels_created_without_tool_output") is not True:
        errors.append("ratings are not declared independent of tool output")
    if provenance.get("documents_are_deidentified") is not True:
        errors.append("documents are not declared deidentified")
    if not str(provenance.get("rater", "")).strip():
        errors.append("independent rater identity or role is missing")
    if duplicate_fixture_ids:
        errors.append(f"duplicate fixture_id ratings: {', '.join(duplicate_fixture_ids)}")
    if duplicate_content_groups:
        groups = "; ".join(
            ", ".join(str(fixture_id) for fixture_id in group["fixture_ids"])
            for group in duplicate_content_groups
        )
        errors.append(f"duplicate document content across fixture IDs: {groups}")
    distinct_compared_fixture_ids = len(compared_fixture_ids)
    if distinct_compared_fixture_ids < MIN_GATE_DOCUMENTS:
        errors.append(
            f"only {distinct_compared_fixture_ids} distinct comparable fixture IDs; "
            f"at least {MIN_GATE_DOCUMENTS} are required"
        )
    distinct_compared_hashes = len(compared_document_hashes)
    if distinct_compared_hashes < MIN_GATE_DOCUMENTS:
        errors.append(
            f"only {distinct_compared_hashes} distinct comparable document hashes; "
            f"at least {MIN_GATE_DOCUMENTS} are required"
        )
    return errors


def _rankdata(values: list[float]) -> list[float]:
    """Average ranks (1-based), ties share the mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + j + 2) / 2.0  # ranks i+1..j+1, averaged
        for k in range(i, j + 1):
            ranks[order[k]] = mean_rank
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    """Spearman rank correlation; None when undefined (constant input)."""
    if len(x) < 2 or len(x) != len(y):
        return None
    rx, ry = _rankdata(x), _rankdata(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    dx = [r - mx for r in rx]
    dy = [r - my for r in ry]
    denom = math.sqrt(sum(d * d for d in dx) * sum(d * d for d in dy))
    if denom == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def _norm_rating(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower().replace("_", "-").replace(" ", "-")
    aliases = {
        "strongly-sativa": "strongly-sativa",
        "strong-sativa": "strongly-sativa",
        "sativa-dominant": "sativa",
        "indica-dominant": "indica",
        "strongly-indica": "strongly-indica",
        "strong-indica": "strongly-indica",
        "sativa": "sativa",
        "indica": "indica",
        "balanced": "balanced",
        "hybrid": "balanced",
    }
    return aliases.get(v)


def run_evaluation(fixtures_dir: Path, labels_path: Path | None = None) -> dict:
    fixtures = sorted(
        p
        for p in fixtures_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png", ".heic"}
    )

    expected: dict = {}
    expected_path = fixtures_dir / "expected_results.json"
    if expected_path.is_file():
        expected = json.loads(expected_path.read_text(encoding="utf-8"))

    per_fixture: dict[str, dict] = {}
    placements: list[int] = []
    for path in fixtures:
        with path.open("rb") as fixture_file:
            document_sha256 = hashlib.file_digest(fixture_file, "sha256").hexdigest()
        entry: dict = {"fixture": path.name, "document_sha256": document_sha256}
        try:
            chemistry = parse_coa(path)
            result = score_chemistry(chemistry)
            again = score_chemistry(parse_coa(path))  # determinism check: same bytes twice
            entry.update(
                {
                    "lab_format": chemistry.lab_format,
                    "completeness": result.completeness,
                    "placement": result.score if result.score >= 0 else None,
                    "confidence_combined": round(result.confidence_combined, 4),
                    "deterministic": result.score == again.score and result.rationale == again.rationale,
                    "fields": {
                        name: {
                            "value": f.value,
                            "unit": f.original_unit,
                            "status": f.status,
                            "derived": f.derived,
                            "plausibility_flag": f.plausibility_flag,
                            "source_span": f.source_span,  # FR-025 audit surface
                        }
                        for name, f in list(chemistry.cannabinoids.items()) + list(chemistry.terpenes.items())
                    },
                }
            )
            if result.score >= 0:
                placements.append(result.score)
        except Exception as exc:  # noqa: BLE001 - failures are data in an evaluation report
            entry.update(
                {"error": type(exc).__name__, "error_code": getattr(exc, "error_code", "INTERNAL_ERROR")}
            )
        per_fixture[path.stem] = entry

    # --- field accuracy vs expected_results.json (when present) ------------
    per_format: dict[str, dict[str, int]] = {}
    docs_ok = 0
    docs_total = 0
    for stem, exp in expected.items():
        got = per_fixture.get(stem)
        if not got or "fields" not in got:
            continue
        fmt = exp.get("lab_format", got.get("lab_format", "unknown"))
        bucket = per_format.setdefault(fmt, {"correct": 0, "total": 0})
        doc_ok = True
        for name, want in exp.get("fields", {}).items():
            bucket["total"] += 1
            field = got["fields"].get(name)
            match = (
                field is not None
                and field["status"] == "verified"
                and field["value"] is not None
                and math.isclose(field["value"], want["value"], rel_tol=0.02, abs_tol=0.02)
            )
            if match:
                bucket["correct"] += 1
            else:
                doc_ok = False
        docs_total += 1
        docs_ok += 1 if doc_ok else 0

    field_accuracy = {
        "available": bool(expected),
        "per_format": {
            fmt: {**b, "accuracy": (b["correct"] / b["total"]) if b["total"] else None}
            for fmt, b in sorted(per_format.items())
        },
        "document_level": {
            "correct": docs_ok,
            "total": docs_total,
            "accuracy": (docs_ok / docs_total) if docs_total else None,
        },
    }

    report: dict = {
        "fixtures_evaluated": len(fixtures),
        "field_accuracy": field_accuracy,
        "placement_range": [min(placements), max(placements)] if placements else None,
        "placement_stddev": (
            math.sqrt(sum((p - sum(placements) / len(placements)) ** 2 for p in placements) / len(placements))
            if placements
            else None
        ),
        "determinism": all(e.get("deterministic", True) for e in per_fixture.values()),
        "per_fixture": per_fixture,
    }

    # --- labels: concordance, Spearman, outperform, inter-rater -------------
    if labels_path is not None:
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        ratings = labels.get("ratings", [])
        fixture_id_counts = Counter(
            str(row.get("fixture_id", "")).strip()
            for row in ratings
            if isinstance(row, dict) and str(row.get("fixture_id", "")).strip()
        )
        duplicate_fixture_ids = sorted(
            fixture_id for fixture_id, count in fixture_id_counts.items() if count > 1
        )
        seen_fixture_ids: set[str] = set()
        compared_fixture_ids: set[str] = set()
        compared_fixture_ids_by_hash: dict[str, list[str]] = {}
        compared = 0
        agreed = 0
        label_compared = 0
        label_agreed = 0
        tool_nums: list[float] = []
        rater_nums: list[float] = []
        inter_rater_pairs = 0
        inter_rater_agreed = 0
        inter_rater_flagged: list[dict] = []
        per_rating: list[dict] = []
        for row in ratings:
            stem = str(row.get("fixture_id", "")).strip()
            # A document gets one vote in every evaluation statistic. Duplicate
            # rows still make the corpus ineligible below, but cannot weight
            # concordance, Spearman, label comparison, or inter-rater counts.
            if stem in seen_fixture_ids:
                continue
            seen_fixture_ids.add(stem)
            got = per_fixture.get(stem)
            drs = _norm_rating(row.get("drs_rating"))
            if not got or got.get("placement") is None or drs is None:
                continue
            tool_bin = placement_bin(got["placement"])
            compared += 1
            compared_fixture_ids.add(stem)
            document_sha256 = str(got["document_sha256"])
            compared_fixture_ids_by_hash.setdefault(document_sha256, []).append(stem)
            agree = tool_bin == drs
            agreed += 1 if agree else 0
            tool_nums.append(BIN_TO_NUMERIC[tool_bin])
            rater_nums.append(BIN_TO_NUMERIC[drs])
            label_bin = _LABEL_TO_BIN.get((row.get("dispensary_label") or "").strip().lower())
            if label_bin:
                label_compared += 1
                label_agreed += 1 if label_bin == drs else 0
            second = _norm_rating(row.get("second_rater_rating"))
            if second is not None:
                inter_rater_pairs += 1
                gap = abs(BIN_TO_NUMERIC[second] - BIN_TO_NUMERIC[drs])
                if gap >= 2:
                    inter_rater_flagged.append(
                        {
                            "fixture_id": stem,
                            "drs_rating": drs,
                            "second_rater_rating": second,
                            "bin_gap": gap,
                        }
                    )
                else:
                    inter_rater_agreed += 1
            per_rating.append(
                {
                    "fixture_id": stem,
                    "tool_bin": tool_bin,
                    "drs_rating": drs,
                    "agree": agree,
                    "dispensary_label_bin": label_bin,
                }
            )

        concordance = (agreed / compared) if compared else None
        tool_rate = concordance
        label_rate = (label_agreed / label_compared) if label_compared else None
        duplicate_content_groups = [
            {"document_sha256": document_sha256, "fixture_ids": sorted(fixture_ids)}
            for document_sha256, fixture_ids in sorted(compared_fixture_ids_by_hash.items())
            if len(fixture_ids) > 1
        ]
        compared_document_hashes = set(compared_fixture_ids_by_hash)
        qualification_errors = _qualification_errors(
            labels,
            compared_fixture_ids,
            compared_document_hashes,
            duplicate_fixture_ids,
            duplicate_content_groups,
        )
        report["concordance"] = {
            "threshold": GATE_THRESHOLD,
            "compared": compared,
            "agreed": agreed,
            "rate": concordance,
            "passes_gate": (
                concordance is not None and concordance >= GATE_THRESHOLD and not qualification_errors
            ),
            "qualification_eligible": not qualification_errors,
            "qualification_errors": qualification_errors,
            "duplicate_fixture_ids": duplicate_fixture_ids,
            "distinct_compared_fixture_ids": len(compared_fixture_ids),
            "distinct_compared_document_hashes": len(compared_document_hashes),
            "duplicate_content_groups": duplicate_content_groups,
            "per_rating": per_rating,
        }
        report["spearman"] = spearman(tool_nums, rater_nums)
        report["outperform_labels"] = {
            "tool_agreement": tool_rate,
            "dispensary_label_agreement": label_rate,
            "difference": (tool_rate - label_rate)
            if (tool_rate is not None and label_rate is not None)
            else None,
            "outperforms": (tool_rate is not None and label_rate is not None and tool_rate > label_rate),
        }
        report["inter_rater"] = {
            "pairs": inter_rater_pairs,
            "agreed": inter_rater_agreed,
            "flagged": inter_rater_flagged,
            "inconsistency_detected": len(inter_rater_flagged) > 3,
        }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="coa_profiler.evaluate", description="Held-out evaluation CLI (FR-018)."
    )
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--labels", default=None)
    parser.add_argument("--gate", action="store_true", help="exit non-zero when concordance is below 80%")
    args = parser.parse_args(argv)

    fixtures_dir = Path(args.fixtures)
    if not fixtures_dir.is_dir():
        print(f"fixtures directory not found: {fixtures_dir}", file=sys.stderr)
        return 2

    report = run_evaluation(fixtures_dir, Path(args.labels) if args.labels else None)
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"evaluation report written to {args.report}")
    print(f"fixtures evaluated: {report['fixtures_evaluated']}; determinism: {report['determinism']}")

    inter = report.get("inter_rater")
    if inter and inter["inconsistency_detected"]:
        # DIS-10 / OBL-23: a loud warning, never a pipeline halt.
        print("INTER-RATER INCONSISTENCY DETECTED")
        for pair in inter["flagged"]:
            print(
                f"  {pair['fixture_id']}: {pair['drs_rating']} vs "
                f"{pair['second_rater_rating']} (bin gap {pair['bin_gap']})"
            )

    concordance = report.get("concordance")
    if concordance is not None:
        rate = concordance["rate"]
        print(
            f"binned concordance: {rate * 100:.1f}% ({concordance['agreed']}/{concordance['compared']})"
            if rate is not None
            else "binned concordance: n/a (no comparable ratings)"
        )
        if report.get("spearman") is not None:
            print(f"spearman rank correlation: {report['spearman']:.3f}")
        out = report.get("outperform_labels", {})
        if out.get("dispensary_label_agreement") is not None:
            print(
                f"outperform-the-labels: tool {out['tool_agreement'] * 100:.1f}% vs "
                f"labels {out['dispensary_label_agreement'] * 100:.1f}% "
                f"(difference {out['difference'] * 100:+.1f} pp)"
            )
        if args.gate:
            qualification_errors = concordance.get("qualification_errors", [])
            if qualification_errors:
                print("Evaluation evidence is not release-qualifying:")
                for error in qualification_errors:
                    print(f"  - {error}")
                return 1
            if rate is None or rate < GATE_THRESHOLD:
                print(
                    f"Concordance below threshold: release blocked. "
                    f"(concordance {rate * 100:.1f}% < {GATE_THRESHOLD * 100:.0f}%)"
                    if rate is not None
                    else "Concordance below threshold: release blocked. (no comparable ratings)"
                )
                print(CONTINGENCY_MESSAGE)
                return 1
            print(f"Concordance {rate * 100:.1f}% meets the {GATE_THRESHOLD * 100:.0f}% gate.")
    elif args.gate:
        print("Concordance below threshold: release blocked. (no labels supplied)")
        print(CONTINGENCY_MESSAGE)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
