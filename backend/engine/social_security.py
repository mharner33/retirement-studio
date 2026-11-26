"""Social Security benefits in today's dollars per month, from the estimates
on the profile (at 62, full retirement age and 70)."""

from backend.profile.models import Person
from backend.rules.models import TaxRules

EARLIEST = 62
LATEST = 70
FRA_67_FROM = 1960  # birth year from which full retirement age is 67
EARLY_MONTHS_FIRST_TIER = 36


def full_retirement_age(birth_year: int) -> float:
    """SSA full retirement age: 66 through 1954, 66 and 2 to 10 months for
    1955-1959, 67 from 1960."""
    if birth_year >= FRA_67_FROM:
        return 67.0
    return 66 + max(0, birth_year - 1954) * 2 / 12


def monthly_benefit(person: Person, claim_age: int) -> float:
    """Own benefit at `claim_age`, interpolated linearly between the 62, full
    retirement age and 70 estimates."""
    age = min(max(claim_age, EARLIEST), LATEST)
    fra = full_retirement_age(person.birth_date.year)
    if age <= fra:
        share = (age - EARLIEST) / (fra - EARLIEST)
        return person.ss_at_62 + share * (person.ss_at_fra - person.ss_at_62)
    share = (age - fra) / (LATEST - fra)
    return person.ss_at_fra + share * (person.ss_at_70 - person.ss_at_fra)


def spousal_topup(own: Person, other: Person, claim_age: int, rules: TaxRules) -> float:
    """Monthly spousal top-up: half the other spouse's full-retirement-age
    benefit less one's own, reduced for each month claimed before full
    retirement age, with no delayed credits."""
    base = max(0.0, 0.5 * other.ss_at_fra - own.ss_at_fra)
    early = max(0, round((full_retirement_age(own.birth_date.year) - claim_age) * 12))
    first = min(early, EARLY_MONTHS_FIRST_TIER)
    factors = rules.ss_reduction
    reduction = (
        factors.spousal_first_36_per_month * first
        + factors.spousal_after_per_month * (early - first)
    )
    return base * (1 - reduction)
