"""Sanitized regressions for text extracted from real Florida lab COAs.

The source PDFs are intentionally not committed.  These strings preserve the
table headings, row ordering, and numeric shapes produced by pdfplumber while
removing patient, batch, facility, and sample identifiers.
"""

import pytest

from coa_profiler.parser import extract_chemistry
from coa_profiler.scorer import score

ACS_EXTRACTED_TEXT = """\
Certificate of Analysis
Florida licensed testing laboratory
Potency - 11 Tested Potency Summary
Analyte Dilution LOD LOQ Result (%)
(1:n) (%) (%) (mg/g)
THCA-A 15.000 3.20E-5 0.0015 307 30.7
Delta-9 THC 15.000 1.30E-5 0.0015 8.17 0.817
CBDA 15.000 1.00E-5 0.0015 0.710 0.0710
CBD 15.000 5.40E-5 0.0015 <LOQ <LOQ
Total Active CBD 15.000 0.623 0.0623
Total Active THC 15.000 278 27.8
Terpenes Summary
Analyte Result (mg/g) (%)
(R)-(+)-Limonene 10.6 1.06%
beta-Myrcene 6.108 0.611%
trans-Caryophyllene 3.584 0.358%
Linalool 2.634 0.263%
alpha-Bisabolol 1.445 0.144%
Fenchyl Alcohol 1.341 0.134%
beta-Pinene 1.263 0.126%
alpha-Humulene 1.088 0.109%
alpha-Pinene 0.961 0.096%
Total Terpenes: 2.901%
"""


MODERN_CANNA_EXTRACTED_TEXT = """\
Certificate of Analysis
Florida licensed testing laboratory
POTENCY SUMMARY (As Received) TERPENES SUMMARY (Top Ten)
Total CBD Total THC Total Cannabinoids Total Terpenes
0.0543% (1.90 mg) 25.9% (906.5 mg) 30.4% (1064 mg) 2.21%
Analyte % mg Analyte %
THCa 26.9 941.5 beta-Caryophyllene 0.491
delta 9-THC 2.31 80.85 d-Limonene 0.453
CBGa 0.942 32.97 Linalool 0.328
CBG 0.121 4.235 alpha-Humulene 0.179
alpha-Pinene 0.0975
CBDa 0.0619 2.1665
trans-Nerolidol 0.0916
CBN 0.0210 0.735
alpha-Bisabolol 0.0798
THCV 0.0142 0.497
beta-Myrcene 0.0795
CBC <LOQ <LOQ
Fenchyl Alcohol 0.0717
CBD <LOQ <LOQ
alpha-Terpineol 0.0659
CBDV <LOQ <LOQ
delta 8-THC <LOQ <LOQ
ANALYSIS SUMMARY
Potency Completed Terpenes Completed
"""


def test_acs_extracted_text_reads_all_reported_summary_terpenes():
    chemistry = extract_chemistry([ACS_EXTRACTED_TEXT])

    assert chemistry.cannabinoids["thca"].value == pytest.approx(30.7)
    assert chemistry.cannabinoids["cbda"].value == pytest.approx(0.071)
    assert chemistry.cannabinoids["thc_total"].value == pytest.approx(27.8)
    assert chemistry.terpenes["fenchyl_alcohol"].value == pytest.approx(0.134)
    assert chemistry.total_reported_terpenes == 9
    assert len(chemistry.terpenes) == 9
    result = score(chemistry)
    assert result.completeness == "full"
    assert result.confidence_data == pytest.approx(1.0)


def test_modern_canna_text_uses_declared_percent_not_package_total_mg():
    chemistry = extract_chemistry([MODERN_CANNA_EXTRACTED_TEXT])

    # A 3.5 g package makes total mg 35x percent, not 10x.  The first column is
    # still unambiguously percent because the source header says "Analyte % mg".
    assert chemistry.cannabinoids["thca"].value == pytest.approx(26.9)
    assert chemistry.cannabinoids["delta9_thc"].value == pytest.approx(2.31)
    assert chemistry.cannabinoids["thc_total"].value == pytest.approx(25.9)
    assert chemistry.cannabinoids["cbd_total"].value == pytest.approx(0.0543)
    assert chemistry.cannabinoids["thc_total"].derived is False
    assert "Total CBD Total THC" in chemistry.cannabinoids["thc_total"].source_span
    assert chemistry.terpenes["fenchyl_alcohol"].value == pytest.approx(0.0717)
    assert chemistry.terpenes["alpha_terpineol"].value == pytest.approx(0.0659)
    assert chemistry.total_reported_terpenes == 10
    assert len(chemistry.terpenes) == 10
    result = score(chemistry)
    assert result.completeness == "full"
    assert result.confidence_data == pytest.approx(1.0)
