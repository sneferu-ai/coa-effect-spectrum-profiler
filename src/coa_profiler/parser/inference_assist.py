"""Optional inference-assist fallback (FR-026, DIS-2).

DISABLED by default (``INFERENCE_ASSIST_ENABLED=false``). The deterministic
parser is the sole active path at launch. When enabled, and only when the
deterministic parser returns ``format: unknown`` or fewer than 50% of expected
fields, the extracted text is sent to an OpenAI-compatible endpoint for
layout classification with a 10-second timeout; on timeout or error the
deterministic result is used.

This is the ONLY module in the package permitted to make an outbound network
call (walk-away gate 2 audits exactly this boundary).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from coa_profiler.config import Config

log = logging.getLogger("coa_profiler.inference_assist")

_TIMEOUT_SECONDS = 10.0
_ALLOWED_FORMATS = {"confident_cannabis", "sc_labs", "generic_ommu"}


def classify_layout(text: str, config: Config) -> str | None:
    """Ask the configured endpoint to classify the COA layout.

    Returns one of the known format names, or None on any failure (timeout,
    error, unrecognized answer) — the caller then keeps the deterministic
    result. Never raises.
    """
    if not config.inference_assist_enabled or not config.inference_assist_url:
        return None
    try:
        import httpx

        headers = {"Content-Type": "application/json"}
        if config.inference_assist_api_key:
            headers["Authorization"] = f"Bearer {config.inference_assist_api_key}"
        payload = {
            "model": "default",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Classify this cannabis certificate-of-analysis layout. Answer with exactly "
                        "one token: confident_cannabis, sc_labs, or generic_ommu."
                    ),
                },
                {"role": "user", "content": text[:8000]},
            ],
            "temperature": 0,
        }
        with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
            resp = client.post(
                config.inference_assist_url.rstrip("/") + "/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            answer = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip().lower()
        if answer in _ALLOWED_FORMATS:
            return answer
        log.warning("inference-assist returned unrecognized layout %r; keeping deterministic result", answer)
        return None
    except Exception as exc:  # noqa: BLE001 - optional network fallback never blocks deterministic parsing
        log.warning("inference-assist unavailable (%s); keeping deterministic result", type(exc).__name__)
        return None
