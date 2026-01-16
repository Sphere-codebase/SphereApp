SHELL := /bin/bash
-include .env
export

PYTHON ?= python3.11
VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(PY) -m pip

# --- CI-ish defaults (override if needed) ---
DATABASE_URL ?= postgresql+psycopg://postgres:postgres@localhost:5432/claims_assistant
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

help:
	@echo "Targets:"
	@echo "  make venv        - create virtual env"
	@echo "  make install     - install deps (incl dev)"
	@echo "  make db-up       - start postgres via docker compose"
	@echo "  make db-down     - stop postgres"
	@echo "  make db-logs     - follow postgres logs"
	@echo "  make db-wait     - wait for postgres health"
	@echo "  make db-upgrade  - apply alembic migrations (uses compose DB)"
	@echo "  make start       - db-up + db-upgrade + run (reload)"
	@echo "  make run         - run API (reload)"
	@echo "  make run-prod    - run API (no reload)"
	@echo "  make test        - run tests"
	@echo "  make fmt         - format (ruff)"
	@echo "  make lint-fix    - autofix lint"
	@echo "  make fmt-check   - CI format check only (ruff format --check)"
	@echo "  make lint        - lint (ruff)"
	@echo "  make type        - type-check (mypy)"
	@echo "  make ci          - fmt-check + lint + migrate + test (CI-like)"
	@echo "  make clean       - remove caches"
	@echo "  make create-user - create a standard user (requires ADMIN_API_KEY)"
	@echo "  make create-admin- create an admin user (requires ADMIN_API_KEY)"
	@echo ""
	@echo "Docker (CI-like smoke):"
	@echo "  make docker-build - build docker image ($(IMAGE_TAG):ci)"
	@echo "  make docker-run   - run container for smoke test"
	@echo "  make docker-smoke - wait for /health and call /ready"
	@echo "  make docker-stop  - stop smoke container"
	@echo "  make docker-ci    - docker-build + docker-run + docker-smoke + docker-stop"
	@echo ""
	@echo "Frontend:"
	@echo "  make frontend-install  - install frontend deps"
	@echo "  make frontend-dev      - run frontend dev server"
	@echo "  make frontend-lint     - lint frontend"
	@echo "  make frontend-typecheck- type-check frontend"
	@echo "  make frontend-test     - test frontend"
	@echo "  make frontend-build    - build frontend"

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

# Compose DB upgrade (your original behavior)
db-upgrade: db-wait
	$(VENV)/bin/python -m alembic upgrade head

# CI-style migrate (uses DATABASE_URL, no compose assumptions)
migrate:
	DATABASE_URL="$(DATABASE_URL)" $(VENV)/bin/python -m alembic -c alembic.ini upgrade head

# --- App run ---
run:
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-prod:
	$(VENV)/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

# One-button local start
start: db-up docker-wait db-upgrade run

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

# CI-like pipeline (mirrors what CI does: format check, lint, migrate, tests)
ci: fmt-check lint-fix migrate test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ htmlcov .coverage

# ---- Docker CI-like smoke (mirrors ci.yml) ----
docker-build:
	@echo "Building image: $(IMAGE_TAG):ci"
	docker build -t "$(IMAGE_TAG):ci" .

docker-run:
	@echo "Starting container sphereapp_ci on :8000"
	docker run -d --rm \
	  -p 8000:8000 \
	  --name sphereapp_ci \
	  --add-host=host.docker.internal:host-gateway \
	  -e DATABASE_URL="postgresql+psycopg://postgres:postgres@host.docker.internal:5432/claims_assistant" \
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

# ---- Frontend helpers (your original) ----
.PHONY: frontend-install node-install

# Install Node.js (npm) via Homebrew (macOS)
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

# Create (if missing) and install React frontend (Vite + React + TypeScript)
frontend-install: node-install
	@test -d frontend || { \
		echo "Creating Vite React+TS app in ./frontend ..."; \
		npm create vite@latest frontend -- --template react-ts; \
	}
	@cd frontend && npm install
	@echo "Done. Run: make frontend-dev"

frontend-dev:
	@cd frontend && npm run dev

frontend-lint:
	@cd frontend && npm run lint

frontend-typecheck:
	@cd frontend && npm run typecheck

frontend-test:
	@cd frontend && npm test

frontend-build:
	@cd frontend && npm run build

.PHONY: help venv install db-up db-down db-logs db-wait docker-wait db-upgrade migrate run run-prod start test fmt fmt-check lint type ci clean \
        docker-build docker-run docker-smoke docker-stop docker-ci \
        frontend-dev frontend-lint frontend-typecheck frontend-test frontend-build

# --- User Management ---
create-user:
	@if [ -z "$(ADMIN_API_KEY)" ]; then \
	  echo "ERROR: ADMIN_API_KEY is required in .env or via argument."; \
	  echo "  Example locally: make create-user EMAIL=bob@example.com PASSWORD=secret"; \
	  exit 1; \
	fi
	@echo "Creating user: $(EMAIL)"
	@curl -s -X POST "$(API_URL)/auth/admin/users" \
	  -H "Content-Type: application/json" \
	  -H "X-Admin-Token: $(ADMIN_API_KEY)" 	  -d '{"email":"$(EMAIL)","password":"$(PASSWORD)"}' \
	  | python -m json.tool

create-admin:
	@if [ -z "$(ADMIN_API_KEY)" ]; then \
	  echo "ERROR: ADMIN_API_KEY is required in .env or via argument."; \
	  echo "  Example locally: make create-admin EMAIL=admin@example.com PASSWORD=secret FULL_NAME='System Admin'"; \
	  exit 1; \
	fi
	@echo "Creating admin: $(EMAIL)"
	@curl -s -X POST "$(API_URL)/auth/admin/users" \
	  -H "Content-Type: application/json" \
	  -H "X-Admin-Token: $(ADMIN_API_KEY)" \
	  -d '{"email":"$(EMAIL)","password":"$(PASSWORD)","full_name":"$(FULL_NAME)","roles":["admin"]}' \
	  | python -m json.tool
