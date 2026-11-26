from typing import cast
from unittest.mock import patch

import httpx
import pymupdf
import pytest
from fastapi.testclient import TestClient
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from agent import extraction
from agent.tests.stub_model import StubModel

ACCOUNT = {
    "doc_type": "account",
    "institution": "Fidelity",
    "statement_date": "2026-09-30",
    "accounts": [
        {
            "kind": "pretax",
            "owner_hint": "Alex",
            "label": "Rollover IRA",
            "balance": 125000.0,
            "last4": "9012",
        }
    ],
}
SOCIAL_SECURITY = {
    "doc_type": "social_security",
    "statement_date": "2026-08-01",
    "monthly_at_62": 1800.0,
    "monthly_at_fra": 2600.0,
    "fra_age": "67",
    "monthly_at_70": 3300.0,
}


def _pdf(lines: list[str]) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + 20 * i), line)
    return doc.tobytes()


def _upload(client: TestClient, data: bytes) -> int:
    res = client.post("/api/statements", files=[("files", ("s.pdf", data))])
    return res.json()[0]["id"]


def _answer(payload: dict) -> StubModel:
    name = (
        "ExtractedStatement"
        if payload["doc_type"] == "account"
        else ("ExtractedSsStatement")
    )
    call = {"name": name, "args": payload, "id": "c1"}
    return StubModel([AIMessage("", tool_calls=[call])])


def _extract(client: TestClient, sid: int, model: StubModel):
    return extraction.extract(sid, cast(httpx.Client, client), model)


def test_extract_puts_pending_review(client: TestClient) -> None:
    sid = _upload(client, _pdf(["Fidelity statement"]))
    result = _extract(client, sid, _answer(ACCOUNT))
    assert result is not None
    assert result.doc_type == "account"
    row = client.get("/api/statements").json()[0]
    assert row["status"] == "pending_review"
    assert row["extracted"]["accounts"][0]["last4"] == "9012"
    assert row["extracted"]["accounts"][0]["owner"] == "self"


def test_extract_social_security_statement(client: TestClient) -> None:
    sid = _upload(client, _pdf(["Your Social Security Statement"]))
    _extract(client, sid, _answer(SOCIAL_SECURITY))
    extracted = client.get("/api/statements").json()[0]["extracted"]
    assert extracted["doc_type"] == "social_security"
    assert (
        extracted["monthly_at_62"],
        extracted["monthly_at_fra"],
        extracted["monthly_at_70"],
    ) == (1800.0, 2600.0, 3300.0)


def test_no_text_skips_model(client: TestClient) -> None:
    sid = _upload(client, _pdf([]))
    model = StubModel([])
    assert _extract(client, sid, model) is None
    assert model.seen == []
    assert client.get("/api/statements").json()[0]["extracted"] is None


def test_model_never_sees_unmasked_number(client: TestClient) -> None:
    sid = _upload(client, _pdf(["Account 1234-5678-9012", "Ending balance 125000.00"]))
    model = _answer(ACCOUNT)
    _extract(client, sid, model)
    seen = " ".join(str(m.content) for batch in model.seen for m in batch)
    assert "1234-5678-9012" not in seen
    assert "****9012" in seen
    assert "125000.00" in seen


def test_toolstrategy_used_with_real_chat_model() -> None:
    model = ChatOpenAI(model="openai/gpt-6-luna", api_key=SecretStr("x"))
    with patch.object(extraction, "create_agent") as create:
        create.return_value.invoke.return_value = {}
        extraction.extract(1, _fake_text_client(), model)
    strategy = create.call_args.kwargs["response_format"]
    assert isinstance(strategy, ToolStrategy)
    agent = create_agent(model, tools=[], response_format=strategy)
    assert agent is not None


def _fake_text_client(put_status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, text="Ending balance 1.00")
        return httpx.Response(put_status, text="nope")

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_missing_structured_response_returns_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch.object(extraction, "create_agent") as create:
        create.return_value.invoke.return_value = {"messages": []}
        assert extraction.extract(9, _fake_text_client(), _answer(ACCOUNT)) is None
    assert "statement 9" in caplog.text


def test_put_failure_returns_none_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    model = _answer(ACCOUNT)
    assert extraction.extract(5, _fake_text_client(500), model) is None
    assert "statement 5" in caplog.text
    assert "nope" in caplog.text


def test_created_client_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    created = _fake_text_client()
    monkeypatch.setattr(extraction, "make_client", lambda: created)
    extraction.extract(1, None, _answer(ACCOUNT))
    assert created.is_closed


def test_injected_client_stays_open() -> None:
    injected = _fake_text_client()
    extraction.extract(1, injected, _answer(ACCOUNT))
    assert not injected.is_closed


def test_no_text_logs(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    sid = _upload(client, _pdf([]))
    _extract(client, sid, StubModel([]))
    assert f"statement {sid} has no readable text" in caplog.text
