from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import health
from agent.model import make_model
from agent.tests.stub_model import StubModel


def test_run_calls_health_tool(client: TestClient, monkeypatch) -> None:
    seen: list[str] = []
    original = client.get

    def spy(*args, **kwargs):
        response = original(*args, **kwargs)
        seen.append(response.text)
        return response

    monkeypatch.setattr(client, "get", spy)
    model = StubModel(
        [
            AIMessage(
                "",
                tool_calls=[{"name": "check_backend", "args": {}, "id": "c1"}],
            ),
            AIMessage("Backend is up"),
        ]
    )
    result = health.run(
        "Is the backend up?", "t1", client=cast(httpx.Client, client), model=model
    )
    assert result == "Backend is up"
    assert any("ok" in text for text in seen)


def test_make_model_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert make_model().model_name == "openrouter/free"  # type: ignore[attr-defined]
