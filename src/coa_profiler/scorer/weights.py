"""Authoritative weight table (FR-007).

This module IS the weight specification. The table below is a literal
dictionary; ``docs/algorithm.md`` (FR-020) reproduces it exactly and the
``/algorithm`` page (FR-023) renders it dynamically from this module.

Weights are literature-derived hypotheses with clinical-informed directional
assignments — not outputs of a quantitative model or clinical trial. Reference
maxima are operator-informed estimates (typical Florida COA ranges), not
statistical maxima; they are tuning parameters subject to validation.

beta_caryophyllene is direction-neutral (weight 0.0) per DIS-14: its citation
(Gertsch et al. 2008) addresses anti-inflammatory CB2 agonism, not directional
effects on the tendency axis. It is extracted, displayed, and listed in the
rationale, but contributes nothing to either directional sum.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# --- Tuning parameters (documented in docs/algorithm.md) -------------------

#: Model-uncertainty contraction factor, full placement (FR-007 Step 4).
CONTRACTION_FULL = 0.85
#: Model-uncertainty contraction factor, degraded mode.
CONTRACTION_DEGRADED = 0.70
#: Model confidence component (FR-009) — an operator judgment about the
#: literature, decoupled from the contraction factor. May be raised to 0.85
#: only after a held-out evaluation shows concordance >= 90%.
MODEL_CONFIDENCE = 0.75
#: Below this combined confidence, placement is refused even in degraded mode.
CONFIDENCE_FLOOR_DEGRADED = 0.25

#: Cannabinoids expected on every COA (FR-009 data-completeness penalties).
EXPECTED_CANNABINOIDS = ("thc_total", "cbd_total")

#: Degraded mode scores from these two compounds alone (DIS-6 b).
DEGRADED_PARTICIPANTS = ("thc_total", "cbd_total")

WEIGHTS: dict[str, dict] = {
    # --- Active directional compounds -------------------------------------
    "myrcene": {
        "display": "Myrcene",
        "kind": "terpene",
        "direction": "indica",
        "weight": 2.5,
        "reference_max": 2.0,
        "citation": "Russo 2011",
        "monitored": False,
    },
    "linalool": {
        "display": "Linalool",
        "kind": "terpene",
        "direction": "indica",
        "weight": 1.8,
        "reference_max": 1.0,
        "citation": "Russo 2011",
        "monitored": False,
    },
    "humulene": {
        "display": "Humulene",
        "kind": "terpene",
        "direction": "indica",
        "weight": 0.8,
        "reference_max": 1.0,
        "citation": "McPartland & Russo 2001",
        "monitored": False,
    },
    "nerolidol": {
        "display": "Nerolidol",
        "kind": "terpene",
        "direction": "indica",
        "weight": 0.6,
        "reference_max": 0.5,
        "citation": "Russo 2011",
        "monitored": False,
    },
    "limonene": {
        "display": "Limonene",
        "kind": "terpene",
        "direction": "sativa",
        "weight": 2.0,
        "reference_max": 2.0,
        "citation": "Russo 2011",
        "monitored": False,
    },
    "alpha_pinene": {
        "display": "α-Pinene",
        "kind": "terpene",
        "direction": "sativa",
        "weight": 1.5,
        "reference_max": 1.5,
        "citation": "McPartland & Russo 2001",
        "monitored": False,
    },
    "beta_pinene": {
        "display": "β-Pinene",
        "kind": "terpene",
        "direction": "sativa",
        "weight": 1.0,
        "reference_max": 1.0,
        "citation": "McPartland & Russo 2001",
        "monitored": False,
    },
    "terpinolene": {
        "display": "Terpinolene",
        "kind": "terpene",
        "direction": "sativa",
        "weight": 1.5,
        "reference_max": 0.8,
        "citation": "Russo 2011",
        "monitored": False,
    },
    "ocimene": {
        "display": "Ocimene",
        "kind": "terpene",
        "direction": "sativa",
        "weight": 1.0,
        "reference_max": 0.5,
        "citation": "McPartland & Russo 2001",
        "monitored": False,
    },
    "thc_total": {
        "display": "THC-total",
        "kind": "cannabinoid",
        "direction": "indica",
        "weight": 0.5,
        "reference_max": 30.0,
        "citation": "Russo & Marcu 2017",
        "monitored": False,
        "note": "weak directional prior",
    },
    "cbd_total": {
        "display": "CBD-total",
        "kind": "cannabinoid",
        "direction": "sativa",
        "weight": 0.5,
        "reference_max": 20.0,
        "citation": "Russo & Marcu 2017",
        "monitored": False,
        "note": "weak directional prior",
    },
    # --- Monitored but not scored (DIS-14) ---------------------------------
    "beta_caryophyllene": {
        "display": "β-Caryophyllene",
        "kind": "terpene",
        "direction": "neutral",
        "weight": 0.0,
        "reference_max": None,
        "citation": "Gertsch et al. 2008",
        "monitored": True,
        "note": "CB2 agonism; no directional evidence on the tendency axis",
    },
}

#: Terpenes extracted and displayed but not in the weight model at launch
#: (no published directional assignment in the cited literature).
UNSCORED_TERRENES = (
    "bisabolol",
    "eucalyptol",
    "camphene",
    "farnesene",
    "valencene",
    "geraniol",
    "fenchyl_alcohol",
    "alpha_terpineol",
)

CITATIONS: dict[str, dict[str, str]] = {
    "Russo 2011": {
        "title": "Taming THC: potential cannabis synergy and phytocannabinoid-terpenoid entourage effects",
        "venue": "British Journal of Pharmacology",
        "doi": "10.1111/j.1476-5381.2011.01238.x",
    },
    "McPartland & Russo 2001": {
        "title": "Cannabis and Cannabis Extracts: Greater Than the Sum of Their Parts?",
        "venue": "Journal of Cannabis Therapeutics",
        "doi": "10.1300/J175v01n03_08",
    },
    "Russo & Marcu 2017": {
        "title": "Cannabis Pharmacology: The Usual Suspects and a Few Promising Leads",
        "venue": "Advances in Pharmacology",
        "doi": "10.1016/bs.apha.2017.03.004",
    },
    "Gertsch et al. 2008": {
        "title": "Beta-caryophyllene is a dietary cannabinoid",
        "venue": "Proceedings of the National Academy of Sciences",
        "doi": "10.1073/pnas.0803601105",
    },
}


def active_weights() -> dict[str, dict]:
    """Compounds that participate in directional scoring (weight > 0)."""
    return {k: v for k, v in WEIGHTS.items() if not v.get("monitored")}


def monitored_compounds() -> dict[str, dict]:
    """Compounds extracted and displayed but contributing weight 0 (DIS-14)."""
    return {k: v for k, v in WEIGHTS.items() if v.get("monitored")}


def weights_file_hash() -> str:
    """SHA-256 of this file's content — provenance stamp on every PDF (FR-011)."""
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
