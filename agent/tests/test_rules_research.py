from pathlib import Path
from typing import cast

import httpx
import pymupdf
import pytest
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


def _web_with(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _fetch_then_save(client: TestClient, web: httpx.Client) -> StubModel:
    model = StubModel(
        [
            _call("fetch_page", {"url": URL}, "c1"),
            _call("save_rules", {"markdown": SEED.read_text()}, "c2"),
            AIMessage("Saved"),
        ]
    )
    assert rules_research.refresh(cast(httpx.Client, client), model, web=web) == "Saved"
    return model


def test_fetch_page_404_lets_agent_continue(client: TestClient) -> None:
    model = _fetch_then_save(client, _web_with(lambda _r: httpx.Response(404)))
    fetched, saved = model.tool_messages()
    assert fetched.startswith(f"Error fetching {URL}")
    assert "filename" in saved


def test_fetch_page_timeout_lets_agent_continue(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    model = _fetch_then_save(client, _web_with(handler))
    fetched, saved = model.tool_messages()
    assert "timed out" in fetched
    assert "filename" in saved


def test_fetch_page_reads_pdf_and_find(client: TestClient) -> None:
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "intro text")
    pdf.new_page().insert_text((72, 72), "Uniform Lifetime Table 27.4")
    data = pdf.tobytes()
    url = "https://www.irs.gov/pub/irs-pdf/p590b.pdf"
    web = _web_with(
        lambda _r: httpx.Response(
            200, content=data, headers={"content-type": "application/pdf"}
        )
    )
    model = StubModel(
        [
            _call("fetch_page", {"url": url, "find": "Uniform Lifetime"}, "c1"),
            AIMessage("d"),
        ]
    )
    rules_research.refresh(cast(httpx.Client, client), model, web=web)
    text = model.tool_messages()[0]
    assert "Uniform Lifetime Table 27.4" in text
    assert "\x00" not in text


def test_refresh_closes_only_its_own_clients(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    created: list[httpx.Client] = []
    real = httpx.Client

    def make(*args, **kwargs) -> httpx.Client:
        created.append(real(*args, **kwargs))
        return created[-1]

    monkeypatch.setattr(rules_research.httpx, "Client", make)
    monkeypatch.setattr(
        rules_research, "make_client", lambda: make(base_url="http://x")
    )
    rules_research.refresh(model=StubModel([AIMessage("done")]))
    assert len(created) == 2
    assert all(c.is_closed for c in created)
    injected = real()
    rules_research.refresh(injected, StubModel([AIMessage("done")]), web=real())
    assert not injected.is_closed


def test_current_rules_error_is_not_returned_as_rules() -> None:
    http = httpx.Client(
        base_url="http://x",
        transport=httpx.MockTransport(lambda _r: httpx.Response(500)),
    )
    model = StubModel([_call("current_rules", {}, "c1"), AIMessage("d")])
    with pytest.raises(httpx.HTTPStatusError):
        rules_research.refresh(
            http, model, web=_web_with(lambda _r: httpx.Response(200))
        )


def test_pdf_url_with_html_body_lets_agent_continue(client: TestClient) -> None:
    pdf_url = "https://www.irs.gov/pub/irs-pdf/p590b.pdf"
    model = StubModel(
        [
            _call("fetch_page", {"url": pdf_url}, "c1"),
            _call("save_rules", {"markdown": SEED.read_text()}, "c2"),
            AIMessage("Saved"),
        ]
    )
    web = _web_with(lambda _r: httpx.Response(200, html="<html>blocked</html>"))
    assert rules_research.refresh(cast(httpx.Client, client), model, web=web) == "Saved"
    read, saved = model.tool_messages()
    assert read.startswith(f"Error reading {pdf_url}")
    assert "filename" in saved


def test_fetch_page_reports_missing_find(client: TestClient) -> None:
    web = _web_with(lambda _r: httpx.Response(200, html="<p>hello world</p>"))
    model = StubModel(
        [_call("fetch_page", {"url": URL, "find": "zzz"}, "c1"), AIMessage("d")]
    )
    rules_research.refresh(cast(httpx.Client, client), model, web=web)
    assert model.tool_messages()[0] == (
        "'zzz' not found; showing the start of the document.\nhello world"
    )
