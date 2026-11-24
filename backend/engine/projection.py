"""Year-by-year projection of a household under one strategy.

Each year: wages and 401(k) contributions, Social Security and pensions, RMDs,
the strategy's Roth conversion, then withdrawals that cover spending, health
premiums and that same year's tax (federal, Colorado and IRMAA), grossed up
by iteration. Then returns are applied, with cash growing at inflation. The
function is pure: the household and rules are not changed.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.engine.accounts import OWNERS, Draw, Owner, Portfolio, WithdrawalOrder
from backend.engine.income import (
    Member,
    health_premiums,
    members,
    pensions,
    social_security,
    wages,
)
from backend.engine.tax import (
    PersonIncome,
    TaxUnit,
    bracket_top,
    colorado_tax,
    federal_tax,
    irmaa_annual,
    rmd,
    rmd_start_age,
    rules_for_year,
    taxable_social_security,
)
from backend.profile.models import Household
from backend.rules.models import FilingStatus, TaxRules

ConversionTarget = Literal["none", "12", "22", "24", "irmaa1"]
MAX_ROUNDS = 20
TOLERANCE = 1.0
CONVERSION_TOLERANCE = 0.01
IRMAA_MARGIN = 1_000.0
BISECT_STEPS = 40
IRMAA_LOOKBACK = 2

ORDER_LABELS: dict[WithdrawalOrder, str] = {
    "taxable_first": "taxable first",
    "pretax_first": "pretax first",
    "proportional": "proportional",
}


class Strategy(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversion_target: ConversionTarget
    convert_from_age: int
    convert_to_age: int
    withdrawal_order: WithdrawalOrder
    claim_ages: tuple[int, int | None]
    extra_spending: float = 0

    def label(self) -> str:
        span = f"{self.convert_from_age}-{self.convert_to_age}"
        if self.conversion_target == "none":
            conversion = "No conversions"
        elif self.conversion_target == "irmaa1":
            conversion = f"Fill to IRMAA tier 1 {span}"
        else:
            conversion = f"Fill {self.conversion_target}% bracket {span}"
        claims = "/".join(str(a) for a in self.claim_ages if a is not None)
        order = ORDER_LABELS[self.withdrawal_order]
        return f"{conversion}, {order}, claim {claims}"


class YearRow(BaseModel):
    """One plan year in nominal dollars. `ages` follow the household order
    (self, spouse), None once a person has passed their plan-to age."""

    year: int
    ages: list[int | None]
    filing: FilingStatus
    wages: float
    social_security: float
    pension: float
    rmd: float
    conversion: float
    withdrawals: dict[str, float]
    spending: float
    health_premiums: float
    ordinary_income: float
    capital_gains: float
    federal_tax: float
    state_tax: float
    irmaa: float
    magi: float
    balances: dict[str, float]
    shortfall: float


class Projection(BaseModel):
    rows: list[YearRow]
    lifetime_tax: float
    after_tax_end: float
    shortfall_year: int | None


@dataclass(frozen=True)
class _Plan:
    household: Household
    strategy: Strategy
    rules: TaxRules
    people: tuple[Member, ...]
    start_year: int

    def year(self, index: int, magis: list[float]) -> "_Year":
        year = self.start_year + index
        inflation = self.household.assumptions.inflation
        living = tuple(m for m in self.people if m.alive(year))
        filing: FilingStatus = "mfj" if len(living) > 1 else "single"
        lookback = magis[index - IRMAA_LOOKBACK] if index >= IRMAA_LOOKBACK else None
        return _Year(
            plan=self,
            year=year,
            index=index,
            rules=rules_for_year(self.rules, year, inflation),
            living=living,
            unit=TaxUnit(filing, tuple(m.age(year) for m in living), year),
            price=(1 + inflation) ** index,
            magi_lookback=lookback,
        )


@dataclass(frozen=True)
class _Year:
    plan: _Plan
    year: int
    index: int
    rules: TaxRules
    living: tuple[Member, ...]
    unit: TaxUnit
    price: float
    magi_lookback: float | None


@dataclass(frozen=True)
class _Base:
    """A year's flows fixed before the conversion and withdrawals."""

    wages: float
    earned: float  # wages less 401(k) contributions
    ss: dict[Owner, float]
    pension: dict[Owner, float]
    rmd: dict[Owner, float]
    spending: float
    health: float

    @property
    def fixed_ordinary(self) -> float:
        return self.earned + sum(self.pension.values()) + sum(self.rmd.values())

    @property
    def inflows(self) -> float:
        return self.fixed_ordinary + sum(self.ss.values())

    @property
    def outflows(self) -> float:
        return self.spending + self.health


@dataclass(frozen=True)
class _Mix:
    """Ordinary income other than Social Security, benefits and gains."""

    fixed: float
    ss: float
    ltcg: float

    def ordinary(self, extra: float, yr: _Year) -> float:
        """Ordinary income, taxable Social Security included, with `extra`
        more of other ordinary income."""
        other = self.fixed + extra
        taxable = taxable_social_security(
            self.ss, other + self.ltcg, yr.unit.filing, yr.rules
        )
        return other + taxable


@dataclass(frozen=True)
class _Taxes:
    ordinary: float = 0.0
    ltcg: float = 0.0
    federal: float = 0.0
    state: float = 0.0
    irmaa: float = 0.0

    @property
    def total(self) -> float:
        return self.federal + self.state + self.irmaa

    @property
    def magi(self) -> float:
        return self.ordinary + self.ltcg


@dataclass(frozen=True)
class _Settlement:
    conversion: dict[int, float]
    draw: Draw
    taxes: _Taxes


def project(
    h: Household,
    s: Strategy,
    rules: TaxRules,
    start_year: int,
    returns: list[float] | None = None,
) -> Projection:
    """Project from `start_year` through the last living person's plan-to
    age. `returns[i]` is the return in plan year i; None uses
    `assumptions.return_rate` every year."""
    plan = _Plan(h, s, rules, members(h, s.claim_ages), start_year)
    portfolio = Portfolio(h.accounts)
    last = max(m.last_year for m in plan.people)
    rows: list[YearRow] = []
    magis: list[float] = []
    for index in range(last - start_year + 1):
        rate = h.assumptions.return_rate if returns is None else returns[index]
        row = _run_year(plan.year(index, magis), portfolio, rate)
        rows.append(row)
        magis.append(row.magi)
    return _summarize(h, rows)


def _run_year(yr: _Year, portfolio: Portfolio, rate: float) -> YearRow:
    portfolio.roll_over(tuple(m.role for m in yr.living))
    base = _begin(yr, portfolio)
    settled = _settle(yr, base, portfolio)
    portfolio.convert(settled.conversion)
    portfolio.withdraw(settled.draw.amounts)
    drawn = sum(settled.draw.amounts.values())
    surplus = base.inflows + drawn - base.outflows - settled.taxes.total
    if surplus > 0:
        portfolio.deposit("cash", yr.living[0].role, surplus)
    portfolio.grow(rate, yr.plan.household.assumptions.inflation)
    return _row(yr, base, settled, portfolio)


def _begin(yr: _Year, portfolio: Portfolio) -> _Base:
    """Wages, contributions (deposited), benefits, pensions, RMDs (taken)
    and spending for the year."""
    h = yr.plan.household
    gross = earned = 0.0
    for m in yr.living:
        wage, contribution = wages(m, yr.year, yr.price)
        gross += wage
        earned += wage - contribution
        if contribution:
            portfolio.deposit("pretax", m.role, contribution)
    cola = (1 + h.assumptions.ss_cola) ** yr.index
    people = yr.plan.people
    return _Base(
        wages=gross,
        earned=earned,
        ss=social_security(people, yr.year, cola, yr.rules),
        pension=pensions(people, yr.year),
        rmd={m.role: _take_rmd(m, yr, portfolio) for m in yr.living},
        spending=_spending(yr),
        health=health_premiums(h, people, yr.year, yr.price, yr.rules),
    )


def _take_rmd(m: Member, yr: _Year, portfolio: Portfolio) -> float:
    age = m.age(yr.year)
    if age < rmd_start_age(m.person.birth_date.year, yr.rules):
        return 0.0
    amount = rmd(portfolio.pretax_balance(m.role), age, yr.rules)
    portfolio.withdraw(portfolio.pretax_split(amount, (m.role,)))
    return amount


def _spending(yr: _Year) -> float:
    spending = yr.plan.household.spending
    one_time = sum(o.amount for o in spending.one_time if o.year == yr.year)
    yearly = (
        spending.essential + spending.discretionary + yr.plan.strategy.extra_spending
    )
    return (yearly + one_time) * yr.price


def _settle(yr: _Year, base: _Base, portfolio: Portfolio) -> _Settlement:
    """Gross up: repeat the conversion, withdrawals and tax until the tax
    changes by less than $1 and the conversion by less than a cent, at most
    20 rounds."""
    settled = _Settlement({}, Draw({}, 0.0), _Taxes())
    for _ in range(MAX_ROUNDS):
        nxt = _round(yr, base, portfolio, settled)
        tax_change = abs(nxt.taxes.total - settled.taxes.total)
        conversion_change = abs(
            sum(nxt.conversion.values()) - sum(settled.conversion.values())
        )
        settled = nxt
        if tax_change < TOLERANCE and conversion_change < CONVERSION_TOLERANCE:
            break
    return settled


def _round(
    yr: _Year, base: _Base, portfolio: Portfolio, prev: _Settlement
) -> _Settlement:
    conversion = _conversion(yr, base, portfolio, prev)
    need = base.outflows + prev.taxes.total - base.inflows
    draw = portfolio.plan(need, yr.plan.strategy.withdrawal_order, conversion)
    return _Settlement(conversion, draw, _taxes(yr, base, portfolio, conversion, draw))


def _conversion(
    yr: _Year, base: _Base, portfolio: Portfolio, prev: _Settlement
) -> dict[int, float]:
    """Pretax to convert: enough to bring ordinary income (including this
    year's pretax withdrawals and the taxable Social Security the conversion
    adds) to the bracket top, or MAGI to $1,000 under the first IRMAA tier."""
    s = yr.plan.strategy
    oldest = max(m.age(yr.year) for m in yr.living)
    if s.conversion_target == "none" or not (
        s.convert_from_age <= oldest <= s.convert_to_age
    ):
        return {}
    drawn = sum(portfolio.by_owner(prev.draw.amounts, "pretax").values())
    mix = _Mix(base.fixed_ordinary + drawn, sum(base.ss.values()), prev.taxes.ltcg)
    cap = sum(portfolio.pretax_balance(o) for o in OWNERS)
    amount = _fill(_goal(yr, mix.ltcg), mix, cap, yr)
    return portfolio.pretax_split(amount, OWNERS)


def _goal(yr: _Year, ltcg: float) -> float:
    """Ordinary income the conversion fills up to."""
    target = yr.plan.strategy.conversion_target
    if target == "irmaa1":
        first_tier = yr.rules.irmaa[yr.unit.filing][1].magi_over
        return first_tier - IRMAA_MARGIN - ltcg
    return bracket_top(int(target) / 100, yr.unit, yr.rules, ltcg)


def _fill(goal: float, mix: _Mix, cap: float, yr: _Year) -> float:
    """Largest extra ordinary income, up to `cap`, that keeps ordinary
    income at or under `goal` (bisection, as taxable Social Security rises
    with it)."""
    if mix.ordinary(0.0, yr) >= goal:
        return 0.0
    low, high = 0.0, min(cap, goal - mix.fixed)
    if mix.ordinary(high, yr) <= goal:
        return high
    for _ in range(BISECT_STEPS):
        mid = (low + high) / 2
        if mix.ordinary(mid, yr) <= goal:
            low = mid
        else:
            high = mid
    return low


def _taxes(
    yr: _Year,
    base: _Base,
    portfolio: Portfolio,
    conversion: dict[int, float],
    draw: Draw,
) -> _Taxes:
    """Federal, Colorado and IRMAA for the year. Conversions count toward
    each person's Colorado retirement income, since the pension and annuity
    subtraction covers taxable IRA distributions."""
    withdrawn = portfolio.by_owner(draw.amounts, "pretax")
    converted = portfolio.by_owner(conversion, "pretax")
    ltcg = portfolio.gains(draw.amounts)
    other = sum(withdrawn.values()) + sum(converted.values())
    mix = _Mix(base.fixed_ordinary + other, sum(base.ss.values()), ltcg)
    ordinary = mix.ordinary(0.0, yr)
    federal = federal_tax(ordinary, ltcg, yr.unit, yr.rules)
    agi = ordinary + ltcg
    distributions: dict[Owner, float] = {o: withdrawn[o] + converted[o] for o in OWNERS}
    incomes = _person_incomes(yr, base, ordinary - mix.fixed, distributions)
    state = colorado_tax(federal.taxable_income, agi, incomes, yr.unit, yr.rules)
    magi = agi if yr.magi_lookback is None else yr.magi_lookback
    irmaa = irmaa_annual(magi, yr.unit.filing, yr.unit.people_65_plus, yr.rules)
    return _Taxes(ordinary, ltcg, federal.tax, state, irmaa)


def _person_incomes(
    yr: _Year, base: _Base, taxable_ss: float, distributions: dict[Owner, float]
) -> list[PersonIncome]:
    """Split taxable Social Security by each person's benefit; retirement
    income is pension plus pretax RMDs, withdrawals and conversions."""
    total_ss = sum(base.ss.values())
    return [
        PersonIncome(
            taxable_ss * base.ss.get(m.role, 0.0) / total_ss if total_ss else 0.0,
            base.pension.get(m.role, 0.0)
            + base.rmd.get(m.role, 0.0)
            + distributions[m.role],
        )
        for m in yr.living
    ]


def _row(yr: _Year, base: _Base, settled: _Settlement, portfolio: Portfolio) -> YearRow:
    taxes = settled.taxes
    return YearRow(
        year=yr.year,
        ages=[m.age(yr.year) if m.alive(yr.year) else None for m in yr.plan.people],
        filing=yr.unit.filing,
        wages=base.wages,
        social_security=sum(base.ss.values()),
        pension=sum(base.pension.values()),
        rmd=sum(base.rmd.values()),
        conversion=sum(settled.conversion.values()),
        withdrawals=portfolio.by_kind(settled.draw.amounts),
        spending=base.spending,
        health_premiums=base.health,
        ordinary_income=taxes.ordinary,
        capital_gains=taxes.ltcg,
        federal_tax=taxes.federal,
        state_tax=taxes.state,
        irmaa=taxes.irmaa,
        magi=taxes.magi,
        balances=portfolio.by_kind(),
        shortfall=settled.draw.shortfall,
    )


def _summarize(h: Household, rows: list[YearRow]) -> Projection:
    """Totals in today's dollars: tax deflated year by year, and the ending
    balances (pretax net of the heirs' tax rate) deflated over the plan."""
    inflation = h.assumptions.inflation
    lifetime_tax = sum(
        (r.federal_tax + r.state_tax + r.irmaa) / (1 + inflation) ** i
        for i, r in enumerate(rows)
    )
    end = rows[-1].balances
    heirs_tax = end["pretax"] * h.assumptions.heir_tax_rate
    after_tax_end = (sum(end.values()) - heirs_tax) / (1 + inflation) ** len(rows)
    shortfall_year = next((r.year for r in rows if r.shortfall > 0), None)
    return Projection(
        rows=rows,
        lifetime_tax=lifetime_tax,
        after_tax_end=after_tax_end,
        shortfall_year=shortfall_year,
    )
