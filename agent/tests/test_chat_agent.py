from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import chat
from agent.tests.stub_model import StubModel
from backend.chat import api as chat_api
from backend.engine.projection import Strategy, YearRow
from backend.plan import api as plan_api
from backend.plan.models import PlanOption, PlanResult
from backend.profile.models import Household
from backend.tests.conftest import build_sample_household

RETIRE_65 = {"op": "set", "path": "self.retirement_age", "value": 65}
STRATEGY = Strategy(
    conversion_target="22",
    convert_from_age=63,
    convert_to_age=70,
    withdrawal_order="taxable_first",
    claim_ages=(67, 67),
)


def _row(year: int, spending: float) -> YearRow:
    return YearRow(
        year=year,
        ages=[63, 61],
        filing="mfj",
        wages=0,
        social_security=0,
        pension=0,
        rmd=0,
        conversion=40_000,
        withdrawals={},
        spending=spending,
        health_premiums=0,
        ordinary_income=0,
        capital_gains=0,
        federal_tax=5_000,
        state_tax=1_000,
        irmaa=0,
        magi=0,
        balances={"pretax": 800_000, "roth": 100_000},
        shortfall=0,
    )


def _option(after_tax_end: float, rate: float) -> PlanOption:
    return PlanOption(
        strategy=STRATEGY,
        label=STRATEGY.label(),
        lifetime_tax=250_000,
        after_tax_end=after_tax_end,
        shortfall_year=None,
        success_rate=rate,
        safe_extra=12_000,
    )


def _plan(after_tax_end: float, rate: float) -> PlanResult:
    return PlanResult(
        rules_file="rules.md",
        rules_stale=False,
        top=[_option(after_tax_end, rate)],
        baseline=_option(after_tax_end - 100_000, rate),
        best_rows=[_row(2027, 80_000), _row(2028, 82_000)],
    )


def _fake_plan_for(h: Household, *_args: object) -> PlanResult:
    if h.self_.retirement_age == 65:
        return _plan(1_248_000, 0.95)
    return _plan(1_162_000, 0.9)


@pytest.fixture
def chat_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(chat_api, "run_chat", lambda: None)
    monkeypatch.setattr(plan_api, "plan_for", _fake_plan_for)
    monkeypatch.setattr(chat_api, "plan_for", _fake_plan_for)
    body = build_sample_household().model_dump(mode="json", by_alias=True)
    assert client.put("/api/profile", json=body).status_code == 200
    return client


def _call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _web(requested: list[str] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if requested is not None:
            requested.append(str(request.url))
        return httpx.Response(200, html="<p>Part B premium $202.90</p>")

    return httpx.Client(transport=httpx.MockTransport(handler))


def _turn(
    client: TestClient,
    responses: list[AIMessage],
    text: str = "What if I retire at 65",
    web: httpx.Client | None = None,
) -> StubModel:
    assert client.post("/api/chat/messages", json={"text": text}).status_code == 202
    model = StubModel(responses)
    chat.respond(cast(httpx.Client, client), model, web or _web())
    return model


def _last(client: TestClient) -> dict:
    return client.get("/api/chat").json()["messages"][-1]


def test_usd() -> None:
    assert chat.usd(1250) == "$1,250.00"
    assert chat.usd(-75.5) == "-$75.50"


def test_whatif_reply_with_proposal(chat_client: TestClient) -> None:
    model = _turn(
        chat_client,
        [
            _call("run_whatif", {"changes": [RETIRE_65]}, "c1"),
            _call(
                "propose_change",
                {"changes": [RETIRE_65], "reason": "More money at the end"},
                "c2",
            ),
            AIMessage("Retiring at 65 leaves $1,248,000.00, $86,000.00 more."),
        ],
    )
    whatif, proposed = model.tool_messages()
    assert "$1,248,000.00" in whatif
    assert "$86,000.00" in whatif
    assert "95.0%" in whatif
    assert "Retirement age (you): set to 65" in whatif
    assert "Retirement age (you): 63 -> 65" in proposed
    state = chat_client.get("/api/chat").json()
    assert state["status"] == "idle"
    reply = state["messages"][-1]
    assert reply["text"].startswith("Retiring at 65 leaves $1,248,000.00")
    assert reply["sources"] == [{"kind": "engine", "label": "Plan engine", "url": None}]
    assert reply["unchecked"] is False
    [card] = reply["changes"]
    assert card["status"] == "proposed"
    assert card["lines"][0]["new"] == 65


def test_invented_figure_retried_then_flagged(chat_client: TestClient) -> None:
    model = _turn(
        chat_client,
        [
            _call("get_plan", {}, "c1"),
            AIMessage("You will have $12,345.00."),
            AIMessage("You will still have $12,345.00."),
        ],
    )
    assert "$12,345.00" in str(model.seen[-1][-1].content)
    reply = _last(chat_client)
    assert reply["text"] == "You will still have $12,345.00."
    assert reply["unchecked"] is True


def test_invented_figure_fixed_on_retry(chat_client: TestClient) -> None:
    _turn(
        chat_client,
        [
            _call("get_plan", {}, "c1"),
            AIMessage("You will have $12,345.00."),
            AIMessage("You will have $1,162,000.00."),
        ],
    )
    reply = _last(chat_client)
    assert reply["text"] == "You will have $1,162,000.00."
    assert reply["unchecked"] is False


def test_earlier_figures_still_check(chat_client: TestClient) -> None:
    _turn(chat_client, [_call("get_plan", {}, "c1"), AIMessage("Ok")])
    model = _turn(chat_client, [AIMessage("Still $1,162,000.00.")], text="Again")
    assert "$1,162,000.00" in str(model.seen[0][0].content)
    assert _last(chat_client)["unchecked"] is False


def test_whatif_rejection_reaches_model(chat_client: TestClient) -> None:
    change = {"op": "set", "path": "self.ss_claim_age", "value": 75}
    model = _turn(
        chat_client,
        [
            _call("run_whatif", {"changes": [change]}, "c1"),
            _call("propose_change", {"changes": [change], "reason": "x"}, "c2"),
            AIMessage("That claim age is not allowed."),
        ],
    )
    whatif, proposed = model.tool_messages()
    assert whatif.startswith("Rejected:")
    assert "ss_claim_age" in whatif
    assert proposed.startswith("Rejected:")
    assert _last(chat_client)["changes"] == []


def test_fetch_page_rejects_unlisted_url(chat_client: TestClient) -> None:
    requested: list[str] = []
    model = _turn(
        chat_client,
        [
            _call("fetch_page", {"url": "https://example.com/x"}, "c1"),
            AIMessage("Not on the list."),
        ],
        web=_web(requested),
    )
    assert model.tool_messages()[0].startswith("Rejected:")
    assert requested == []
    assert _last(chat_client)["sources"] == []


def test_fetch_page_source_recorded(chat_client: TestClient) -> None:
    url = chat.SOURCES[0]
    model = _turn(
        chat_client,
        [_call("fetch_page", {"url": url}, "c1"), AIMessage("Part B is $202.90.")],
    )
    assert "$202.90" in model.tool_messages()[0]
    reply = _last(chat_client)
    assert reply["sources"] == [{"kind": "web", "label": url, "url": url}]
    assert reply["unchecked"] is False


def test_model_never_sees_first_name(chat_client: TestClient) -> None:
    model = _turn(
        chat_client,
        [
            _call("get_profile", {}, "c1"),
            _call("get_plan", {}, "c2"),
            AIMessage("Yes"),
        ],
        text="Can Alex retire at 65",
    )
    assert "[YOU]" in model.tool_messages()[0]
    assert all("Alex" not in str(m.content) for seen in model.seen for m in seen)


def test_report_step_sets_step(chat_client: TestClient) -> None:
    steps: list[str] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        steps.append(chat_client.get("/api/chat").json()["step"])
        return httpx.Response(200, html="<p>ok</p>")

    _turn(
        chat_client,
        [
            _call("report_step", {"text": "Reading Medicare costs"}, "c1"),
            _call("fetch_page", {"url": chat.SOURCES[0]}, "c2"),
            AIMessage("Done"),
        ],
        web=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert steps == ["Reading Medicare costs"]


def test_lookup_tools_and_sources(chat_client: TestClient) -> None:
    strategy = STRATEGY.model_dump(mode="json")
    model = _turn(
        chat_client,
        [
            _call("get_rules", {}, "c1"),
            _call("spending_benchmark", {}, "c2"),
            _call("run_strategy", {"strategy": strategy}, "c3"),
            AIMessage("Done"),
        ],
    )
    rules, bench, strat = model.tool_messages()
    assert rules.startswith("# Retirement rules")
    assert "per month" in bench
    assert "not only couples" in bench
    assert "Current best" in strat
    reply = _last(chat_client)
    kinds = [(s["kind"], s["label"]) for s in reply["sources"]]
    assert kinds[0][0] == "rules"
    assert kinds[0][1].startswith("Rules file ")
    assert ("engine", "Plan engine") in kinds
    assert any(s["kind"] == "web" and "bls.gov" in s["url"] for s in reply["sources"])
