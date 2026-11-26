"""Strategy grid and ranking."""

from dataclasses import dataclass
from itertools import product

from backend.engine.projection import ConversionTarget, Projection, Strategy, project
from backend.engine.social_security import full_retirement_age
from backend.engine.tax import rmd_start_age
from backend.profile.models import Household, Person
from backend.rules.models import TaxRules

TARGETS: tuple[ConversionTarget, ...] = ("12", "22", "24", "irmaa1")
ORDERS = ("taxable_first", "pretax_first", "proportional")
CLAIM_EARLY = 62
CLAIM_LATE = 70
CONVERT_DELAY = 2


@dataclass(frozen=True)
class RankedStrategy:
    strategy: Strategy
    projection: Projection


def _claim_ages(p: Person) -> list[int]:
    if p.ss_claim_age is not None:
        return [p.ss_claim_age]
    fra = int(full_retirement_age(p.birth_date.year))
    return list(dict.fromkeys((CLAIM_EARLY, fra, CLAIM_LATE)))


def strategy_grid(h: Household, rules: TaxRules) -> list[Strategy]:
    """Conversion windows follow the oldest person, as the projection does."""
    oldest = min((h.self_, h.spouse or h.self_), key=lambda p: p.birth_date)
    froms = (oldest.retirement_age, oldest.retirement_age + CONVERT_DELAY)
    tos = (CLAIM_LATE, rmd_start_age(oldest.birth_date.year, rules) - 1)
    windows: list[tuple[ConversionTarget, int, int]] = [
        ("none", froms[0], tos[0]),
        *product(TARGETS, froms, tos),
    ]
    claims = product(
        _claim_ages(h.self_), _claim_ages(h.spouse) if h.spouse else [None]
    )
    grid = (
        Strategy(
            conversion_target=target,
            convert_from_age=start,
            convert_to_age=stop,
            withdrawal_order=order,
            claim_ages=claim,
        )
        for (target, start, stop), order, claim in product(windows, ORDERS, claims)
    )
    return list(dict.fromkeys(grid))


def rank_key(p: Projection) -> tuple[bool, float, float]:
    return (p.shortfall_year is not None, -p.after_tax_end, p.lifetime_tax)


def rank(h: Household, rules: TaxRules, start_year: int) -> list[RankedStrategy]:
    ranked = [
        RankedStrategy(s, project(h, s, rules, start_year))
        for s in strategy_grid(h, rules)
    ]
    return sorted(ranked, key=lambda r: rank_key(r.projection))
