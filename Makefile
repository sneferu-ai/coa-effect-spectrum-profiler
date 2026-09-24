.PHONY: install dev prod test test-unit test-integration test-acceptance lint build copylint gates fixtures

install:
	pip install --constraint constraints-runtime.txt -e ".[dev]"

dev:
	uvicorn coa_profiler.app:app --reload --no-access-log --port 8080

prod:
	OMP_THREAD_LIMIT=1 gunicorn coa_profiler.app:app -w 1 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8080 --timeout 120

test:
	pytest

test-unit:
	pytest tests/unit -q

test-integration:
	pytest tests/integration -q

test-acceptance:
	pytest tests/acceptance -q

lint:
	ruff check src/ tests/ scripts/

build:
	python -m build

copylint:
	python -m coa_profiler.copylint --templates src/coa_profiler/web/templates/ --fixtures fixtures/

gates:
	./scripts/run_walkaway_gates.sh

fixtures:
	PYTHONPATH=src python3 scripts/make_fixtures.py
