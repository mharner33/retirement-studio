# Retirement Studio

A retirement analysis and planning tool. It reviews your accounts, applies current IRS rules and models scenarios to lower taxes and balance spending over your expected lifespan.

## Run it

- Setup: `uv sync && npm install`
- Development: `npm run dev` (backend on port 8000, dashboard on port 5173)
- Container: `podman compose up -d`, then open http://localhost:8000
- All checks: `npm run check`

Put your OpenRouter key in `.env` as `OPENROUTER_API_KEY`. Your documents and the database live in `data/`, which is not tracked by git.

See `docs/` for the spec, tech stack, standards and status.
