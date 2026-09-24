"""Typed errors for the COA profiler (surface S3).

Each error carries a stable ``error_code`` used by the web layer for typed
error pages, by the batch CLI for ``FAIL: <file> <error_code>`` lines, and by
the evaluation CLI. No stack traces or internal state ever reach the user.
"""

from __future__ import annotations


class COAError(Exception):
    """Base class for all user-visible typed errors."""

    error_code = "INTERNAL_ERROR"
    http_status = 422
    user_title = "Something went wrong"
    user_message = "An internal error occurred. Please try again."
    recovery = "Try uploading the certificate again."

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.user_message)
        self.detail = detail


class InvalidFileTypeError(COAError):
    error_code = "INVALID_FILE_TYPE"
    user_title = "Unsupported file type"
    user_message = (
        "We accept a certificate of analysis as a PDF, JPEG, PNG, or HEIC file. "
        "The file you sent does not look like any of these."
    )
    recovery = "Upload the original PDF from the dispensary, or a clear photo saved as JPEG, PNG, or HEIC."


class FileTooLargeError(COAError):
    error_code = "FILE_TOO_LARGE"
    user_title = "File too large"
    user_message = "The file is larger than the upload limit."
    recovery = "Try a smaller photo or the original PDF. The limit is shown on the upload page."


class DocumentResourceLimitError(COAError):
    """The input is valid, but unsafe to expand within bounded resources."""

    error_code = "DOCUMENT_RESOURCE_LIMIT"
    user_title = "Document is too large to process safely"
    user_message = (
        "This document has too many pages or its page/image dimensions are too large for safe processing."
    )
    recovery = "Upload only the COA pages, or use a smaller original PDF or image."


class HeicUnsupportedError(COAError):
    error_code = "HEIC_UNSUPPORTED"
    user_title = "HEIC photos unavailable"
    user_message = "This server cannot read HEIC photos right now."
    recovery = "On your phone, re-save or screenshot the photo as a JPEG or PNG and upload that instead."


class NotACOAError(COAError):
    error_code = "NOT_A_COA"
    user_title = "This does not look like a certificate of analysis"
    user_message = (
        "We could not find a certificate-of-analysis structure in this document "
        "(no cannabinoid table or certificate header)."
    )
    recovery = "Upload the certificate of analysis that came with your product, not a receipt or menu."


class UnreadableDocumentError(COAError):
    error_code = "UNREADABLE_DOCUMENT"
    user_title = "We could not read this document"
    user_message = (
        "The photo or scan is not clear enough for us to read the chemistry values reliably. "
        "We never guess values we cannot read."
    )
    recovery = (
        "Retake the photo in good light, flat and straight-on, filling the frame with the document, "
        "or upload the original PDF instead."
    )


class NoUsableChemistryError(COAError):
    error_code = "NO_USABLE_CHEMISTRY"
    user_title = "No readable chemistry values"
    user_message = (
        "We found a certificate-like document, but none of the cannabinoid or terpene "
        "values could be read. We never estimate values we cannot read."
    )
    recovery = "Try a sharper photo or the original PDF from the dispensary."


class ProcessingTimeoutError(COAError):
    error_code = "PROCESSING_TIMEOUT"
    user_title = "Processing took too long"
    user_message = "Reading this document took longer than the time limit."
    recovery = "Try again. If it keeps happening, upload a smaller or clearer file."


class RateLimitedError(COAError):
    error_code = "RATE_LIMITED"
    http_status = 429
    user_title = "Too many uploads"
    user_message = "You have uploaded too many files in a short time."
    recovery = "Wait a minute and try again."


class ServerBusyError(COAError):
    error_code = "SERVER_BUSY"
    http_status = 503
    user_title = "Server busy"
    user_message = "The analysis queue is full right now."
    recovery = "Wait about 30 seconds and try again."


class MetadataScrubError(COAError):
    error_code = "METADATA_SCRUB_FAILED"
    http_status = 422
    user_title = "Could not prepare the file"
    user_message = "We could not make a private working copy of your file, so it was discarded."
    recovery = "Try re-saving the file or taking a fresh photo, then upload again."
