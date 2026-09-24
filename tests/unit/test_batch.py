"""FR-017 batch CLI: exit codes, ordering, failures, determinism, ZIP."""

import hashlib
import io
import zipfile
from pathlib import Path

import pypdf

from coa_profiler.batch import BatchEntry, _render_reference_sheet, run_batch
from coa_profiler.batch import main as batch_main

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
BATCH = FIXTURES / "batch"


def test_batch_happy_path(tmp_path, capsys):
    out = tmp_path / "out"
    code = batch_main(["--input-dir", str(BATCH), "--output-dir", str(out), "--customer", "Test Practice"])
    assert code == 0  # 4/5 = 80% >= 80%
    stdout = capsys.readouterr().out
    assert "PASS: coa_01.pdf score=" in stdout
    assert "FAIL: corrupt.pdf INVALID_FILE_TYPE" in stdout

    # One branded PDF per successful COA + reference sheet + ZIP.
    for i in range(1, 5):
        assert (out / f"coa_0{i}.pdf").is_file()
    sheet = (out / "reference_sheet.pdf").read_bytes()
    text = pypdf.PdfReader(io.BytesIO(sheet)).pages[0].extract_text()
    assert "FAILED: corrupt.pdf" in text
    # Entries sorted alphabetically by filename (deterministic).
    positions = [
        text.index(name) for name in ("coa_01.pdf", "coa_02.pdf", "coa_03.pdf", "coa_04.pdf", "corrupt.pdf")
    ]
    assert positions == sorted(positions)

    with zipfile.ZipFile(out / "batch_profiles.zip") as zf:
        names = zf.namelist()
    assert "failures.log" in names
    assert "coa_01.pdf" in names
    assert "corrupt.pdf" not in names

    # Distinct placements across fixtures (input sensitivity, AC-016).
    scores = [
        int(line.split("score=")[1])
        for line in stdout.splitlines()
        if line.startswith("PASS:") and "score=" in line
    ]
    assert len(set(scores)) >= 2


def test_batch_determinism(tmp_path):
    d1, d2 = tmp_path / "d1", tmp_path / "d2"
    run_batch(BATCH, d1, "T", skip_invalid=True, log=lambda *a: None)
    run_batch(BATCH, d2, "T", skip_invalid=True, log=lambda *a: None)
    for name in ["coa_01.pdf", "coa_02.pdf", "coa_03.pdf", "coa_04.pdf", "reference_sheet.pdf"]:
        assert (d1 / name).read_bytes() == (d2 / name).read_bytes(), name


def test_skip_invalid_excludes_from_denominator(tmp_path):
    out = tmp_path / "out"
    code, entries = run_batch(BATCH, out, "T", skip_invalid=True, log=lambda *a: None)
    assert code == 0
    attempted = [e for e in entries if not e.skipped]
    assert len(attempted) == 4 and all(e.ok for e in attempted)


def test_all_fail_exit_2(tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "garbage.pdf").write_bytes(b"not a pdf at all")
    code, _ = run_batch(bad, tmp_path / "out", "T", log=lambda *a: None)
    assert code == 2


def test_below_threshold_exit_1(tmp_path):
    # 1 valid + 2 corrupt = 33% < 80%.
    src = tmp_path / "src"
    src.mkdir()
    (src / "a_valid.pdf").write_bytes((BATCH / "coa_01.pdf").read_bytes())
    (src / "b_bad.pdf").write_bytes(b"junk")
    (src / "c_bad.pdf").write_bytes(b"junk2")
    code, _ = run_batch(src, tmp_path / "out", "T", log=lambda *a: None)
    assert code == 1


def test_output_equal_to_input_is_fatal_without_modifying_originals(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    original = source / "original.pdf"
    original.write_bytes((BATCH / "coa_01.pdf").read_bytes())
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    messages: list[str] = []

    code, entries = run_batch(source, source, "T", log=messages.append)

    assert code == 2
    assert entries == []
    assert messages == [
        "FATAL: unsafe batch paths: output directory must be different from the input directory"
    ]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    assert list(source.iterdir()) == [original]


def test_output_nested_under_input_is_fatal_without_creating_or_modifying(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    original = source / "original.pdf"
    original.write_bytes((BATCH / "coa_01.pdf").read_bytes())
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    nested_output = source / "generated" / "profiles"
    messages: list[str] = []

    code, entries = run_batch(source, nested_output, "T", log=messages.append)

    assert code == 2
    assert entries == []
    assert messages == ["FATAL: unsafe batch paths: output directory must not be inside the input directory"]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    assert not nested_output.exists()
    assert list(source.iterdir()) == [original]


def test_duplicate_stems_get_distinct_outputs(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    fixture = (BATCH / "coa_01.pdf").read_bytes()
    (src / "sample.pdf").write_bytes(fixture)
    (src / "sample.jpg").write_bytes(fixture)

    out = tmp_path / "out"
    code, entries = run_batch(src, out, "T", log=lambda *a: None)

    assert code == 0
    assert all(entry.ok for entry in entries)
    assert (out / "sample-pdf.pdf").is_file()
    assert (out / "sample-jpg.pdf").is_file()
    with zipfile.ZipFile(out / "batch_profiles.zip") as zf:
        assert {"sample-pdf.pdf", "sample-jpg.pdf"}.issubset(zf.namelist())


def test_reference_sheet_paginates_without_dropping_rows():
    entries = [BatchEntry(f"coa_{idx:03}.pdf", True, False, 50, 1.0, "full", None) for idx in range(100)]

    reader = pypdf.PdfReader(io.BytesIO(_render_reference_sheet(entries, "Test Practice")))
    text = "\n".join(page.extract_text() for page in reader.pages)

    assert len(reader.pages) > 1
    assert "coa_000.pdf" in text
    assert "coa_099.pdf" in text
