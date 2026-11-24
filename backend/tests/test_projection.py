from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.engine.projection import Projection, Strategy, YearRow, project
from backend.engine.social_security import monthly_benefit
from backend.engine.tax import TaxUnit, bracket_top, irmaa_annual, rules_for_year
from backend.profile.models import Household, Person
from backend.rules import store
from backend.rules.models import TaxRules

START = 2026


@pytest.fixture(scope="module")
def rules() -> TaxRules:
    return store.parse_rules((store.SEED_DIR / store.SEED_FILENAME).read_text())


def strategy(target: str = "none", **kw: object) -> Strategy:
    data: dict[str, object] = {
        "conversion_target": target,
        "convert_from_age": 63,
        "convert_to_age": 74,
        "withdrawal_order": "taxable_first",
        "claim_ages": (67, 67),
    }
    return Strategy.model_validate(data | kw)


def row(p: Projection, year: int) -> YearRow:
    return next(r for r in p.rows if r.year == year)


def test_strategy_label() -> None:
    assert (
        strategy("12").label() == "Fill 12% bracket 63-74, taxable first, claim 67/67"
    )
    assert (
        strategy("none", withdrawal_order="proportional", claim_ages=(70, None)).label()
        == "No conversions, proportional, claim 70"
    )
    assert strategy("irmaa1").label().startswith("Fill to IRMAA tier 1 63-74")


def test_project_rows_span_to_last_plan_to_age(
    sample_household: Household, rules: TaxRules
) -> None:
    p = project(sample_household, strategy(), rules, START)
    # self born 1963 to 82 -> 2045; spouse born 1965 to 82 -> 2047
    assert [r.year for r in p.rows] == list(range(2026, 2048))
    assert p.rows[0].ages == [63, 61]
    assert p.rows[-1].ages == [None, 82]


def test_no_conversion_strategy_has_zero_conversions(
    sample_household: Household, rules: TaxRules
) -> None:
    p = project(sample_household, strategy("none"), rules, START)
    assert all(r.conversion == 0 for r in p.rows)


def test_fill_12_conversion_hits_bracket_top(
    sample_household: Household, rules: TaxRules
) -> None:
    p = project(sample_household, strategy("12"), rules, START)
    converting = [r for r in p.rows if r.conversion > 0]
    assert converting[0].year == 2026
    assert all(63 <= max(a for a in r.ages if a) <= 74 for r in converting)
    for r in converting[:5]:
        unit = TaxUnit(r.filing, tuple(a for a in r.ages if a is not None), r.year)
        year_rules = rules_for_year(rules, r.year, 0.025)
        top = bracket_top(0.12, unit, year_rules, r.capital_gains)
        assert r.ordinary_income == pytest.approx(top, abs=1.0)
    assert row(p, 2038).conversion == 0


def test_rmd_starts_at_75_for_1963(
    sample_household: Household, rules: TaxRules
) -> None:
    p = project(sample_household, strategy("none"), rules, START)
    assert row(p, 2037).rmd == 0
    assert row(p, 2038).rmd > 0


def test_cobra_then_bridge_then_part_b(
    sample_household: Household, rules: TaxRules
) -> None:
    h = sample_household.model_copy(deep=True)
    h.spending.bridge_monthly = 1_000
    p = project(h, strategy(), rules, START)
    # retires 2026 at 63: 12 months COBRA, then 6 COBRA + 6 bridge, then Part B at 65
    assert row(p, 2026).health_premiums == pytest.approx(12 * 1_800)
    assert row(p, 2027).health_premiums == pytest.approx(
        (6 * 1_800 + 6 * 1_000) * 1.025
    )
    part_b_2028 = rules_for_year(rules, 2028, 0.025).part_b_base_monthly
    assert row(p, 2028).health_premiums == pytest.approx(12 * part_b_2028)
    # spouse turns 65 in 2030: two people on Part B
    part_b_2030 = rules_for_year(rules, 2030, 0.025).part_b_base_monthly
    assert row(p, 2030).health_premiums == pytest.approx(2 * 12 * part_b_2030)


def test_survivor_files_single_and_keeps_larger_benefit(
    sample_household: Household, rules: TaxRules
) -> None:
    h = sample_household.model_copy(deep=True)
    h.self_.plan_to_age = 72  # last year 2035
    p = project(h, strategy(), rules, START)
    assert row(p, 2035).filing == "mfj"
    survivor = row(p, 2036)
    assert survivor.filing == "single"
    assert survivor.ages == [None, 71]
    larger = monthly_benefit(h.self_, 67) * 12 * 1.025 ** (2036 - START)
    assert survivor.social_security == pytest.approx(larger)
    assert survivor.balances["pretax"] > 0
    # the survivor's RMD age (born 1965, 75) applies to the rolled-over 401(k)
    assert row(p, 2039).rmd == 0
    assert row(p, 2040).rmd > 0


def test_already_retired_person_starts_now(rules: TaxRules) -> None:
    me = Person(
        first_name="Pat",
        birth_date=date(1958, 1, 1),
        retirement_age=60,
        wages=90_000,
        ss_at_62=2_000,
        ss_at_fra=2_800,
        ss_at_70=3_500,
        pension_annual=12_000,
        pension_start_age=60,
    )
    h = Household.model_validate(
        {
            "self": me,
            "accounts": [
                {
                    "id": "c",
                    "kind": "cash",
                    "owner": "self",
                    "label": "Cash",
                    "balance": 500_000,
                    "as_of": "2026-01-01",
                }
            ],
            "spending": {"essential": 40_000},
            "assumptions": {},
        }
    )
    p = project(h, strategy(claim_ages=(62, None)), rules, START)
    first = p.rows[0]
    assert first.ages == [68]
    assert first.filing == "single"
    assert first.wages == 0
    assert first.pension == 12_000
    assert first.social_security == pytest.approx(2_000 * 12)
    assert p.rows[-1].year == 1958 + 82


def test_overspending_reports_shortfall_without_error(
    sample_household: Household, rules: TaxRules
) -> None:
    p = project(sample_household, strategy(extra_spending=200_000), rules, START)
    assert p.shortfall_year is not None
    assert p.rows[-1].year == 2047
    late = row(p, p.shortfall_year + 1)
    assert sum(late.balances.values()) == 0


def test_deterministic_same_inputs_same_output(
    sample_household: Household, rules: TaxRules
) -> None:
    s = strategy("22", withdrawal_order="proportional")
    assert project(sample_household, s, rules, START) == project(
        sample_household, s, rules, START
    )


def test_returns_sequence_changes_outcome(
    sample_household: Household, rules: TaxRules
) -> None:
    base = project(sample_household, strategy(), rules, START)
    poor = project(sample_household, strategy(), rules, START, [0.0] * 22)
    assert poor.after_tax_end < base.after_tax_end
    assert base.lifetime_tax > 0


def test_irmaa1_stays_under_first_threshold(
    sample_household: Household, rules: TaxRules
) -> None:
    p = project(sample_household, strategy("irmaa1"), rules, START)
    uncapped = [r for r in p.rows if r.conversion > 0 and r.balances["pretax"] > 0]
    assert len(uncapped) >= 4
    for r in uncapped:
        threshold = rules_for_year(rules, r.year, 0.025).irmaa[r.filing][1].magi_over
        assert r.magi == pytest.approx(threshold - 1_000, abs=1.0)


def test_pretax_first_and_proportional_draw_pretax(
    sample_household: Household, rules: TaxRules
) -> None:
    first = project(
        sample_household, strategy(withdrawal_order="pretax_first"), rules, START
    )
    prop = project(
        sample_household, strategy(withdrawal_order="proportional"), rules, START
    )
    assert first.rows[0].withdrawals["pretax"] > 0
    assert first.rows[0].withdrawals["taxable"] == 0
    assert prop.rows[0].withdrawals["pretax"] > 0
    assert prop.rows[0].withdrawals["taxable"] > 0


def test_project_endpoint_returns_rows(
    client: TestClient, sample_household: Household
) -> None:
    body = {
        "conversion_target": "12",
        "convert_from_age": 63,
        "convert_to_age": 74,
        "withdrawal_order": "taxable_first",
        "claim_ages": [67, 67],
    }
    assert client.post("/api/plan/project", json=body).status_code == 409
    saved = sample_household.model_dump(mode="json", by_alias=True)
    assert client.put("/api/profile", json=saved).status_code == 200
    res = client.post("/api/plan/project", json=body)
    assert res.status_code == 200
    data = res.json()
    assert data["rows"][0]["year"] == date.today().year
    assert data["rows"][0]["conversion"] > 0
    assert set(data) >= {"rows", "lifetime_tax", "after_tax_end", "shortfall_year"}


ORDERS = ("taxable_first", "pretax_first", "proportional")


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("target", ["12", "22", "24"])
def test_conversion_never_overshoots_bracket_top(
    sample_household: Household, rules: TaxRules, target: str, order: str
) -> None:
    p = project(
        sample_household, strategy(target, withdrawal_order=order), rules, START
    )
    converting = [r for r in p.rows if r.conversion > 0]
    assert converting
    for r in converting:
        unit = TaxUnit(r.filing, tuple(a for a in r.ages if a is not None), r.year)
        year_rules = rules_for_year(rules, r.year, 0.025)
        top = bracket_top(int(target) / 100, unit, year_rules, r.capital_gains)
        assert r.ordinary_income <= top + 1


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("target", ["12", "24"])
@pytest.mark.parametrize("extra", [0, 190_000])
def test_money_is_conserved_every_year(
    sample_household: Household, rules: TaxRules, target: str, order: str, extra: int
) -> None:
    s = strategy(target, withdrawal_order=order, extra_spending=extra)
    p = project(sample_household, s, rules, START)
    start = sum(a.balance for a in sample_household.accounts)
    for r in p.rows:
        b = r.balances
        cash = b["cash"] / 1.025
        before_growth = cash + (sum(b.values()) - b["cash"]) / 1.06
        inflows = r.wages + r.social_security + r.pension + r.shortfall
        outflows = r.spending + r.health_premiums
        tax = r.federal_tax + r.state_tax + r.irmaa
        assert start + inflows - outflows - tax == pytest.approx(before_growth, abs=1)
        start = sum(b.values())


def test_spending_comes_before_conversion(rules: TaxRules) -> None:
    # One year, 401(k) only. Spending plus its tax fits in the $100,000; the
    # conversion may only use what is left, so it never causes a shortfall.
    h = Household.model_validate(
        {
            "self": {
                "first_name": "Lee",
                "birth_date": "1960-01-01",
                "retirement_age": 60,
                "plan_to_age": 66,
                "ss_at_62": 0,
                "ss_at_fra": 0,
                "ss_at_70": 0,
            },
            "accounts": [
                {
                    "id": "p",
                    "kind": "pretax",
                    "owner": "self",
                    "label": "IRA",
                    "balance": 100_000,
                    "as_of": "2026-01-01",
                }
            ],
            "spending": {"essential": 80_000},
            "assumptions": {},
        }
    )
    none = project(h, strategy("none", claim_ages=(70, None)), rules, START)
    fill = project(h, strategy("22", claim_ages=(70, None)), rules, START)
    assert none.shortfall_year is None
    assert fill.shortfall_year is None
    (row_none,) = none.rows
    (row_fill,) = fill.rows
    assert 0 < row_fill.conversion < 100_000 - row_none.withdrawals["pretax"]
    assert row_fill.balances["pretax"] == pytest.approx(0, abs=1)


def test_no_year_both_converts_and_falls_short(
    sample_household: Household, rules: TaxRules
) -> None:
    fill = project(
        sample_household, strategy("12", extra_spending=190_000), rules, START
    )
    none = project(
        sample_household, strategy("none", extra_spending=190_000), rules, START
    )
    assert fill.shortfall_year is not None
    assert none.shortfall_year is not None
    assert fill.shortfall_year >= none.shortfall_year
    assert not [r.year for r in fill.rows if r.conversion > 0 and r.shortfall > 0]


def test_irmaa_uses_magi_from_two_years_earlier(
    sample_household: Household, rules: TaxRules
) -> None:
    p = project(
        sample_household, strategy("24", withdrawal_order="pretax_first"), rules, START
    )
    high, _, now = row(p, 2026), row(p, 2027), row(p, 2028)
    assert high.magi > 400_000
    assert high.irmaa == 0  # nobody is 65 yet
    rules_2028 = rules_for_year(rules, 2028, 0.025)
    # self turns 65 in 2028; the surcharge follows 2026's MAGI, not 2028's
    assert now.irmaa == pytest.approx(irmaa_annual(high.magi, "mfj", 1, rules_2028))
    assert now.irmaa > 0
    assert irmaa_annual(now.magi, "mfj", 1, rules_2028) == 0


def test_colorado_splits_taxable_ss_by_benefit(
    sample_household: Household, rules: TaxRules
) -> None:
    p = project(sample_household, strategy("12", claim_ages=(64, 62)), rules, START)
    r = row(p, 2027)  # ages 64 and 62, both claimed, AGI over the under-65 limit
    # Benefits: self 2,560 x 12 x 1.025 = 31,488; spouse 1,400 x 12 x 1.025 = 17,220.
    assert r.social_security == pytest.approx(48_708)
    # Taxable SS is the 85% maximum, 41,401.80. The spouse's share is
    # 41,401.80 x 17,220 / 48,708 = 0.85 x 17,220 = 14,637.00.
    taxable_ss = r.ordinary_income - r.conversion
    assert taxable_ss == pytest.approx(41_401.80, abs=0.01)
    spouse_share = taxable_ss * 17_220 / 48_708
    assert spouse_share == pytest.approx(14_637.00, abs=0.01)
    # Caps 20,000 x 1.025 = 20,500 each. Self: the conversion alone fills the
    # cap. Spouse: only the SS share, under the cap. Federal taxable income is
    # ordinary + gains - 33,005 (the 32,200 standard deduction inflated).
    federal_taxable = r.ordinary_income + r.capital_gains - 33_005
    expected = 0.044 * (federal_taxable - 20_500 - spouse_share)
    assert r.state_tax == pytest.approx(expected, abs=0.01)
    assert r.state_tax == pytest.approx(4_128.56, abs=0.01)
