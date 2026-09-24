"""``python -m coa_profiler`` — development server entry point."""

from __future__ import annotations


def main() -> None:
    import uvicorn

    from coa_profiler.config import load_config

    cfg = load_config()
    uvicorn.run("coa_profiler.app:app", host="127.0.0.1", port=cfg.port, reload=False)


if __name__ == "__main__":
    main()
