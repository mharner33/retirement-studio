import json
from datetime import date
from functools import cache
from pathlib import Path

from pydantic import BaseModel

from backend.plan.models import PlanResult
from backend.profile.models import Household, age_on

SEED = Path(__file__).parent / "seed" / "bls_spending.json"


class AgeGroup(BaseModel):
    label: str
    min_age: int
    max_age: int | None
    annual_spending: float


class IncomeBand(BaseModel):
    label: str
    min_income: float
    max_income: float | None
    annual_spending: float


class Seed(BaseModel):
    source_url: str
    table_year: int
    age_groups: list[AgeGroup]
    income_bands: list[IncomeBand]


class Benchmark(BaseModel):
    source_url: str
    table_year: int
    age_group: str
    age_group_annual: float
    income_band: str
    income_band_annual: float
    planned_annual: float


@cache
def load_seed() -> Seed:
    return Seed.model_validate(json.loads(SEED.read_text()))


def benchmark(h: Household, plan: PlanResult) -> Benchmark:
    seed = load_seed()
    today = date.today()
    age = max(age_on(p.birth_date, today) for p in (h.self_, h.spouse) if p)
    group = next(
        g
        for g in seed.age_groups
        if g.min_age <= age and (g.max_age is None or age <= g.max_age)
    )
    rows = plan.best_rows
    planned = next(
        (
            r.spending
            for r in rows
            if r.ages[0] is not None and r.ages[0] >= h.self_.retirement_age
        ),
        rows[0].spending,
    )
    band = next(
        b
        for b in seed.income_bands
        if planned >= b.min_income and (b.max_income is None or planned < b.max_income)
    )
    return Benchmark(
        source_url=seed.source_url,
        table_year=seed.table_year,
        age_group=group.label,
        age_group_annual=group.annual_spending,
        income_band=band.label,
        income_band_annual=band.annual_spending,
        planned_annual=planned,
    )
