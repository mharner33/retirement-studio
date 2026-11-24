# Status

Phases 1 (skeleton), 2 (household profile) and 3 (rules file and projection engine) are complete, with one Phase 3 criterion open (see below). The profile can be entered, saved and reloaded, and `POST /api/plan/project` projects it year by year under a strategy. There is no strategy search or Plan page yet.

## What exists

- `backend/`: FastAPI app from `create_app(data_dir, dist_dir)`, SQLite tables (`profile`, `statements`, `rules`) and `GET /api/health`. When `dashboard/dist` exists, the app serves it at `/`.
- `backend/profile/`: household models and `GET`/`PUT /api/profile` (404 until a profile is saved, 422 with field errors on bad input).
- `backend/rules/`: the `TaxRules` schema, the seed rules file `seed/retirement_rules_2026-01-01.md` (2026 federal, LTCG, Social Security taxation, RMD, IRMAA, Social Security reduction and Colorado figures) and `current_rules` (newest accepted file in `data/rules/`, else the seed).
- `backend/engine/tax.py`: federal tax (with the senior deduction), bracket tops, taxable Social Security, Colorado tax, IRMAA, RMDs and `rules_for_year` (inflates dollar thresholds).
- `backend/engine/social_security.py`: full retirement age, `monthly_benefit` (interpolated from the 62, FRA and 70 estimates) and `spousal_topup`.
- `backend/engine/projection.py` (with `income.py` and `accounts.py`): `Strategy`, `YearRow`, `Projection` and `project()`. Each year covers wages, Social Security (COLA, spousal and survivor), pensions, RMDs, the Roth conversion, withdrawals in the strategy order, and federal, Colorado and IRMAA tax paid in the same year (grossed up by iteration). Then it applies returns. One projection of the sample household takes about 4 ms.
- `backend/plan/api.py`: `POST /api/plan/project` (body `Strategy`; 409 until a profile is saved).
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

## Next

Phase 4: strategy search, what-if success rate, safe extra spending and the Plan page (see `docs/PLAN.md`).
