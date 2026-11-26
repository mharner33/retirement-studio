from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.chat.benchmark import Seed, benchmark, load_seed
from backend.engine.projection import YearRow
from backend.plan.models import PlanResult
from backend.tests.conftest import build_sample_household


def plan_with(*spending: float) -> PlanResult:
    rows = [
        YearRow.model_construct(ages=[a, a], spending=s)
        for a, s in enumerate(spending, 60)
    ]
    return SimpleNamespace(best_rows=rows)  # type: ignore[return-value]


def test_seed_validates() -> None:
    seed = load_seed()
    assert Seed.model_validate(seed.model_dump()) == seed
    assert seed.source_url.startswith("https://www.bls.gov/")
    mins = [b.min_income for b in seed.income_bands]
    assert mins == sorted(mins)
    assert mins[0] == 0
    assert seed.income_bands[-1].max_income is None
    assert all(
        b.max_income == n.min_income
        for b, n in zip(seed.income_bands, seed.income_bands[1:], strict=False)
    )
    assert seed.age_groups[-1].max_age is None


def test_picks_band_for_planned_spending() -> None:
    h = build_sample_household()
    h.self_.birth_date = date(date.today().year - 60, 1, 1)
    # self retires at 63: third row has age 62? rows start at age 60 -> index 3
    b = benchmark(h, plan_with(10, 10, 10, 85000.0, 200000.0))
    assert b.planned_annual == 85000.0
    assert b.income_band == "$70,000 to $99,999"
    assert b.income_band_annual == 70971


def test_already_retired_uses_first_row() -> None:
    h = build_sample_household()
    h.self_.retirement_age = 50
    b = benchmark(h, plan_with(45000.0, 300000.0))
    assert b.planned_annual == 45000.0
    assert b.income_band == "$40,000 to $49,999"


def test_age_group_of_older_person() -> None:
    h = build_sample_household()
    h.self_.birth_date = date(date.today().year - 40, 1, 1)
    assert h.spouse is not None
    h.spouse.birth_date = date(date.today().year - 70, 1, 1)
    b = benchmark(h, plan_with(50000.0))
    assert b.age_group == "65-74"
    assert b.age_group_annual == 69333


def test_benchmark_route(client: TestClient) -> None:
    assert client.get("/api/chat/benchmark").status_code == 409
    body = build_sample_household().model_dump(mode="json", by_alias=True)
    assert client.put("/api/profile", json=body).status_code == 200
    r = client.get("/api/chat/benchmark")
    assert r.status_code == 200
    assert r.json()["source_url"].startswith("https://www.bls.gov/")
