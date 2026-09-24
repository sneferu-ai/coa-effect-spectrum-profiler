"""PDF text-layer extraction (FR-003).

Primary engine: pdfplumber (spec section 6). Portability fallback: PyMuPDF
(fitz) with the same contract — one string per page, page order preserved —
used when pdfplumber is not installed. Both are lazy-imported so the rest of
the package works without either.
"""

from __future__ import annotations

from pathlib import Path


def extract_text_pages(pdf_path: str | Path) -> list[str]:
    """Extract the embedded text layer from all pages, in page order."""
    try:
        return _extract_pdfplumber(pdf_path)
    except Exception:  # noqa: BLE001 - retry valid PDFs with an independent extraction engine
        # Valid PDFs occasionally exercise a parser-specific failure.  Retry
        # the whole document with the independent engine rather than turning a
        # pdfplumber exception into a generic upload failure.
        return _extract_fitz(pdf_path)


def _extract_pdfplumber(pdf_path: str | Path) -> list[str]:
    import pdfplumber  # type: ignore[import-not-found]

    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages


def _extract_fitz(pdf_path: str | Path) -> list[str]:
    import fitz  # type: ignore[import-not-found]

    pages: list[str] = []
    with fitz.open(str(pdf_path)) as doc:
        for page in doc:
            # Explicit text mode retains block/line breaks; sorting restores
            # reading order for pages whose content streams are out of order.
            pages.append(page.get_text("text", sort=True) or "")
    return pages


def strip_pdf_metadata(src: str | Path, dst: str | Path) -> None:
    """Rewrite a PDF without metadata or embedded files into ``dst`` (FR-002).

    PyMuPDF is a runtime dependency: it rewrites the trailer info dictionary,
    removes XMP metadata, and removes embedded attachments that may contain
    patient identifiers. Raises on failure so the caller can discard the
    session with a typed metadata-scrub error.
    """
    import fitz  # type: ignore[import-not-found]

    with fitz.open(str(src)) as doc:
        doc.set_metadata({})
        doc.del_xml_metadata()
        for attachment_name in tuple(doc.embfile_names()):
            doc.embfile_del(attachment_name)
        doc.save(str(dst), garbage=4, deflate=True, clean=True)
