# Status

Phases 1 (skeleton) and 2 (household profile) are complete. The profile can be entered, saved and reloaded; no projection or planning features are built yet.

## What exists

- `backend/`: FastAPI app from `create_app(data_dir, dist_dir)`, SQLite tables (`profile`, `statements`, `rules`) and `GET /api/health`. When `dashboard/dist` exists, the app serves it at `/`.
- `backend/profile/`: household models and `GET`/`PUT /api/profile` (404 until a profile is saved, 422 with field errors on bad input).
- `agent/`: the entry point `run(task, thread_id)`, with one tool that calls the health route. Tests use a stub model.
- `dashboard/`: React shell with light and dark themes per `docs/BRAND.md` a Status page, and a Profile page: a six-step guided form (You, Spouse, Income, Accounts, Spending, Assumptions) for a new profile, and one editable page once a profile exists. Money fields show $1,250.00 when not focused.
- `e2e/`: Playwright tests of the status page, the dark theme and the profile form (fill, save, reload) (`playwright.config.ts` starts both servers).
- `lefthook.yml`: pre-commit runs all Python and TypeScript checks in parallel.
- `Containerfile` and `compose.yaml`: a two-stage image (Node builds the dashboard, Python 3.12 serves everything on port 8000) with `./data` mounted at `/data`.

## How to run it

- Setup: `uv sync && npm install` (the `prepare` script installs lefthook and Playwright Chromium)
- Development: `npm run dev`, then open http://localhost:5173
- Container: `podman compose up -d`, then open http://localhost:8000. Stop it with `podman compose down`.
- Checks: `npm run check` (Python, TypeScript and e2e). If port 8000 is taken, set `BACKEND_PORT=8123` for the e2e backend and the Vite proxy.

## Next

Phase 3: rules file and projection engine (see `docs/PLAN.md`).
