from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


def age_on(birth_date: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (birth_date.month, birth_date.day)
    return today.year - birth_date.year - (not had_birthday)


class Person(BaseModel):
    first_name: str
    birth_date: date
    retirement_age: int = Field(ge=50, le=80)
    plan_to_age: int = 82
    wages: float = 0
    contribution_401k: float = 0
    ss_at_62: float
    ss_at_fra: float
    ss_at_70: float
    ss_claim_age: int | None = Field(default=None, ge=62, le=70)
    pension_annual: float = 0
    pension_start_age: int | None = None
    pension_survivor_pct: float = 0

    @model_validator(mode="after")
    def plan_to_age_above_current_age(self) -> Self:
        if self.plan_to_age <= age_on(self.birth_date, date.today()):
            raise ValueError("plan_to_age must be above current age")
        return self


class Account(BaseModel):
    id: str
    kind: Literal["pretax", "roth", "taxable", "cash", "hsa"]
    owner: Literal["self", "spouse"]
    label: str
    balance: float = Field(ge=0)
    cost_basis: float = 0
    last4: str | None = None
    as_of: date


class OneTime(BaseModel):
    year: int
    amount: float
    label: str


class Spending(BaseModel):
    essential: float
    discretionary: float = 0
    cobra_monthly: float = 0
    bridge_monthly: float = 0
    bridge_is_aca: bool = False
    one_time: list[OneTime] = []


class Assumptions(BaseModel):
    return_rate: float = 0.06
    inflation: float = 0.025
    ss_cola: float = 0.025
    volatility: float = 0.12
    heir_tax_rate: float = 0.22


class Household(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    self_: Person = Field(alias="self")
    spouse: Person | None = None
    state: Literal["CO"] = "CO"
    accounts: list[Account]
    spending: Spending
    assumptions: Assumptions
    home_value: float = 0
    mask_terms: list[str] = []

    @property
    def filing_status(self) -> Literal["single", "mfj"]:
        return "mfj" if self.spouse else "single"
