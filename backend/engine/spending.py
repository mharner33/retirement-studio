"""Safe extra yearly spending on the fixed-rate path."""

from backend.engine.projection import Strategy, project
from backend.profile.models import Household
from backend.rules.models import TaxRules

STEP = 100
MAX_EXTRA = 200_000


def safe_extra(h: Household, s: Strategy, rules: TaxRules, start_year: int) -> float:
    """Largest extra spending (today's dollars, a multiple of $100.00, up to
    $200,000.00) with no shortfall; 0 when even the base plan runs short."""

    def lasts(steps: int) -> bool:
        trial = s.model_copy(update={"extra_spending": steps * STEP})
        return project(h, trial, rules, start_year).shortfall_year is None

    low, high = 0, MAX_EXTRA // STEP
    if not lasts(low):
        return 0
    if lasts(high):
        return MAX_EXTRA
    while high - low > 1:
        mid = (low + high) // 2
        if lasts(mid):
            low = mid
        else:
            high = mid
    return low * STEP
