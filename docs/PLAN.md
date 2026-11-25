# Retirement Studio Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. `docs/PROCESS.md` is binding: build phases in order, check every success criterion, tick it here, update `docs/STATUS.md`, commit.

**Goal:** A local, containerized app for one household that captures its finances, projects them year by year with federal and Colorado tax, searches Roth conversion and withdrawal strategies, and reports the best plan with a what-if success percentage and safe extra spending.

**Architecture:** FastAPI + SQLite (`backend/`) holds the profile, statements and rules status and runs a pure-Python projection engine. LangChain agents (`agent/`) research rules and extract statements, reaching data only over the backend HTTP API. React dashboard (`dashboard/`) is built to static files and served by FastAPI in one container image.

**Tech Stack:** Python 3.12, uv, FastAPI, stdlib `sqlite3`, Pydantic, pymupdf, httpx, beautifulsoup4, LangChain `create_agent` + `langchain-openai` against OpenRouter; React 19, Vite, TypeScript (strict), Recharts, Vitest, Testing Library, Playwright; Podman.

**Spec:** `docs/superpowers/specs/2026-11-24-retirement-studio-design.md`

## Global Constraints

- Python `>=3.12` (`.python-version` = `3.12`); always `uv run`, never `python3`.
- Tests never call a real model; agents are tested with `agent/tests/stub_model.py`.
- `npm run check` passes at the end of every phase; coverage stays at 80% on both sides; never disable a rule, lower a threshold, exclude a file or use `--no-verify`. Never push.
- Agents reach data only through the backend HTTP API (an injected `httpx.Client`).
- TypeScript strict, no `any`.
- UI per `docs/BRAND.md`: Instrument Sans / Instrument Serif / JetBrains Mono (numbers), light and dark themes with the exact hex values listed there, rounded panels with no outline, no one-edge borders, no exclamation marks, money as `$1,250.00`.
- Default assumptions: plan-to age 82, return 6%, inflation 2.5%, Social Security COLA 2.5%, volatility 12%, heir tax rate 22%, 1,000 what-if paths with fixed seed 7.
- Rules files older than 90 days are stale. Refreshed rules are pending until accepted.
- Statement text sent to the model has account numbers masked to the last 4 digits and every profile `mask_terms` entry replaced with `[MASKED]`.
- `data/` is gitignored and is the container volume; never open `data/evals/`.
- Keep `docs/STATUS.md` current.

## Review Focus

- A person already past retirement age, claiming age or RMD age when the plan starts: engine starts each income stream from the current year and does not back-fill past years. Test in Task 3.3.
- Spending larger than all income and balances: projection reports `shortfall_year` and keeps producing rows with zero balances; nothing raises. Test in Task 3.3.
- Plan years past the rules file year: brackets, deductions and IRMAA thresholds are inflated by the inflation assumption from the rules year. Test in Task 3.2.
- A researched rules file with a missing or malformed JSON block: `POST /api/rules` returns 422 and the accepted file stays in use. Test in Task 5.1.
- A scanned PDF with no text layer: statement status becomes `no_text`, the extraction agent is not called. Test in Task 6.1.

---

## File map

```
backend/
  main.py            app, routers, static dashboard mount
  settings.py        DATA_DIR, DB path, BACKEND_URL from env
  db.py              sqlite3 connect + schema
  profile/models.py  Household Pydantic models
  profile/api.py     GET/PUT /api/profile
  rules/models.py    TaxRules schema
  rules/store.py     parse, save, accept, current rules, diff
  rules/api.py       /api/rules*
  rules/seed/retirement_rules_2026-01-01.md
  engine/tax.py, social_security.py, projection.py, search.py, whatif.py, spending.py
  plan/api.py        /api/plan*
  statements/pdf.py, statements/api.py
  tests/
agent/
  model.py           make_model()
  backend_client.py  make_client()
  health.py          run(task, thread_id)
  rules_research.py  refresh(client, model)
  extraction.py      extract(client, model, statement_id)
  tests/stub_model.py, tests/
dashboard/
  index.html, src/main.tsx, App.tsx, api.ts, types.ts, format.ts, theme.ts, styles.css
  src/pages/ProfilePage.tsx, PlanPage.tsx, RulesPage.tsx, StatementsPage.tsx
e2e/*.spec.ts
Containerfile, compose.yaml, lefthook.yml, tsconfig.json, eslint.config.js,
.prettierrc.json, vite.config.ts, playwright.config.ts
```

Builder's calls fixed here: stdlib `sqlite3` (no ORM); the household profile is one JSON row; navigation is a sidebar with React state (no router library); TS types are hand-written in `dashboard/src/types.ts` to mirror the Pydantic models.

---

## Phase 1: Foundation and skeleton

### Task 1.1: Python environment and backend health

**Files:** Modify `.python-version`, `pyproject.toml`; create `backend/__init__.py`, `backend/settings.py`, `backend/db.py`, `backend/main.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`.

**Interfaces — Produces:**
- `settings.data_dir() -> Path` (env `DATA_DIR`, default `./data`), `settings.db_path() -> Path` (`data_dir()/studio.db`).
- `db.connect(path: Path) -> sqlite3.Connection` creating tables `profile(id INTEGER PRIMARY KEY CHECK (id = 1), body TEXT)`, `statements(id INTEGER PRIMARY KEY, filename TEXT, status TEXT, extracted TEXT, created_at TEXT)`, `rules(filename TEXT PRIMARY KEY, status TEXT, created_at TEXT)`.
- `main.create_app(data_dir: Path | None = None) -> FastAPI`; module-level `app = create_app()`. `GET /api/health` → `{"status": "ok"}`.
- `conftest.py` fixture `client(tmp_path) -> TestClient` built from `create_app(tmp_path)`.

- [ ] Set `.python-version` to `3.12`, `requires-python = ">=3.12"`, `description`. Dependencies become: fastapi, uvicorn, httpx, pydantic, pymupdf, beautifulsoup4, langchain, langchain-openai, python-dotenv, python-multipart. Remove the rest (boto3, gradio, ollama, psycopg, claude-agent-sdk, deepagents, langgraph-checkpoint-postgres, langchain-mcp-adapters, mangum, ipykernel, ipywidgets, nbformat, plotly, pandas, openai, openrouter, requests, tqdm, langfuse) and the `server` group. Remove `[project.scripts]` and `[build-system]` and delete `src/retirement_studio/` (the uv scaffold; nothing uses it). `rm -rf .venv && uv sync`.
- [ ] Write `test_health_returns_ok` (`client.get("/api/health").json() == {"status": "ok"}`) and `test_connect_creates_tables` (table names from `sqlite_master` equal `{"profile", "statements", "rules"}`). Run `uv run pytest backend --no-cov`; expect FAIL (import error).
- [ ] Implement the interfaces above. Run again; expect PASS.
- [ ] Commit `chore: python 3.12, trimmed deps, backend health route`.

### Task 1.2: Agent entry point with stub model

**Files:** Create `agent/__init__.py`, `agent/model.py`, `agent/backend_client.py`, `agent/health.py`, `agent/tests/stub_model.py`, `agent/tests/test_health_agent.py`.

**Interfaces — Produces:**
- `model.make_model() -> BaseChatModel`: `ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY, model=MODEL_NAME or "openai/gpt-6-luna", reasoning_effort="medium")`, loading `.env` with python-dotenv.
- `backend_client.make_client() -> httpx.Client` with `base_url` from env `BACKEND_URL`, default `http://localhost:8000`.
- `health.run(task: str, thread_id: str, client: httpx.Client | None = None, model: BaseChatModel | None = None) -> str`: `create_agent` with one tool `check_backend()` that calls `GET /api/health`; returns the final message text. `thread_id` goes into the run config.
- `stub_model.StubModel(responses: list[AIMessage])`: subclass of `GenericFakeChatModel` whose `bind_tools` returns `self`, so it can script tool calls.

- [ ] Write `test_run_calls_health_tool`: the stub emits a tool call to `check_backend` then `AIMessage("Backend is up")`. The client is the backend `TestClient`. Assert the result is `"Backend is up"` and the tool message content contains `ok`. Also add `test_make_model_uses_env` (monkeypatch `MODEL_NAME=openrouter/free`; assert `make_model().model_name == "openrouter/free"`; no network). Expect FAIL, implement, expect PASS.
- [ ] Commit `feat: agent entry point with health tool`.

### Task 1.3: Dashboard, tooling config, theme

**Files:** Create `tsconfig.json`, `eslint.config.js`, `.prettierrc.json`, `.prettierignore`, `vite.config.ts` (root `dashboard`, `/api` proxied to `:8000`, Vitest in jsdom with v8 coverage thresholds 80), `dashboard/index.html`, `dashboard/src/{main.tsx,App.tsx,api.ts,format.ts,theme.ts,styles.css}`, tests `dashboard/src/format.test.ts`, `dashboard/src/App.test.tsx`.

**Interfaces — Produces:**
- `formatUsd(n: number): string`, for example `1250` → `"$1,250.00"` and `-75.5` → `"-$75.50"`.
- `api.getJson<T>(path: string): Promise<T>`, `api.putJson<T>(path: string, body: unknown): Promise<T>`, `api.postJson<T>(path, body?)`.
- `theme.ts`: `Theme = "light" | "dark"`, `initialTheme(): Theme` (localStorage key `theme` in try/catch, else `prefers-color-scheme`), `applyTheme(t: Theme): void` sets `data-theme` on `<html>`.
- `App`: sidebar (pages: Profile, Plan, Rules, Statements; extra pages are added in later phases), theme toggle button labeled "Dark theme" / "Light theme", and a status line "Backend is up" or "Backend is down" from `/api/health`.
- `styles.css`: CSS custom properties for every row of the `docs/BRAND.md` color table under `[data-theme="light"]` and `[data-theme="dark"]`; Google Fonts link in `index.html`.

- [ ] Write the `format.test.ts` cases above, plus `App.test.tsx`: mock `fetch` → status text "Backend is up"; failure → "Backend is down"; clicking the toggle sets `document.documentElement.dataset.theme` to `"dark"`. Expect FAIL, implement, expect PASS (`npx vitest run --root dashboard`).
- [ ] Commit `feat: dashboard shell with brand themes and health status`.

### Task 1.4: e2e, hooks, container, docs

**Files:** Create `playwright.config.ts` (`webServer`: backend on 8000 with `DATA_DIR` pointing to a temp dir, Vite on 5173), `e2e/health.spec.ts`, `lefthook.yml`, `Containerfile`, `compose.yaml`, `.containerignore`; modify `backend/main.py` (serve `dashboard/dist` at `/` when the folder exists), `docs/TECH_STACK.md` (drop the claim-id line, Python 3.12), `docs/STATUS.md`, `README.md`.

- [x] `e2e/health.spec.ts`: page shows "Backend is up"; after the theme toggle, the body background is `rgb(25, 27, 46)`.
- [x] `lefthook.yml` pre-commit runs in parallel: `uv run ruff format --check`, `uv run ruff check`, `npx pyright`, `uv run pytest -q`, `npx prettier --check -u dashboard e2e *.config.*`, `npx eslint dashboard e2e *.config.*`, `npx tsc`, `npx vitest run --root dashboard --coverage`.
- [x] `Containerfile`: stage 1 `node:26` runs `npm ci && npx vite build dashboard`; stage 2 `python:3.12-slim` with uv runs `uv sync --frozen --no-dev`, copies `backend/`, `agent/` and `dashboard/dist`, sets `DATA_DIR=/data`, `EXPOSE 8000`, CMD uvicorn. `compose.yaml`: one service, port `8000:8000`, volume `./data:/data:Z`, `env_file: .env`, healthcheck on `/api/health`.
- [x] Add a backend test `test_serves_dashboard_when_built` (a tmp `dist/index.html` is served at `/`).
- [x] Commit `chore: e2e, pre-commit hooks, container`.

**Phase 1 success criteria**
- [x] `uv run python --version` prints `Python 3.12.x`; `uv run python -c "import pymupdf"` exits 0.
- [x] `npm run check` passes (Python and TS coverage both ≥80%, e2e green).
- [x] `npm run dev`, then `curl -s localhost:8000/api/health` → `{"status":"ok"}`.
- [x] `podman build -t retirement-studio -f Containerfile .` succeeds; `podman compose up -d`, then `curl -s localhost:8000/api/health` → `{"status":"ok"}`, and `curl -s localhost:8000/` returns HTML containing `<div id="root">`.
- [x] Playwright MCP: the dashboard at `localhost:5173` shows "Backend is up" in both themes, and the colors match `docs/BRAND.md`.
- [x] `git commit` on a staged file runs the lefthook checks (visible in output).

---

## Phase 2: Household profile

### Task 2.1: Profile model and API

**Files:** Create `backend/profile/{__init__,models,api}.py`, `backend/tests/test_profile.py`.

**Interfaces — Produces (Pydantic, all money in today's dollars as `float`):**
- `Person`: `first_name: str`, `birth_date: date`, `retirement_age: int` (50–80), `plan_to_age: int = 82` (must be > current age), `wages: float = 0`, `contribution_401k: float = 0` (employee plus match, per year), `ss_at_62: float`, `ss_at_fra: float`, `ss_at_70: float` (monthly), `ss_claim_age: int | None` (62–70, `None` lets the search choose), `pension_annual: float = 0`, `pension_start_age: int | None`, `pension_survivor_pct: float = 0`.
- `Account`: `id: str`, `kind: Literal["pretax", "roth", "taxable", "cash", "hsa"]`, `owner: Literal["self", "spouse"]`, `label: str`, `balance: float >= 0`, `cost_basis: float = 0` (taxable only), `last4: str | None`, `as_of: date`.
- `Spending`: `essential: float`, `discretionary: float = 0`, `cobra_monthly: float = 0`, `bridge_monthly: float = 0`, `bridge_is_aca: bool = False`, `one_time: list[OneTime(year: int, amount: float, label: str)] = []`.
- `Assumptions`: `return_rate=0.06`, `inflation=0.025`, `ss_cola=0.025`, `volatility=0.12`, `heir_tax_rate=0.22`.
- `Household`: `self_: Person` (alias `"self"`), `spouse: Person | None`, `state: Literal["CO"] = "CO"`, `accounts: list[Account]`, `spending: Spending`, `assumptions: Assumptions`, `home_value: float = 0`, `mask_terms: list[str] = []`. Property `filing_status -> Literal["single", "mfj"]`.
- `GET /api/profile` → `Household` or 404; `PUT /api/profile` → saved `Household`.
- `profile.api.load_household(conn) -> Household | None` (used by later phases).
- Fixture `sample_household() -> Household` in `backend/tests/conftest.py`: self born 1963-06-15, retiring at 63, spouse born 1965-03-01, pretax $900,000.00, roth $60,000.00, taxable $250,000.00 with basis $150,000.00, cash $40,000.00, essential $60,000.00, discretionary $15,000.00, COBRA $1,800.00 a month. Later phases reuse it.

- [ ] Tests: `test_put_then_get_roundtrip`; `test_get_without_profile_404`; `test_negative_balance_422`; `test_plan_to_age_not_above_current_age_422`; `test_filing_status_follows_spouse`. Expect FAIL, implement, expect PASS.
- [ ] Commit `feat: household profile API`.

### Task 2.2: Profile form

**Files:** Create `dashboard/src/types.ts` (mirrors 2.1), `dashboard/src/pages/ProfilePage.tsx`, `dashboard/src/components/MoneyInput.tsx`, tests beside them; `e2e/profile.spec.ts`.

**Interfaces — Produces:** `ProfilePage` with steps "You", "Spouse", "Income", "Accounts", "Spending", "Assumptions", plus Back and Next buttons and "Save" on the last step. Once a profile exists, it opens as a single editable page with every section. `MoneyInput` shows `$1,250.00` when not focused and accepts plain digits.

- [x] Tests: the stepper advances and keeps values; Save sends the JSON shape from 2.1 to `PUT /api/profile`; a 422 shows the field message next to the field; "Add spouse" and "Remove spouse" toggle the spouse section; `MoneyInput` formats on blur. In e2e, fill the form with the `sample_household` values, save, reload, and the values persist.
- [x] Commit `feat: guided profile form`.

**Phase 2 success criteria**
- [x] `npm run check` passes.
- [x] `curl -X PUT localhost:8000/api/profile -d @sample.json` followed by `GET` returns the same body; a negative balance returns 422 with a `balance` error.
- [x] Playwright MCP: complete the six steps, reload, every value is shown with money as `$900,000.00`; the dark theme reads correctly.

---

## Phase 3: Rules file and projection engine

### Task 3.1: Rules schema, seed file and loader

**Files:** Create `backend/rules/{__init__,models,store}.py`, `backend/rules/seed/retirement_rules_2026-01-01.md`, `backend/tests/test_rules_store.py`.

**Interfaces — Produces:**
- `TaxRules` (Pydantic): `year: int`, `sources: list[str]`, `federal_brackets: dict[FilingStatus, list[Bracket(rate: float, up_to: float | None)]]`, `standard_deduction: dict[FilingStatus, float]`, `additional_65: dict[FilingStatus, float]` (per person), `senior_deduction: SeniorDeduction | None` (`amount_per_person`, `phaseout_start: dict[FilingStatus, float]`, `phaseout_rate`, `last_year`), `ltcg_brackets: dict[FilingStatus, list[Bracket]]`, `ss_taxation_thresholds: dict[FilingStatus, tuple[float, float]]`, `rmd_start_ages: list[RmdStart(born_from: int, born_to: int | None, age: int)]`, `uniform_lifetime_table: dict[int, float]`, `part_b_base_monthly: float`, `irmaa: dict[FilingStatus, list[IrmaaTier(magi_over: float, part_b_monthly: float, part_d_monthly: float)]]`, `ss_reduction: SsReduction` (`own_first_36_per_month`, `own_after_per_month`, `spousal_first_36_per_month`, `spousal_after_per_month`, `delayed_credit_per_year`), `colorado: ColoradoRules` (`rate`, `retirement_subtraction: list[AgeCap(min_age, max_age: int | None, cap)]`, `ss_full_subtraction_min_age: int`).
- `store.parse_rules(markdown: str) -> TaxRules`: reads the single fenced ```` ```json ```` block, and raises `RulesFormatError` if it is missing or invalid.
- `store.current_rules(conn, data_dir) -> tuple[TaxRules, str]`: the newest `accepted` file under `data_dir/rules/`, else the seed. Returns the rules and their filename.
- The seed file holds the 2026 figures from the official IRS, SSA, CMS and Colorado DOR pages, each section with its source URL. The implementer must copy the figures from those pages, not from memory.

- [ ] Tests: `test_seed_parses` (year 2026, mfj brackets ascending, last `up_to` is None); `test_missing_json_block_raises`; `test_current_rules_falls_back_to_seed`; `test_current_rules_prefers_newest_accepted`.
- [ ] Commit `feat: rules schema with seed rules file`.

### Task 3.2: Tax functions

**Files:** Create `backend/engine/{__init__,tax}.py`, `backend/tests/test_tax.py`.

**Interfaces — Produces** (all pure; `rules_for_year(rules, year, inflation) -> TaxRules` inflates every dollar threshold by `(1+inflation)^(year-rules.year)` for later years; RMD tables, rates and SS thresholds are not inflated):
- `taxable_social_security(ss: float, other_income: float, filing: FilingStatus, rules) -> float` (provisional = other + 0.5·ss, statutory two-tier formula, capped at 0.85·ss).
- `federal_tax(ordinary: float, ltcg: float, filing, ages: list[int], year: int, rules) -> FederalTax(taxable_income, tax, marginal_rate)`: standard deduction + `additional_65` per person 65+ + senior deduction if `year <= last_year`; ltcg stacked on top of ordinary.
- `bracket_top(rate: float, filing, ages, year, rules) -> float`: the gross ordinary income that fills the bracket at `rate` (deductions included).
- `colorado_tax(federal_taxable: float, taxable_ss: float, retirement_income: float, ages: list[int], rules) -> float`.
- `irmaa_annual(magi_two_years_prior: float, filing, people_65_plus: int, rules) -> float` (surcharge above base, both parts, ×12 per person).
- `rmd(balance: float, age: int, rules) -> float` = balance / table[age]; `rmd_start_age(birth_year: int, rules) -> int`.

- [ ] Tests (values from the statutory formula or the seed table):
  - `test_ss_taxation_mfj`: ss 40,000, other 30,000 → 11,100.00.
  - `test_ss_taxation_below_threshold_zero`: ss 30,000, other 10,000, mfj → 0.
  - `test_ss_taxation_capped_at_85pct`.
  - `test_rmd_age_75`: balance 500,000 → 20,325.20 (divisor 24.6).
  - `test_rmd_start_age`: born 1963 → 75; born 1955 → 73.
  - `test_federal_tax_zero_below_deduction`.
  - `test_bracket_top_fills_12pct` (federal_tax at `bracket_top(0.12)` has marginal 0.12; adding $1 more gives 0.22).
  - `test_ltcg_zero_rate_inside_bracket`.
  - `test_rules_for_year_inflates_thresholds` (2030 mfj standard deduction = 2026 value × 1.025^4).
  - `test_colorado_subtraction_caps_by_age`.
  - `test_irmaa_zero_below_first_tier`.
- [ ] Commit `feat: federal, Colorado, IRMAA and RMD tax functions`.

### Task 3.3: Social Security and yearly projection

**Files:** Create `backend/engine/{social_security,projection}.py`, `backend/plan/{__init__,api}.py`, tests `backend/tests/test_social_security.py`, `backend/tests/test_projection.py`.

**Interfaces — Produces:**
- `social_security.monthly_benefit(person: Person, claim_age: int) -> float`: linear interpolation between `ss_at_62`, `ss_at_fra` (FRA 67 for born 1960+, 66–67 by month per SSA for earlier years) and `ss_at_70`.
- `social_security.spousal_topup(own: Person, other: Person, claim_age: int, rules) -> float` = `max(0, 0.5·other.ss_at_fra − own.ss_at_fra)` reduced by `ss_reduction` spousal factors before FRA. It is paid only once both have claimed.
- `Strategy` (frozen dataclass): `conversion_target: Literal["none", "12", "22", "24", "irmaa1"]`, `convert_from_age: int`, `convert_to_age: int`, `withdrawal_order: Literal["taxable_first", "pretax_first", "proportional"]`, `claim_ages: tuple[int, int | None]`, `extra_spending: float = 0`. Method `label() -> str`, for example `"Fill 12% bracket 63-72, taxable first, claim 67/67"`.
- `YearRow`: `year`, `ages`, `wages`, `social_security`, `pension`, `rmd`, `conversion`, `withdrawals: dict[str, float]` (by account kind), `spending`, `health_premiums`, `federal_tax`, `state_tax`, `irmaa`, `balances: dict[str, float]`, `magi`.
- `Projection`: `rows: list[YearRow]`, `lifetime_tax: float` (federal + state + IRMAA, in today's dollars), `after_tax_end: float` (today's dollars; pretax × (1 − heir_tax_rate)), `shortfall_year: int | None`.
- `projection.project(h: Household, s: Strategy, rules: TaxRules, start_year: int, returns: list[float] | None = None) -> Projection` (`returns=None` uses `assumptions.return_rate` every year).
- `POST /api/plan/project` (body `Strategy`) → `Projection` for the saved household and current rules.

Yearly order (fixed here because the tests do not decide it): (1) wages and 401(k) contributions until each retirement age; (2) Social Security from the claim age with COLA, spousal top-up, survivor keeps the larger benefit, pension with survivor percent; (3) RMD from `rmd_start_age`, using the survivor's age after a death; (4) conversion within `[convert_from_age, convert_to_age]` of the older living person = `max(0, target_ceiling − ordinary income so far)`, where `irmaa1` means first IRMAA threshold − $1,000; (5) spending = (essential + discretionary + extra) inflated + one-time + health premiums (COBRA for 18 months from retirement, then bridge until 65, then Part B base) + last year's tax bill; (6) cover the gap from accounts in the strategy order, cash always first; taxable withdrawals realize gain pro-rata to basis; tax is grossed up by iterating up to 20 times until it changes by less than $1; (7) apply returns (cash grows at inflation); (8) when a person passes `plan_to_age`, their accounts roll to the survivor and filing becomes `single` the following year. The plan ends after the last living person's `plan_to_age`. `shortfall_year` is the first year the gap cannot be covered; rows continue with zero balances.

- [x] Tests:
  - `test_monthly_benefit_interpolates` (claim 65 between the 62 and 67 values).
  - `test_spousal_topup_when_low_own_benefit`.
  - `test_spousal_topup_zero_when_own_high`.
  - `test_project_rows_span_to_last_plan_to_age`.
  - `test_no_conversion_strategy_has_zero_conversions`.
  - `test_fill_12_conversion_hits_bracket_top`.
  - `test_rmd_starts_at_75_for_1963`.
  - `test_cobra_then_bridge_then_part_b`.
  - `test_survivor_files_single_and_keeps_larger_benefit`.
  - `test_already_retired_person_starts_now` (Review Focus).
  - `test_overspending_reports_shortfall_without_error` (Review Focus).
  - `test_deterministic_same_inputs_same_output`.
  - API: `test_project_endpoint_returns_rows` (needs a saved profile; 409 without one).
- [x] Commit `feat: year-by-year projection engine`.

**Phase 3 success criteria**
- [x] `npm run check` passes.
- [x] `uv run pytest backend/tests/test_tax.py backend/tests/test_projection.py --no-cov -q` passes.
- [x] With the sample profile saved, `curl -X POST localhost:8000/api/plan/project -H 'content-type: application/json' -d '{"conversion_target":"12","convert_from_age":63,"convert_to_age":74,"withdrawal_order":"taxable_first","claim_ages":[67,67]}'` returns rows from 2026 to the spouse's plan-to year, with non-zero `conversion` from age 63. The same call with `"conversion_target":"none"` has `rmd` starting in 2038. (Amended during the build: under fill-12% the sample's pretax balance is fully converted or spent by 2035, so no RMD is due.)
- [x] Hand check: one row's federal tax recomputed by hand from the seed brackets matches within $1.00. Record the check in `docs/STATUS.md`.

---

## Phase 4: Strategy search, what-if, safe spending, Plan page

### Task 4.1: Search, what-if and safe extra spending

**Files:** Create `backend/engine/{search,whatif,spending}.py`, tests for each; extend `backend/plan/api.py`.

**Interfaces — Produces:**
- `search.strategy_grid(h: Household, rules) -> list[Strategy]`. Conversion targets are all five. `convert_from_age` is the retirement age or retirement + 2. `convert_to_age` is 70 or RMD start − 1. Every withdrawal order is included. Claim ages are 62, FRA and 70 for each person, or only the fixed claim age when a person has one set. `"none"` collapses the from/to ages. Duplicates are removed.
- `search.rank(h, rules, start_year) -> list[RankedStrategy(strategy, projection)]`: sorted by a key where plans that last (`shortfall_year is None`) come before those that run short, then higher `after_tax_end`, then lower `lifetime_tax`.
- `whatif.success_rate(h, s, rules, start_year, paths=1000, seed=7) -> float`: yearly returns are drawn from `random.Random(seed)` normal(`return_rate`, `volatility`); success means no shortfall.
- `spending.safe_extra(h, s, rules, start_year) -> float`: bisection on `extra_spending` between 0 and $200,000.00 to $100.00 precision; the largest extra amount with no shortfall on the fixed-rate path.
- `GET /api/plan` → `PlanResult`: `rules_file`, `rules_stale: bool`, `top: list[PlanOption(strategy, label, lifetime_tax, after_tax_end, shortfall_year, success_rate, safe_extra)]` (the top 5), `baseline: PlanOption` (the best `"none"` strategy, for comparison), `best_rows: list[YearRow]`.

- [ ] Tests:
  - `test_grid_size_and_no_duplicates` (sample household; size between 100 and 700).
  - `test_rank_prefers_lasting_plans`.
  - `test_conversions_beat_none_for_sample` (the best strategy is not `"none"`, and its `after_tax_end` > baseline).
  - `test_success_rate_repeatable_with_seed`.
  - `test_success_rate_zero_when_spending_impossible`.
  - `test_safe_extra_is_boundary` (`safe_extra` has no shortfall; +$200.00 runs short).
  - `test_plan_endpoint_shape`.
  - `test_plan_endpoint_runtime_under_20s` (sample household, marked `slow`; it still runs in the default suite).
- [ ] Commit `feat: strategy search, what-if success rate, safe extra spending`.

### Task 4.2: Plan page

**Files:** Create `dashboard/src/pages/PlanPage.tsx`, `dashboard/src/components/{StrategyTable,YearTable,BalanceChart}.tsx`, tests; add `recharts`; `e2e/plan.spec.ts`.

**Interfaces — Produces:** The Plan page calls `GET /api/plan` and shows:
- A headline: the best strategy label, lifetime tax, after-tax money at the plan-to age, and "You can safely spend $X more per year" with "Works in N% of market paths".
- A comparison table of the top 5 plus the "No conversions" baseline.
- The year-by-year table, with columns Year, Ages, Social Security, Withdrawals (with source), Roth conversion, Tax, Spending and End balance, all numbers in JetBrains Mono and `formatUsd`.
- A stacked area chart of balances by account kind using brand colors.
- A notice "Rules are out of date" when `rules_stale`.
- A notice when the bridge is ACA: "Roth conversions before 65 may reduce your ACA premium subsidy. This plan does not include it."
- "Complete your profile first" when there's no profile, and "Calculating plan" while loading.

- [x] Tests: the headline renders from a mocked `PlanResult`; the table shows `$1,250.00` formatting; the ACA notice appears only when `bridge_is_aca`; the empty state appears on 409. In e2e, save the sample profile, open Plan, and see the headline and at least 20 table rows.
- [x] Commit `feat: plan page with strategy comparison and year table`.

**Phase 4 success criteria**
- [x] `npm run check` passes.
- [x] `time curl -s localhost:8000/api/plan` finishes in under 20 s for the sample profile. The response has 5 `top` entries, each with `0 <= success_rate <= 1` and `safe_extra >= 0`, and the top entry's `after_tax_end` is at least the baseline's.
- [x] Two identical `GET /api/plan` calls return identical JSON.
- [x] Playwright MCP: the Plan page shows the headline, comparison table, year table and chart in both themes, with no exclamation marks in the text.

---

## Phase 5: IRS rules research agent and Rules page

### Task 5.1: Rules API with pending review

**Files:** Create `backend/rules/api.py`; extend `store.py`; `backend/tests/test_rules_api.py`.

**Interfaces — Produces:**
- `store.save_pending(conn, data_dir, markdown: str, today: date) -> str` writes `data_dir/rules/retirement_rules_YYYY-MM-DD.md` with status `pending`.
- `store.accept(conn, filename)`.
- `store.diff(old: TaxRules, new: TaxRules) -> list[Change(path: str, old: str, new: str)]` (flattened dotted paths, values formatted).
- `store.status(conn, data_dir, today) -> RulesStatus(current_file, current_date, age_days, stale, pending_file | None, changes: list[Change])`, where `stale` is `age_days > 90`. The seed's date counts as its file date.
- Routes:
  - `GET /api/rules/status`
  - `GET /api/rules/{filename}` (the markdown)
  - `POST /api/rules` (body `{"markdown": str}`; 422 on `RulesFormatError`)
  - `POST /api/rules/{filename}/accept`
  - `POST /api/rules/refresh` (starts `agent.rules_research.refresh` as a FastAPI background task and returns 202)

- [ ] Tests:
  - `test_post_valid_rules_is_pending_not_current`.
  - `test_post_malformed_rules_422_keeps_current` (Review Focus).
  - `test_accept_makes_current`.
  - `test_diff_lists_changed_bracket`.
  - `test_stale_after_90_days`.
  - `test_refresh_returns_202` (monkeypatch the agent function).
- [ ] Commit `feat: rules API with pending review and staleness`.

### Task 5.2: Research agent

**Files:** Create `agent/rules_research.py`, `agent/tests/test_rules_research.py`.

**Interfaces — Produces:**
- `SOURCES: list[str]`: official pages only. Include the IRS inflation adjustments release for the current year, IRS RMD and Uniform Lifetime Table (Pub 590-B), SSA benefit reduction and spousal pages, the CMS Part B premium and IRMAA fact sheet, the Colorado DOR pension/annuity subtraction and Social Security subtraction pages, and the IRS senior deduction page.
- Tools: `fetch_page(url: str) -> str` (rejects URLs not in `SOURCES`; httpx GET; BeautifulSoup text, truncated to 40,000 characters); `current_rules() -> str` (`GET` of the current file via the backend); `save_rules(markdown: str) -> str` (`POST /api/rules`, returns the status or the 422 message so the agent can fix and retry).
- `refresh(client: httpx.Client | None = None, model: BaseChatModel | None = None) -> str`. The system prompt asks for the same headings and JSON schema as the current file, a source URL for every section, and today's date.

- [ ] Tests (stub model, backend `TestClient`, `httpx.MockTransport` for pages):
  - `test_refresh_saves_pending_file` (the stub calls `fetch_page` then `save_rules` with a valid seed-derived file).
  - `test_fetch_page_rejects_unlisted_url`.
  - `test_save_rules_reports_422_to_agent`.
- [ ] Commit `feat: rules research agent`.

### Task 5.3: Rules page

**Files:** Create `dashboard/src/pages/RulesPage.tsx` and its test; `e2e/rules.spec.ts`.

**Interfaces — Produces:** The page shows the current rules date and age in days, the source list, a "Refresh rules" button (`POST /api/rules/refresh`, then shows "Research started. Check back in a few minutes."), and the pending review: a table of path, old value and new value, with "Accept" and "Keep current" buttons. A stale banner, "Rules are out of date", appears here and on the Plan page.

- [x] Tests: the stale banner shows when `stale`; Accept posts to the accept route and refreshes status; no pending section appears without a pending file. In e2e, `POST /api/rules` a modified seed through the API, open Rules, see the change row, Accept, and the current date updates.
- [x] Commit `feat: rules review page`.

**Phase 5 success criteria**
- [x] `npm run check` passes.
- [x] `curl -X POST localhost:8000/api/rules -d '{"markdown":"no json"}'` → 422, and `GET /api/rules/status` still shows the seed.
- [x] Live run, the only step that calls a real model, done by hand with `.env` set: `uv run python -c "from agent.rules_research import refresh; print(refresh())"` creates a pending file in `data/rules/` whose JSON validates, and the Rules page lists its changes. Record the outcome and cost in `docs/STATUS.md`.
- [x] Playwright MCP: the review flow from the e2e test works in both themes.

---

## Phase 6: Statement extraction and container release

### Task 6.1: PDF text and masking

**Files:** Create `backend/statements/{__init__,pdf,api}.py`, `backend/tests/test_statements.py`. Fixture PDFs are generated in tests with pymupdf from made-up text; no real statements are committed.

**Interfaces — Produces:**
- `pdf.extract_text(path: Path) -> str` (pymupdf, pages joined).
- `pdf.mask(text: str, terms: list[str]) -> str`: digit runs of 6 or more (spaces and dashes allowed inside) become `****` plus the last 4 digits; each term is replaced with `[MASKED]`, case-insensitive.
- Routes:
  - `POST /api/statements` (multipart field `files`, one or more files; each PDF is saved to `data_dir/statements/` with status `uploaded`; returns `list[UploadResult(filename, id: int | None, error: str | None)]`; a non-PDF or duplicate filename gets an `error` while the other files are still saved). PDFs copied straight into that folder are picked up by `POST /api/statements/scan`.
  - `GET /api/statements`
  - `GET /api/statements/{id}/text` (masked text; sets status `no_text` and returns 422 when empty)
  - `PUT /api/statements/{id}/extraction` (body `ExtractedDocument`; status `pending_review`)
  - `POST /api/statements/{id}/accept` (body: the edited `ExtractedDocument`; status `accepted`). For an account statement, it upserts profile accounts matched by `kind` + `owner` + `last4`, otherwise appends. For a Social Security statement, it sets `ss_at_62`, `ss_at_fra` and `ss_at_70` on the person chosen in the body's `person: "self" | "spouse"`.
  - `POST /api/statements/{id}/extract` (background agent run, 202)
- `ExtractedDocument` is a union discriminated by `doc_type`:
  - `ExtractedStatement`: `doc_type: Literal["account"]`, `institution: str`, `statement_date: date`, `accounts: list[ExtractedAccount(kind, owner_hint: str, label, balance, cost_basis: float | None, last4: str | None)]`.
  - `ExtractedSsStatement`: `doc_type: Literal["social_security"]`, `statement_date: date`, `person: Literal["self", "spouse"] | None` (set at review), `monthly_at_62: float`, `monthly_at_fra: float`, `fra_age: str` (for example `"67"`), `monthly_at_70: float`. These are the "estimated monthly benefit" figures on the ssa.gov statement.

- [ ] Tests:
  - `test_extract_text_from_generated_pdf`.
  - `test_mask_account_numbers_keeps_last4` (`"Account 1234-5678-9012"` → `"Account ****9012"`).
  - `test_mask_ssn_keeps_last4` (`"SSN 123-45-6789"` → `"SSN ****6789"`).
  - `test_mask_terms_case_insensitive`.
  - `test_image_only_pdf_sets_no_text` (Review Focus; the PDF has a drawn rectangle and no text).
  - `test_accept_updates_matching_account_balance`.
  - `test_accept_appends_new_account`.
  - `test_accept_ss_statement_sets_spouse_estimates`.
  - `test_accept_ss_statement_without_person_422`.
  - `test_upload_multiple_files_returns_one_result_each`.
  - `test_upload_mixed_batch_saves_pdfs_and_reports_non_pdf` (3 files, one `.txt` → 2 ids and 1 error).
- [ ] Commit `feat: statement upload, text extraction and masking`.

### Task 6.2: Extraction agent

**Files:** Create `agent/extraction.py`, `agent/tests/test_extraction.py`.

**Interfaces — Produces:** `extract(statement_id: int, client: httpx.Client | None = None, model: BaseChatModel | None = None) -> ExtractedDocument | None`. It gets the masked text over the API, runs `create_agent` with `response_format=ExtractedDocument` and no tools, and `PUT`s the result. The system prompt tells the model to choose `social_security` for an ssa.gov "Your Social Security Statement" and `account` otherwise. When the text route returns 422, it returns `None` without calling the model.

- [ ] Tests:
  - `test_extract_puts_pending_review` (the stub returns an account statement).
  - `test_extract_social_security_statement` (the stub returns `doc_type="social_security"`; the stored extraction has the three monthly figures).
  - `test_no_text_skips_model` (the stub asserts it was never called).
  - `test_model_never_sees_unmasked_number` (capture the stub's input messages; the full account number is absent).
- [ ] Commit `feat: statement extraction agent`.

### Task 6.3: Statements page and release checks

**Files:** Create `dashboard/src/pages/StatementsPage.tsx` and its test; `e2e/statements.spec.ts`; update `README.md` (setup, `podman compose up`, where to put PDFs) and `docs/STATUS.md`.

**Interfaces — Produces:**
- The upload area accepts several PDFs at once, by drag and drop or a "Choose files" button (`<input type="file" multiple accept="application/pdf">`). It shows one result line per file: saved, or the error.
- An "Extract all" button starts extraction for every `uploaded` file.
- The statement list shows status labels: "Uploaded", "Reading", "Ready to review", "No text found", "Accepted".
- The review form depends on `doc_type`:
  - Account statements get editable rows (kind, owner, label, balance and basis shown in `formatUsd`).
  - Social Security statements show "Whose statement is this?" (You or Spouse, required) and the three editable monthly amounts.
- Both forms have "Accept" and "Discard" buttons, and the page shows "Nothing is saved until you accept."

- [ ] Tests:
  - Dropping 3 files sends one multipart request with 3 `files` parts and lists 3 results.
  - A rejected file shows its error while the others show as saved.
  - The account review form edits a balance before Accept and sends the edited value.
  - The Social Security form blocks Accept until a person is chosen.
  - "No text found" shows for `no_text`.
  - e2e: upload two generated PDFs in one action, then `PUT` an account extraction and a Social Security extraction through the API (no model). Review and accept both. The Profile page shows the new balance and the spouse's new Social Security estimates.
- [ ] Commit `feat: statements review page`.

**Phase 6 success criteria**
- [ ] `npm run check` passes.
- [ ] `podman build` and `podman compose up -d` work. Inside the container, `/api/health` is ok, the dashboard loads at `localhost:8000`, a profile saved through the UI survives `podman compose down && podman compose up -d` (stored in `./data/studio.db`), and an uploaded PDF appears in `./data/statements/`.
- [ ] Live run by hand with `.env`: upload one real account statement and one real Social Security statement together, run "Extract all", review, accept, and the Plan page updates. Record the outcome in `docs/STATUS.md` with no account details.
- [ ] Playwright MCP: Profile, Plan, Rules and Statements pages all render in both themes; money everywhere looks like `$1,250.00`; no exclamation marks.
- [ ] `docs/STATUS.md` describes everything built and how to run it; the chat agent is listed as next, in `docs/PLAN_CHAT.md`.
