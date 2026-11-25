# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

Read every file listed in AGENTS.md "Start here" before planning, building or answering questions. `docs/PROCESS.md` sets the workflow and its rules are binding.

## Commands

Run from the repo root. Always use `uv run`, never `python3`.

- Install: `uv sync && npm install` (the `prepare` script installs lefthook and Playwright Chromium)
- Dev servers: `npm run dev` (backend via uvicorn `backend.main:app` with reload, plus `vite dashboard`)
- All checks: `npm run check` (must pass before handing work over)
  - `npm run check:python`: ruff format check, ruff lint, pyright, pytest with coverage
  - `npm run check:ts`: prettier, eslint, tsc, vitest with coverage (root `dashboard`)
  - `npm run e2e`: Playwright
- Format: `npm run format`
- Single Python test: `uv run pytest backend/tests/test_x.py::test_name --no-cov` (`--no-cov` skips the 80% gate that `addopts` adds)
- Single TS test: `npx vitest run --root dashboard path/to/file.test.tsx -t "name"`
- Single e2e test: `npx playwright test e2e/file.spec.ts -g "name"`

## Architecture

Four top-level parts, each in its own folder:

- `backend/`: FastAPI + SQLite. The single source of data; everything else goes through its HTTP API.
- `agent/`: LangChain `create_agent` on OpenRouter (`OPENROUTER_API_KEY` in `.env`; model from `MODEL_NAME`, default `openai/gpt-6-luna`, medium reasoning). Built agents: IRS-rules research and PDF statement extraction (pymupdf). Next: a chat agent (`docs/PLAN_CHAT.md`). Agents reach data only through the backend API, never the database directly.
- `dashboard/`: React 19 + Vite + TypeScript (strict, no `any`).
- `e2e/`: Playwright tests against the running app.

`data/` is gitignored and holds user statements (PDF) and the IRS rules markdown file (timestamped, refreshed every 3 months). Do not open `data/evals/` unless asked. The app must run in a container (Docker or Podman).

Tooling scope: ruff, pyright, pytest and coverage are configured in `pyproject.toml` to cover only `backend/` and `agent/`. Tests live in `*/tests/` (S101 and PLR2004 allowed there).

## Rules worth repeating

- Tests never call a real model; use a stub.
- Never `git commit --no-verify`, never push, never lower thresholds or disable rules to get green; ask instead.
- Keep `docs/STATUS.md` current; plans go in `docs/PLAN.md` (pilot) or `docs/PLAN_<NAME>.md`.
- UI follows `docs/BRAND.md` (light and dark themes, US dollars formatted as $1,250.00, no exclamation marks).
