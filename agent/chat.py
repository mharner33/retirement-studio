from contextlib import ExitStack
from datetime import date

import httpx
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool
from pydantic import TypeAdapter

from agent.backend_client import make_client
from agent.model import make_model
from agent.numbers import unchecked_figures
from agent.pages import fetch_text, make_web_client
from backend.chat.benchmark import Benchmark
from backend.chat.models import ContextMessage, Proposal, Reply, Source
from backend.engine.projection import Projection, Strategy, YearRow
from backend.plan.changes import FIELDS, ChangeLine, ProfileChange, SetField
from backend.plan.models import PlanOption, PlanResult, WhatIfResult

SOURCES = [
    "https://www.medicare.gov/basics/costs/medicare-costs",
    "https://www.medicare.gov/drug-coverage-part-d/costs-for-medicare-drug-coverage",
    "https://www.medicare.gov/health-drug-plans/medigap/basics/costs",
    "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-deductibles",
    "https://www.medicaid.gov/medicaid/eligibility/index.html",
    "https://www.healthfirstcolorado.gov/apply-now/do-you-qualify/",
    "https://www.bls.gov/cex/tables/calendar-year/mean-item-share-average-standard-error.htm",
]

PLAN_ENGINE = Source(kind="engine", label="Plan engine")

SYSTEM_PROMPT = """You answer questions from the owner of Retirement Studio about
their household's retirement plan. Today's date is {today}.

Rules:
- Use the tools to answer about this household. get_plan gives the current plan,
  run_whatif tries profile changes, run_strategy tries one strategy, get_profile
  gives the saved profile, get_rules gives the tax and Medicare rules file,
  spending_benchmark gives national spending averages, fetch_page reads an
  official page.
- Never state a number that is not in a tool result. Copy every dollar amount
  and percentage exactly as a tool gives it. Never do arithmetic yourself; if no
  tool gives a figure, say you do not have it.
- Say which source each answer used: the plan engine, the rules file or the
  official page URL.
- Call propose_change only after a run_whatif result supports the change.
- Changes to the spouse, accounts or balances cannot be proposed; point the
  owner to the Profile or Statements page for those.
- Medicaid asset limits come only from the official pages; say that they are
  far below this household's savings if the page supports it.
- When you use spending_benchmark, say that the BLS figures cover all consumer
  units of that age or income, not only couples.
- fetch_page accepts only these URLs. If they do not answer the question, say so:
{sources}
- Call report_step with a short label, such as "Running plan with retirement at
  65", before run_whatif, run_strategy, spending_benchmark and fetch_page.
- Refer to people as [YOU] and [SPOUSE].
- Write plain business English, no exclamation marks. This is not professional
  tax, legal or medical advice; say so when it matters."""

RETRY = (
    "These figures are not in any tool result: {figures}. Rewrite your answer "
    "using only figures copied exactly from tool results."
)

changes_adapter = TypeAdapter(list[ProfileChange])
lines_adapter = TypeAdapter(list[ChangeLine])
context_adapter = TypeAdapter(list[ContextMessage])


def usd(x: float) -> str:
    return f"-${-x:,.2f}" if x < 0 else f"${x:,.2f}"


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _value(kind: str, value: float | None) -> str:
    if value is None:
        return "none"
    if kind == "money":
        return usd(value)
    if kind == "rate":
        return pct(value)
    return str(int(value))


def _tried(changes: list[ProfileChange]) -> list[str]:
    """Describe the changes from the model's own arguments; the route's lines
    may carry unmasked one-time labels."""
    out = []
    for c in changes:
        if isinstance(c, SetField):
            info = FIELDS[c.path]
            out.append(f"- {info.label}: set to {_value(info.kind, c.value)}")
        elif c.op == "add_one_time":
            out.append(
                f"- Add one-time expense {c.item.year}: {c.item.label}, "
                f"{usd(c.item.amount)}"
            )
        else:
            out.append(f"- Remove one-time expense number {c.index}")
    return out


def _row(r: YearRow) -> str:
    ages = "/".join(str(a) if a is not None else "-" for a in r.ages)
    tax = r.federal_tax + r.state_tax + r.irmaa
    return (
        f"{r.year} | {ages} | {usd(r.social_security)} | {usd(r.conversion)} | "
        f"{usd(tax)} | {usd(r.spending)} | {usd(sum(r.balances.values()))}"
    )


def _rows(rows: list[YearRow]) -> list[str]:
    return [
        "Year | ages | Social Security | conversion | tax | spending | end balance",
        *(_row(r) for r in rows),
    ]


def _option(title: str, o: PlanOption) -> list[str]:
    return [
        f"{title}: {o.label}",
        f"  Lifetime tax: {usd(o.lifetime_tax)}",
        f"  After-tax money at the end: {usd(o.after_tax_end)}",
        f"  Safe extra spending: {usd(o.safe_extra)} per year, "
        f"{usd(o.safe_extra / 12)} per month",
        f"  Success rate: {pct(o.success_rate)}",
        f"  Shortfall year: {o.shortfall_year or 'none'}",
    ]


def _plan_text(plan: PlanResult) -> str:
    return "\n".join(
        [
            *_option("Best strategy", plan.top[0]),
            *_option("Baseline (no conversions)", plan.baseline),
            "Best strategy year rows:",
            *_rows(plan.best_rows),
        ]
    )


def _money(label: str, a: float, b: float, names: tuple[str, str]) -> str:
    return f"{label}: {names[0]} {usd(a)}, {names[1]} {usd(b)}, difference {usd(b - a)}"


def _shortfall(a: int | None, b: int | None, names: tuple[str, str]) -> str:
    return f"Shortfall year: {names[0]} {a or 'none'}, {names[1]} {b or 'none'}"


def _compare(title: str, a: PlanOption, b: PlanOption) -> list[str]:
    names = ("current", "what-if")
    return [
        f"{title}: current {a.label}; what-if {b.label}",
        _money("  Lifetime tax", a.lifetime_tax, b.lifetime_tax, names),
        _money("  After-tax money at the end", a.after_tax_end, b.after_tax_end, names),
        _money("  Safe extra spending per year", a.safe_extra, b.safe_extra, names),
        _money(
            "  Safe extra spending per month",
            a.safe_extra / 12,
            b.safe_extra / 12,
            names,
        ),
        f"  Success rate: current {pct(a.success_rate)}, what-if "
        f"{pct(b.success_rate)}, difference "
        f"{pct(b.success_rate - a.success_rate)} points",
        "  " + _shortfall(a.shortfall_year, b.shortfall_year, names),
    ]


def _whatif_text(changes: list[ProfileChange], result: WhatIfResult) -> str:
    current, whatif = result.current, result.whatif
    return "\n".join(
        [
            "Changes tried:",
            *_tried(changes),
            *_compare("Best strategy", current.top[0], whatif.top[0]),
            *_compare("Baseline (no conversions)", current.baseline, whatif.baseline),
            "What-if best strategy year rows:",
            *_rows(whatif.best_rows),
        ]
    )


def _strategy_text(strategy: Strategy, p: Projection, best: PlanOption) -> str:
    names = ("current best", "this strategy")
    return "\n".join(
        [
            f"This strategy: {strategy.label()}",
            f"Current best: {best.label}",
            _money("Lifetime tax", best.lifetime_tax, p.lifetime_tax, names),
            _money(
                "After-tax money at the end", best.after_tax_end, p.after_tax_end, names
            ),
            _shortfall(best.shortfall_year, p.shortfall_year, names),
            "This strategy year rows:",
            *_rows(p.rows),
        ]
    )


def _benchmark_text(b: Benchmark) -> str:
    return "\n".join(
        [
            f"BLS Consumer Expenditure Survey, {b.table_year} tables: {b.source_url}",
            "These BLS figures cover all consumer units of that age or income, "
            "not only couples.",
            f"Age group {b.age_group}: {usd(b.age_group_annual)} per year, "
            f"{usd(b.age_group_annual / 12)} per month",
            f"Income band {b.income_band} (the band holding the plan's spending): "
            f"{usd(b.income_band_annual)} per year, "
            f"{usd(b.income_band_annual / 12)} per month",
            "Planned spending in the first retirement year (plan engine): "
            f"{usd(b.planned_annual)} per year, {usd(b.planned_annual / 12)} per month",
        ]
    )


def _rejected(response: httpx.Response) -> str | None:
    if response.status_code == httpx.codes.UNPROCESSABLE_ENTITY:
        return f"Rejected: {response.json()['detail']}"
    response.raise_for_status()
    return None


class _Turn:
    """Tools for one reply, plus the sources and proposals they collect."""

    def __init__(self, client: httpx.Client, web: httpx.Client) -> None:
        self.client = client
        self.web = web
        self.sources: list[Source] = []
        self.proposals: list[Proposal] = []

    def cite(self, source: Source) -> None:
        if source not in self.sources:
            self.sources.append(source)

    def plan(self) -> PlanResult:
        response = self.client.get("/api/plan")
        response.raise_for_status()
        return PlanResult.model_validate(response.json())

    def tools(self) -> list[BaseTool]:
        return [*_plan_tools(self), *_lookup_tools(self), *_owner_tools(self)]


def _plan_tools(turn: _Turn) -> list[BaseTool]:
    client = turn.client

    @tool
    def get_plan() -> str:
        """Return the current plan: best and baseline strategy figures and
        the best strategy's year rows."""
        turn.cite(PLAN_ENGINE)
        return _plan_text(turn.plan())

    @tool
    def run_whatif(changes: list[ProfileChange]) -> str:
        """Run the full plan on an unsaved copy of the profile with these
        changes and compare it with the current plan. Slow."""
        parsed = changes_adapter.validate_python(changes)
        response = client.post(
            "/api/plan/whatif",
            json=changes_adapter.dump_python(parsed, mode="json"),
        )
        if rejected := _rejected(response):
            return rejected
        turn.cite(PLAN_ENGINE)
        return _whatif_text(parsed, WhatIfResult.model_validate(response.json()))

    @tool
    def run_strategy(strategy: Strategy) -> str:
        """Project one strategy on the saved profile and compare it with
        the current best strategy."""
        parsed = Strategy.model_validate(strategy)
        response = client.post("/api/plan/project", json=parsed.model_dump(mode="json"))
        if rejected := _rejected(response):
            return rejected
        projection = Projection.model_validate(response.json())
        turn.cite(PLAN_ENGINE)
        return _strategy_text(parsed, projection, turn.plan().top[0])

    return [get_plan, run_whatif, run_strategy]


def _lookup_tools(turn: _Turn) -> list[BaseTool]:
    client = turn.client

    @tool
    def get_profile() -> str:
        """Return the saved household profile as JSON (names masked)."""
        response = client.get("/api/chat/profile")
        response.raise_for_status()
        return response.text

    @tool
    def spending_benchmark() -> str:
        """Return BLS average spending for the household's age group and for
        the income band matching the plan's spending, per year and month."""
        response = client.get("/api/chat/benchmark")
        response.raise_for_status()
        b = Benchmark.model_validate(response.json())
        turn.cite(PLAN_ENGINE)
        turn.cite(Source(kind="web", label=b.source_url, url=b.source_url))
        return _benchmark_text(b)

    @tool
    def get_rules() -> str:
        """Return the current tax and Medicare rules file as markdown."""
        status = client.get("/api/rules/status")
        status.raise_for_status()
        name = status.json()["current_file"]
        response = client.get(f"/api/rules/{name}")
        response.raise_for_status()
        turn.cite(Source(kind="rules", label=f"Rules file {name}"))
        return response.text

    @tool
    def fetch_page(url: str, find: str = "") -> str:
        """Fetch an official page from the allowed list and return its text.
        For long documents pass `find`, a keyword to start the text near."""
        text = fetch_text(turn.web, url, SOURCES, find)
        if not text.startswith(("Rejected", "Error")):
            turn.cite(Source(kind="web", label=url, url=url))
        return text

    return [get_profile, spending_benchmark, get_rules, fetch_page]


def _owner_tools(turn: _Turn) -> list[BaseTool]:
    client = turn.client

    @tool
    def propose_change(changes: list[ProfileChange], reason: str) -> str:
        """Propose a profile change to the owner as a card with Apply and
        Dismiss. Use only after run_whatif supports it."""
        parsed = changes_adapter.validate_python(changes)
        response = client.post(
            "/api/chat/changes/check",
            json=changes_adapter.dump_python(parsed, mode="json"),
        )
        if rejected := _rejected(response):
            return rejected
        turn.proposals.append(Proposal(changes=parsed, reason=reason))
        lines = lines_adapter.validate_python(response.json())
        return "Proposed:\n" + "\n".join(
            f"- {x.label}: {_value(x.kind, x.old)} -> {_value(x.kind, x.new)}"
            for x in lines
        )

    @tool
    def report_step(text: str) -> str:
        """Show a short progress label to the owner."""
        client.put("/api/chat/step", json={"text": text}).raise_for_status()
        return "ok"

    return [propose_change, report_step]


def respond(
    client: httpx.Client | None = None,
    model: BaseChatModel | None = None,
    web: httpx.Client | None = None,
) -> None:
    with ExitStack() as stack:
        if client is None:
            client = stack.enter_context(make_client())
        if web is None:
            web = stack.enter_context(make_web_client())
        _run(client, web, model)


def _tool_texts(messages: list[AnyMessage]) -> list[str]:
    return [str(m.content) for m in messages if isinstance(m, ToolMessage)]


def _run(client: httpx.Client, web: httpx.Client, model: BaseChatModel | None) -> None:
    response = client.get("/api/chat/context")
    response.raise_for_status()
    context = context_adapter.validate_python(response.json())
    earlier = [t for m in context for t in m.tool_results]
    history: list[AnyMessage] = [
        HumanMessage(m.text) if m.role == "user" else AIMessage(m.text) for m in context
    ]
    prompt = SYSTEM_PROMPT.format(
        today=date.today().isoformat(), sources="\n".join(SOURCES)
    )
    if earlier:
        prompt += "\n\nFigures from earlier answers:\n" + "\n\n".join(earlier)

    turn = _Turn(client, web)
    agent = create_agent(
        model or make_model(), tools=turn.tools(), system_prompt=prompt
    )
    messages: list[AnyMessage] = agent.invoke({"messages": [*history]})["messages"]
    tool_texts = _tool_texts(messages[len(history) :])
    unchecked = unchecked_figures(messages[-1].text, earlier + tool_texts)
    if unchecked:
        retry: list[AnyMessage] = [
            *messages,
            HumanMessage(RETRY.format(figures=", ".join(unchecked))),
        ]
        messages = agent.invoke({"messages": [*retry]})["messages"]
        tool_texts += _tool_texts(messages[len(retry) :])
        unchecked = unchecked_figures(messages[-1].text, earlier + tool_texts)

    reply = Reply(
        text=messages[-1].text,
        sources=turn.sources,
        tool_results=tool_texts,
        unchecked=bool(unchecked),
        proposals=turn.proposals,
    )
    client.post(
        "/api/chat/reply", json=reply.model_dump(mode="json")
    ).raise_for_status()
