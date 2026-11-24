from backend.engine.projection import Strategy
from backend.engine.whatif import return_paths, success_rate, success_rates
from backend.profile.models import Household
from backend.rules.models import TaxRules

START = 2026
STRATEGY = Strategy(
    conversion_target="12",
    convert_from_age=63,
    convert_to_age=74,
    withdrawal_order="taxable_first",
    claim_ages=(67, 67),
)


def test_return_paths_one_return_per_plan_year(sample_household: Household) -> None:
    paths = return_paths(sample_household, START, 3, seed=7)
    assert len(paths) == 3
    assert all(len(p) == 22 for p in paths)
    assert paths == return_paths(sample_household, START, 3, seed=7)
    assert paths != return_paths(sample_household, START, 3, seed=8)


def test_success_rate_repeatable_with_seed(
    sample_household: Household, rules: TaxRules
) -> None:
    tight = sample_household.model_copy(deep=True)
    tight.spending.essential = 80_000
    first = success_rate(tight, STRATEGY, rules, START, return_paths(tight, START, 60))
    again = success_rate(tight, STRATEGY, rules, START, return_paths(tight, START, 60))
    assert first == again
    assert 0 < first < 1


def test_success_rate_defaults_to_1000_seeded_paths(
    sample_household: Household, rules: TaxRules
) -> None:
    assert len(return_paths(sample_household, START)) == 1000
    assert success_rate(sample_household, STRATEGY, rules, START) == success_rate(
        sample_household, STRATEGY, rules, START, return_paths(sample_household, START)
    )


def test_success_rate_zero_when_spending_impossible(
    sample_household: Household, rules: TaxRules
) -> None:
    broke = sample_household.model_copy(deep=True)
    broke.spending.essential = 2_000_000
    paths = return_paths(broke, START, 20)
    assert success_rate(broke, STRATEGY, rules, START, paths) == 0.0


def test_success_rates_batch_matches_single(
    sample_household: Household, rules: TaxRules
) -> None:
    tight = sample_household.model_copy(deep=True)
    tight.spending.essential = 80_000
    other = STRATEGY.model_copy(update={"conversion_target": "none"})
    paths = return_paths(tight, START, 40)
    assert success_rates(tight, [STRATEGY, other], rules, START, paths) == [
        success_rate(tight, STRATEGY, rules, START, paths),
        success_rate(tight, other, rules, START, paths),
    ]
