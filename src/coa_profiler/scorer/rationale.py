"""Plain-language rationale generation (FR-008).

Every sentence is templated and names the compounds, their values and units
exactly as reported on the COA, and their directional contribution. All output
is checked against the banned lexicon (FR-010) before being returned; the
copy-lint CI scan exercises this generator over every fixture COA (FR-019).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from coa_profiler.lexicon import MONITORED_NOTE, find_banned
from coa_profiler.scorer.weights import UNSCORED_TERRENES, WEIGHTS

if TYPE_CHECKING:
    from coa_profiler.parser.fields import COAChemistry, ParsedField


def _as_reported(f: ParsedField) -> str:
    """Value and unit exactly as reported on the COA, with normalization note."""
    if f.original_value is None:
        return "unreadable"
    reported = f"{f.original_value:g} {f.original_unit}" if f.original_unit else f"{f.original_value:g}"
    if f.derived:
        return f"{f.value:g}% (derived; see note)"
    if f.original_unit and f.original_unit != "%":
        return f"{reported} (= {f.value:g}%)"
    return f"{f.value:g}%"


def _display(name: str) -> str:
    spec = WEIGHTS.get(name)
    return spec["display"] if spec else name.replace("_", " ").title()


def build_rationale(
    chemistry: COAChemistry,
    driving_compounds: list[tuple[str, float, str]],
    completeness: str,
) -> list[str]:
    """Templated rationale sentences naming the top 2-3 driving compounds."""
    if completeness == "refusal" or not driving_compounds:
        return []

    sentences: list[str] = []
    if completeness == "degraded":
        sentences.append(
            "With terpene data insufficient, this placement uses only the weighted THC-total "
            "and CBD-total contributions — a particularly contested basis for directional placement."
        )

    all_fields = {**chemistry.cannabinoids, **chemistry.terpenes}
    verbs = {
        "indica": "pulls the placement toward the indica-leaning end",
        "sativa": "pulls the placement toward the sativa-leaning end",
    }
    for rank, (name, contribution, direction) in enumerate(driving_compounds):
        f = all_fields.get(name)
        if f is None or f.value is None:
            continue
        if rank == 0:
            lead = "is the strongest contributor"
        elif rank == 1:
            lead = "is the second-strongest contributor"
        else:
            lead = "also contributes"
        sentences.append(f"{_display(name)} ({_as_reported(f)} on your COA) {lead}: it {verbs[direction]}.")

    monitored = [n for n, spec in WEIGHTS.items() if spec.get("monitored")]
    for name in monitored:
        f = all_fields.get(name)
        if f is not None and f.status == "verified" and f.value is not None:
            sentences.append(f"{_display(name)} ({_as_reported(f)}) is {MONITORED_NOTE}.")

    unscored = [
        n
        for n in UNSCORED_TERRENES
        if (f := all_fields.get(n)) is not None and f.status == "verified" and f.value is not None
    ]
    if unscored:
        listed = ", ".join(f"{_display(n)} ({_as_reported(all_fields[n])})" for n in unscored)
        sentences.append(
            f"Additional compounds present on your COA not included in the current model: {listed}."
        )

    for sentence in sentences:
        hits = find_banned(sentence)
        if hits:  # defensive: the templates above are designed clean
            raise ValueError(f"rationale sentence failed copy-lint: {hits[0].term!r} in {sentence!r}")
    return sentences
