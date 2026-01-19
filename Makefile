SHELL := /bin/bash

# Load .env if exists (expects KEY=VALUE lines)
-include .env
export

PYTHON ?= python3.11
VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(PY) -m pip

# --- CI-ish defaults (override if needed) ---
ENV ?= test
JWT_SECRET ?= ci-secret
READY_CHECK_LLM ?= false

IMAGE_NAME ?= sphereapp
IMAGE_TAG ?= $(shell echo "$(IMAGE_NAME)" | tr '[:upper:]' '[:lower:]')

HEALTH_URL ?= http://localhost:8000/health
READY_URL ?= http://localhost:8000/ready

API_URL ?= http://localhost:8000
ADMIN_API_KEY ?=
EMAIL ?= user@example.com
PASSWORD ?= secret
FULL_NAME ?=
ROLE ?= user

.DEFAULT_GOAL := help

# -----------------------
# Helpers
# -----------------------
require-db-url:
	@test -n "$(DATABASE_URL)" || (echo "ERROR: DATABASE_URL is not set. Put it into .env"; exit 1)

help:
	@echo "Targets:"
	@echo "  make venv         - create virtual env"
	@echo "  make install      - install deps (incl dev)"
	@echo "  make migrate      - apply alembic migrations using DATABASE_URL from .env"
	@echo "  make run          - run API (reload)"
	@echo "  make run-prod     - run API (no reload)"
	@echo "  make start        - migrate + run (reload)"
	@echo "  make test         - run tests"
	@echo "  make fmt          - format (ruff)"
	@echo "  make lint-fix     - autofix lint (ruff check --fix)"
	@echo "  make fmt-check    - CI format check (ruff format --check)"
	@echo "  make lint         - lint (ruff)"
	@echo "  make type         - type-check (mypy)"
	@echo "  make ci           - fmt-check + lint + migrate + test"
	@echo "  make clean        - remove caches"
	@echo "  make create-user  - create standard user (requires ADMIN_API_KEY)"
	@echo "  make create-admin - create admin user (requires ADMIN_API_KEY)"
	@echo ""
	@echo "Docker (CI-like smoke):"
	@echo "  make docker-build - build docker image ($(IMAGE_TAG):ci)"
	@echo "  make docker-run   - run container for smoke test (uses DATABASE_URL)"
	@echo "  make docker-smoke - wait for /health and call /ready"
	@echo "  make docker-stop  - stop smoke container"
	@echo "  make docker-ci    - docker-build + docker-run + docker-smoke + docker-stop"
	@echo ""
	@echo "Frontend:"
	@echo "  make frontend-install   - install frontend deps"
	@echo "  make frontend-dev       - run frontend dev server"
	@echo "  make frontend-lint      - lint frontend"
	@echo "  make frontend-typecheck - type-check frontend"
	@echo "  make frontend-test      - test frontend"
	@echo "  make frontend-build     - build frontend"
	@echo ""
	@echo "Audit:"
	@echo "  make audit-install  - install audit deps"
	@echo "  make audit-run      - run audit suite (ruff/vulture/dup/coverage/summary)"

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip

install: venv
	$(PIP) install -e ".[dev]"

# -----------------------
# DB migrations (Supabase / any DATABASE_URL)
# -----------------------
migrate: require-db-url
	@echo "Running migrations against DATABASE_URL from .env"
	DATABASE_URL="$(DATABASE_URL)" $(PY) -m alembic -c alembic.ini upgrade head

# -----------------------
# App run
# -----------------------
run:
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-prod:
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

start: migrate run

test:
	$(VENV)/bin/pytest -q

# Developer format + autofix
fmt:
	$(VENV)/bin/ruff format .

lint-fix:
	$(VENV)/bin/ruff check . --fix

# CI format check only
fmt-check:
	$(VENV)/bin/ruff format . --check

lint:
	$(VENV)/bin/ruff check . --output-format=github

type:
	$(VENV)/bin/mypy app

# CI-like pipeline
ci: fmt-check lint migrate test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ htmlcov .coverage

# -----------------------
# Docker CI-like smoke
# -----------------------
docker-build:
	@echo "Building image: $(IMAGE_TAG):ci"
	docker build -t "$(IMAGE_TAG):ci" .

docker-run: require-db-url
	@echo "Starting container sphereapp_ci on :8000 (DATABASE_URL from .env)"
	docker run -d --rm \
	  -p 8000:8000 \
	  --name sphereapp_ci \
	  --add-host=host.docker.internal:host-gateway \
	  -e DATABASE_URL="$(DATABASE_URL)" \
	  -e ENV="$(ENV)" \
	  -e JWT_SECRET="$(JWT_SECRET)" \
	  -e READY_CHECK_LLM="$(READY_CHECK_LLM)" \
	  "$(IMAGE_TAG):ci"

docker-smoke:
	@echo "Waiting for /health: $(HEALTH_URL)"
	@for i in $$(seq 1 30); do \
	  if curl -fsS "$(HEALTH_URL)" > /dev/null; then \
	    echo "health ok"; \
	    break; \
	  fi; \
	  echo "waiting for app ($$i/30)..."; \
	  sleep 2; \
	  if [ $$i -eq 30 ]; then \
	    echo "App did not become healthy"; \
	    docker logs sphereapp_ci || true; \
	    exit 1; \
	  fi; \
	done
	@echo "Calling /ready: $(READY_URL)"
	@curl -fsS "$(READY_URL)" > /dev/null
	@echo "ready ok"

docker-stop:
	@docker stop sphereapp_ci || true

docker-ci: docker-build docker-run docker-smoke docker-stop

# -----------------------
# Frontend helpers
# -----------------------
.PHONY: frontend-install node-install

node-install:
	@command -v brew >/dev/null 2>&1 || { \
		echo "Homebrew not found. Install it first:"; \
		echo '/bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'; \
		exit 1; \
	}
	@command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 || { \
		echo "Installing Node.js (includes npm) via Homebrew..."; \
		brew install node; \
	}
	@echo "Node: $$(node -v)"
	@echo "npm:  $$(npm -v)"

frontend-install: node-install
	@test -d frontend-dev || { \
		echo "Creating Vite React+TS app in ./frontend-dev ..."; \
		npm create vite@latest frontend-dev -- --template react-ts; \
	}
	@cd frontend-dev && npm install
	@echo "Done. Run: make frontend-dev"

frontend-dev:
	@cd frontend-dev && npm run dev

frontend-lint:
	@cd frontend-dev && npm run lint

frontend-typecheck:
	@cd frontend-dev && npm run typecheck

frontend-test:
	@cd frontend-dev && npm test

frontend-build:
	@cd frontend-dev && npm run build

# -----------------------
# User Management
# -----------------------
create-user:
	@if [ -z "$(ADMIN_API_KEY)" ]; then \
	  echo "ERROR: ADMIN_API_KEY is required in .env or via argument."; \
	  echo "  Example: make create-user EMAIL=bob@example.com PASSWORD=secret"; \
	  exit 1; \
	fi
	@echo "Creating user: $(EMAIL)"
	@curl -s -X POST "$(API_URL)/auth/admin/users" \
	  -H "Content-Type: application/json" \
	  -H "X-Admin-Token: $(ADMIN_API_KEY)" \
	  -d '{"email":"$(EMAIL)","password":"$(PASSWORD)"}' \
	  | python -m json.tool

create-admin:
	@if [ -z "$(ADMIN_API_KEY)" ]; then \
	  echo "ERROR: ADMIN_API_KEY is required in .env or via argument."; \
	  echo "  Example: make create-admin EMAIL=admin@example.com PASSWORD=secret FULL_NAME=\"System Admin\""; \
	  exit 1; \
	fi
	@echo "Creating admin: $(EMAIL)"
	@curl -s -X POST "$(API_URL)/auth/admin/users" \
	  -H "Content-Type: application/json" \
	  -H "X-Admin-Token: $(ADMIN_API_KEY)" \
	  -d '{"email":"$(EMAIL)","password":"$(PASSWORD)","full_name":"$(FULL_NAME)","roles":["admin"]}' \
	  | python -m json.tool

# =========================
# Audit (static analysis)
# =========================
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff
COVERAGE := .venv/bin/coverage
VULTURE := .venv/bin/vulture

AUDIT_DIR := audit
APP_DIR := app
TEST_DIR := tests

JSCPD := jscpd

audit-init:
	@mkdir -p $(AUDIT_DIR)
	@mkdir -p tools

audit-install: audit-init
	@echo "Installing python audit deps into .venv..."
	@$(VENV)/bin/pip install -q -U ruff coverage vulture pytest
	@echo "Installing jscpd (global via npm)..."
	@command -v npm >/dev/null 2>&1 && npm i -g jscpd >/dev/null 2>&1 || echo "npm not found; skip jscpd install"
	@echo "Done."

audit-ruff: audit-init
	@echo "Running ruff..."
	@$(RUFF) check $(APP_DIR) > $(AUDIT_DIR)/ruff.txt || true

audit-tests-fast: audit-init
	@echo "Running a smaller, faster test subset (idempotent + core)..."
	@$(PYTEST) -q \
		tests/test_claim_ingest_idempotent.py \
		tests/test_claims_pdf_ingest.py::test_ingest_pdf_idempotent \
		> $(AUDIT_DIR)/pytest_fast.txt || true

audit-tests: audit-init
	@echo "Running full pytest (may take time)..."
	@$(PYTEST) -q > $(AUDIT_DIR)/pytest.txt || true

audit-coverage: audit-init
	@echo "Running pytest under coverage..."
	@$(COVERAGE) erase
	@$(COVERAGE) run -m pytest -q || true
	@$(COVERAGE) json -o $(AUDIT_DIR)/coverage.json
	@$(COVERAGE) report -m > $(AUDIT_DIR)/coverage_report.txt || true

audit-public-coverage: audit-init audit-coverage
	@echo "Generating public functions without coverage report..."
	@$(PY) tools/audit_public_functions_coverage.py > $(AUDIT_DIR)/public_functions_without_coverage.log || true

audit-deadcode: audit-init
	@echo "Running vulture dead-code scan..."
	@$(VULTURE) $(APP_DIR) \
		--exclude "$(APP_DIR)/db/migrations/*,$(TEST_DIR)/*,$(AUDIT_DIR)/*" \
		--min-confidence 80 \
		> $(AUDIT_DIR)/vulture.txt || true

audit-dup: audit-init
	@echo "Running jscpd duplication scan..."
	@command -v $(JSCPD) >/dev/null 2>&1 && \
		$(JSCPD) ./$(APP_DIR) \
			-f python \
			-l 6 \
			-k 60 \
			-r "console,markdown" \
			-o ./$(AUDIT_DIR) \
			-g \
			-i "**/.venv/**,**/__pycache__/**,**/node_modules/**,**/.git/**,**/audit/**,**/db/migrations/**,**/schemas/**" \
		|| echo "jscpd not found; run: npm i -g jscpd"

audit-summary: audit-init
	@echo "Building audit summary..."
	@$(PY) tools/audit_summary.py > $(AUDIT_DIR)/SUMMARY.md || true
	@echo "Summary written to $(AUDIT_DIR)/SUMMARY.md"

audit-run: audit-init audit-ruff audit-deadcode audit-dup audit-public-coverage audit-summary
	@echo "Audit completed. See ./$(AUDIT_DIR)/"

.PHONY: help venv install require-db-url migrate run run-prod start test fmt fmt-check lint lint-fix type ci clean \
        docker-build docker-run docker-smoke docker-stop docker-ci \
        frontend-dev frontend-lint frontend-typecheck frontend-test frontend-build \
        create-user create-admin \
        audit-init audit-install audit-ruff audit-tests-fast audit-tests audit-coverage audit-public-coverage audit-deadcode audit-dup audit-summary audit-run

diff:
	git diff > changes.diff
