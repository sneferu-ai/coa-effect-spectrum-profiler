"""Unit regressions for PDF text extraction fallbacks."""

from coa_profiler.parser import text_extract


def test_pdfplumber_failure_retries_with_fitz(monkeypatch):
    def fail_pdfplumber(_path):
        raise ValueError("synthetic pdfplumber parser failure")

    monkeypatch.setattr(text_extract, "_extract_pdfplumber", fail_pdfplumber)
    monkeypatch.setattr(
        text_extract,
        "_extract_fitz",
        lambda _path: ["Potency\nTHCA 26.9", "Terpenes\nMyrcene 0.50"],
    )

    assert text_extract.extract_text_pages("certificate.pdf") == [
        "Potency\nTHCA 26.9",
        "Terpenes\nMyrcene 0.50",
    ]
