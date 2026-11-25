# Status

Phases 1 (skeleton), 2 (household profile), 3 (rules file and projection engine), 4 (strategy search and Plan page) and 5 (rules research agent and Rules page) are complete, with one Phase 3 criterion open (see below). The profile can be entered, saved and reloaded. `GET /api/plan` ranks strategies, and the Plan page shows the best one, a comparison table, a balance chart and the year-by-year table.

## What exists

- `backend/`: FastAPI app from `create_app(data_dir, dist_dir)`, SQLite tables (`profile`, `statements`, `rules`) and `GET /api/health`. When `dashboard/dist` exists, the app serves it at `/`.
- `backend/profile/`: household models and `GET`/`PUT /api/profile` (404 until a profile is saved, 422 with field errors on bad input).
- `backend/rules/`: the `TaxRules` schema, the seed rules file `seed/retirement_rules_2026-01-01.md` (2026 federal, LTCG, Social Security taxation, RMD, IRMAA, Social Security reduction and Colorado figures) and `current_rules` (newest accepted file in `data/rules/`, else the seed).
- `backend/engine/tax.py`: federal tax (with the senior deduction), bracket tops, taxable Social Security, Colorado tax, IRMAA, RMDs and `rules_for_year` (inflates dollar thresholds).
- `backend/engine/social_security.py`: full retirement age, `monthly_benefit` (interpolated from the 62, FRA and 70 estimates) and `spousal_topup`.
- `backend/engine/projection.py` (with `income.py` and `accounts.py`): `Strategy`, `YearRow`, `Projection` and `project()`. Each year covers wages, Social Security (COLA, spousal and survivor), pensions, RMDs, the Roth conversion, withdrawals in the strategy order, and federal, Colorado and IRMAA tax paid in the same year (grossed up by iteration). Then it applies returns. One projection of the sample household takes about 4 ms.
- `backend/plan/api.py`: `POST /api/plan/project` (body `Strategy`; 409 until a profile is saved).
- `backend/engine/search.py`, `whatif.py` and `spending.py` with `GET /api/plan` (409 until a profile is saved). It ranks the strategy grid (459 strategies for the sample). For the top 5 and the best no-conversion baseline, it reports the what-if success rate at base spending (1,000 return paths, seed 7, the same paths for every strategy) and the safe extra spending on the fixed-rate path. It also returns the rules file name, whether that file is stale (over 90 days old) and the best strategy's year rows.
- Plan time budget: `GET /api/plan` must finish in under 20 s on the owner's 16-core host, with the container given no CPU limit. The what-if paths run in one process pool per request, sized to the CPUs the process may use. Measured for the sample: 6.2 s with `taskset -c 0-15` and 18.8 s with `taskset -c 0,1`.
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

## Phase 3 checks

- Projection call: post with `-H 'content-type: application/json'`. Without it, curl sends form data and FastAPI answers 422. With the sample profile saved, the fill-12% strategy (63 to 74, taxable first, claim 67/67) returns rows 2026 to 2047 and converts $133,000.00 in 2026 (age 63). Its `rmd` stays zero, because that strategy draws the 401(k) down to $0.00 by 2035. With `"conversion_target":"none"`, RMDs start in 2038 as expected (age 75 for 1963). That criterion stays unticked in `docs/PLAN.md` until the expectation is settled.
- Hand check of federal tax, 2026 row of that fill-12% projection (mfj, ages 63 and 61, seed rules, nobody 65 or older):
  - Ordinary income $133,000.00 (the conversion) less the $32,200.00 standard deduction gives ordinary taxable income of $100,800.00.
  - 10%: $24,800.00 × 0.10 = $2,480.00. 12%: ($100,800.00 − $24,800.00) × 0.12 = $9,120.00. Ordinary tax is $11,600.00.
  - Long-term gains of $31,116.43 stack on top, from $100,800.00 to $131,916.43. That is entirely above the $98,900.00 0% limit, so the tax is $31,116.43 × 0.15 = $4,667.46.
  - Total by hand: $16,267.46. The engine gives $16,267.46 (16,267.4645), a difference of $0.00.

- `dashboard/src/pages/PlanPage.tsx` with `components/{StrategyTable,YearTable,BalanceChart}.tsx`: calls `GET /api/plan` (about 6 s, shows "Calculating plan") and `GET /api/profile` (for the ACA notice and the heir tax rate). It shows a headline, the top 5 plus the no-conversion baseline with after-tax money and the share of market paths that work side by side, a stacked area chart of balances by account type (Recharts 3.11.1, series colors validated in both themes), and the year table. Notices: "Rules are out of date", the ACA subsidy warning, and "Complete your profile first" on 409. The sidebar has Plan.

## Phase 4 checks

- Sample profile saved, `time curl -s localhost:8000/api/plan` took 6.3 s. It returns 5 `top` entries, every `success_rate` is within 0 to 1, every `safe_extra` is at least 0 and the top `after_tax_end` ($1,162,337.62) is above the baseline's ($1,130,107.82). Two calls returned byte-identical JSON.
- The Plan page was screenshotted in light and dark themes: headline, comparison table, chart and 22-row year table all render, with no exclamation marks.

- `backend/rules/api.py`: `GET /api/rules/status`, `GET /api/rules/{filename}`, `POST /api/rules` (422 on an invalid file), `POST /api/rules/{filename}/accept` (404, 409, 422) and `POST /api/rules/refresh` (202). Refreshed rules stay pending until accepted.
- `agent/rules_research.py`: the research agent. It fetches only the listed official pages and saves a pending rules file through the API.
- `dashboard/src/pages/RulesPage.tsx`: shows the rules date and age, the source URLs of the current file, a "Refresh rules" button and the pending review (path, current and new values, "Accept" and "Keep current"). Sections of the pending file marked "Not refreshed on" are listed under the table. Accept errors show the backend message. "Keep current" only hides the review for this visit, since there is no reject route; the file stays pending. The sidebar has Rules.
- Task 4.2 review fixes: the plan request is aborted on unmount, the headline figures use the number font, `formatPercent` floors to one decimal (only a true 1.0 shows 100.0%), and `formatCompact` handles values just under $1M and negatives.

## Phase 5 checks

- `POST /api/rules` with `{"markdown":"no json"}` returned 422 (`expected one json block, found 0`) on a backend started with a temp `DATA_DIR`, and `GET /api/rules/status` still showed the seed (`retirement_rules_2026-01-01.md`, no pending file).
- Live run (done by the controller with a real model): the research agent produced the pending file `retirement_rules_2026-11-24.md` in `data/rules/`, and its JSON validates. It has 3 changes, all source URLs, and the figures are unchanged. Its Colorado section reads "Not refreshed on 2026-11-24: source unavailable." because tax.colorado.gov returns 403. Model cost was not recorded. The file is not accepted and is left for the owner to review; the Rules page shows "Not refreshed: Colorado (source unavailable)" for it.
- The review flow (modified seed posted through the API, change row, Accept, date updates) passes in Playwright and was screenshotted in light and dark themes with no exclamation marks.

## Next

Phase 6: statement extraction and container release (see `docs/PLAN.md`).
