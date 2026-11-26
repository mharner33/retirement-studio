import time
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.plan import api as plan_api
from backend.profile.models import Household
from backend.rules.models import TaxRules
from backend.tests.conftest import build_sample_household

TIME_BUDGET = 20.0


@pytest.fixture(scope="module")
def timed_plan(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[int, dict[str, Any], float]:
    client = TestClient(create_app(tmp_path_factory.mktemp("plan")))
    saved = build_sample_household().model_dump(mode="json", by_alias=True)
    assert client.put("/api/profile", json=saved).status_code == 200
    began = time.perf_counter()
    res = client.get("/api/plan")
    return res.status_code, res.json(), time.perf_counter() - began


def test_plan_needs_profile(client: TestClient) -> None:
    assert client.get("/api/plan").status_code == 409


def test_plan_endpoint_shape(timed_plan: tuple[int, dict[str, Any], float]) -> None:
    status, data, _ = timed_plan
    assert status == 200
    assert set(data) == {"rules_file", "rules_stale", "top", "baseline", "best_rows"}
    assert data["rules_file"] == "retirement_rules_2026-01-01.md"
    expected = (date.today() - date(2026, 1, 1)).days > 90
    assert data["rules_stale"] == expected
    assert len(data["top"]) == 5
    option_keys = {
        "strategy",
        "label",
        "lifetime_tax",
        "after_tax_end",
        "shortfall_year",
        "success_rate",
        "safe_extra",
    }
    for option in [*data["top"], data["baseline"]]:
        assert set(option) == option_keys
        assert 0 <= option["success_rate"] <= 1
        assert option["safe_extra"] >= 0
    assert data["baseline"]["strategy"]["conversion_target"] == "none"
    ends = [o["after_tax_end"] for o in data["top"]]
    assert ends == sorted(ends, reverse=True)
    assert data["top"][0]["after_tax_end"] > data["baseline"]["after_tax_end"]
    assert data["best_rows"][0]["year"] == date.today().year


@pytest.mark.slow
def test_plan_endpoint_runtime_under_20s(
    timed_plan: tuple[int, dict[str, Any], float],
) -> None:
    status, _, seconds = timed_plan
    assert status == 200
    assert seconds < TIME_BUDGET


def _save_sample(client: TestClient) -> None:
    saved = build_sample_household().model_dump(mode="json", by_alias=True)
    assert client.put("/api/profile", json=saved).status_code == 200


def test_whatif_retire_at_65(client: TestClient) -> None:
    _save_sample(client)
    body = [{"op": "set", "path": "self.retirement_age", "value": 65}]
    res = client.post("/api/plan/whatif", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["whatif"]["best_rows"][0]["wages"] > 0
    assert data["current"] == client.get("/api/plan").json()
    assert data["changes"] == [
        {"label": "Retirement age (you)", "kind": "age", "old": 63, "new": 65}
    ]
    assert client.get("/api/profile").json()["self"]["retirement_age"] == 63


def test_whatif_422_on_bad_change(client: TestClient) -> None:
    _save_sample(client)
    body = [{"op": "set", "path": "self.first_name", "value": 1}]
    res = client.post("/api/plan/whatif", json=body)
    assert res.status_code == 422
    assert "first_name" in res.json()["detail"]


def test_whatif_409_without_profile(client: TestClient) -> None:
    assert client.post("/api/plan/whatif", json=[]).status_code == 409


def test_plan_for_cached(
    monkeypatch: pytest.MonkeyPatch, rules: TaxRules, sample_household: Household
) -> None:
    calls: list[int] = []
    real_rank = plan_api.rank

    def counting_rank(*args: Any) -> Any:
        calls.append(1)
        return real_rank(*args)

    monkeypatch.setattr(plan_api, "rank", counting_rank)
    plan_api._cache.clear()
    first = plan_api.plan_for(sample_household, rules, "r.md", 2026, False)
    second = plan_api.plan_for(sample_household, rules, "r.md", 2026, False)
    assert second is first
    assert len(calls) == 1
