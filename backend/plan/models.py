from pydantic import BaseModel

from backend.engine.projection import Strategy, YearRow
from backend.plan.changes import ChangeLine


class PlanOption(BaseModel):
    strategy: Strategy
    label: str
    lifetime_tax: float
    after_tax_end: float
    shortfall_year: int | None
    success_rate: float
    safe_extra: float


class PlanResult(BaseModel):
    rules_file: str
    rules_stale: bool
    top: list[PlanOption]
    baseline: PlanOption
    best_rows: list[YearRow]


class WhatIfResult(BaseModel):
    current: PlanResult
    whatif: PlanResult
    changes: list[ChangeLine]
