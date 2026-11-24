# Status

Phase 1 (skeleton) is complete. Every check, the pre-commit hook and the container are in place; no retirement features are built yet.

## What exists

- `backend/`: FastAPI app from `create_app(data_dir, dist_dir)`, SQLite tables (`profile`, `statements`, `rules`) and `GET /api/health`. When `dashboard/dist` exists, the app serves it at `/`.
- `agent/`: the entry point `run(task, thread_id)`, with one tool that calls the health route. Tests use a stub model.
- `dashboard/`: React shell with light and dark themes per `docs/BRAND.md` and a Status page that reads "Backend is up" or "Backend is down".
- `e2e/`: Playwright test of the status page and the dark theme (`playwright.config.ts` starts both servers).
- `lefthook.yml`: pre-commit runs all Python and TypeScript checks in parallel.
- `Containerfile` and `compose.yaml`: a two-stage image (Node builds the dashboard, Python 3.12 serves everything on port 8000) with `./data` mounted at `/data`.

## How to run it

- Setup: `uv sync && npm install` (the `prepare` script installs lefthook and Playwright Chromium)
- Development: `npm run dev`, then open http://localhost:5173
- Container: `podman compose up -d`, then open http://localhost:8000. Stop it with `podman compose down`.
- Checks: `npm run check` (Python, TypeScript and e2e)

## Next

Phase 2: household profile (see `docs/PLAN.md`).
