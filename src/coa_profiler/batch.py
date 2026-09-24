"""Operator batch CLI (FR-017, surface S8).

Processes a directory of certificates through the identical
parse -> score -> render pipeline, producing one branded PDF per COA, a
paginated reference sheet (entries sorted alphabetically by input filename for
deterministic output), and a ZIP archive with the successful PDFs plus
``failures.log``. Operator-only, offline, no network calls.

Exit codes: 0 if >= 80% of attempted COAs succeed, 1 if < 80%, and 2 for a
fatal operator/path error or when all attempted files fail.
"""

from __future__ import annotations

import argparse
import io
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from coa_profiler.config import load_config
from coa_profiler.errors import COAError
from coa_profiler.parser import parse_coa, sniff_file_type
from coa_profiler.pdf import render_profile_pdf
from coa_profiler.result_data import build_result_json, field_rows
from coa_profiler.scorer import score as score_chemistry
from coa_profiler.scorer.weights import weights_file_hash

SUCCESS_THRESHOLD = 0.80

#: Fixed ZIP entry timestamp — output must be byte-deterministic (FR-022).
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


@dataclass
class BatchEntry:
    filename: str
    ok: bool
    skipped: bool
    score: int | None
    confidence: float | None
    completeness: str
    error_code: str | None


class UnsafeBatchPathError(ValueError):
    """The requested output could overwrite or contaminate the input tree."""


def _resolve_batch_paths(input_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    """Resolve and reject output paths that overlap the protected input tree."""
    resolved_input = input_dir.expanduser().resolve()
    resolved_output = output_dir.expanduser().resolve()
    if resolved_output == resolved_input:
        raise UnsafeBatchPathError("output directory must be different from the input directory")
    if resolved_input in resolved_output.parents:
        raise UnsafeBatchPathError("output directory must not be inside the input directory")
    return resolved_input, resolved_output


def _render_reference_sheet(entries: list[BatchEntry], customer: str) -> bytes:
    """Paginated reference sheet, entries sorted alphabetically by filename."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter, invariant=True, pdfVersion=(1, 4))
    c.setTitle("COA batch reference sheet")
    _, h = letter

    def start_page(continuation: bool = False) -> float:
        y = h - 54
        c.setFont("Helvetica-Bold", 14)
        suffix = " (continued)" if continuation else ""
        c.drawString(54, y, f"Batch COA profiles — {customer}{suffix}")
        c.setFont("Helvetica", 9)
        return y - 24

    y = start_page()
    for e in sorted(entries, key=lambda e: e.filename):
        if y < 54:
            c.showPage()
            y = start_page(continuation=True)
        if e.skipped:
            line = f"SKIPPED: {e.filename}"
        elif e.ok:
            if e.completeness == "refusal":
                line = f"{e.filename}: no placement (insufficient readable data)"
            else:
                line = f"{e.filename}: placement {e.score}/100, combined confidence {e.confidence:.2f}"
        else:
            line = f"FAILED: {e.filename} {e.error_code}"
        c.drawString(54, y, line)
        y -= 13
    c.showPage()
    c.save()
    return buf.getvalue()


def _output_names(files: list[Path]) -> dict[Path, str]:
    """Return deterministic, collision-free profile names for input files."""
    stem_counts = Counter(path.stem.casefold() for path in files)
    used: set[str] = set()
    names: dict[Path, str] = {}
    for path in files:
        stem = path.stem
        if stem_counts[stem.casefold()] > 1:
            extension = path.suffix.removeprefix(".").lower() or "file"
            base = f"{stem}-{extension}"
        else:
            base = stem
        candidate = f"{base}.pdf"
        sequence = 2
        while candidate.casefold() in used:
            candidate = f"{base}-{sequence}.pdf"
            sequence += 1
        used.add(candidate.casefold())
        names[path] = candidate
    return names


def run_batch(
    input_dir: Path,
    output_dir: Path,
    customer: str,
    branding_logo: str | None = None,
    skip_invalid: bool = False,
    log=print,
) -> tuple[int, list[BatchEntry]]:
    # Validate before mkdir, input enumeration, or any output write. Resolving
    # both sides catches relative aliases and existing symlinks as well as
    # literal equal/nested paths.
    try:
        input_dir, output_dir = _resolve_batch_paths(input_dir, output_dir)
    except UnsafeBatchPathError as exc:
        log(f"FATAL: unsafe batch paths: {exc}")
        return 2, []

    cfg = load_config()
    version = cfg.version
    whash = weights_file_hash()

    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[BatchEntry] = []
    pdf_outputs: dict[str, bytes] = {}
    failures: list[str] = []

    files = sorted(p for p in input_dir.iterdir() if p.is_file())
    output_names = _output_names(files)
    for path in files:
        name = path.name
        try:
            data = path.read_bytes()
        except OSError:
            data = b""
        ftype = sniff_file_type(data) if data else None
        if ftype is None:
            if skip_invalid:
                log(f"SKIP: {name} (not a readable certificate file)")
                entries.append(BatchEntry(name, False, True, None, None, "skipped", None))
                continue
            log(f"FAIL: {name} INVALID_FILE_TYPE")
            entries.append(BatchEntry(name, False, False, None, None, "failed", "INVALID_FILE_TYPE"))
            failures.append(f"{name}: INVALID_FILE_TYPE")
            continue
        try:
            chemistry = parse_coa(path, config=cfg)
            placement = score_chemistry(chemistry)
        except COAError as err:
            if skip_invalid and err.error_code in {"NOT_A_COA", "UNREADABLE_DOCUMENT", "NO_USABLE_CHEMISTRY"}:
                log(f"SKIP: {name} ({err.error_code})")
                entries.append(BatchEntry(name, False, True, None, None, "skipped", None))
                continue
            log(f"FAIL: {name} {err.error_code}")
            entries.append(BatchEntry(name, False, False, None, None, "failed", err.error_code))
            failures.append(f"{name}: {err.error_code}")
            continue
        except Exception:  # noqa: BLE001 - one bad operator file must not abort a batch
            if skip_invalid:
                log(f"SKIP: {name} (unreadable)")
                entries.append(BatchEntry(name, False, True, None, None, "skipped", None))
                continue
            log(f"FAIL: {name} INTERNAL_ERROR")
            entries.append(BatchEntry(name, False, False, None, None, "failed", "INTERNAL_ERROR"))
            failures.append(f"{name}: INTERNAL_ERROR")
            continue

        # Degraded and refusal results count as successes: the pipeline ran.
        pdf_bytes = render_profile_pdf(
            chemistry,
            placement,
            version=version,
            weights_hash=whash,
            customer_name=customer,
            branding_logo=branding_logo,
            result_json=build_result_json(
                placement,
                field_rows(chemistry, placement),
                version,
                whash,
            ),
        )
        output_name = output_names[path]
        pdf_outputs[output_name] = pdf_bytes
        (output_dir / output_name).write_bytes(pdf_bytes)
        if placement.completeness == "refusal":
            log(f"PASS: {name} score=n/a (refusal — chemotype summary only)")
            entries.append(BatchEntry(name, True, False, None, None, "refusal", None))
        else:
            log(f"PASS: {name} score={placement.score}")
            entries.append(
                BatchEntry(
                    name,
                    True,
                    False,
                    placement.score,
                    placement.confidence_combined,
                    placement.completeness,
                    None,
                )
            )

    sheet = _render_reference_sheet(entries, customer)
    (output_dir / "reference_sheet.pdf").write_bytes(sheet)

    failures_log = ("\n".join(failures) + "\n") if failures else ""
    (output_dir / "failures.log").write_text(failures_log, encoding="utf-8")

    zip_path = output_dir / "batch_profiles.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pdf_name in sorted(pdf_outputs):
            info = zipfile.ZipInfo(pdf_name, date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, pdf_outputs[pdf_name])
        info = zipfile.ZipInfo("failures.log", date_time=_ZIP_EPOCH)
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, failures_log)

    attempted = [e for e in entries if not e.skipped]
    succeeded = [e for e in attempted if e.ok]
    if not attempted or not succeeded:
        code = 2
    else:
        code = 0 if len(succeeded) / len(attempted) >= SUCCESS_THRESHOLD else 1
    log(
        f"batch complete: {len(succeeded)}/{len(attempted)} succeeded "
        f"({len(entries) - len(attempted)} skipped) -> exit {code}"
    )
    return code, entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="coa_profiler.batch", description="Offline batch COA profiler (FR-017)."
    )
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--customer", required=True)
    parser.add_argument("--branding-logo", default=None)
    parser.add_argument("--skip-invalid", action="store_true")
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        print(f"input directory not found: {input_dir}", file=sys.stderr)
        return 2
    code, _ = run_batch(
        input_dir,
        Path(args.output_dir),
        args.customer,
        branding_logo=args.branding_logo,
        skip_invalid=args.skip_invalid,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
