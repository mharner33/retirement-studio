# Planning chat agent design

Date: 2026-11-25. Source of truth for the chat agent; `docs/PLAN_CHAT.md` turns it into phases. Builds on `2026-11-24-retirement-studio-design.md`, whose constraints and anti-goals still apply.

## Intent

The owner wants to ask plain-English questions about their own retirement plan and get answers grounded in their numbers, without editing the form and reading tables to work them out. Example questions from the owner:

1. "What if I retire at 65 instead of 63?"
2. "What is the average monthly spend for a retired couple with our savings level?"
3. "What are the estimated costs for Medicare/Medicaid at 65?"

When a what-if shows a better choice, the agent proposes the profile change and the owner confirms it.

## Goals

- A Chat page where the owner asks questions and gets answers that state where each figure came from.
- Answers draw on three kinds of source, and each answer names the one it used:
  1. **The engine**, for anything involving the household's numbers. What-ifs run the full plan on an unsaved copy of the profile and compare the result with the current plan: best strategy, lifetime tax, after-tax money at the plan-to age, safe extra spending and success rate.
  2. **The rules file**, for tax and Medicare figures it already holds (Part B base premium, IRMAA tiers, brackets, RMD ages).
  3. **A fixed list of official pages** (owner's choice), for facts outside both, such as national spending averages by age, Part D, Medigap and Medicare Advantage costs, and Medicaid eligibility. The agent cites the page URL. If the listed pages don't answer the question, it says so.
- Profile changes are proposed as a change card in the reply, for example "Retirement age (you): 63 → 65", with Apply and Dismiss. Apply saves through `PUT /api/profile`, so the normal validation applies. Nothing changes without Apply.
- One ongoing conversation, stored in SQLite so it survives reloads and container restarts, with a "New conversation" button that clears it.

## Non-goals

- Several conversations, conversation search or export.
- Word-by-word streaming of replies.
- Medicaid planning. Asset limits are far below this household's savings; the agent says so from the official page rather than modeling it.
- ACA subsidy modeling (still a non-goal from the pilot).
- The agent changing rules files or statements. It reads them; it proposes changes only to the profile.

## Anti-goals

- The model doing arithmetic. Every dollar figure, difference, monthly conversion and percentage in a reply comes from a tool result. If a tool doesn't produce a number, the agent doesn't state one.
- A profile change saved without the owner clicking Apply.
- Figures from outside the engine and rules file without a cited official URL.
- Sending first names, `mask_terms` entries or account numbers to the model provider.
- Advice framed as professional tax, legal or medical advice.

## Constraints

- Everything in the pilot design's Constraints section: the fixed stack, Podman, agents reach data only through the backend HTTP API, tests use the stub model, `npm run check` at 80% coverage with no rule changes, `docs/BRAND.md` (money as $1,250.00, no exclamation marks).
- A full plan run takes about 6 s on the owner's host. A reply with two what-ifs and a few model calls can take 15 to 40 s.

## Approaches considered (how a reply reaches the page)

- **A. Background turn with polling (owner's choice).** `POST` saves the owner's message, starts the agent as a FastAPI background task and returns 202. The page polls every 2 s (as the Statements page does) and shows the current step, for example "Running plan with retirement at 65". The reply is stored, so leaving the page loses nothing. Reuses existing patterns.
- **B. One blocking request.** Simplest, but the page shows "Thinking" for up to 40 s with no progress, and leaving the page loses the in-progress view.
- **C. Streaming (SSE).** Most responsive, but it needs a new transport and harder tests, and most of the wait is engine time, not model output.

## Decisions after the builder check

- **Number check (owner's choice).** Code, not only the prompt, enforces the no-arithmetic rule. Before a reply is saved, every dollar amount and percentage in it must match a number in that turn's tool results (compared after normalizing formats such as $1,248,000.00, 1248000 and 6.2%). Ages and years are not checked. On a mismatch the agent gets one retry, told which figures failed. If the retry still fails, the reply is saved with a visible note: "Some figures could not be checked." The stored history keeps each turn's tool results, so a follow-up may repeat a figure from an earlier turn and it still checks.
- **Spending by "savings level" (owner's choice).** BLS tables are cut by age and income, not savings. A tool picks, in code, the BLS income band that contains the household's planned first-retirement-year spending from the current plan, and returns that band's average alongside the age-group average. The reply cites both the plan engine and the BLS table.
- **What a what-if or proposed change can touch (my call).** Single-value fields: retirement, claiming and plan-to ages, wages and 401(k) contribution, pension amount and start age, spending amounts, COBRA and bridge premiums, and assumptions. Also adding or removing a one-time expense. Not adding or removing the spouse or accounts, and not account balances; the agent points the owner to the Profile or Statements page for those. Changes are addressed by a fixed map of allowed profile paths to labels; anything else is rejected by the tool and the apply route.
- **Strategy what-ifs (my call).** Questions such as "what if I fill the 22% bracket" or "withdraw pre-tax first" use the existing `POST /api/plan/project` through a `run_strategy(strategy)` tool, compared with the current best strategy. No change card, since strategies are not saved.
- **Names in replies (my call).** Masking and unmasking live in the backend. The model sees placeholders (`[YOU]`, `[SPOUSE]`, `[MASKED]` for `mask_terms`). Stored messages, replies and tool results keep the placeholders, so later turns never send names. `GET /api/chat` swaps `[YOU]` and `[SPOUSE]` back to the first names for display. Change-card labels use "you" and "spouse" and need no swap.

## Design

### Backend

- **What-if route.** A route that runs the same work as `GET /api/plan` on a household in the request body instead of the saved one, and returns a `PlanResult`. Builder's call: `POST /api/plan/whatif` with body `Household`; validation errors are 422 as for `PUT /api/profile`. `GET /api/plan` and the new route share one function.
- **Chat storage.** New table(s) for messages: role (user or assistant), text, created time, a status for the turn in progress (working, done, failed), the current step label, the sources cited, and any proposed profile changes with their state (proposed, applied, dismissed). Exact schema is the builder's call.
- **Chat routes.** Builder's call on exact shapes:
  - `GET /api/chat`: the conversation, with the status and step of a turn in progress.
  - `POST /api/chat/messages`: body `{"text": str}`. Saves the message, starts the agent in the background, returns 202. 409 while a turn is already working. 409 without a saved profile.
  - `POST /api/chat/changes/{id}/apply` and `/dismiss`: apply loads the saved profile, sets the proposed fields, saves with `PUT` semantics (422 on invalid) and marks it applied.
  - `DELETE /api/chat`: new conversation.
  - Internal routes the agent uses to report its step, save its reply, and record proposals and sources, so the agent still writes only through the HTTP API.
- A turn left "working" when the process restarts is marked failed at startup, and the page shows "This reply did not finish. Ask again."

### Agent (`agent/chat.py`)

- Entry point `run(thread_id)`-style function that reads the conversation over the API, runs `create_agent` with the tools below, and posts the reply.
- Tools (each returns text or JSON for the model):
  - `get_profile()`: the saved profile, masked.
  - `get_plan()`: the current plan summary (top strategy, figures, key year rows).
  - `run_whatif(changes)`: applies field changes to a copy of the profile, calls the what-if route, and returns the new plan side by side with the current one, with the differences already computed in code.
  - `run_strategy(strategy)`: one strategy on the saved profile via `POST /api/plan/project`, compared with the current best.
  - `spending_benchmark()`: the BLS age-group and matched income-band averages, with the band chosen in code (see above).
  - `get_rules()`: the current rules figures.
  - `fetch_page(url)`: only URLs on the chat source list (see below), same fetch and truncation as the rules agent (shared code).
  - `propose_change(changes, reason)`: records a change card. Only fields that exist on the profile are accepted.
  - `report_step(text)`: sets the progress label on the page.
- Arithmetic helpers belong in tools, not the model: monthly from yearly, differences between plans. The system prompt forbids stating numbers not found in tool results.
- **Masking.** Before any text goes to the model, the profile's first names and `mask_terms` entries are replaced, in the owner's messages and in tool results, as described under "Names in replies". Account numbers are never included (only `last4`, as now).
- **Number check.** As described above, run on the reply before it is saved.
- **Source list.** A fixed list of official pages, in the same style as `SOURCES` in `agent/rules_research.py`. Candidates: BLS Consumer Expenditure Survey tables by age of reference person and by income; Medicare.gov costs page (Parts A, B, D, Medigap overview); CMS Part D base beneficiary premium; Medicaid.gov eligibility; the Colorado Health First Colorado (Medicaid) eligibility page. The builder verifies each URL is reachable and lists any that refuse automated fetches.
- Context: the conversation history sent to the model is the stored messages, oldest dropped first past a builder-chosen limit.

### Dashboard

- A Chat entry in the sidebar.
- The conversation, the owner's messages and the agent's replies, each reply with its sources (URLs as links, "Plan engine" or "Rules file dated YYYY-MM-DD").
- A text box with Send, disabled while a turn is working. While working, the step label shows ("Running plan with retirement at 65").
- Change cards in replies: field label, old value, new value (money as $1,250.00), Apply and Dismiss. After Apply the card reads "Applied"; after Dismiss, "Dismissed". An Apply 422 shows the field message on the card.
- "New conversation" button.
- "Complete your profile first" when no profile is saved, as on the Plan page.
- Light and dark themes per `docs/BRAND.md`.

```
 Chat                                   New conversation
 ┌──────────────────────────────────────────────────────┐
 │ You: What if I retire at 65 instead of 63?           │
 │ Studio: Retiring at 65 leaves $1,248,000.00 at 82,   │
 │   $86,000.00 more than now. Best plan changes to ... │
 │   Source: plan engine                                │
 │   ┌ Retirement age (you): 63 → 65  [Apply] [Dismiss] ┐
 └──────────────────────────────────────────────────────┘
  [ Ask about your plan...                      ] [Send]
```

## Left to the builder

Table schema, route shapes beyond the above, the conversation length limit, how change cards name fields (a fixed map of profile paths to labels is expected), component structure, the number of phases in `docs/PLAN_CHAT.md` (per `docs/PROCESS.md`), and the exact source URLs.
