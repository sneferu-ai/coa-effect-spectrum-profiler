"""FR-011/FR-022 PDF rendering: bounded page, audit data, determinism."""

import io
import json
from pathlib import Path

import pypdf
import pytest

from coa_profiler.parser import parse_coa
from coa_profiler.parser.fields import CANNABINOID_PATTERNS, TERPENE_PATTERNS
from coa_profiler.pdf import render_profile_pdf
from coa_profiler.pdf.render import _scrub_branding_logo, _top_weighted_terpenes
from coa_profiler.result_data import build_result_json, display_name, field_rows
from coa_profiler.scorer import score
from coa_profiler.scorer.weights import weights_file_hash
from tests.conftest import make_chemistry

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


@pytest.fixture()
def sample():
    chem = parse_coa(FIXTURES / "fl_coa_sample.pdf")
    return chem, score(chem)


def test_one_page_under_cap(sample):
    chem, placement = sample
    data = render_profile_pdf(chem, placement, version="v0.1.0", weights_hash=weights_file_hash())
    assert data.startswith(b"%PDF-1.4")
    assert len(data) < 500 * 1024

    reader = pypdf.PdfReader(io.BytesIO(data))
    assert len(reader.pages) == 1
    assert tuple(float(value) for value in reader.pages[0].mediabox) == (0.0, 0.0, 612.0, 792.0)
    assert reader.metadata["/CreationDate"] == "D:20260101000000Z"
    assert reader.metadata["/ModDate"] == "D:20260101000000Z"


def test_byte_identical(sample):
    chem, placement = sample
    a = render_profile_pdf(chem, placement, version="v0.1.0", weights_hash=weights_file_hash())
    b = render_profile_pdf(chem, placement, version="v0.1.0", weights_hash=weights_file_hash())
    assert a == b  # FR-022 determinism


def test_content_includes_required_blocks(sample):
    chem, placement = sample
    data = render_profile_pdf(chem, placement, version="v0.1.0", weights_hash=weights_file_hash())
    text = pypdf.PdfReader(io.BytesIO(data)).pages[0].extract_text()
    assert "Placement" in text
    assert "chemistry-derived" in text
    assert "Myrcene" in text
    assert "v0.1.0" in text
    assert weights_file_hash()[:16] in text
    assert "Data completeness" in text
    assert "uncertainty band" in text.lower() or "Uncertainty band" in text
    assert "Beta-Caryophyllene" in text
    assert "\x00" not in text
    assert "Chemistry inputs read for this model" in text
    assert "THC-total" in text


def test_refusal_profile_renders():
    chem = parse_coa(FIXTURES / "no_chemistry.pdf")
    placement = score(chem)
    assert placement.completeness == "refusal"
    data = render_profile_pdf(chem, placement, version="v0.1.0", weights_hash=weights_file_hash())
    assert data.startswith(b"%PDF") and len(data) < 500 * 1024
    reader = pypdf.PdfReader(io.BytesIO(data))
    text = reader.pages[0].extract_text()
    assert "Dominant terpenes:" not in text
    result_data = json.loads(reader.attachments["coa-profile-data.json"][0])
    assert result_data["score"] is None
    assert result_data["label"] is None
    assert result_data["band_low"] is None
    assert result_data["band_high"] is None
    assert result_data["scoring_steps"] == {
        "raw_score": None,
        "contraction_factor": None,
        "contracted_score": None,
        "rounded_score": None,
    }


def test_no_cannabinoid_refusal_does_not_label_dominant_terpenes():
    chemistry = make_chemistry(
        {},
        {
            "myrcene": (0.8, "%"),
            "limonene": (0.4, "%"),
            "linalool": (0.2, "%"),
        },
        total_reported_terpenes=3,
    )
    placement = score(chemistry)
    assert placement.completeness == "refusal"
    assert "No Total THC or Total CBD" in placement.refusal_reason

    data = render_profile_pdf(
        chemistry,
        placement,
        version="v0.1.0",
        weights_hash=weights_file_hash(),
    )
    text = pypdf.PdfReader(io.BytesIO(data)).pages[0].extract_text()

    assert "Myrcene:" in text  # chemistry remains visible
    assert "Dominant terpenes:" not in text


def test_batch_branding_params(sample):
    chem, placement = sample
    branded = render_profile_pdf(
        chem, placement, version="v0.1.0", weights_hash=weights_file_hash(), customer_name="Test Practice"
    )
    plain = render_profile_pdf(chem, placement, version="v0.1.0", weights_hash=weights_file_hash())
    assert branded != plain
    text = pypdf.PdfReader(io.BytesIO(branded)).pages[0].extract_text()
    assert "Test Practice" in text


def test_result_and_full_source_json_are_embedded_exactly(sample):
    chem, placement = sample
    version = "v0.1.0"
    weights_hash = weights_file_hash()
    result_json = build_result_json(placement, field_rows(chem, placement), version, weights_hash)

    data = render_profile_pdf(
        chem,
        placement,
        version=version,
        weights_hash=weights_hash,
        result_json=result_json,
    )
    reader = pypdf.PdfReader(io.BytesIO(data))

    assert reader.attachments["coa-profile-data.json"] == [result_json.encode("utf-8")]
    sources = json.loads(reader.attachments["coa-profile-sources.json"][0])
    by_key = {entry["key"]: entry for entry in sources["sources"]}
    for name, field in {**chem.cannabinoids, **chem.terpenes}.items():
        assert by_key[name]["source_span"] == field.source_span


def test_dominant_terpenes_are_ranked_by_weighted_contribution():
    chemistry = make_chemistry(
        {"thc_total": (18.0, "%"), "cbd_total": (0.5, "%")},
        {
            # The largest raw value is monitored and must never appear as a
            # directional contributor. Linalool outranks alpha-pinene despite
            # its lower raw percentage because its normalized weight is larger.
            "beta_caryophyllene": (5.0, "%"),
            "limonene": (0.8, "%"),
            "alpha_pinene": (0.6, "%"),
            "linalool": (0.4, "%"),
            "myrcene": (0.3, "%"),
        },
        total_reported_terpenes=5,
    )
    placement = score(chemistry)
    assert placement.completeness == "full"

    data = render_profile_pdf(
        chemistry,
        placement,
        version="v0.1.0",
        weights_hash=weights_file_hash(),
    )
    text = pypdf.PdfReader(io.BytesIO(data)).pages[0].extract_text()

    assert "Dominant terpenes: Limonene 0.8%, Linalool 0.4%, Alpha-Pinene 0.6%" in text
    dominant_line = next(line for line in text.splitlines() if line.startswith("Dominant terpenes:"))
    assert "Caryophyllene" not in dominant_line


def test_dominant_terpenes_use_uncapped_reference_ratio():
    chemistry = make_chemistry(
        {"thc_total": (18.0, "%")},
        {
            # Without the spec-required uncapped ratio, Myrcene (2.5 capped)
            # would outrank Limonene (2.0 capped). At 2x its reference maximum,
            # Limonene's actual weighted contribution is 4.0.
            "limonene": (4.0, "%"),
            "myrcene": (2.0, "%"),
            "beta_caryophyllene": (0.5, "%"),
        },
        total_reported_terpenes=3,
    )

    assert [name for name, _value in _top_weighted_terpenes(chemistry)[:2]] == [
        "limonene",
        "myrcene",
    ]


def test_dense_registry_keeps_all_24_rows_above_disclaimer():
    cannabinoids = {name: (0.11 + index / 100, "%") for index, name in enumerate(CANNABINOID_PATTERNS)}
    terpenes = {name: (0.21 + index / 100, "%") for index, name in enumerate(TERPENE_PATTERNS)}
    chemistry = make_chemistry(
        cannabinoids,
        terpenes,
        total_reported_terpenes=len(terpenes),
    )
    # Prove the attachment does not truncate a citation that is too long for
    # the visible page by design.
    chemistry.terpenes["myrcene"].source_span = "FULL-SOURCE " + "evidence " * 80
    placement = score(chemistry)

    data = render_profile_pdf(
        chemistry,
        placement,
        version="v0.1.0",
        weights_hash=weights_file_hash(),
    )
    page = pypdf.PdfReader(io.BytesIO(data)).pages[0]
    text = page.extract_text()

    assert "Chemistry inputs read for this model (24 rows)" in text
    expected_names = [
        display_name(name).replace("α", "Alpha").replace("β", "Beta")
        for name in [*CANNABINOID_PATTERNS, *TERPENE_PATTERNS]
    ]
    assert all(f"{name}:" in text for name in expected_names)

    row_positions: list[float] = []

    def collect_rows(rendered, _cm, text_matrix, _font, _size):
        if any(f"{name}:" in rendered for name in expected_names):
            row_positions.append(float(text_matrix[5]))

    page.extract_text(visitor_text=collect_rows)
    assert len(row_positions) == 24
    assert min(row_positions) > 1.62 * 72  # disclaimer begins at this fixed baseline

    sources = json.loads(pypdf.PdfReader(io.BytesIO(data)).attachments["coa-profile-sources.json"][0])
    myrcene = next(entry for entry in sources["sources"] if entry["key"] == "myrcene")
    assert myrcene["source_span"] == chemistry.terpenes["myrcene"].source_span


def test_branding_logo_is_reencoded_without_metadata(tmp_path):
    from PIL import Image

    logo_path = tmp_path / "logo.jpg"
    image = Image.new("RGB", (32, 16), "orange")
    exif = Image.Exif()
    exif[0x010E] = "PRIVATE LOGO METADATA"
    image.save(
        logo_path,
        format="JPEG",
        exif=exif,
        icc_profile=b"PRIVATE-ICC-PROFILE",
    )

    scrubbed = _scrub_branding_logo(str(logo_path))

    with Image.open(io.BytesIO(scrubbed)) as clean:
        assert "exif" not in clean.info
        assert "icc_profile" not in clean.info
    assert b"PRIVATE LOGO METADATA" not in scrubbed
    assert b"PRIVATE-ICC-PROFILE" not in scrubbed
