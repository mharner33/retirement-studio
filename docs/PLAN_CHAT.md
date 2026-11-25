# Planning Chat Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. `docs/PROCESS.md` is binding: build phases in order, check every success criterion, tick it here, update `docs/STATUS.md`, commit.

**Goal:** A Chat page where the owner asks plain-English questions about their plan, gets answers whose every figure comes from the engine, the rules file or a cited official source, and applies proposed profile changes with one click.

**Architecture:** The backend gains a what-if route (the plan on a changed copy of the saved profile), chat storage with masking, and a background chat turn. `agent/chat.py` runs `create_agent` with tools that reach data only over the backend API, checks every figure in its reply against tool results in code, and posts the reply. The dashboard polls the conversation every 2 s.

**Tech Stack:** As the pilot (`docs/PLAN.md`): FastAPI, stdlib `sqlite3`, Pydantic, httpx, LangChain `create_agent` on OpenRouter, React 19, Vite, strict TypeScript, Vitest, Playwright, Podman. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-25-chat-agent-design.md` (builds on `2026-11-24-retirement-studio-design.md`).

## Global Constraints

- Everything in `docs/PLAN.md` Global Constraints still applies (uv, stub model in tests, `npm run check` at 80% coverage on both sides, no rule changes, no `--no-verify`, never push, agents reach data only through the backend HTTP API, strict TS with no `any`, `docs/BRAND.md`, money as `$1,250.00`, no exclamation marks).
- The model never does arithmetic: every dollar amount and percentage in a saved reply must match a tool result, or the reply carries the note "Some figures could not be checked."
- Nothing reaches the model with a first name, a `mask_terms` entry or a full account number. Placeholders are `[YOU]`, `[SPOUSE]` and `[MASKED]`.
- No profile change is saved without the owner clicking Apply.
- Figures from outside the engine and rules file cite an official URL from the chat source list.
- Copy: "Ask about your plan", "Send", "New conversation", "Apply", "Applied", "Dismiss", "Dismissed", "Some figures could not be checked.", "This reply did not finish. Ask again.", "Complete your profile first".

## Review Focus

- A what-if or proposed change that breaks validation (claim age 75, `plan_to_age` at or below the current age): the route returns 422 with the field message, the tool hands it to the model, nothing crashes. Test in Task 1.1 and Task 3.2.
- A second message sent while a turn is working (double click, two tabs): 409, and only one agent run starts. Test in Task 2.2.
- The backend restarting, or the model failing, mid-turn: the turn ends as failed and the page shows "This reply did not finish. Ask again." Test in Task 2.2 and Task 4.1.
- A first name that is also part of other words (name "Ann", text "annual"): masking replaces whole words only, and unmasking never touches other text. Test in Task 2.1.
- Apply after the profile was edited in the form since the proposal: Apply changes only the proposed fields on the current saved profile and keeps the other edits. Test in Task 2.2.

---

## File map

```
backend/
  plan/changes.py      ProfileChange types, FIELDS map, apply_changes()
  plan/api.py          + POST /api/plan/whatif, cached plan computation
  chat/__init__.py
  chat/masking.py      mask_for_model(), unmask()
  chat/models.py       chat Pydantic models
  chat/store.py        sqlite reads and writes for messages, changes, turn state
  chat/benchmark.py    spending benchmark lookup
  chat/seed/bls_spending.json
  chat/api.py          /api/chat*
  db.py                + chat tables
  main.py              + chat router, failed-turn recovery at startup
agent/
  pages.py             fetch_text() shared by the rules and chat agents
  numbers.py           unchecked_figures()
  chat.py              respond(), tools, system prompt, SOURCES
dashboard/src/
  pages/ChatPage.tsx, components/ChangeCard.tsx, types.ts (+ chat types), App.tsx (+ Chat)
e2e/chat.spec.ts
```

Builder's calls fixed here (deviations from the design's suggestions, all within "left to the builder"):
- `POST /api/plan/whatif` takes a list of `ProfileChange` and applies it to the saved profile in the backend, instead of a full `Household` body. The agent never needs the unmasked profile, and the change rules live in one place.
- The spending benchmark is a seed file copied by hand from the official BLS Consumer Expenditure Survey tables (as the seed rules file was), with its source URL and table year, served by the backend. BLS pages often refuse automated fetches, and code must pick the band. The reply cites the BLS URL.
- The plan computation is cached in memory by (profile JSON, rules file name, year), 8 entries, so a what-if compares against the current plan without a second 6 s run.
- History sent to the model: the last 20 messages.

---

## Phase 1: Profile changes and what-if route

### Task 1.1: Profile changes and what-if route

**Files:** Create `backend/plan/changes.py`, `backend/tests/test_changes.py`; modify `backend/plan/api.py`, `backend/plan/models.py`, `backend/tests/test_plan.py`.

**Interfaces — Produces:**
- `SetField(op: Literal["set"], path: str, value: float | int | None)`, `AddOneTime(op: Literal["add_one_time"], item: OneTime)`, `RemoveOneTime(op: Literal["remove_one_time"], index: int)`; `ProfileChange` is their union discriminated by `op`.
- `FIELDS: dict[str, FieldInfo(label: str, kind: Literal["money", "age", "rate"])]`. Keys, for `self` and `spouse` (label suffix " (you)" / " (spouse)"): `retirement_age`, `plan_to_age`, `ss_claim_age` (age), `wages`, `contribution_401k`, `pension_annual` (money), `pension_start_age` (age). Plus `spending.essential`, `spending.discretionary`, `spending.cobra_monthly`, `spending.bridge_monthly` (money) and `assumptions.return_rate`, `assumptions.inflation`, `assumptions.ss_cola`, `assumptions.volatility`, `assumptions.heir_tax_rate` (rate). Labels in plain words, for example "Retirement age (you)", "Essential spending per year", "Return rate".
- `ChangeError(ValueError)` with a plain message.
- `apply_changes(h: Household, changes: list[ProfileChange]) -> Household`: returns a new validated household (dump, edit, `Household.model_validate`, `check_plan_to_age`). Raises `ChangeError` for a path not in `FIELDS`, a `spouse.*` path without a spouse, or a bad `remove_one_time` index; Pydantic and `PlanToAgeError` errors become `ChangeError` with the field message.
- `ChangeLine(label: str, kind: Literal["money", "age", "rate"], old: float | None, new: float | None)` and `describe(h: Household, changes: list[ProfileChange]) -> list[ChangeLine]`. A one-time add reads label `"One-time expense {year}: {label}"`, kind money, old None; a remove has new None.
- `plan_for(h: Household, rules: TaxRules, rules_file: str, start_year: int, stale: bool) -> PlanResult`: the body of today's `GET /api/plan`, cached as above. `GET /api/plan` calls it.
- `WhatIfResult(current: PlanResult, whatif: PlanResult, changes: list[ChangeLine])`. `POST /api/plan/whatif` (body `list[ProfileChange]`) → `WhatIfResult`; 409 without a profile; 422 on `ChangeError` with `detail` the message. The saved profile is unchanged.

- [x] Tests in `test_changes.py`:
  - `test_set_retirement_age_returns_new_household` (sample, `self.retirement_age` 65 → 65; the input household still has 63).
  - `test_unknown_path_rejected` (`self.first_name` → `ChangeError`).
  - `test_spouse_path_without_spouse_rejected`.
  - `test_claim_age_out_of_range_rejected` (`self.ss_claim_age` 75 → `ChangeError` whose message names `ss_claim_age`) (Review Focus).
  - `test_plan_to_age_below_current_age_rejected` (Review Focus).
  - `test_add_and_remove_one_time`.
  - `test_describe_lines` (`spending.essential` 60,000 → 70,000 gives `ChangeLine("Essential spending per year", "money", 60000, 70000)`).
- [x] Tests in `test_plan.py`:
  - `test_whatif_retire_at_65` (sample saved; `whatif.best_rows[0]` has wages, `current.best_rows[0]` the same as `GET /api/plan`; `GET /api/profile` still shows 63).
  - `test_whatif_422_on_bad_change` and `test_whatif_409_without_profile`.
  - `test_plan_for_cached` (second call with the same inputs returns the same object without calling `rank`; monkeypatch `rank` to count).
- [x] Run `uv run pytest backend/tests/test_changes.py backend/tests/test_plan.py --no-cov`: FAIL, implement, PASS.
- [x] Commit `feat: profile changes and what-if plan route`.

**Phase 1 success criteria**
- [x] `npm run check` passes.
- [x] With the sample profile saved and the backend running, `curl -s -X POST localhost:8000/api/plan/whatif -H 'content-type: application/json' -d '[{"op":"set","path":"self.retirement_age","value":65}]'` returns `current`, `whatif` and one change line "Retirement age (you)" 63 → 65, and `GET /api/profile` still shows 63.
- [x] The same call with `"path":"self.first_name"` returns 422 with a plain message.
- [x] `time` on the what-if call right after a `GET /api/plan` is under 20 s (the current plan comes from the cache).

---

## Phase 2: Chat storage, masking and routes

### Task 2.1: Masking

**Files:** Create `backend/chat/__init__.py`, `backend/chat/masking.py`, `backend/tests/test_chat_masking.py`.

**Interfaces — Produces:**
- `mask_for_model(text: str, h: Household) -> str`: self first name → `[YOU]`, spouse first name → `[SPOUSE]` (whole words, case-insensitive), then `backend.statements.pdf.mask(text, h.mask_terms)` (terms → `[MASKED]`, long digit runs → last 4).
- `unmask(text: str, h: Household) -> str`: `[YOU]` and `[SPOUSE]` back to the first names. `[MASKED]` stays.

- [x] Tests: `test_masks_first_names_whole_words` (name "Ann": "Ann's annual budget" → "[YOU]'s annual budget") (Review Focus); `test_masks_terms_and_account_numbers`; `test_unmask_restores_names_only`; `test_spouse_placeholder_unused_without_spouse`.
- [x] FAIL, implement, PASS. Commit `feat: chat masking`.

### Task 2.2: Chat store, routes and background turn

**Files:** Create `backend/chat/{models,store,api}.py`, `backend/tests/test_chat_api.py`; modify `backend/db.py`, `backend/main.py`.

**Interfaces — Produces:**
- Tables: `chat_messages(id INTEGER PRIMARY KEY, role TEXT, text TEXT, sources TEXT, tool_results TEXT, unchecked INTEGER, created_at TEXT)`, `chat_changes(id INTEGER PRIMARY KEY, message_id INTEGER, changes TEXT, reason TEXT, status TEXT)` (`proposed`, `applied`, `dismissed`), `chat_turn(id INTEGER PRIMARY KEY CHECK (id = 1), status TEXT, step TEXT)` (`idle`, `working`, `failed`). Text is stored masked.
- Models: `Source(kind: Literal["engine", "rules", "web"], label: str, url: str | None)`; `ChangeCard(id, reason, status, lines: list[ChangeLine], error: str | None)`; `ChatMessage(id, role: Literal["user", "assistant"], text, sources: list[Source], unchecked: bool, changes: list[ChangeCard])`; `ChatState(status, step: str | None, messages: list[ChatMessage])`; `Proposal(changes: list[ProfileChange], reason: str)`; `Reply(text, sources: list[Source], tool_results: list[str], unchecked: bool, proposals: list[Proposal])`; `ContextMessage(role, text, tool_results: list[str])`.
- Owner routes:
  - `GET /api/chat` → `ChatState`, text passed through `unmask`. Change lines are computed by `describe` when the proposal is recorded and stored with it.
  - `POST /api/chat/messages` (body `{"text": str}`, non-blank) → 202. 409 "No profile saved" without a profile; 409 "A reply is in progress" while `working`. Stores the masked text, sets `working`, adds the background task `run_chat()`.
  - `POST /api/chat/changes/{id}/apply` → `ChangeCard`: `apply_changes` on the current saved profile, `save_household`, status `applied`. 422 with the message on `ChangeError` (card stays `proposed`); 409 when not `proposed`. `/dismiss` → `dismissed`.
  - `DELETE /api/chat` → 204, clears messages and changes; 409 while `working`.
- Agent routes (used only by `agent/chat.py`):
  - `GET /api/chat/context` → `list[ContextMessage]`, the last 20 messages, masked.
  - `GET /api/chat/profile` → the saved profile as JSON text passed through `mask_for_model`.
  - `PUT /api/chat/step` (body `{"text": str}`).
  - `POST /api/chat/changes/check` (body `list[ProfileChange]`) → `list[ChangeLine]`, or 422 with the message.
  - `POST /api/chat/reply` (body `Reply`) → stores the assistant message, its proposals with their lines, sets `idle`.
- `run_chat()`: lazily imports `agent.chat.respond` (as `run_extract` does). On any exception it logs and sets the turn to `failed`. If `respond` returns without posting a reply, the turn is also set to `failed`.
- `create_app` sets a `working` turn to `failed` at startup.
- `failed` is cleared to `working` by the next message.

- [x] Tests (monkeypatch `run_chat` where no agent should run):
  - `test_post_message_202_and_stores_masked` (sample name "Alex": text "Can Alex retire at 65" is stored as "Can [YOU] retire at 65"; `GET /api/chat` shows "Can Alex retire at 65"; status `working`).
  - `test_post_message_409_while_working` (Review Focus; the background function was called once).
  - `test_post_message_409_without_profile` and `test_blank_message_422`.
  - `test_reply_sets_idle_and_shows_change_card`.
  - `test_apply_keeps_other_profile_edits` (propose `self.retirement_age` 65; then `PUT /api/profile` with essential 70,000; apply; the profile has both) (Review Focus).
  - `test_apply_invalid_change_422_card_stays_proposed`, `test_apply_twice_409`, `test_dismiss`.
  - `test_context_is_masked_and_limited_to_20`.
  - `test_startup_marks_working_turn_failed` (Review Focus; write `working`, build a new app on the same dir, status `failed`).
  - `test_run_chat_failure_marks_failed` (patch the import to raise).
  - `test_delete_clears_conversation` and `test_delete_409_while_working`.
- [x] FAIL, implement, PASS. Commit `feat: chat storage, routes and background turn`.

### Task 2.3: Spending benchmark

**Files:** Create `backend/chat/benchmark.py`, `backend/chat/seed/bls_spending.json`, `backend/tests/test_benchmark.py`; modify `backend/chat/api.py`.

**Interfaces — Produces:**
- Seed file: `{"source_url", "table_year", "age_groups": [{"label", "min_age", "max_age": int | null, "annual_spending"}], "income_bands": [{"label", "min_income", "max_income": float | null, "annual_spending"}]}`. The figures are average annual expenditures from the latest BLS Consumer Expenditure Survey calendar-year tables, by age of reference person and by income before taxes, copied from the official page, not from memory.
- `Benchmark(source_url, table_year, age_group: str, age_group_annual: float, income_band: str, income_band_annual: float, planned_annual: float)`.
- `benchmark(h: Household, plan: PlanResult) -> Benchmark`: the age group of the older living person today; `planned_annual` is the `spending` of the first row of `plan.best_rows` in which `self` has reached `retirement_age` (the first row if already retired); the income band whose range contains `planned_annual`.
- `GET /api/chat/benchmark` → `Benchmark` (409 without a profile; uses `plan_for`).

- [x] Tests: `test_seed_validates` (bands ascending, last `max_income` None, the source URL is on bls.gov); `test_picks_band_for_planned_spending`; `test_already_retired_uses_first_row`; `test_age_group_of_older_person`.
- [x] FAIL, implement, PASS. Commit `feat: spending benchmark`.

**Phase 2 success criteria**
- [x] `npm run check` passes.
- [x] With the sample profile saved and `run_chat` not yet wired to an agent (the import fails and the turn goes `failed`): `curl -X POST localhost:8000/api/chat/messages -H 'content-type: application/json' -d '{"text":"Can Alex retire at 65"}'` → 202; then `GET /api/chat` shows the message with "Alex" and status `failed`; `sqlite3 data/studio.db "select text from chat_messages"` shows "[YOU]".
- [x] `GET /api/chat/benchmark` returns an age group, an income band and the BLS URL.

---

## Phase 3: Chat agent

### Task 3.1: Shared page fetching and the number check

**Files:** Create `agent/pages.py`, `agent/numbers.py`, `agent/tests/test_numbers.py`; modify `agent/rules_research.py` (use `pages.fetch_text`; its tests stay green unchanged).

**Interfaces — Produces:**
- `pages.fetch_text(web: httpx.Client, url: str, allowed: list[str], find: str = "") -> str`: the existing `fetch_page` body from `rules_research.py` (rejection message, PDF text, `find`, 40,000-character cut), with `allowed` as a parameter. `USER_AGENT` and `make_web_client()` move here too.
- `numbers.unchecked_figures(reply: str, tool_texts: list[str]) -> list[str]`: the dollar tokens (`$` followed by digits with optional commas and cents) and percent tokens (digits with optional decimals followed by `%`) in `reply` that match no number in `tool_texts`. Numbers in tool texts are every `$` token, every `%` token and every bare number. A dollar token matches a tool number equal to it in cents, or equal after rounding to whole dollars when the token has no cents. A percent token `p` matches a tool number `v` when `v` or `v × 100` rounds to `p` at the token's decimal places. Ages, years and other bare numbers in the reply are not checked. Returns tokens as written.

- [x] Tests: `test_matches_formatted_money` (`"$1,248,000.00"` vs `"1248000.0"` → `[]`); `test_matches_whole_dollars` (`"$86,000"` vs `"85999.6"` → `[]`); `test_flags_invented_money` (`"$86,000.00"` vs `"85000"` → `["$86,000.00"]`); `test_matches_rate_as_percent` (`"6.2%"` vs `"0.062"` → `[]`); `test_ignores_years_and_ages` (`"In 2030 at 67"` → `[]`).
- [x] FAIL, implement, PASS; `uv run pytest agent --no-cov` still green. Commit `refactor: shared page fetching; feat: figure check`.

### Task 3.2: Chat agent

**Files:** Create `agent/chat.py`, `agent/tests/test_chat_agent.py`.

**Interfaces — Consumes:** the agent routes of Task 2.2, `POST /api/plan/whatif`, `POST /api/plan/project`, `GET /api/plan`, `GET /api/chat/benchmark`, `GET /api/rules/status` and `GET /api/rules/{file}`, `pages.fetch_text`, `numbers.unchecked_figures`.

**Interfaces — Produces:**
- `SOURCES: list[str]`, official pages only: Medicare.gov costs (Parts A, B, D), Medigap costs, the CMS 2026 Part B premium fact sheet (already in the rules agent list), Medicaid.gov eligibility, Colorado Health First Colorado eligibility, and the BLS Consumer Expenditure tables page. The builder confirms each URL loads with `fetch_text` and records in `docs/STATUS.md` any that refuse automated fetches.
- `respond(client: httpx.Client | None = None, model: BaseChatModel | None = None, web: httpx.Client | None = None) -> None`, following the `refresh` client pattern.
- Tools (results are text; money already formatted as `$1,250.00` and rates as percentages by code, so the model can copy them):
  - `get_profile()`: `GET /api/chat/profile`.
  - `get_plan()`: summary of `GET /api/plan`: best label, lifetime tax, after-tax money at the end, safe extra per year and per month, success rate, shortfall year, the baseline the same way, and per-year rows (year, ages, Social Security, conversion, tax, spending, end balance).
  - `run_whatif(changes: list[ProfileChange])`: `POST /api/plan/whatif`; current and what-if summaries side by side and each difference computed in code. A 422 returns `"Rejected: <message>"`.
  - `run_strategy(strategy: Strategy)`: `POST /api/plan/project`, compared in code with the current best strategy's projection (lifetime tax, after-tax money, shortfall year and differences).
  - `spending_benchmark()`: `GET /api/chat/benchmark`, including the monthly figures (annual ÷ 12, in code) and the BLS URL.
  - `get_rules()`: the current rules markdown.
  - `fetch_page(url: str, find: str = "")`: `fetch_text(web, url, SOURCES, find)`.
  - `propose_change(changes: list[ProfileChange], reason: str)`: `POST /api/chat/changes/check`; on 200 keeps the proposal for the reply, on 422 returns the message.
  - `report_step(text: str)`: `PUT /api/chat/step`.
- Sources are collected in code from the tools called: `get_plan`, `run_whatif`, `run_strategy` → engine "Plan engine"; `get_rules` → rules "Rules file <name>"; `fetch_page` → web with the URL; `spending_benchmark` → engine "Plan engine" plus web with the BLS URL.
- Flow: `GET /api/chat/context`; build the history (user and assistant messages; earlier turns' tool results go into the system prompt as "Figures from earlier answers"); run the agent; collect this turn's tool message texts; run `unchecked_figures` against this turn's plus the earlier tool results. On a mismatch, invoke once more with the conversation so far plus a message listing the figures that are not in any tool result and asking for a rewrite using only tool figures; check again. `POST /api/chat/reply` with `unchecked` true if the second check still fails.
- System prompt essentials: answer about this household using tools; state no number that is not in a tool result, and copy figures exactly as tools give them; say which source each answer used; propose a change only after a what-if supports it; for spouse or account changes, point to the Profile or Statements page; Medicaid asset limits from the official page; plain business English, no exclamation marks, not professional advice; refer to people as `[YOU]` and `[SPOUSE]`; call `report_step` before slow tools.

- [x] Tests (stub model, backend `TestClient` as `client`, `httpx.MockTransport` as `web`; sample profile saved; plan routes monkeypatched to small fixed `PlanResult`s so tests stay fast):
  - `test_whatif_reply_with_proposal` (the stub calls `run_whatif` with retirement age 65, then `propose_change`, then replies with a figure copied from the tool result; `GET /api/chat` shows the reply, source "Plan engine", one proposed card, `unchecked` false).
  - `test_invented_figure_retried_then_flagged` (both replies contain `$12,345.00`; the stub saw a second request naming `$12,345.00`; the stored reply has `unchecked` true).
  - `test_invented_figure_fixed_on_retry` (`unchecked` false).
  - `test_whatif_rejection_reaches_model` (claim age 75; the tool message contains "Rejected") (Review Focus).
  - `test_fetch_page_rejects_unlisted_url` and `test_fetch_page_source_recorded`.
  - `test_model_never_sees_first_name` (the user message "Can Alex retire at 65"; no message in `stub.seen` contains "Alex").
  - `test_report_step_sets_step`.
- [x] FAIL, implement, PASS. Commit `feat: planning chat agent`.

**Phase 3 success criteria**
- [x] `npm run check` passes.
- [x] `uv run pytest agent --no-cov -q` passes, including the rules research tests after the `pages.py` move.
- [x] `test_whatif_reply_with_proposal` drives the full turn through the real backend routes (`POST /api/chat/messages` → `respond` → `GET /api/chat` shows the reply and status `idle`).

---

## Phase 4: Chat page

### Task 4.1: Chat page and change cards

**Files:** Create `dashboard/src/pages/ChatPage.tsx`, `dashboard/src/components/ChangeCard.tsx`, tests beside them, `e2e/chat.spec.ts`; modify `dashboard/src/types.ts`, `dashboard/src/App.tsx` (sidebar "Chat"), `dashboard/src/styles.css`; add `deleteJson` to `api.ts` if needed.

**Interfaces — Produces:**
- `types.ts`: `Source`, `ChangeLine`, `ChangeCard`, `ChatMessage`, `ChatState` mirroring Task 2.2.
- `ChatPage`: loads `GET /api/chat`; shows messages (owner and "Studio"), each assistant reply with its sources (web sources as links, others as text) and, when `unchecked`, the note "Some figures could not be checked."; a text box with placeholder "Ask about your plan" and "Send" (disabled while `working` or blank); while `working`, the step label (or "Working on it" with no step) and a poll every 2,000 ms that stops when the status leaves `working`; on `failed`, "This reply did not finish. Ask again."; "New conversation" (`DELETE /api/chat`, disabled while working); "Complete your profile first" on 409 from Send or when `GET /api/profile` is 404.
- `ChangeCard`: one row per line, label, old and new (money with `formatUsd`, rates as percentages, ages as plain numbers, a missing value as "None"), "Apply" and "Dismiss" while `proposed`; "Applied" or "Dismissed" otherwise; an Apply 422 shows the message on the card.

- [x] Tests:
  - Renders a conversation with a reply, its sources and a change card from a mocked `ChatState`.
  - Send posts `{"text": ...}`, clears the box, shows the step label and polls until `idle` (fake timers).
  - Send is disabled while `working`.
  - The failed state shows "This reply did not finish. Ask again." (Review Focus).
  - The unchecked note shows only when `unchecked`.
  - Change card: money line reads `$60,000.00` → `$70,000.00`; Apply posts to the apply route and shows "Applied"; a 422 shows the message.
  - New conversation calls `DELETE /api/chat`.
  - e2e (no model; the Playwright backend runs with `CHAT_AGENT=off`, so `run_chat` returns at once and leaves the turn `working`): save the sample profile, post a message, then `POST /api/chat/reply` through the API with a reply and a proposal for `self.retirement_age` 65. Open Chat, see the reply and the card, Apply, open Profile and see retirement age 65.
- [x] `CHAT_AGENT=off` is read in `run_chat` only (documented in `docs/STATUS.md`), so e2e never calls a model.
- [x] Commit `feat: chat page with change cards`.

**Phase 4 success criteria**
- [x] `npm run check` passes.
- [x] Playwright screenshots of the Chat page with a reply, a sources line, a change card and the unchecked note, in light and dark themes, colors per `docs/BRAND.md`, money as `$1,250.00`, no exclamation marks.

---

## Phase 5: Live run and release

### Task 5.1: Container and live checks

**Files:** Modify `docs/STATUS.md`, `README.md` (one line on the Chat page).

- [ ] `npm run container:up`; the Chat page loads at `localhost:8000`; a conversation survives `npm run container:down` and `container:up`.
- [ ] Commit `docs: chat agent status`.

**Phase 5 success criteria**
- [ ] `npm run check` passes.
- [ ] Container: the image builds, `/api/health` is ok, Chat loads, the conversation survives a restart, and a turn interrupted by `container:down` shows "This reply did not finish. Ask again." after `container:up`.
- [ ] Live run by hand with `.env` (the only step that calls a real model), the owner's three questions in one conversation:
  - "What if I retire at 65 instead of 63?": the reply compares both plans with figures that match the Plan page for each, cites the plan engine and offers a retirement age card. Apply it, and the Plan page reflects 65. (Then set it back in the form.)
  - "What is the average monthly spend for a retired couple with our savings level?": the reply gives the BLS age-group and income-band monthly figures and the household's planned monthly spending, citing the plan engine and the BLS URL.
  - "What are the estimated costs for Medicare/Medicaid at 65?": the reply gives Part B from the rules file, any Part D or Medigap figures with their official URL, and says Medicaid asset limits rule it out, citing the page.
  - No reply shows "Some figures could not be checked." for these three; if one does, record the figure and fix the tool or prompt.
  - Record the outcome in `docs/STATUS.md` without account details, plus any source URLs that refused fetches.
- [ ] `docs/STATUS.md` describes the chat agent, its routes, `CHAT_AGENT=off`, and how to run it.
