"""Yearly income and health costs for the people in a household.

Ages are whole years: `year - birth year`. A person is alive through the year
they reach `plan_to_age`.
"""

from dataclasses import dataclass

from backend.engine.accounts import Owner
from backend.engine.social_security import monthly_benefit, spousal_topup
from backend.profile.models import Household, Person
from backend.rules.models import TaxRules

MEDICARE_AGE = 65
COBRA_MONTHS = 18


@dataclass(frozen=True)
class Member:
    role: Owner
    person: Person
    claim_age: int

    def age(self, year: int) -> int:
        return year - self.person.birth_date.year

    def alive(self, year: int) -> bool:
        return self.age(year) <= self.person.plan_to_age

    @property
    def last_year(self) -> int:
        return self.person.birth_date.year + self.person.plan_to_age

    def claimed(self, year: int) -> bool:
        return self.age(year) >= self.claim_age

    def own_benefit(self) -> float:
        """Yearly own Social Security benefit in today's dollars."""
        return monthly_benefit(self.person, self.claim_age) * 12

    def pension_started(self, year: int) -> bool:
        start = self.person.pension_start_age or self.person.retirement_age
        return self.age(year) >= start


def members(h: Household, claim_ages: tuple[int, int | None]) -> tuple[Member, ...]:
    """The household's people; a missing claim age falls back to the
    profile's, then to 67."""
    people: list[Member] = [
        Member("self", h.self_, claim_ages[0] or h.self_.ss_claim_age or 67)
    ]
    if h.spouse:
        claim = claim_ages[1] or h.spouse.ss_claim_age or 67
        people.append(Member("spouse", h.spouse, claim))
    return tuple(people)


def wages(m: Member, year: int, price: float) -> tuple[float, float]:
    """Wages and 401(k) contributions, inflated, until the retirement year."""
    if m.age(year) >= m.person.retirement_age:
        return 0.0, 0.0
    return m.person.wages * price, m.person.contribution_401k * price


def social_security(
    people: tuple[Member, ...], year: int, cola: float, rules: TaxRules
) -> dict[Owner, float]:
    """Yearly benefits for the living, multiplied by `cola` (the growth since
    the plan start). Spousal top-ups are paid once both have claimed; after a
    death the survivor keeps the larger of the two benefits.

    Simplification: the survivor receives the deceased's benefit (at the
    deceased's claim age) from the first year after the death, even before
    reaching their own claim age, and with no survivor-age reduction.
    """
    living = [m for m in people if m.alive(year)]
    own: dict[Owner, float] = {
        m.role: m.own_benefit() if m.claimed(year) else 0.0 for m in living
    }
    if len(living) < len(people):
        dead = next(m.own_benefit() for m in people if not m.alive(year))
        return {m.role: max(own[m.role], dead) * cola for m in living}
    if len(living) > 1 and all(m.claimed(year) for m in living):
        a, b = living
        own[a.role] += spousal_topup(a.person, b.person, a.claim_age, rules) * 12
        own[b.role] += spousal_topup(b.person, a.person, b.claim_age, rules) * 12
    return {role: amount * cola for role, amount in own.items()}


def pensions(people: tuple[Member, ...], year: int) -> dict[Owner, float]:
    """Pensions are flat in nominal dollars; a survivor receives
    `pension_survivor_pct` (a fraction) of the deceased's pension."""
    living = [m for m in people if m.alive(year)]
    out: dict[Owner, float] = {m.role: 0.0 for m in living}
    for m in people:
        if not m.pension_started(year):
            continue
        share = 1.0 if m.alive(year) else m.person.pension_survivor_pct
        out[m.role if m.alive(year) else living[0].role] += (
            m.person.pension_annual * share
        )
    return out


def health_premiums(
    h: Household, people: tuple[Member, ...], year: int, price: float, rules: TaxRules
) -> float:
    """COBRA for 18 months from the self's retirement year, then the bridge
    premium until the self turns 65 (both inflated by `price`), and Part B base
    for each living person 65 or older (`rules` are already for `year`)."""
    me = people[0]
    retired = me.person.birth_date.year + me.person.retirement_age
    total = 0.0
    if me.alive(year) and retired <= year and me.age(year) < MEDICARE_AGE:
        cobra = min(12, max(0, COBRA_MONTHS - 12 * (year - retired)))
        monthly = (
            cobra * h.spending.cobra_monthly + (12 - cobra) * h.spending.bridge_monthly
        )
        total += monthly * price
    on_medicare = sum(m.alive(year) and m.age(year) >= MEDICARE_AGE for m in people)
    return total + on_medicare * rules.part_b_base_monthly * 12
