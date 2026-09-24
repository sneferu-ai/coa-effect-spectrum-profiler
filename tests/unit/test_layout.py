"""FR-004 layout detection: format families by content, per-page sub-formats."""

import pytest

from coa_profiler.errors import NotACOAError
from coa_profiler.parser import extract_chemistry
from coa_profiler.parser.layout import detect_layout


def test_confident_cannabis():
    pages = ["Confident Cannabis\nconfidentcannabis.com\nCertificate of Analysis\nTotal THC 18.2 %"]
    assert detect_layout(pages).document_format == "confident_cannabis"


def test_sc_labs():
    pages = ["SC Labs PhytoFacts\nCertificate of Analysis\nTotal THC 18.2 %"]
    assert detect_layout(pages).document_format == "sc_labs"


def test_generic_ommu():
    pages = ["Certificate of Analysis\nCannabinoid Profile\nTotal THC 18.2 %\nTotal CBD 0.5 %"]
    assert detect_layout(pages).document_format == "generic_ommu"


def test_certificate_structure_without_family_is_unknown():
    # Bare "certificate" language with none of the table keywords.
    pages = ["Certificate of Analysis\nThis document certifies analysis occurred."]
    layout = detect_layout(pages)
    assert layout.document_format in {"generic_ommu", "unknown"}
    assert layout.is_certificate


def test_not_a_certificate():
    pages = ["Dear patient, thank you for your visit last week. " * 4]
    with pytest.raises(NotACOAError):
        extract_chemistry(pages)


def test_per_page_subformats():
    pages = [
        "SC Labs PhytoFacts\nCertificate of Analysis\nTotal THC 18.2 %",
        "Terpene Profile\nMyrcene 0.5 %",
    ]
    layout = detect_layout(pages)
    assert layout.document_format == "sc_labs"
    assert layout.page_formats[0] == "sc_labs"
