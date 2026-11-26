# Retirement Studio

A retirement analysis and planning tool. It reviews your accounts, applies current IRS rules and models scenarios to lower taxes and balance spending over your expected lifespan.

## Run it

- Setup: `uv sync && npm install`, then `mkdir -p data` and `touch .env` on a fresh clone.
- Development: `npm run dev` (backend on port 8000, dashboard on port 5173)
- Container: `npm run container:up` builds the image, starts the container and waits until it is healthy. Then open http://localhost:8000. `npm run container:logs` follows the logs and `npm run container:down` stops it. Your profile and files stay in `./data`.
- All checks: `npm run check`. The end-to-end tests need ports 8000 and 5173 free, so stop the container and the dev servers first.

Put your OpenRouter key in `.env` as `OPENROUTER_API_KEY`. It is only needed for statement reading, rules research and the Chat page. Your documents and the database live in `data/`, which is not tracked by git.

## Adding statements

Open the Statements page, drop your PDF statements on it or use "Choose files", then select "Extract all". Review each result, fix anything that is wrong and select "Accept". Nothing is saved to your profile until you accept. You can also copy PDFs into `data/statements/` by hand. Uploaded files are stored there too.

## Chat

Open the Chat page and ask about your plan, for example "What if I retire at 65 instead of 63?". Answers use the plan engine, the rules file and a short list of official pages, and name their source. When the agent proposes a profile change, it shows a card; nothing changes until you select "Apply".

See `docs/` for the spec, tech stack, standards and status.
