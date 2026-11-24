from typing import Literal

from pydantic import BaseModel

FilingStatus = Literal["single", "mfj"]


class Bracket(BaseModel):
    rate: float
    up_to: float | None


class SeniorDeduction(BaseModel):
    amount_per_person: float
    phaseout_start: dict[FilingStatus, float]
    phaseout_rate: float
    last_year: int


class RmdStart(BaseModel):
    born_from: int
    born_to: int | None
    age: int


class IrmaaTier(BaseModel):
    magi_over: float
    part_b_monthly: float
    part_d_monthly: float


class SsReduction(BaseModel):
    own_first_36_per_month: float
    own_after_per_month: float
    spousal_first_36_per_month: float
    spousal_after_per_month: float
    delayed_credit_per_year: float


class AgeCap(BaseModel):
    min_age: int
    max_age: int | None
    cap: float


class ColoradoRules(BaseModel):
    rate: float
    retirement_subtraction: list[AgeCap]
    ss_full_subtraction_min_age: int


class TaxRules(BaseModel):
    year: int
    sources: list[str]
    federal_brackets: dict[FilingStatus, list[Bracket]]
    standard_deduction: dict[FilingStatus, float]
    additional_65: dict[FilingStatus, float]
    senior_deduction: SeniorDeduction | None
    ltcg_brackets: dict[FilingStatus, list[Bracket]]
    ss_taxation_thresholds: dict[FilingStatus, tuple[float, float]]
    rmd_start_ages: list[RmdStart]
    uniform_lifetime_table: dict[int, float]
    part_b_base_monthly: float
    irmaa: dict[FilingStatus, list[IrmaaTier]]
    ss_reduction: SsReduction
    colorado: ColoradoRules
