# SphereApp Frontend

API-only backend lives in the repo root. This folder is a standalone SPA for the new UI.

## Requirements
- Node.js 18+ (for Vite, Vitest, and the shadcn/ui + AI Elements CLIs)

## Setup
```bash
cd frontend
npm install
```

## Run dev server
```bash
npm run dev
```

## Build
```bash
npm run build
```

## Lint
```bash
npm run lint
```

## Typecheck
```bash
npm run typecheck
```

## Tests
```bash
npm test
```

## Environment variables
Create a `.env` file in `frontend/` or set env vars:
- `VITE_API_BASE_URL` (required) — base URL for the backend API, e.g. `http://localhost:8000`
- `VITE_ADMIN_API_KEY` (optional) — used for admin bootstrap flows

## Notes
- This SPA uses strict TypeScript and disallows `any`.
- API shapes should be kept in sync with `docs/API_INVENTORY.md`.
