# AGENTS.md
Developer-experience rules for refactor agents in this repository.

## Fast validation gates (default)
After refactor steps, run only the fast gates:
- `.venv/bin/python -m compileall app`
- `.venv/bin/ruff check app || true`
- `.venv/bin/pytest -q tests/test_claim_ingest_idempotent.py --maxfail=1 || true`

## Full test suite (optional)
- Full `pytest` is optional and should be run manually or in CI.
- Do not run full `pytest` by default during agent refactors.
