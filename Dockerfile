# COA Effect-Spectrum Profiler — production image (spec section 8).
# Pinned Tesseract + fixed base image digest where feasible (DIS-12/A-10).
# Pin the digest at deploy time (spec section 8, "fixed base image digest
# where feasible"): resolve with `docker buildx imagetools inspect
# python:3.11-slim-bookworm` and append @sha256:<digest> below. A fabricated
# digest would fail the build, so the floating tag is the honest default.
FROM python:3.11-slim-bookworm

ARG COA_PROFILER_VERSION
ENV COA_PROFILER_VERSION=${COA_PROFILER_VERSION} \
    OMP_THREAD_LIMIT=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

LABEL org.opencontainers.image.version=${COA_PROFILER_VERSION}

# Cache-busting URLs and result provenance depend on this identifier. Never
# build a production image whose release ID can be silently reused.
RUN test -n "$COA_PROFILER_VERSION" || \
    (echo "COA_PROFILER_VERSION build arg is required" >&2; exit 1)

RUN apt-get update && apt-get install -y --no-install-recommends \
      tesseract-ocr=5.3.0-2 \
      poppler-utils \
      libheif-dev \
      libgl1 \
      libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md constraints-runtime.txt ./
COPY src/ ./src/
RUN pip install --constraint constraints-runtime.txt .

# Run the public service without root privileges.  Session working files live
# on the /tmp tmpfs declared by docker-compose, so the application tree stays
# read-only in production.
RUN useradd --create-home --uid 10001 coa && chown -R coa:coa /app
USER coa

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"

# Single gunicorn worker, Uvicorn worker class (DIS-11).  The container must
# listen on its network interface; docker-compose limits the published host
# socket to 127.0.0.1.
CMD ["gunicorn", "coa_profiler.app:app", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", \
     "-b", "0.0.0.0:8080", "--timeout", "120"]
