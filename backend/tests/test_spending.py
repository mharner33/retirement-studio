from backend.engine.projection import Strategy, project
from backend.engine.spending import safe_extra
from backend.profile.models import Household
from backend.rules.models import TaxRules

START = 2026
STRATEGY = Strategy(
    conversion_target="22",
    convert_from_age=63,
    convert_to_age=70,
    withdrawal_order="taxable_first",
    claim_ages=(70, 67),
)


def test_safe_extra_is_boundary(sample_household: Household, rules: TaxRules) -> None:
    extra = safe_extra(sample_household, STRATEGY, rules, START)
    assert 0 < extra < 200_000
    assert extra % 100 == 0
    at = STRATEGY.model_copy(update={"extra_spending": extra})
    over = STRATEGY.model_copy(update={"extra_spending": extra + 200})
    assert project(sample_household, at, rules, START).shortfall_year is None
    assert project(sample_household, over, rules, START).shortfall_year is not None


def test_safe_extra_zero_when_base_runs_short(
    sample_household: Household, rules: TaxRules
) -> None:
    broke = sample_household.model_copy(deep=True)
    broke.spending.essential = 2_000_000
    assert safe_extra(broke, STRATEGY, rules, START) == 0
