import sys
import types
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import db, settings
from backend.chat import api as chat_api
from backend.main import create_app
from backend.profile.models import OneTime
from backend.tests.conftest import build_sample_household


def put_profile(client: TestClient) -> None:
    body = build_sample_household().model_dump(mode="json", by_alias=True)
    assert client.put("/api/profile", json=body).status_code == 200


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    monkeypatch.setattr(chat_api, "run_chat", lambda: calls.append(1))
    return calls


def send(client: TestClient, text: str = "Can Alex retire at 65"):
    return client.post("/api/chat/messages", json={"text": text})


def proposal(path: str = "self.retirement_age", value: float = 65) -> dict:
    return {
        "changes": [{"op": "set", "path": path, "value": value}],
        "reason": "Work two more years",
    }


def reply(client: TestClient, proposals: list[dict] | None = None, text: str = "Ok"):
    return client.post(
        "/api/chat/reply",
        json={
            "text": text,
            "sources": [{"kind": "engine", "label": "Plan run", "url": None}],
            "tool_results": ["retire at 65: $1,000.00"],
            "unchecked": False,
            "proposals": proposals or [],
        },
    )


def card_id(client: TestClient) -> int:
    return client.get("/api/chat").json()["messages"][-1]["changes"][0]["id"]


def test_post_message_202_and_stores_masked(client: TestClient, calls) -> None:
    put_profile(client)
    assert send(client).status_code == 202
    state = client.get("/api/chat").json()
    assert state["status"] == "working"
    assert state["messages"][0]["text"] == "Can Alex retire at 65"
    assert calls == [1]
    with closing(db.connect(settings.db_path(client.app.state.data_dir))) as conn:  # type: ignore[attr-defined]
        stored = conn.execute("SELECT text FROM chat_messages").fetchone()[0]
    assert stored == "Can [YOU] retire at 65"


def test_post_message_409_while_working(client: TestClient, calls) -> None:
    put_profile(client)
    assert send(client).status_code == 202
    res = send(client)
    assert res.status_code == 409
    assert res.json()["detail"] == "A reply is in progress"
    assert calls == [1]
    assert len(client.get("/api/chat").json()["messages"]) == 1


def test_post_message_409_without_profile(client: TestClient, calls) -> None:
    res = send(client)
    assert res.status_code == 409
    assert res.json()["detail"] == "No profile saved"
    assert calls == []


def test_blank_message_422(client: TestClient, calls) -> None:
    put_profile(client)
    assert send(client, "   ").status_code == 422
    assert calls == []


def test_reply_sets_idle_and_shows_change_card(client: TestClient, calls) -> None:
    put_profile(client)
    send(client)
    assert reply(client, [proposal()], "[YOU] can retire at 65").status_code == 200
    state = client.get("/api/chat").json()
    assert state["status"] == "idle"
    message = state["messages"][1]
    assert message["role"] == "assistant"
    assert message["text"] == "Alex can retire at 65"
    assert message["sources"][0]["label"] == "Plan run"
    card = message["changes"][0]
    assert card["status"] == "proposed"
    assert card["reason"] == "Work two more years"
    assert card["lines"] == [
        {"label": "Retirement age (you)", "kind": "age", "old": 63, "new": 65}
    ]


def test_reply_with_invalid_proposal_422_stores_nothing(
    client: TestClient, calls
) -> None:
    put_profile(client)
    send(client)
    assert reply(client, [proposal("self.bogus")]).status_code == 422
    state = client.get("/api/chat").json()
    assert state["status"] == "working"
    assert len(state["messages"]) == 1


def test_check_changes(client: TestClient) -> None:
    put_profile(client)
    ok = client.post("/api/chat/changes/check", json=proposal()["changes"])
    assert ok.json()[0]["new"] == 65
    bad = client.post("/api/chat/changes/check", json=proposal("self.bogus")["changes"])
    assert bad.status_code == 422
    assert "cannot be changed" in bad.json()["detail"]


def test_check_masks_labels_from_the_saved_profile(client: TestClient) -> None:
    household = build_sample_household()
    household.mask_terms = ["Acme"]
    household.spending.one_time = [
        OneTime(year=2030, amount=5_000, label="Alex trip with Acme")
    ]
    client.put("/api/profile", json=household.model_dump(mode="json", by_alias=True))
    res = client.post(
        "/api/chat/changes/check", json=[{"op": "remove_one_time", "index": 0}]
    )
    assert res.status_code == 200
    assert "Alex" not in res.text
    assert "Acme" not in res.text
    assert "[YOU]" in res.text


def test_apply_keeps_other_profile_edits(client: TestClient, calls) -> None:
    put_profile(client)
    send(client)
    reply(client, [proposal()])
    edited = build_sample_household()
    edited.spending.essential = 70_000
    client.put("/api/profile", json=edited.model_dump(mode="json", by_alias=True))
    res = client.post(f"/api/chat/changes/{card_id(client)}/apply")
    assert res.status_code == 200
    assert res.json()["status"] == "applied"
    profile = client.get("/api/profile").json()
    assert profile["self"]["retirement_age"] == 65
    assert profile["spending"]["essential"] == 70_000


def test_apply_invalid_change_422_card_stays_proposed(
    client: TestClient, calls
) -> None:
    put_profile(client)
    send(client)
    reply(client, [proposal("spouse.retirement_age", 64)])
    solo = build_sample_household()
    solo.spouse = None
    client.put("/api/profile", json=solo.model_dump(mode="json", by_alias=True))
    res = client.post(f"/api/chat/changes/{card_id(client)}/apply")
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], str)
    card = client.get("/api/chat").json()["messages"][-1]["changes"][0]
    assert card["status"] == "proposed"
    assert client.get("/api/profile").json()["spouse"] is None


def test_apply_twice_409(client: TestClient, calls) -> None:
    put_profile(client)
    send(client)
    reply(client, [proposal()])
    url = f"/api/chat/changes/{card_id(client)}/apply"
    assert client.post(url).status_code == 200
    assert client.post(url).status_code == 409


def test_apply_unknown_404(client: TestClient) -> None:
    assert client.post("/api/chat/changes/99/apply").status_code == 404


def test_dismiss(client: TestClient, calls) -> None:
    put_profile(client)
    send(client)
    reply(client, [proposal()])
    cid = card_id(client)
    assert client.post(f"/api/chat/changes/{cid}/dismiss").json()["status"] == (
        "dismissed"
    )
    assert client.post(f"/api/chat/changes/{cid}/apply").status_code == 409
    assert client.get("/api/profile").json()["self"]["retirement_age"] == 63


def test_context_is_masked_and_limited_to_20(client: TestClient, calls) -> None:
    put_profile(client)
    for i in range(25):
        send(client, f"Question {i} for Alex")
        reply(client, text=f"Answer {i}")
    context = client.get("/api/chat/context").json()
    assert len(context) == 20
    assert context[-1] == {
        "role": "assistant",
        "text": "Answer 24",
        "tool_results": ["retire at 65: $1,000.00"],
    }
    assert context[-2]["text"] == "Question 24 for [YOU]"
    assert context[0]["text"] == "Question 15 for [YOU]"
    assert "Alex" not in str(context)


def test_profile_route_is_masked(client: TestClient) -> None:
    assert client.get("/api/chat/profile").status_code == 404
    put_profile(client)
    text = client.get("/api/chat/profile").text
    assert "Alex" not in text
    assert "[YOU]" in text


def test_step_is_shown_until_reply(client: TestClient, calls) -> None:
    put_profile(client)
    send(client)
    assert client.put("/api/chat/step", json={"text": "Running"}).status_code == 204
    assert client.get("/api/chat").json()["step"] == "Running"
    reply(client)
    assert client.get("/api/chat").json()["step"] is None


def test_startup_marks_working_turn_failed(
    client: TestClient, tmp_path: Path, calls
) -> None:
    put_profile(client)
    send(client)
    assert client.get("/api/chat").json()["status"] == "working"
    restarted = TestClient(create_app(tmp_path))
    assert restarted.get("/api/chat").json()["status"] == "failed"
    assert send_ok(restarted)


def send_ok(client: TestClient) -> bool:
    res = send(client)
    return res.status_code == 202 and client.get("/api/chat").json()["status"] == (
        "working"
    )


def fake_agent(monkeypatch: pytest.MonkeyPatch, respond) -> None:
    module = types.ModuleType("agent.chat")
    module.respond = respond  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agent.chat", module)


def test_run_chat_failure_marks_failed(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom() -> None:
        raise RuntimeError("boom")

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    fake_agent(monkeypatch, boom)
    put_profile(client)
    send(client)
    assert client.get("/api/chat").json()["status"] == "failed"


def test_run_chat_without_reply_marks_failed(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    fake_agent(monkeypatch, lambda: None)
    put_profile(client)
    send(client)
    assert client.get("/api/chat").json()["status"] == "failed"


def test_run_chat_leaves_posted_reply_idle(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    fake_agent(monkeypatch, lambda: reply(client))
    put_profile(client)
    send(client)
    assert client.get("/api/chat").json()["status"] == "idle"


def test_delete_clears_conversation(client: TestClient, calls) -> None:
    put_profile(client)
    send(client)
    reply(client, [proposal()])
    assert client.delete("/api/chat").status_code == 204
    state = client.get("/api/chat").json()
    assert state == {"status": "idle", "step": None, "messages": []}


def test_delete_clears_failed_turn(client: TestClient, tmp_path: Path, calls) -> None:
    put_profile(client)
    send(client)
    restarted = TestClient(create_app(tmp_path))
    assert restarted.delete("/api/chat").status_code == 204
    assert restarted.get("/api/chat").json()["status"] == "idle"


def test_delete_409_while_working(client: TestClient, calls) -> None:
    put_profile(client)
    send(client)
    assert client.delete("/api/chat").status_code == 409
    assert len(client.get("/api/chat").json()["messages"]) == 1


def test_get_without_profile_returns_stored_text(client: TestClient, calls) -> None:
    put_profile(client)
    send(client)
    with closing(db.connect(settings.db_path(client.app.state.data_dir))) as conn:  # type: ignore[attr-defined]
        conn.execute("DELETE FROM profile")
        conn.commit()
    assert client.get("/api/chat").json()["messages"][0]["text"] == (
        "Can [YOU] retire at 65"
    )
