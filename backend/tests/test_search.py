from backend.engine.projection import Projection
from backend.engine.search import rank, rank_key, strategy_grid
from backend.profile.models import Household
from backend.rules.models import TaxRules

START = 2026


def projection(
    shortfall_year: int | None, after_tax_end: float, tax: float
) -> Projection:
    return Projection(
        rows=[],
        lifetime_tax=tax,
        after_tax_end=after_tax_end,
        shortfall_year=shortfall_year,
    )


def test_grid_size_and_no_duplicates(
    sample_household: Household, rules: TaxRules
) -> None:
    grid = strategy_grid(sample_household, rules)
    assert 100 <= len(grid) <= 700
    assert len(set(grid)) == len(grid)
    assert len(grid) == 459
    assert {s.conversion_target for s in grid} == {"none", "12", "22", "24", "irmaa1"}
    assert {s.convert_from_age for s in grid if s.conversion_target != "none"} == {
        63,
        65,
    }
    assert {s.convert_to_age for s in grid if s.conversion_target != "none"} == {70, 74}
    assert {s.claim_ages for s in grid} == {
        (a, b) for a in (62, 67, 70) for b in (62, 67, 70)
    }


def test_grid_uses_fixed_claim_age_and_single(
    sample_household: Household, rules: TaxRules
) -> None:
    single = sample_household.model_copy(update={"spouse": None})
    single.self_ = single.self_.model_copy(update={"ss_claim_age": 66})
    grid = strategy_grid(single, rules)
    assert {s.claim_ages for s in grid} == {(66, None)}
    assert len(grid) == 17 * 3


def test_rank_key_prefers_lasting_plans() -> None:
    short_rich = projection(2040, 9_000_000, 0)
    lasting_poor = projection(None, 1_000, 500_000)
    lasting_rich = projection(None, 2_000, 600_000)
    lasting_rich_low_tax = projection(None, 2_000, 100_000)
    ordered = sorted(
        [short_rich, lasting_poor, lasting_rich, lasting_rich_low_tax], key=rank_key
    )
    assert ordered == [lasting_rich_low_tax, lasting_rich, lasting_poor, short_rich]


def test_rank_prefers_lasting_plans(
    sample_household: Household, rules: TaxRules
) -> None:
    tight = sample_household.model_copy(deep=True)
    tight.spending.essential = 90_000
    ranked = rank(tight, rules, START)
    lasts = [r.projection.shortfall_year is None for r in ranked]
    assert any(lasts)
    assert not all(lasts)
    assert lasts == sorted(lasts, reverse=True)
    keys = [rank_key(r.projection) for r in ranked]
    assert keys == sorted(keys)


def test_conversions_beat_none_for_sample(
    sample_household: Household, rules: TaxRules
) -> None:
    ranked = rank(sample_household, rules, START)
    best = ranked[0]
    baseline = next(r for r in ranked if r.strategy.conversion_target == "none")
    assert best.strategy.conversion_target != "none"
    assert best.projection.shortfall_year is None
    assert best.projection.after_tax_end > baseline.projection.after_tax_end
