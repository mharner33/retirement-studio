from typing import cast

import httpx
import pymupdf
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

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
