from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.engine.projection import Projection, Strategy, YearRow, project
from backend.engine.social_security import monthly_benefit
from backend.engine.tax import TaxUnit, bracket_top, rules_for_year
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
