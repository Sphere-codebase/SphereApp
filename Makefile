SHELL := /bin/bash

PYTHON ?= python3.11
VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(PY) -m pip

.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  make venv        - create virtual env"
	@echo "  make install     - install deps (incl dev)"
	@echo "  make db-up       - start postgres via docker compose"
	@echo "  make db-down     - stop postgres"
	@echo "  make db-logs     - follow postgres logs"
	@echo "  make db-wait     - wait for postgres health"
	@echo "  make db-upgrade  - apply alembic migrations"
	@echo "  make start       - db-up + db-upgrade + run (reload)"
	@echo "  make run         - run API (reload)"
	@echo "  make run-prod    - run API (no reload)"
	@echo "  make test        - run tests"
	@echo "  make fmt         - format (ruff)"
	@echo "  make lint        - lint (ruff)"
	@echo "  make type        - type-check (mypy)"
	@echo "  make clean       - remove caches"

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip

install: venv
	$(PIP) install -e ".[dev]"

# --- DB helpers (docker compose) ---
db-up:
	docker compose up -d

db-down:
	docker compose down

db-logs:
	docker compose logs -f postgres

db-wait:
	@echo "Waiting for Postgres..."
	@until docker exec claims_assistant_postgres pg_isready -U postgres -d claims_assistant >/dev/null 2>&1; do \
		sleep 1; \
	done
	@echo "Postgres is ready."

docker-wait: db-wait

db-upgrade: db-wait
	$(VENV)/bin/python -m alembic upgrade head

# --- App run ---
run:
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-prod:
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# One-button local start
start: db-up docker-wait db-upgrade run

test:
	$(VENV)/bin/pytest -q

fmt:
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check . --fix

lint:
	$(VENV)/bin/ruff check .

type:
	$(VENV)/bin/mypy app

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ htmlcov .coverage
