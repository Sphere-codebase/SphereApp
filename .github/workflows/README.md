# SphereApp

FastAPI service with Postgres + Alembic migrations and optional local LLM (LM Studio).

## Requirements
- Python 3.11
- Docker (for Postgres)
- (Optional) LM Studio for local LLM server

## Local run

### 1) Start Postgres
```bash
docker compose up -d
```

### 2) Set env
Create .env (or export vars in your shell). Minimum:

```bash
export DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/claims_assistant"
export JWT_SECRET="dev-secret"
export ENV="dev"
# Optional: readiness should not depend on LLM during local debugging
export READY_CHECK_LLM="false"
```

### 3) Run migrations
```bash
python -m alembic upgrade head
```

### 4) Start API
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5) Health checks
```bash
curl -i http://localhost:8000/health
curl -i http://localhost:8000/ready
```

## Auth quickstart

Register:

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"doc1@example.com","password":"secret"}'; echo
```

Login:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"doc1@example.com","password":"secret"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
echo "$TOKEN"
```

Me:

```bash
curl -i http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-ID: me-1"
```

## Chat

Minimal chat:

```bash
curl -i -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: chat-1" \
  -d '{"message":"Say exactly OK"}'; echo
```

Continue a session:

```bash
SESSION_ID="<paste from previous response>"
curl -i -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: chat-2" \
  -d "{\"session_id\":\"$SESSION_ID\",\"message\":\"What did I just ask you to say? Answer in one word.\"}"; echo
```

## LM Studio (optional)

Run LM Studio server on your LLM machine, e.g.:

- Same machine: `http://127.0.0.1:1234/v1`
- Another machine on the same Wi-Fi: `http://<LM_IP>:1234/v1`

Then set:

```bash
export LLM_BASE_URL="http://<LM_IP>:1234/v1"
```

## Tests
```bash
pytest -q -rs
```

## CI
GitHub Actions workflow:

- starts Postgres as a service
- runs Alembic migrations and tests
- builds Docker image
- smoke-tests /health and /ready on port 8000

---

If you want next steps:
- add CI badge to README
- split CI into jobs (lint / test / docker-smoke)
- prepare a separate `docker-compose.ci.yml`
