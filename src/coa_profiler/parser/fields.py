"""Structured chemistry record + cite-and-verify field extraction (FR-005).

Every extracted value must trace to a literal text span in the extracted
document text; any field that cannot be verified is recorded as ``unreadable``
and is never interpolated, defaulted, or estimated.

Unit normalization to % w/w before storage:
  %      -> used directly
  mg/g   -> x 0.1
  mg/mL  -> x 0.1   (assumes density ~1.0 g/mL; tracked as assumption A-17)
  ppm    -> x 0.0001
The original value and unit are preserved alongside the normalized value.

THCA/CBDA derivation (DIS-15): when a COA reports THCA and delta-9 THC
separately but no "Total THC" line, Total THC = delta-9 + 0.877 x THCA
(likewise Total CBD = CBD + 0.877 x CBDA), marked ``derived: true``.

Plausibility flags (FR-028) live here as well: values outside expected ranges
are flagged (still used for scoring — they trace to the document), and a
document whose extracted values are mostly implausible is downgraded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Data model (spec section 5) -------------------------------------------


@dataclass
class ParsedField:
    name: str
    value: float | None = None  # normalized % w/w; None when unreadable
    original_value: float | None = None  # as reported on the COA, before conversion
    original_unit: str | None = None  # "%", "mg/g", "mg/mL", "ppm"
    status: str = "unreadable"  # "verified" | "unreadable"
    unreadable_reason: str | None = None
    source_span: str | None = None  # literal extracted text backing the value
    conflicting_value: bool = False
    derived: bool = False  # True for THCA/CBDA-derived totals (DIS-15)
    plausibility_flag: bool = False  # True when value exceeds expected range (FR-028)
    user_flagged: bool = False  # always False at launch; reserved hook (DIS-3)
    conflict_span: str | None = None  # losing span retained on multi-page conflicts
    derivation_note: str | None = None


@dataclass
class COAChemistry:
    cannabinoids: dict[str, ParsedField] = field(default_factory=dict)
    terpenes: dict[str, ParsedField] = field(default_factory=dict)
    lab_format: str = "unknown"
    total_reported_terpenes: int | None = None
    ocr_mean_confidence: float | None = None
    forced_refusal_reason: str | None = None  # set by the FR-028 >50% rule


# --- Compound registry ------------------------------------------------------

_NUM = r"(\d+(?:\.\d+)?)"
_UNIT = r"(mg\s*/\s*g|mg\s*/\s*ml|mg\s*/\s*mL|ppm|%|mg)"
_ND = r"(ND|N/D|<\s*LOQ|<\s*0\.0\d+)"

#: A bare numeric table column (supports scientific notation, e.g. LOD "3.20E-5").
_SCI_NUM = r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
#: Real lab tables (ACS Laboratory / Kaycha style) print dilution/LOD/LOQ/mg-g
#: columns between the analyte name and the unit-bearing value. Allow the
#: value+unit match to skip up to two such bare numeric columns on the same
#: line (a bare number is only skippable when followed by whitespace, so a
#: value with an attached unit is never consumed as a skip).
_SKIP_COLS = rf"(?:{_SCI_NUM}\s+){{0,2}}"


#: Names must start at a non-letter boundary: without this, the bare-"a"
#: alternative of alpha-pinene matches inside "bet(a-Pinene)" and reads the
#: neighboring row's value.
_NAME_PREFIX = r"(?i)(?<![A-Za-z])("


def _rx(*names: str) -> re.Pattern[str]:
    """Match a compound name followed shortly by a numeric value + unit."""
    alt = "|".join(names)
    return re.compile(rf"{_NAME_PREFIX}{alt})\b[^\d\n]{{0,24}}{_SKIP_COLS}{_NUM}\s*{_UNIT}")


CANNABINOID_PATTERNS: dict[str, re.Pattern[str]] = {
    # Order of lookup matters at call sites: totals first, then components.
    "thc_total": _rx(
        r"total\s*thc",
        r"thc\s*total",
        r"total\s*delta[\s\-]?9[\s\-]?thc",
        r"total\s*active\s*thc",  # ACS Laboratory wording
    ),
    "cbd_total": _rx(r"total\s*cbd", r"cbd\s*total", r"total\s*active\s*cbd"),
    "thca": _rx(r"thca\b", r"tetrahydrocannabinolic\s+acid"),
    "cbda": _rx(r"cbda\b", r"cannabidiolic\s+acid"),
    "delta9_thc": _rx(r"(?:delta|Δ|d)\s*[\-]?\s*9[\s\-]*thc", r"d9[\s\-]?thc", r"delta9[\s\-]?thc"),
    "cbd": _rx(r"\bcbd\b"),
}

TERPENE_PATTERNS: dict[str, re.Pattern[str]] = {
    "myrcene": _rx(r"(?:β|beta[\s\-])?myrcene"),
    "linalool": _rx(r"linalool"),
    "humulene": _rx(r"(?:α|alpha[\s\-])?humulene"),
    "nerolidol": _rx(r"nerolidol"),
    "limonene": _rx(r"(?:d[\s\-])?limonene"),
    "alpha_pinene": _rx(r"(?:α|alpha|a)[\s\-]?pinene"),
    "beta_pinene": _rx(r"(?:β|beta|b)[\s\-]?pinene"),
    "terpinolene": _rx(r"terpinolene"),
    "ocimene": _rx(r"ocimene"),
    "beta_caryophyllene": _rx(r"(?:β|beta)[\s\-]?caryophyllene", r"trans[\s\-]?caryophyllene"),
    "bisabolol": _rx(r"(?:α|alpha)[\s\-]?bisabolol", r"bisabolol"),
    "eucalyptol": _rx(r"eucalyptol", r"1,8[\s\-]?cineole"),
    "camphene": _rx(r"camphene"),
    "farnesene": _rx(r"(?:α|alpha|β|beta)[\s\-]?farnesene", r"farnesene"),
    "valencene": _rx(r"valencene"),
    "geraniol": _rx(r"geraniol"),
    "fenchyl_alcohol": _rx(r"fenchyl[\s\-]+alcohol"),
    "alpha_terpineol": _rx(r"(?:α|alpha|a)[\s\-]?terpineol"),
}

# ND patterns are derived from the numeric patterns lazily by
# _nd_pattern_for (same name alternation, ND/<LOQ in place of the number).


def _name_alternation(pattern: re.Pattern[str]) -> str | None:
    """Recover the compound-name alternation from an ``_rx``-built pattern."""
    src = pattern.pattern
    if not src.startswith(_NAME_PREFIX):
        return None
    rest = src[len(_NAME_PREFIX) :]
    end = rest.find(r")\b")
    return rest[:end] if end > 0 else None


def _nd_pattern_for(name: str, patterns: dict[str, re.Pattern[str]]) -> re.Pattern[str] | None:
    alt = _name_alternation(patterns[name])
    if alt is None:
        return None
    return re.compile(rf"{_NAME_PREFIX}{alt})\b[^\n]{{0,24}}?{_ND}\b")


#: One bare numeric table token (used by the dual-column rule below).
_NUM_TOKEN_RE = re.compile(rf"^{_SCI_NUM}$")

#: Relative tolerance for the mg/g <-> % cross-check (values are printed
#: rounded to 3-4 significant digits on real certificates).
_DUAL_COLUMN_REL_TOL = 0.06

#: Unit-in-header inference is valid only inside a nearby, explicitly labelled
#: chemistry panel.  Keeping the window bounded prevents a percent header in a
#: different table (or explanatory prose later in the report) from lending its
#: unit to an unrelated number.
_TABLE_CONTEXT_LIMIT = 3000
_HEADER_REGION_LIMIT = 1000
_CANNABINOID_HEADING_RE = re.compile(
    r"(?im)(?:\bpotency(?:\s+(?:profile|summary|analysis))?\b|"
    r"^\s*cannabinoids?(?:\s+(?:profile|summary|analysis))?\s*$)"
)
_TERPENE_HEADING_RE = re.compile(r"(?i)\bterpenes?(?:\s+(?:profile|summary|analysis))?\b")
# Modern Canna prints the cannabinoid percent followed by total milligrams;
# total milligrams depend on package mass and therefore do NOT obey mg/g = 10x%.
_PCT_THEN_TOTAL_MG_HEADER_RE = re.compile(r"(?i)\banalyte\s+%\s+mg(?!\s*/\s*g)\b(?:\s+analyte\s+%)?")
_PCT_ONLY_HEADER_RE = re.compile(r"(?im)^\s*analyte\s+(?:result\s*)?(?:\(\s*%\s*\)|%)(?!\s+mg\s*/\s*g)")
_MGG_RE = re.compile(r"(?i)mg\s*/\s*g")
# A generic denominator may include analytes outside our extraction registry,
# but only when the source explicitly declares a result table.  This header
# grammar deliberately excludes prose that merely mentions an analyte.
_TERPENE_RESULT_HEADER_RE = re.compile(
    r"(?im)^\s*analyte(?:\s+name)?(?:\s+results?)?"
    # ACS emits both units as separately parenthesized columns:
    # ``Analyte Result (mg/g) (%)``. Accept the same declared layout when
    # either unit loses its parentheses during text-layer extraction.
    r"(?:\s+(?:\(\s*mg\s*/\s*g\s*\)|mg\s*/\s*g))?"
    r"(?:\s+results?)?\s+(?:\(\s*%\s*\)|%)"
    # Modern Canna's merged header remains ``Analyte % mg Analyte %``.
    r"(?:\s+mg)?(?:\s+analyte\s+%)?\s*$"
)
_TERPENE_PANEL_END_RE = re.compile(
    r"(?im)^\s*(?:methods?|methodology|analysis\s+summary|potency(?:\s+summary)?|"
    r"cannabinoids?(?:\s+(?:profile|summary|analysis))?|pesticides?|microbials?|"
    r"residual\s+solvents?|heavy\s+metals?|mycotoxins?|foreign\s+material)\b"
)
_ANALYTE_WORDS = (
    r"[A-Za-zΑ-ωα-ωβΔ][A-Za-zΑ-ωα-ωβΔ0-9,+()/'\-]*(?:\s+[A-Za-zΑ-ωα-ωβΔ][A-Za-zΑ-ωα-ωβΔ0-9,+()/'\-]*){0,5}"
)
_GENERIC_INLINE_RESULT_ROW_RE = re.compile(
    rf"^\s*(?P<name>{_ANALYTE_WORDS})\s+(?:{_SCI_NUM}\s+){{0,5}}"
    rf"(?:{_SCI_NUM}\s*(?:%|mg\s*/\s*g|mg\s*/\s*mL|ppm)|{_ND})\s*$",
    re.IGNORECASE,
)
_GENERIC_BARE_RESULT_TAIL_RE = re.compile(
    rf"(?P<name>{_ANALYTE_WORDS})\s+(?:{_SCI_NUM}|{_ND})\s*$",
    re.IGNORECASE,
)

# Modern Canna's summary declares four headings on one line and their values
# on the next.  The first two parenthesized mg values are package totals, not
# mg/g, so the literal percentages are authoritative.  Keeping this grammar
# exact prevents a generic prose occurrence of "Total THC" from becoming a
# field while preserving the report's own rounded totals instead of deriving
# needlessly precise substitutes from component rows.
_MODERN_SUMMARY_TOTALS_RE = re.compile(
    r"(?im)^\s*Total\s+CBD\s+Total\s+THC\s+Total\s+Cannabinoids\s+Total\s+Terpenes\s*$\n"
    r"\s*(?P<cbd>\d+(?:\.\d+)?)%\s*\([^\n)]*\)\s+"
    r"(?P<thc>\d+(?:\.\d+)?)%\s*\([^\n)]*\)\s+"
    r"\d+(?:\.\d+)?%\s*\([^\n)]*\)\s+\d+(?:\.\d+)?%"
)


def _table_region(text: str, position: int, kind: str) -> str | None:
    """Return the bounded panel text preceding ``position``, if labelled."""
    heading_re = _TERPENE_HEADING_RE if kind == "terpene" else _CANNABINOID_HEADING_RE
    headings = list(heading_re.finditer(text, 0, position))
    if not headings:
        return None
    start = headings[-1].start()
    if position - start > _TABLE_CONTEXT_LIMIT:
        return None
    return text[start:position]


def _table_column_mode(text: str, position: int, kind: str) -> str | None:
    """Identify a source-declared unit layout for the nearby chemistry panel.

    ``pct_total_mg`` is Modern Canna's ``Analyte % mg`` layout.  ``mgg_pct``
    covers tables that declare paired mg/g and percent result columns.  A bare
    ``pct`` mode is accepted only for terpene tables with an explicit percent
    column.
    """
    region = _table_region(text, position, kind)
    if region is None:
        return None
    header = region[:_HEADER_REGION_LIMIT]
    if _PCT_THEN_TOTAL_MG_HEADER_RE.search(header):
        return "pct_total_mg"
    if re.search(r"(?i)\banalyte\b", header) and _MGG_RE.search(header) and "%" in header:
        return "mgg_pct"
    if kind == "terpene" and _PCT_ONLY_HEADER_RE.search(header):
        return "pct"
    return None


def _dual_column_line(
    name: str, pattern: re.Pattern[str], text: str, kind: str
) -> tuple[ParsedField, float] | None:
    """Unit-from-column-structure extraction for unit-less table rows (FR-005).

    Real Florida certificates (ACS Laboratory / Kaycha families) print analyte
    rows whose units live only in the column header, e.g.::

        THCA-A 15.000 3.20E-5 0.0015 307 30.7      (dilution, LOD, LOQ, mg/g, %)
        Total Active THC 15.000 278 27.8

    The inline name+value+unit grammar cannot read these. This rule stays
    cite-and-verify: it takes the CONTIGUOUS run of bare numeric tokens
    immediately after the name (stopping at the first non-numeric token, so a
    merged neighboring column or definition prose is never consumed). An ACS
    mg/g-plus-% table must self-verify at the 10:1 conversion. A Modern Canna
    ``Analyte % mg`` table instead declares that the first value is percent;
    its total-mg column varies with package mass and is never used as a unit
    conversion.
    """
    alt = _name_alternation(pattern)
    if alt is None:
        return None
    name_re = re.compile(rf"{_NAME_PREFIX}{alt})\b")
    offset = 0
    for line in text.splitlines():
        try:
            m = name_re.search(line)
            if not m:
                continue
            absolute_position = offset + m.start()
            column_mode = _table_column_mode(text, absolute_position, kind)
            if column_mode not in {"pct_total_mg", "mgg_pct"}:
                continue
            rest = line[m.end() :]
            gap = re.match(r"[^\d\n]{0,24}", rest)
            gap_end = gap.end() if gap else 0
            tail = rest[gap_end:]
            run: list[float] = []
            run_char_end = 0
            for tok in re.finditer(r"\S+", tail):
                if _NUM_TOKEN_RE.match(tok.group(0)):
                    run.append(float(tok.group(0)))
                    run_char_end = tok.end()
                else:
                    break
            if len(run) < 2:
                continue
            if column_mode == "pct_total_mg":
                # The header, rather than a package-mass assumption, identifies
                # the first value as percent.  The following total-mg value may
                # be 10x, 35x, or another factor depending on package size.
                pct = run[0]
                derivation_note = "unit taken from the table's declared % column"
            else:
                x, y = run[-2], run[-1]
                lo, hi = min(x, y), max(x, y)
                if lo == 0.0 and hi == 0.0:
                    pct = 0.0
                elif lo > 0.0 and abs(hi - 10.0 * lo) <= _DUAL_COLUMN_REL_TOL * hi:
                    pct = lo
                else:
                    continue
                derivation_note = "unit inferred from paired mg/g and % columns (10:1 cross-check)"
            span = line[m.start() : m.end() + gap_end + run_char_end].strip()[:160]
            return ParsedField(
                name=name,
                value=pct,
                original_value=pct,
                original_unit="%",
                status="verified",
                source_span=span,
                derivation_note=derivation_note,
            ), float(offset + m.start())
        finally:
            offset += len(line) + 1
    return None


# --- Unit normalization ------------------------------------------------------

_UNIT_FACTORS = {"%": 1.0, "mg/g": 0.1, "mg/ml": 0.1, "ppm": 0.0001}


def normalize_unit(value: float, unit: str) -> tuple[float, str] | None:
    """Return (normalized % w/w, canonical unit label) or None when unknown."""
    u = re.sub(r"\s+", "", unit).lower()
    u = {"mg/g": "mg/g", "mg/ml": "mg/mL", "%": "%", "ppm": "ppm"}.get(u)
    if u is None:
        return None
    return value * _UNIT_FACTORS[{"mg/mL": "mg/ml"}.get(u, u)], u


# --- Extraction --------------------------------------------------------------


def _single_column_line(name: str, pattern: re.Pattern[str], text: str) -> tuple[ParsedField, float] | None:
    """Single-value terpene rows under a %-declaring column header (FR-005).

    Modern Canna certificates print terpenes as ``beta-Caryophyllene 0.491``
    — one bare number whose unit lives only in the ``Analyte %`` header. The
    read stays cite-and-verify: it fires only when the page text literally
    declares the % column header, only for a row whose numeric run is exactly
    one number, and only within the terpene plausibility ceiling; the header
    declaration is recorded in the derivation note.
    """
    alt = _name_alternation(pattern)
    if alt is None:
        return None
    name_re = re.compile(rf"{_NAME_PREFIX}{alt})\b")
    offset = 0
    for line in text.splitlines():
        try:
            m = name_re.search(line)
            if not m:
                continue
            absolute_position = offset + m.start()
            if _table_column_mode(text, absolute_position, "terpene") not in {
                "pct_total_mg",
                "pct",
            }:
                continue
            rest = line[m.end() :]
            gap = re.match(r"[^\d\n]{0,24}", rest)
            gap_end = gap.end() if gap else 0
            tail = rest[gap_end:]
            run: list[str] = []
            run_char_end = 0
            for tok in re.finditer(r"\S+", tail):
                if _NUM_TOKEN_RE.match(tok.group(0)):
                    run.append(tok.group(0))
                    run_char_end = tok.end()
                else:
                    break
            if len(run) != 1:
                continue
            value = float(run[0])
            if value > TERPENE_MAX:
                continue
            span = line[m.start() : m.end() + gap_end + run_char_end].strip()[:160]
            return ParsedField(
                name=name,
                value=value,
                original_value=value,
                original_unit="%",
                status="verified",
                source_span=span,
                derivation_note="unit taken from the table's declared % column header",
            ), float(offset + m.start())
        finally:
            offset += len(line) + 1
    return None


def _extract_one(
    name: str, pattern: re.Pattern[str], text: str, page_index: int, kind: str = "cannabinoid"
) -> tuple[ParsedField, float] | None:
    """Find the first numeric citation of ``name`` on a page.

    Returns (field, match_position) or None when not present on the page.
    ND / below-LOQ results are recorded as verified 0.0 (the document reports
    the compound as not detected — a real measurement, not a missing one).
    """
    m = pattern.search(text)
    if m:
        raw_value = float(m.group(2))
        unit = m.group(3)
        span = text[max(0, m.start()) : m.end()]
        if raw_value < 0:
            return ParsedField(
                name=name,
                status="unreadable",
                unreadable_reason="negative value reported",
                source_span=span,
            ), float(m.start())
        norm = normalize_unit(raw_value, unit)
        if norm is None:
            return ParsedField(
                name=name,
                original_value=raw_value,
                original_unit=unit,
                status="unreadable",
                unreadable_reason=f"unrecognized unit {unit!r}",
                source_span=span,
            ), float(m.start())
        value, canonical_unit = norm
        return ParsedField(
            name=name,
            value=value,
            original_value=raw_value,
            original_unit=canonical_unit,
            status="verified",
            source_span=span,
        ), float(m.start())
    nd = _nd_pattern_for(name, {name: pattern})
    if nd is not None:
        m = nd.search(text)
        if m:
            span = text[max(0, m.start()) : m.end()]
            return ParsedField(
                name=name,
                value=0.0,
                original_value=0.0,
                original_unit="%",
                status="verified",
                source_span=span,
            ), float(m.start())
    # Last resorts for unit-in-header table rows: the mg/g <-> % column pair
    # (ACS Laboratory / Kaycha layouts), then — terpenes only — the
    # single-value %-header rule (Modern Canna layout).
    got = _dual_column_line(name, pattern, text, kind)
    if got is not None:
        return got
    if kind == "terpene":
        return _single_column_line(name, pattern, text)
    return None


def _extract_summary_totals(text: str) -> dict[str, ParsedField]:
    """Read strictly paired summary headings/values from supported reports."""
    match = _MODERN_SUMMARY_TOTALS_RE.search(text)
    if match is None:
        return {}
    source_span = match.group(0).strip()
    return {
        name: ParsedField(
            name=name,
            value=float(match.group(group)),
            original_value=float(match.group(group)),
            original_unit="%",
            status="verified",
            source_span=source_span,
        )
        for name, group in (("cbd_total", "cbd"), ("thc_total", "thc"))
    }


def count_reported_terpenes(pages: list[str]) -> int | None:
    """Count distinct terpene result-row names independently of extraction.

    This is deliberately not ``len(extracted_terpenes)``: a recognized row may
    be unreadable, and that miss must remain visible to the sufficiency and
    confidence calculations.  Names count only when they occur after a nearby
    terpene panel heading and are followed on the same line by a numeric or
    ND/LOQ result token.  The function returns ``None`` when the source has no
    identifiable terpene panel, so callers can use the absolute sufficiency
    rule without inventing a denominator.
    """
    # Join pages so a labelled panel whose rows continue after a page break
    # retains its context.  The ordinary bounded-distance rule still applies,
    # so a heading cannot lend meaning arbitrarily far into a later page.
    text = "\n".join(pages)
    reported: set[str] = set()
    saw_panel = bool(_TERPENE_HEADING_RE.search(text))

    def row_identity(raw_name: str) -> str | None:
        raw_name = re.sub(r"\s+", " ", raw_name.strip()).casefold()
        if (
            not raw_name
            or raw_name in {"nd", "n/d", "loq"}
            or raw_name.startswith(("total ", "analyte ", "result "))
        ):
            return None
        # Collapse aliases already known to the registry so the generic pass
        # cannot double-count the same source analyte as a recognized row.
        for canonical, pattern in TERPENE_PATTERNS.items():
            alt = _name_alternation(pattern)
            if alt is not None and re.search(rf"{_NAME_PREFIX}{alt})\b", raw_name):
                return f"known:{canonical}"
        return f"source:{raw_name}"

    def explicit_table_state(position: int) -> bool | None:
        """True in an explicit result table, False after its end, else None."""
        region = _table_region(text, position, "terpene")
        if region is None:
            return None
        headers = list(_TERPENE_RESULT_HEADER_RE.finditer(region))
        if not headers:
            return None
        after_header = region[headers[-1].end() :]
        return not bool(_TERPENE_PANEL_END_RE.search(after_header))

    offset = 0
    for line in text.splitlines():
        for name, pattern in TERPENE_PATTERNS.items():
            alt = _name_alternation(pattern)
            if alt is None:
                continue
            match = re.search(rf"{_NAME_PREFIX}{alt})\b", line)
            if not match:
                continue
            position = offset + match.start()
            if _table_region(text, position, "terpene") is None:
                continue
            if explicit_table_state(position) is False:
                continue
            tail = line[match.end() :]
            if re.match(rf"[^\d\n]{{0,24}}(?:{_SCI_NUM}|{_ND})\b", tail, re.IGNORECASE):
                reported.add(f"known:{name}")

        # Unknown/unmodeled analytes affect the source denominator too, but a
        # generic name is accepted only inside an explicitly headed result
        # table and before a recognized next-section boundary.  This prevents
        # numbers in method prose from degrading confidence.
        if explicit_table_state(offset) is True:
            generic = _GENERIC_INLINE_RESULT_ROW_RE.match(line)
            if generic is None:
                generic = _GENERIC_BARE_RESULT_TAIL_RE.search(line)
            if generic is not None and (identity := row_identity(generic.group("name"))) is not None:
                reported.add(identity)
        offset += len(line) + 1
    if not saw_panel:
        return None
    return len(reported)


@dataclass
class PageExtraction:
    page_index: int
    page_format: str
    format_score: float
    cannabinoids: dict[str, ParsedField]
    terpenes: dict[str, ParsedField]
    text: str


def extract_page(page_index: int, text: str, page_format: str, format_score: float) -> PageExtraction:
    cann = _extract_summary_totals(text)
    terp: dict[str, ParsedField] = {}
    for name, pattern in CANNABINOID_PATTERNS.items():
        if name in cann:
            continue
        got = _extract_one(name, pattern, text, page_index, kind="cannabinoid")
        if got:
            cann[name] = got[0]
    for name, pattern in TERPENE_PATTERNS.items():
        got = _extract_one(name, pattern, text, page_index, kind="terpene")
        if got:
            terp[name] = got[0]
    return PageExtraction(page_index, page_format, format_score, cann, terp, text)


def merge_pages(
    pages: list[PageExtraction], document_format: str
) -> tuple[dict[str, ParsedField], dict[str, ParsedField]]:
    """FR-004/FR-005 multi-page merge with conflict resolution.

    When the same compound appears on multiple pages with different values,
    the value from the page whose sub-format signature most strongly matches
    the document-level format wins; the conflict is recorded and the losing
    span retained.
    """
    merged_c: dict[str, ParsedField] = {}
    merged_t: dict[str, ParsedField] = {}
    for table, merged in ((lambda p: p.cannabinoids, merged_c), (lambda p: p.terpenes, merged_t)):
        names: set[str] = set()
        for p in pages:
            names.update(table(p).keys())
        for name in sorted(names):
            candidates: list[tuple[PageExtraction, ParsedField]] = [
                (p, table(p)[name]) for p in pages if name in table(p)
            ]
            verified = [(p, f) for p, f in candidates if f.status == "verified"]
            pool = verified if verified else candidates
            # Rank: sub-format matches document format first, then signature
            # strength, then earlier page.
            pool.sort(
                key=lambda pf: (
                    0 if pf[0].page_format == document_format else 1,
                    -pf[0].format_score,
                    pf[0].page_index,
                )
            )
            _, winner = pool[0]
            losers = [f for p, f in pool[1:] if f is not winner and f.value != winner.value]
            if losers:
                winner.conflicting_value = True
                winner.conflict_span = losers[0].source_span
            merged[name] = winner
    return merged_c, merged_t


# --- THCA/CBDA derivation (DIS-15) ------------------------------------------

DECARBOXYLATION_FACTOR = 0.877


def derive_totals(cannabinoids: dict[str, ParsedField]) -> None:
    """Derive Total THC / Total CBD from components when no total line exists."""
    from coa_profiler.lexicon import DERIVATION_NOTE, DERIVATION_NOTE_CBD

    total_thc = cannabinoids.get("thc_total")
    thca = cannabinoids.get("thca")
    d9 = cannabinoids.get("delta9_thc")
    if (
        (total_thc is None or total_thc.status != "verified")
        and thca
        and d9
        and thca.status == "verified"
        and d9.status == "verified"
        and thca.value is not None
        and d9.value is not None
    ):
        derived_value = d9.value + DECARBOXYLATION_FACTOR * thca.value
        span = f"{d9.source_span or ''} + 0.877 × ({thca.source_span or ''})"
        cannabinoids["thc_total"] = ParsedField(
            name="thc_total",
            value=derived_value,
            original_value=derived_value,
            original_unit="%",
            status="verified",
            source_span=span,
            derived=True,
            derivation_note=DERIVATION_NOTE,
        )
    total_cbd = cannabinoids.get("cbd_total")
    cbda = cannabinoids.get("cbda")
    cbd = cannabinoids.get("cbd")
    if (
        (total_cbd is None or total_cbd.status != "verified")
        and cbda
        and cbd
        and cbda.status == "verified"
        and cbd.status == "verified"
        and cbda.value is not None
        and cbd.value is not None
    ):
        derived_value = cbd.value + DECARBOXYLATION_FACTOR * cbda.value
        span = f"{cbd.source_span or ''} + 0.877 × ({cbda.source_span or ''})"
        cannabinoids["cbd_total"] = ParsedField(
            name="cbd_total",
            value=derived_value,
            original_value=derived_value,
            original_unit="%",
            status="verified",
            source_span=span,
            derived=True,
            derivation_note=DERIVATION_NOTE_CBD,
        )


# --- Plausibility (FR-028) ----------------------------------------------------

THC_TOTAL_MAX = 40.0
CBD_TOTAL_MAX = 25.0
TERPENE_MAX = 10.0


def apply_plausibility(chemistry: COAChemistry) -> None:
    """Flag out-of-range values in place. Flagged values are still used for
    scoring (they trace to the document); the flag signals a possible
    extraction error to the user."""
    for name, f in {**chemistry.cannabinoids, **chemistry.terpenes}.items():
        if f.status != "verified" or f.value is None:
            continue
        if (
            f.value < 0
            or name == "thc_total"
            and f.value > THC_TOTAL_MAX
            or name == "cbd_total"
            and f.value > CBD_TOTAL_MAX
            or name in chemistry.terpenes
            and f.value > TERPENE_MAX
        ):
            f.plausibility_flag = True


def implausible_fraction(chemistry: COAChemistry) -> float:
    """Share of verified extracted values that exceed plausibility ranges."""
    fields = [
        f
        for f in {**chemistry.cannabinoids, **chemistry.terpenes}.values()
        if f.status == "verified" and f.value is not None
    ]
    if not fields:
        return 0.0
    flagged = sum(1 for f in fields if f.plausibility_flag)
    return flagged / len(fields)
