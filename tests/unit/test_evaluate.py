"""FR-018 evaluation CLI: fresh computation, gate, Spearman, inter-rater."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from coa_profiler.evaluate import main as evaluate_main
from coa_profiler.evaluate import run_evaluation, spearman

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
EVAL = FIXTURES / "eval"


def _qualifying_labels(tmp_path: Path, source: str = "labels.json") -> Path:
    labels = json.loads((EVAL / source).read_text())
    labels["provenance"] = {
        "kind": "independent-real-coa",
        "labels_created_without_tool_output": True,
        "documents_are_deidentified": True,
        "rater": "test independent rater",
    }
    path = tmp_path / source
    path.write_text(json.dumps(labels))
    return path


def test_spearman_math():
    assert spearman([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)
    assert spearman([1, 1, 1], [1, 2, 3]) is None  # constant input: undefined


def test_report_fresh_and_complete(tmp_path):
    report_path = tmp_path / "report.json"
    code = evaluate_main(
        ["--fixtures", str(EVAL), "--labels", str(EVAL / "labels.json"), "--report", str(report_path)]
    )
    assert code == 0
    report = json.loads(report_path.read_text())
    assert report["determinism"] is True
    assert report["concordance"]["rate"] == pytest.approx(1.0)
    assert report["concordance"]["passes_gate"] is False
    assert report["concordance"]["qualification_eligible"] is False
    assert report["spearman"] == pytest.approx(1.0)
    assert "field_accuracy" in report
    assert report["field_accuracy"]["available"] is True
    assert report["placement_range"][0] < report["placement_range"][1]
    out = report["outperform_labels"]
    assert out["tool_agreement"] == pytest.approx(1.0)
    assert out["dispensary_label_agreement"] < 1.0  # some labels are deliberately wrong
    assert out["outperforms"] is True
    # Source spans are present for audit (FR-025).
    some = report["per_fixture"]["eval_01"]["fields"]
    assert any(f["source_span"] for f in some.values())


def test_fresh_computation_not_canned(tmp_path):
    # AC-015: modifying one rating must change the concordance.
    labels = json.loads((EVAL / "labels.json").read_text())
    r1 = run_evaluation(EVAL, None)
    labels["ratings"][0]["drs_rating"] = (
        "strongly-indica" if labels["ratings"][0]["drs_rating"] == "strongly-sativa" else "strongly-sativa"
    )
    changed = tmp_path / "labels_changed.json"
    changed.write_text(json.dumps(labels))
    r2_before = run_evaluation(EVAL, EVAL / "labels.json")
    r2_after = run_evaluation(EVAL, changed)
    assert r2_before["concordance"]["rate"] != r2_after["concordance"]["rate"]
    assert "concordance" not in r1  # labels absent -> block absent


def test_gate_blocks_below_80(tmp_path, capsys):
    labels = _qualifying_labels(tmp_path, "labels_fail.json")
    code = evaluate_main(
        ["--fixtures", str(EVAL), "--labels", str(labels), "--report", str(tmp_path / "r.json"), "--gate"]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "Concordance below threshold: release blocked." in out
    assert "FALLBACK: 3-bin system recommended" in out


def test_gate_passes_at_80(tmp_path, capsys):
    labels = _qualifying_labels(tmp_path)
    code = evaluate_main(
        ["--fixtures", str(EVAL), "--labels", str(labels), "--report", str(tmp_path / "r.json"), "--gate"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "meets the 80% gate" in out


def test_gate_rejects_synthetic_self_labels(tmp_path, capsys):
    code = evaluate_main(
        [
            "--fixtures",
            str(EVAL),
            "--labels",
            str(EVAL / "labels.json"),
            "--report",
            str(tmp_path / "r.json"),
            "--gate",
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "not release-qualifying" in out
    assert "independent real COAs" in out
    assert "independent of tool output" in out


def test_duplicate_fixture_ids_cannot_fake_minimum_corpus(tmp_path, capsys):
    labels = json.loads(_qualifying_labels(tmp_path).read_text())
    labels["ratings"] = [dict(labels["ratings"][0]) for _ in range(20)]
    labels_path = tmp_path / "duplicate_labels.json"
    report_path = tmp_path / "duplicate_report.json"
    labels_path.write_text(json.dumps(labels))

    code = evaluate_main(
        [
            "--fixtures",
            str(EVAL),
            "--labels",
            str(labels_path),
            "--report",
            str(report_path),
            "--gate",
        ]
    )

    report = json.loads(report_path.read_text())
    concordance = report["concordance"]
    assert code == 1
    assert concordance["compared"] == 1
    assert len(concordance["per_rating"]) == 1
    assert concordance["duplicate_fixture_ids"] == ["eval_01"]
    assert concordance["qualification_eligible"] is False
    assert any(
        "only 1 distinct comparable document hashes" in error for error in concordance["qualification_errors"]
    )
    out = capsys.readouterr().out
    assert "duplicate fixture_id ratings: eval_01" in out


def test_duplicate_fixture_id_blocks_otherwise_large_enough_corpus(tmp_path):
    labels = json.loads(_qualifying_labels(tmp_path).read_text())
    labels["ratings"].append(dict(labels["ratings"][0]))
    labels_path = tmp_path / "one_duplicate.json"
    labels_path.write_text(json.dumps(labels))

    report = run_evaluation(EVAL, labels_path)

    concordance = report["concordance"]
    assert concordance["compared"] == 20
    assert concordance["duplicate_fixture_ids"] == ["eval_01"]
    assert concordance["passes_gate"] is False
    assert concordance["qualification_eligible"] is False


def test_distinct_filenames_with_identical_bytes_cannot_fake_document_count(tmp_path, monkeypatch):
    identical_pdf_bytes = b"%PDF-1.4\nidentical held-out document\n%%EOF\n"
    ratings = []
    for index in range(1, 21):
        fixture_id = f"copy_{index:02}"
        (tmp_path / f"{fixture_id}.pdf").write_bytes(identical_pdf_bytes)
        ratings.append({"fixture_id": fixture_id, "drs_rating": "balanced"})
    labels_path = tmp_path / "copied_documents.json"
    labels_path.write_text(
        json.dumps(
            {
                "provenance": {
                    "kind": "independent-real-coa",
                    "labels_created_without_tool_output": True,
                    "documents_are_deidentified": True,
                    "rater": "test independent rater",
                },
                "ratings": ratings,
            }
        )
    )

    chemistry = SimpleNamespace(lab_format="generic_ommu", cannabinoids={}, terpenes={})
    placement = SimpleNamespace(
        score=50,
        completeness="full",
        confidence_combined=0.75,
        rationale=["deterministic test placement"],
    )
    monkeypatch.setattr("coa_profiler.evaluate.parse_coa", lambda _path: chemistry)
    monkeypatch.setattr("coa_profiler.evaluate.score_chemistry", lambda _chemistry: placement)

    report = run_evaluation(tmp_path, labels_path)

    concordance = report["concordance"]
    assert concordance["compared"] == 20
    assert concordance["distinct_compared_fixture_ids"] == 20
    assert concordance["distinct_compared_document_hashes"] == 1
    assert concordance["qualification_eligible"] is False
    assert len(concordance["duplicate_content_groups"]) == 1
    assert concordance["duplicate_content_groups"][0]["fixture_ids"] == [
        f"copy_{index:02}" for index in range(1, 21)
    ]
    assert any(
        "only 1 distinct comparable document hashes" in error for error in concordance["qualification_errors"]
    )


def test_inter_rater_flagging(tmp_path, capsys):
    report_path = tmp_path / "irr.json"
    evaluate_main(
        ["--fixtures", str(EVAL), "--labels", str(EVAL / "labels.json"), "--report", str(report_path)]
    )
    report = json.loads(report_path.read_text())
    irr = report["inter_rater"]
    assert irr["pairs"] == 20
    assert len(irr["flagged"]) == 1  # eval_07 differs by >= 2 bins by construction
    assert irr["flagged"][0]["fixture_id"] == "eval_07"
    assert irr["inconsistency_detected"] is False  # 1 of 20, threshold is >3
    assert "evaluation paused" not in capsys.readouterr().out  # OBL-23: never halts
