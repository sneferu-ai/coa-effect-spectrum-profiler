"""HTTP routes (S1–S7, FR-001..FR-031).

RESTful server-rendered routing and cookie-based sessions. A bounded thread
pool supervises one killable spawned process per upload (FR-030) so native
parser work cannot block the event loop or survive its absolute deadline.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from coa_profiler.errors import (
    COAError,
    DocumentResourceLimitError,
    FileTooLargeError,
    HeicUnsupportedError,
    InvalidFileTypeError,
    ProcessingTimeoutError,
    RateLimitedError,
    ServerBusyError,
)
from coa_profiler.lexicon import (
    BAND_NOTE,
    CONFIDENCE_NOTE,
    DEGRADED_NOTICE,
    MONITORED_NOTE,
    STANDING_DISCLAIMER,
)
from coa_profiler.parser import parse_coa, sniff_file_type
from coa_profiler.parser.fields import COAChemistry
from coa_profiler.parser.ocr import heic_decoder_available, tesseract_available
from coa_profiler.pdf import render_profile_pdf
from coa_profiler.result_data import (
    build_result_json,
)
from coa_profiler.result_data import (
    field_rows as _field_rows,
)
from coa_profiler.scorer import score as score_chemistry
from coa_profiler.scorer.placement import PlacementResult, placement_label, readable_terpenes
from coa_profiler.scorer.weights import (
    UNSCORED_TERRENES,
    weights_file_hash,
)
from coa_profiler.web.process_isolation import (
    DEFAULT_UPLOAD_PROCESS_CLEANUP_BUDGET_S,
    UploadProcessManager,
)
from coa_profiler.web.rate_limit import RateLimiter, client_ip
from coa_profiler.web.session import SESSION_COOKIE, SessionRecord, SessionStore

if TYPE_CHECKING:
    from coa_profiler.config import Config

log = logging.getLogger("coa_profiler.web")

router = APIRouter()

#: Processing wall-clock bound inside the upload route (below the 120 s
#: production proxy/server timeout).
PROCESSING_TIMEOUT_S = 110.0
# The spawned child owns the complete strip -> parse -> score pipeline. Its
# deadline plus TERM/KILL cleanup must finish before the route's final guard.
ISOLATED_PIPELINE_TIMEOUT_S = 100.0
if (
    ISOLATED_PIPELINE_TIMEOUT_S + DEFAULT_UPLOAD_PROCESS_CLEANUP_BUDGET_S >= PROCESSING_TIMEOUT_S
):  # pragma: no cover - constants are a deployment invariant
    raise RuntimeError("isolated upload deadline must leave time for forced process cleanup")

_TEMPLATES_DIR = Path(__file__).parent / "templates"

_FILE_TYPE_LABELS = {"pdf": "PDF", "jpeg": "JPEG", "png": "PNG", "heic": "HEIC"}

CONTACT_SUBJECT = "Batch COA Profile Inquiry"


# --- feedback (FR-024) --------------------------------------------------------


class FeedbackIn(BaseModel):
    helpful: bool
    placement: int = Field(ge=0, le=100)
    completeness: str = Field(pattern="^(full|degraded|refusal)$")
    lab_format: Literal["confident_cannabis", "sc_labs", "generic_ommu", "unknown"]


@dataclass
class FeedbackBucket:
    """Spec section 5 data model — non-identifying derived data only."""

    completeness: str
    lab_format: str
    helpful_yes: int = 0
    helpful_no: int = 0


class FeedbackAggregate:
    """Ephemeral in-memory aggregate. No IP, no session token, no chemistry."""

    def __init__(self) -> None:
        self.buckets: dict[tuple[str, str], FeedbackBucket] = {}
        self.global_yes = 0
        self.global_no = 0
        self.total_responses = 0

    def record(self, body: FeedbackIn) -> None:
        key = (body.completeness, body.lab_format)
        bucket = self.buckets.setdefault(key, FeedbackBucket(body.completeness, body.lab_format))
        if body.helpful:
            bucket.helpful_yes += 1
            self.global_yes += 1
        else:
            bucket.helpful_no += 1
            self.global_no += 1
        self.total_responses += 1

    def summary(self) -> dict:
        return {
            "global": {"yes": self.global_yes, "no": self.global_no},
            "buckets": [
                {
                    "completeness": b.completeness,
                    "lab_format": b.lab_format,
                    "yes": b.helpful_yes,
                    "no": b.helpful_no,
                }
                for b in sorted(self.buckets.values(), key=lambda b: (b.completeness, b.lab_format))
            ],
        }


# --- upload processing (runs inside the thread pool, FR-030) ------------------


def _write_private_bytes(path: Path, data: bytes) -> None:
    """Create a new owner-only file without a world-readable mode window."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def _strip_and_store(
    data: bytes,
    ftype: str,
    session_dir: Path,
    config: Config | None = None,
) -> Path:
    """FR-002: strip EXIF/document metadata, re-encode to a canonical working
    copy inside the session temp directory. Original bytes never leave it."""
    from PIL import Image

    from coa_profiler.errors import MetadataScrubError
    from coa_profiler.parser.ocr import open_image_any
    from coa_profiler.parser.resource_limits import (
        ResourceLimits,
        validate_image_resources,
        validate_pdf_resources,
    )
    from coa_profiler.parser.text_extract import strip_pdf_metadata

    original = session_dir / f"original.{ftype if ftype != 'jpeg' else 'jpg'}"
    _write_private_bytes(original, data)
    limits = ResourceLimits.from_config(config)
    try:
        if ftype == "pdf":
            # Refuse pathological page geometry before rewriting the upload.
            validate_pdf_resources(original, limits, dpi=200)
            working = session_dir / "working.pdf"
            strip_pdf_metadata(original, working)
        else:
            # Re-encoding to PNG through a fresh image drops EXIF and all
            # metadata (PIL only writes metadata when explicitly passed).
            with open_image_any(str(original)) as img:
                validate_image_resources(img, limits)
                working = session_dir / "working.png"
                img.convert("RGB").save(working, format="PNG")
        working.chmod(0o600)
        # The unstripped upload is needed only long enough to create the
        # canonical working copy.  Keeping it for the whole session expands
        # the privacy exposure without helping parsing or downloads.
        original.unlink()
    except (DocumentResourceLimitError, HeicUnsupportedError):
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise DocumentResourceLimitError("Image decoder rejected excessive dimensions") from exc
    except Exception as exc:
        raise MetadataScrubError() from exc
    return working


def process_upload(
    data: bytes, ftype: str, session_dir: Path, config: Config
) -> tuple[COAChemistry, PlacementResult, str]:
    """The full synchronous pipeline for one upload (spawned child process)."""
    working = _strip_and_store(data, ftype, session_dir, config)
    chemistry = parse_coa(working, config=config)
    placement: PlacementResult = score_chemistry(chemistry)
    return chemistry, placement, str(working)


# --- template context ---------------------------------------------------------


def _result_context(record: SessionRecord, request: Request) -> dict:
    p = record.placement
    cfg = request.app.state.config
    version = cfg.version
    weights_hash = weights_file_hash()
    fields = _field_rows(record.chemistry, p)
    cary = record.chemistry.terpenes.get("beta_caryophyllene")
    cary_present = bool(cary and cary.status == "verified" and cary.value is not None)
    remaining = record.created_at + record.ttl_seconds - time.time()
    return {
        "request": request,
        "placement": p,
        "chemistry": record.chemistry,
        "completeness": p.completeness,
        "score": p.score,
        "label": placement_label(p.score) if p.score >= 0 else "",
        "band_low": p.band_low,
        "band_high": p.band_high,
        "marker_pct": p.score if p.score >= 0 else 50,
        "band_left_pct": p.band_low,
        "band_width_pct": max(0, p.band_high - p.band_low),
        "dc_pct": round(p.confidence_data * 100),
        "mc_pct": round(p.confidence_model * 100),
        "cc_pct": round(p.confidence_combined * 100),
        "rationale": p.rationale,
        "fields": fields,
        "disclaimer": STANDING_DISCLAIMER,
        "confidence_note": CONFIDENCE_NOTE,
        "band_note": BAND_NOTE,
        "degraded_notice": DEGRADED_NOTICE,
        "terpene_count": readable_terpenes(record.chemistry),
        "version": version,
        "weights_hash": weights_hash,
        "ttl_minutes": cfg.session_ttl_seconds // 60 or 1,
        "ttl_expiring_soon": remaining < 60,
        "lab_format": record.chemistry.lab_format,
        "caryophyllene_present": cary_present,
        "caryophyllene_value": f"{cary.value:g}%" if cary_present else "",
        "monitored_note": MONITORED_NOTE,
        "refusal_reason": p.refusal_reason or "No readable chemistry values were found.",
        "result_json": build_result_json(p, fields, version, weights_hash),
    }


def _templates(request: Request):
    return request.app.state.templates


def _error_page(
    request: Request, err: COAError, status: int | None = None, retry_after: int | None = None
) -> HTMLResponse:
    headers = {"Retry-After": str(retry_after)} if retry_after else {}
    return _templates(request).TemplateResponse(
        request,
        "error.html",
        {
            "title": err.user_title,
            "message": err.user_message,
            "recovery": err.recovery,
            "error_code": err.error_code,
            "retry_after": retry_after,
        },
        status_code=status or err.http_status,
        headers=headers,
    )


def _get_session_or_410(request: Request) -> SessionRecord | Response:
    store: SessionStore = request.app.state.sessions
    record = store.get(request.cookies.get(SESSION_COOKIE))
    if record is None:
        return _templates(request).TemplateResponse(
            request,
            "error.html",
            {
                "title": "Session expired",
                "error_code": "SESSION_EXPIRED",
                "message": "Your session has ended. Upload your COA again to get a new result.",
                "recovery": "Upload again",
                "retry_after": None,
            },
            status_code=410,
        )
    return record


#: SPEC D4 — Tier 1 errors re-render upload.html with an inline alert banner
#: so the user corrects the mistake without losing the page; everything else
#: (rate limit, server busy, scrub failure) is a dedicated error page.
_TIER1_INLINE_CODES = {
    "INVALID_FILE_TYPE",
    "FILE_TOO_LARGE",
    "DOCUMENT_RESOURCE_LIMIT",
    "HEIC_UNSUPPORTED",
    "NOT_A_COA",
    "UNREADABLE_DOCUMENT",
    "NO_USABLE_CHEMISTRY",
    "PROCESSING_TIMEOUT",
}


def _landing_context(request: Request, error: COAError | None = None) -> dict:
    cfg = request.app.state.config
    heic_ready = bool(cfg.heic_enabled and heic_decoder_available())
    return {
        "max_upload_mb": cfg.max_upload_mb,
        "max_upload_bytes": cfg.max_upload_bytes,
        "accept_extensions": ".pdf,.jpg,.jpeg,.png,.heic" if heic_ready else ".pdf,.jpg,.jpeg,.png",
        "heic_ready": heic_ready,
        "ttl_minutes": cfg.session_ttl_seconds // 60 or 1,
        "contact_email": cfg.contact_email,
        "contact_subject": CONTACT_SUBJECT,
        "inference_assist_enabled": cfg.inference_assist_enabled,
        "error": (
            {
                "title": error.user_title,
                "message": error.user_message,
                "recovery": error.recovery,
                "error_code": error.error_code,
            }
            if error
            else None
        ),
    }


# --- routes -------------------------------------------------------------------


def _upload_reject(request: Request, err: COAError) -> Response:
    """D4: recoverable input errors render inline on the upload page (422)."""
    if err.error_code in _TIER1_INLINE_CODES:
        return _templates(request).TemplateResponse(
            request,
            "upload.html",
            _landing_context(request, error=err),
            status_code=422,
        )
    return _error_page(request, err)


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return _templates(request).TemplateResponse(
        request,
        "upload.html",
        _landing_context(request),
    )


@router.post("/upload")
async def upload(request: Request, file: UploadFile) -> Response:
    cfg = request.app.state.config
    limiter: RateLimiter = request.app.state.rate_limiter
    ip = client_ip(request, cfg)
    allowed, retry_after = limiter.check("upload", ip, cfg.rate_limit_per_minute)
    if not allowed:
        log.info("rate_limit hit bucket=upload")
        return _error_page(request, RateLimitedError(), status=429, retry_after=retry_after)

    data = await file.read(cfg.max_upload_bytes + 1)
    if len(data) > cfg.max_upload_bytes:
        return _upload_reject(request, FileTooLargeError())
    ftype = sniff_file_type(data)
    if ftype is None:
        return _upload_reject(request, InvalidFileTypeError())
    if ftype == "heic" and (not cfg.heic_enabled or not heic_decoder_available()):
        return _upload_reject(request, HeicUnsupportedError())

    # FR-030: the bounded thread pool supervises spawned parser children;
    # saturation is still an immediate 503 with Retry-After.
    if request.app.state.pool_in_flight >= cfg.processing_thread_pool_size:
        log.info("thread pool saturated (%d in flight)", request.app.state.pool_in_flight)
        return _error_page(request, ServerBusyError(), status=503, retry_after=30)

    store: SessionStore = request.app.state.sessions
    token = secrets.token_hex(16)  # 128-bit; minted up-front so the session dir is unique
    session_started_at = time.time()
    session_dir = store.new_session_dir(token)
    request.app.state.pool_in_flight += 1
    release_slot_in_route = True
    try:
        manager: UploadProcessManager = request.app.state.upload_processes
        process_job = manager.submit(
            process_upload,
            data,
            ftype,
            session_dir,
            cfg,
            timeout_seconds=ISOLATED_PIPELINE_TIMEOUT_S,
        )
        worker_future = asyncio.wrap_future(process_job.future)
        chemistry, placement, working_path = await asyncio.wait_for(
            # The child has its own earlier absolute deadline. This outer
            # guard protects against supervisor defects while leaving enough
            # time to TERM/KILL the process group before the server timeout.
            asyncio.shield(worker_future),
            timeout=PROCESSING_TIMEOUT_S,
        )
    except TimeoutError:
        process_job.cancel()
        release_slot_in_route = False
        _defer_worker_cleanup(request.app, worker_future, session_dir)
        return _upload_reject(request, ProcessingTimeoutError())
    except asyncio.CancelledError:
        process_job.cancel()
        release_slot_in_route = False
        _defer_worker_cleanup(request.app, worker_future, session_dir)
        raise
    except COAError as err:
        _discard_dir(session_dir)
        return _upload_reject(request, err)
    except Exception:
        _discard_dir(session_dir)
        log.exception("upload processing failed")
        return _error_page(request, COAError())
    finally:
        if release_slot_in_route:
            request.app.state.pool_in_flight -= 1

    # Success: replace any previous session owned by this client (FR-012
    # teardown on a new upload), mint the session, set the cookie.
    store.teardown(request.cookies.get(SESSION_COOKIE))
    record = store.create(
        chemistry,
        placement,
        working_path,
        token=token,
        created_at=session_started_at,
    )
    remaining_ttl = max(0, math.ceil(record.created_at + record.ttl_seconds - time.time()))
    resp = RedirectResponse("/result", status_code=303)
    resp.set_cookie(
        SESSION_COOKIE,
        record.session_token,
        max_age=remaining_ttl,
        httponly=True,
        samesite="strict",
        secure=cfg.session_cookie_secure,
    )
    return resp


def _discard_dir(session_dir: Path) -> bool:
    """Remove an unregistered upload directory without hiding retention failures."""
    import shutil

    if not session_dir.exists():
        return True
    try:
        shutil.rmtree(session_dir)
    except OSError:
        log.exception("failed to discard upload directory %s; startup sweep will retry", session_dir)
        return False
    if session_dir.exists():
        log.error("upload directory still exists after removal: %s; startup sweep will retry", session_dir)
        return False
    return True


def _defer_worker_cleanup(app, worker_future: asyncio.Future, session_dir: Path) -> None:
    """Keep capacity admitted until the supervisor confirms its child is dead."""

    def settle(future: asyncio.Future) -> None:
        # Consume any exception so asyncio does not report an abandoned
        # future while deliberately discarding the late result.
        if not future.cancelled():
            late_error = future.exception()
            if late_error is not None:
                log.info("abandoned upload worker settled with %s", type(late_error).__name__)
        _discard_dir(session_dir)
        app.state.pool_in_flight = max(0, app.state.pool_in_flight - 1)

    worker_future.add_done_callback(settle)


@router.get("/result", response_class=HTMLResponse)
async def result(request: Request) -> Response:
    record = _get_session_or_410(request)
    if isinstance(record, Response):
        return record
    ctx = _result_context(record, request)
    template = {"full": "result.html", "degraded": "degraded.html", "refusal": "refusal.html"}[
        record.placement.completeness
    ]
    return _templates(request).TemplateResponse(request, template, ctx)


@router.get("/result/profile.pdf")
async def profile_pdf(request: Request) -> Response:
    record = _get_session_or_410(request)
    if isinstance(record, Response):
        # SPEC §1.3: never serve an HTML error page at a .pdf URL — redirect
        # to /result, which renders the 410 session-expired page.
        if record.status_code == 410:
            return RedirectResponse("/result", status_code=303)
        return record
    cfg = request.app.state.config
    fields = _field_rows(record.chemistry, record.placement)
    pdf_bytes = render_profile_pdf(
        record.chemistry,
        record.placement,
        version=cfg.version,
        weights_hash=weights_file_hash(),
        result_json=build_result_json(record.placement, fields, cfg.version, weights_file_hash()),
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="coa_profile.pdf"'},
    )


@router.get("/new")
async def analyze_another(request: Request) -> Response:
    """ "Analyze another COA": tear down the session, then go home (FR-012)."""
    request.app.state.sessions.teardown(request.cookies.get(SESSION_COOKIE))
    resp = RedirectResponse("/", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@router.post("/feedback")
async def feedback(request: Request, body: FeedbackIn) -> Response:
    record = request.app.state.sessions.get(request.cookies.get(SESSION_COOKIE))
    if record is None:
        return JSONResponse({"error": "live session required"}, status_code=403)

    # Feedback dimensions describe the server-owned result, not arbitrary
    # client labels.  Reject stale/tampered page data before it can contaminate
    # the bounded aggregate.
    if (
        body.placement != record.placement.score
        or body.completeness != record.placement.completeness
        or body.lab_format != record.chemistry.lab_format
    ):
        return JSONResponse({"error": "feedback result mismatch"}, status_code=422)
    cfg = request.app.state.config
    ip = client_ip(request, cfg)
    allowed, retry_after = request.app.state.rate_limiter.check(
        "feedback", ip, cfg.feedback_rate_limit_per_minute
    )
    if not allowed:
        return JSONResponse(
            {"error": "rate_limited"}, status_code=429, headers={"Retry-After": str(retry_after)}
        )
    aggregate: FeedbackAggregate = request.app.state.feedback
    aggregate.record(body)
    if aggregate.total_responses % 100 == 0:
        log.info("feedback_summary: %s", aggregate.summary())
    return Response(status_code=204)


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request) -> HTMLResponse:
    cfg = request.app.state.config
    return _templates(request).TemplateResponse(
        request,
        "privacy.html",
        {
            "ttl_minutes": cfg.session_ttl_seconds // 60 or 1,
            "session_ttl_seconds": cfg.session_ttl_seconds,
            "cookie_secure": cfg.session_cookie_secure,
            "log_ip_retention": cfg.log_ip_retention,
            "contact_email": cfg.contact_email,
            "inference_assist_enabled": cfg.inference_assist_enabled,
        },
    )


@router.get("/algorithm", response_class=HTMLResponse)
async def algorithm(request: Request) -> HTMLResponse:
    from coa_profiler.scorer.weights import (
        CITATIONS,
        EXPECTED_CANNABINOIDS,
        MODEL_CONFIDENCE,
        active_weights,
        monitored_compounds,
    )

    def _row(name: str, spec: dict) -> dict:
        return {
            "key": name,
            "display": spec["display"],
            "kind": spec["kind"],
            "direction": spec["direction"],
            "weight": spec["weight"],
            "reference_max": spec["reference_max"],
            "citation": spec["citation"],
            "note": spec.get("note", ""),
        }

    return _templates(request).TemplateResponse(
        request,
        "algorithm.html",
        {
            "active_rows": [_row(n, s) for n, s in active_weights().items()],
            "monitored_rows": [_row(n, s) for n, s in monitored_compounds().items()],
            "omitted_terpenes": [
                {
                    "compound": n.replace("_", " ").title(),
                    "reason": "no published directional assignment in the cited literature",
                }
                for n in UNSCORED_TERRENES
            ],
            "citations": CITATIONS,
            "model_confidence": MODEL_CONFIDENCE,
            "expected_cannabinoids": list(EXPECTED_CANNABINOIDS),
            "disclaimer": STANDING_DISCLAIMER,
            "weights_hash": weights_file_hash(),
            "version": request.app.state.config.version,
        },
    )


@router.get("/healthz")
async def healthz(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "version": request.app.state.config.version})


@router.get("/readyz")
async def readyz(request: Request) -> Response:
    cfg = request.app.state.config
    heic_ready = heic_decoder_available() if cfg.heic_enabled else True
    checks = {
        "parser_ready": _parser_ready(),
        "ocr_ready": tesseract_available(),
        "heic_ready": heic_ready,
        "thread_pool_available": request.app.state.pool_in_flight < cfg.processing_thread_pool_size,
    }
    ready = all(checks.values())
    return JSONResponse(
        {"status": "ready" if ready else "not_ready", **checks}, status_code=200 if ready else 503
    )


def _parser_ready() -> bool:
    try:
        import fitz  # noqa: F401

        return True
    except ImportError:
        try:
            import pdfplumber  # type: ignore[import-not-found]  # noqa: F401

            return True
        except ImportError:
            return False
