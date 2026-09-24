"""Copy-lint CLI (FR-019, surface S10).

Two scopes:
- boot: static template files only (fast; AC-043 budget 5 s)
- CI:   static templates plus dynamically generated rationale from every
        fixture COA (thorough; exercises the full parse -> score pipeline)

Exit 0 when clean, 1 on any hit. The application runs the boot scan at
startup and refuses to start on a hit unless COPYLINT_SOFT_FAIL=true.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from coa_profiler.lexicon import find_banned

BOOT_BUDGET_SECONDS = 5.0


@dataclass(frozen=True)
class CopyHit:
    location: str
    term: str
    matched: str
    context: str


def _scan_text(location: str, text: str) -> list[CopyHit]:
    hits: list[CopyHit] = []
    for h in find_banned(text):
        start = max(0, h.index - 30)
        context = text[start : h.index + len(h.matched) + 30].replace("\n", " ")
        hits.append(CopyHit(location=location, term=h.term, matched=h.matched, context=context))
    return hits


def scan_templates(templates_dir: str | Path) -> list[CopyHit]:
    """Boot scope: static .html template files only."""
    hits: list[CopyHit] = []
    directory = Path(templates_dir)
    if not directory.is_dir():
        return [CopyHit(str(directory), "<missing>", "", "templates directory not found")]
    for path in sorted(directory.glob("*.html")):
        hits.extend(_scan_text(str(path), path.read_text(encoding="utf-8")))
    return hits


def scan_dynamic_rationale(fixtures_dir: str | Path) -> list[CopyHit]:
    """CI scope: generate rationale from every parseable fixture and lint it."""
    hits: list[CopyHit] = []
    from coa_profiler.parser import parse_coa
    from coa_profiler.scorer import score

    directory = Path(fixtures_dir)
    paths = sorted(p for p in directory.rglob("*") if p.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png"})
    scanned = 0
    for path in paths:
        try:
            chemistry = parse_coa(path)
            result = score(chemistry)
        except Exception:  # noqa: BLE001,S112 - unparseable fixtures have no generated copy to lint
            continue  # unparseable fixtures produce no copy; the typed errors are linted statically
        scanned += 1
        for i, sentence in enumerate(result.rationale):
            hits.extend(_scan_text(f"{path}:rationale[{i}]", sentence))
    # Loud accounting so a broken parser can never silently shrink the scan.
    print(f"copy-lint dynamic scan: {scanned}/{len(paths)} fixture(s) produced rationale", file=sys.stderr)
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="coa_profiler.copylint", description="Banned-lexicon scanner (FR-019)."
    )
    parser.add_argument("--templates", required=True, help="templates directory (boot scope)")
    parser.add_argument("--fixtures", default=None, help="fixtures directory (CI scope: dynamic rationale)")
    args = parser.parse_args(argv)

    started = time.monotonic()
    hits = scan_templates(args.templates)
    scope = "templates"
    if args.fixtures:
        hits.extend(scan_dynamic_rationale(args.fixtures))
        scope = "templates+rationale"
    elapsed = time.monotonic() - started

    if elapsed >= BOOT_BUDGET_SECONDS and not args.fixtures:
        print(f"WARNING: boot scan took {elapsed:.2f}s (budget {BOOT_BUDGET_SECONDS:.0f}s)", file=sys.stderr)
    if hits:
        for hit in hits:
            print(f"BANNED TERM {hit.term!r} in {hit.location}: …{hit.context}…")
        print(f"copy-lint FAILED ({len(hits)} hit(s), scope={scope}, {elapsed:.2f}s)")
        return 1
    print(f"copy-lint clean (scope={scope}, {elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
