"""COA Effect-Spectrum Profiler.

Deterministic chemistry-to-spectrum placement for Florida OMMU certificates
of analysis. Public API: ``coa_profiler.parser.parse_coa`` and
``coa_profiler.scorer.score``.
"""

from coa_profiler.config import detect_version

__version__ = detect_version()

__all__ = ["__version__", "detect_version"]
