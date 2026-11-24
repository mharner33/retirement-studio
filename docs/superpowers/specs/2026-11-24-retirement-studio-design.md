# Retirement Studio design

Date: 2026-11-24. Source of truth for what to build; `docs/PLAN.md` turns it into phases.

## Intent

One household (the owner and possibly a spouse) plans retirement on their own machine. The owner plans to retire around 63 and lives in Colorado. The questions the app must answer, in order of importance:

1. When to start Roth conversions and how much to convert each year.
2. How to shrink Required Minimum Distributions (RMDs) so they do not push income into higher brackets or Medicare IRMAA surcharges later.
3. A yearly spending budget covered by Social Security plus withdrawals, lasting to a plan-to age (default 82, editable).
4. Which accounts to withdraw from first (taxable, pre-tax, Roth) to keep the most money working.

Questions 1 and 2 are one optimization: conversions in the low-income years between retirement and Social Security/RMDs reduce later RMDs.

## Goals

- A guided form that captures the household's situation, editable later on one page.
- A deterministic projection engine: year by year from now to the plan-to age, with federal tax, Colorado tax, RMDs, IRMAA and Social Security taxation.
- A strategy search that compares named, rule-based strategies and ranks them by lifetime tax and ending balance.
- A what-if check: about 1,000 simulated market paths on the top strategies, reported as a success percentage.
- A rules file of current IRS and Colorado retirement rules in `data/`, timestamped, refreshed by a research agent when older than 3 months.
- PDF statement extraction (401(k), IRA, brokerage) with a review step before anything is saved.
- A spouse can be added, and the plan re-runs.
- A spending budget: the user enters essential spending; the app checks it lasts to the plan-to age and reports how much more can safely be spent each year on top of it.
- A planning chat agent (built after the form, planned separately in `docs/PLAN_CHAT.md`) that answers what-if questions and proposes form changes for the user to confirm.

## Non-goals (for now)

- Logins, multiple households, hosting for others.
- ACA premium subsidy modeling. Pre-Medicare coverage is assumed to be COBRA or a spouse's plan.
- Medicare/Medicaid recommendations beyond IRMAA in the tax math.
- Exact year-by-year optimization (linear programming). May be added later as a refinement.
- Tax rules for states other than Colorado.
- Filing tax returns or giving advice framed as professional advice.

## Anti-goals

- The model doing tax or growth arithmetic. All numbers come from tested code.
- Silently saving extracted statement numbers. A misread balance must be caught by the user.
- Recommendations that cannot be stated as a plain rule ("fill the 12% bracket from 63 to 72").
- Sending account numbers or names to the model provider.

## Constraints

- Stack fixed by `docs/TECH_STACK.md`: FastAPI + SQLite backend, LangChain `create_agent` on OpenRouter, React 19 + Vite + strict TypeScript dashboard, Playwright e2e.
- Runs in a container. The machine has Podman, not Docker. Target Podman, keep a standard `Containerfile`/`compose.yaml` that Docker can also run.
- Python 3.12+. The current `.venv` is 3.11 because `.python-version` pins it; fix the pin, `requires-python`, and add `pymupdf` to `pyproject.toml`. Drop packages the stack does not use (boto3, gradio, ollama, psycopg, claude-agent-sdk, langgraph-checkpoint-postgres, mangum, ipykernel, ipywidgets, nbformat, plotly, pandas unless used, deepagents).
- Agents reach data only through the backend HTTP API.
- Tests never call a model; use a stub.
- `npm run check` must pass: 80% coverage on both sides, no rule changes.
- UI follows `docs/BRAND.md`: light and dark themes, money as $1,250.00, no exclamation marks.

## Approaches considered (strategy search)

- **A. Search over named strategies (chosen).** Enumerate combinations of conversion target bracket, conversion start/stop age, withdrawal order and Social Security claiming age per person; run the deterministic projection for each (a few hundred runs); rank. Every result is a readable rule and is easy to test. May miss slightly better irregular patterns.
- **B. Linear programming optimizer.** Exact yearly amounts, but tax cliffs (IRMAA, Social Security taxation thresholds) need mixed-integer modeling; results are hard to explain and test. Deferred.
- **C. Let the planning agent reason out the plan.** Rejected: not repeatable, not testable.

The owner chose A.

## Decisions made with the owner

- Single household, local only, no auth.
- Planning horizon: plan-to age 82 by default, editable.
- Returns: one fixed rate (default 6% nominal, 2.5% inflation, editable) for the year-by-year table, plus a what-if success percentage from ~1,000 simulated paths.
- Retirement around 63. Pre-Medicare health coverage: model COBRA premium for 18 months, then an editable bridge premium until Medicare at 65. If the bridge is an ACA plan, show a note that conversions in that window can reduce the subsidy; do not model it.
- Colorado state tax is modeled (flat rate plus the retirement income subtraction and Social Security rules current per the rules file).
- Statement text is extracted locally with pymupdf; account numbers and names are masked before text goes to OpenRouter; extracted values land on a review screen and are saved only when confirmed.
- Input: guided form first; planning chat agent in a later phase, which proposes form changes for confirmation.
- Budget: both. The user enters essential (and optionally discretionary) spending; the app checks it lasts and also solves for the highest extra yearly spending that still lasts to the plan-to age.
- The spouse has her own Social Security work record.

## Calls made after the builder check (owner to confirm)

- Ranking: strategies rank by after-tax money left at the plan-to age, in today's dollars, with spending fixed. Pre-tax balances count net of an assumed tax rate (editable, default 22%) so leaving tax unpaid cannot look good. IRMAA surcharges count as cost. Running short ranks below any plan that lasts.
- Safe extra spending: solved by bisection on the top 5 strategies only, not the whole grid. Reported for the fixed-rate path and with its what-if success percentage.
- Spousal and survivor Social Security: computed from the full-retirement-age estimates already on the form; no extra fields. Spousal top-up = max(0, 50% of the other spouse's full-retirement-age benefit minus own), reduced for early claiming; the survivor keeps the larger benefit. Reduction factors come from the rules file.
- Rules research: the agent reads a fixed list of official pages (IRS, SSA, Medicare, Colorado Department of Revenue) with plain HTTP fetches; no paid search service, no new keys.
- Rules review: a refreshed rules file is saved as pending, the Rules page shows which figures changed, and the engine uses it only after the user accepts it.
- Pilot scope: `docs/PLAN.md` covers setup fixes, the form, the engine and search, the what-if range and Plan page, the rules agent, PDF extraction and the container. The chat agent goes in `docs/PLAN_CHAT.md`.

## Design (the builder's calls are marked)

### Household profile (form)

Steps: You, Spouse (optional), Income, Accounts, Spending, Assumptions. Fields, per best practice:

- People: name (first only), birth date, retirement age, plan-to age, Social Security estimate at 62, full retirement age and 70 (from ssa.gov), claiming age, pension amount, start age and survivor percentage.
- Filing status follows whether a spouse exists (married filing jointly).
- Income until retirement: wages, 401(k) contributions and employer match.
- Accounts: type (pre-tax 401(k)/IRA, Roth 401(k)/IRA, taxable brokerage with cost basis, cash, HSA), owner, balance, as-of date. Home value recorded for net worth only; not spent unless the user says so (builder's call).
- Spending: yearly essential and discretionary amounts in today's dollars, pre-Medicare health premiums (COBRA monthly premium, bridge monthly premium), one-time expenses by year.
- Assumptions: return, inflation, Social Security cost-of-living rate, plan-to age.

### Rules

- The research agent writes `data/rules/retirement_rules_YYYY-MM-DD.md`: readable markdown with sources and dates, plus one fenced JSON block of the figures the engine needs (federal brackets, standard deduction and age-65 additions, any temporary senior deduction, capital gains brackets, Social Security taxation thresholds, RMD start age by birth year and the Uniform Lifetime Table, IRMAA tiers, contribution limits, Colorado rate and retirement subtraction). Builder's call: JSON block inside the markdown so one file serves people and code.
- The backend loads the newest accepted file, validates the JSON block with Pydantic, and exposes its date. Older than 90 days → dashboard shows "Rules are out of date" with a refresh button that runs the agent.
- A seed rules file checked into the repo (outside `data/`) lets the engine and tests run before the agent exists (builder's call).
- Brackets beyond the rules year are inflated at the assumed inflation rate.

### Projection engine (pure Python, `backend/`)

For each year from now to the last plan-to age: wages and contributions until retirement, Social Security from the claiming age, pensions, RMDs from the start age, the strategy's Roth conversion, withdrawals in the strategy's order to cover spending plus tax, federal and Colorado tax, IRMAA based on income two years earlier, growth at the fixed rate. Output: one row per year (the table the owner saw in conversation) plus totals: lifetime tax, ending balance by account type, first year money runs short (if any).

Builder's call: when one spouse passes the plan-to age, the survivor continues as a single filer (the higher Social Security benefit continues); this captures the widow's tax increase that makes early conversions more valuable.

### Strategy search

Grid over: conversion target (none, top of 12%, 22%, 24% bracket, or a fixed IRMAA tier ceiling), conversion start and stop ages, withdrawal order (taxable→pre-tax→Roth, pre-tax→taxable→Roth, proportional), Social Security claiming age per person (62, full retirement age, 70). Rank as described under "Calls made after the builder check"; show lifetime tax and ending balance. Top 5 get the what-if run: about 1,000 paths with random yearly returns (builder's call: normal distribution, mean from assumptions, editable volatility, default 12%), seeded so results repeat.

### Agents (`agent/`)

- Research agent: refreshes the rules file. Tools: web search/fetch, backend API to save the file.
- Extraction agent: input is masked text from pymupdf, output is structured account records posted to the backend as pending until reviewed.
- Planning agent (last): reads the profile and results through the API, answers questions, proposes profile changes that the user confirms in the form.
- All share one entry point pattern `run(task, thread_id)`; the template's "claim id" goes away (update `docs/TECH_STACK.md`).

### Dashboard

Pages: Profile (the form), Statements (upload/list PDFs from `data/`, review extracted values), Plan (strategy comparison, year-by-year table, safe extra spending, success percentage, balances chart), Rules (date, sources, refresh, review of changed figures), Chat (later). Light and dark themes per `docs/BRAND.md`.

### Container

One image: a built dashboard served as static files by FastAPI, `data/` mounted as a volume, SQLite file inside the volume, `.env` passed at run time. `podman compose up` (or `podman run`) starts it.

## Left to the builder

Database schema, API shapes, component structure, chart library (lightweight, brand colors), exact grid ranges, file naming beyond what is above, phase split in `docs/PLAN.md` (5 or 6 phases per `docs/PROCESS.md`).

## Known gaps in the repo to fix in the first phase

- `backend/`, `agent/`, `dashboard/`, `e2e/` do not exist; `docs/STATUS.md` claims a skeleton.
- No TS, ESLint, Prettier, Vite, Vitest or Playwright config; `lefthook.yml` is commented out.
- Python pin and dependencies as listed under Constraints.
