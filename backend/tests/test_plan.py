import time
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
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
