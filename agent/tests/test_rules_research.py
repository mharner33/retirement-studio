from pathlib import Path
from typing import cast

import httpx
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import rules_research
from agent.tests.stub_model import StubModel

SEED = next(Path("backend/rules/seed").glob("retirement_rules_*.md"))
URL = rules_research.SOURCES[0]


def _call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


def _web(requested: list[str]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            200, html="<html><body><p>Bracket 12,400</p></body></html>"
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def _run(client: TestClient, model: StubModel, requested: list[str]) -> str:
    return rules_research.refresh(
        cast(httpx.Client, client), model, web=_web(requested)
    )


def test_refresh_saves_pending_file(client: TestClient) -> None:
    requested: list[str] = []
    model = StubModel(
        [
            _call("current_rules", {}, "c1"),
            _call("fetch_page", {"url": URL}, "c2"),
            _call("save_rules", {"markdown": SEED.read_text()}, "c3"),
            AIMessage("Saved"),
        ]
    )
    assert _run(client, model, requested) == "Saved"
    assert requested == [URL]
    current, page, saved = model.tool_messages()
    assert current.startswith("# Retirement rules for tax year 2026")
    assert "Bracket 12,400" in page
    assert "filename" in saved
    status = client.get("/api/rules/status").json()
    assert status["pending_file"] is not None


def test_fetch_page_rejects_unlisted_url(client: TestClient) -> None:
    requested: list[str] = []
    model = StubModel(
        [_call("fetch_page", {"url": "https://example.com/x"}, "c1"), AIMessage("done")]
    )
    _run(client, model, requested)
    assert requested == []
    assert "not in the allowed sources" in model.tool_messages()[0]


def test_save_rules_reports_422_to_agent(client: TestClient) -> None:
    model = StubModel(
        [_call("save_rules", {"markdown": "# nothing"}, "c1"), AIMessage("done")]
    )
    _run(client, model, [])
    message = model.tool_messages()[0]
    assert message.startswith("Rejected:")
    assert client.get("/api/rules/status").json()["pending_file"] is None


def test_fetch_page_truncates_text(client: TestClient) -> None:
    big = httpx.Client(
        transport=httpx.MockTransport(
            lambda _r: httpx.Response(200, html="<p>" + "x" * 50_000 + "</p>")
        )
    )
    model = StubModel([_call("fetch_page", {"url": URL}, "c1"), AIMessage("done")])
    rules_research.refresh(cast(httpx.Client, client), model, web=big)
    assert len(model.tool_messages()[0]) == rules_research.MAX_PAGE_CHARS
