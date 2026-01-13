SHELL := /bin/bash

PYTHON ?= python3.11
VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(PY) -m pip

.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  make venv     - create virtual env"
	@echo "  make install  - install deps (incl dev)"
	@echo "  make run      - run API (reload)"
	@echo "  make db-upgrade - apply alembic migrations"
	@echo "  make test     - run tests"
	@echo "  make fmt      - format (ruff)"
	@echo "  make lint     - lint (ruff)"
	@echo "  make type     - type-check (mypy)"
	@echo "  make clean    - remove caches"

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip

install: venv
	$(PIP) install -e ".[dev]"

run:
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

db-upgrade:
	$(VENV)/bin/python -m alembic upgrade head

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

# pyenv install 3.11.9
# pyenv local 3.11.9
# python -m venv .venv
# source .venv/bin/activate
# pip install -e ".[dev]"
