import pytest

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
from backend.rules import store
from backend.rules.models import TaxRules

SEED = store.SEED_DIR / store.SEED_FILENAME


@pytest.fixture(scope="module")
def rules() -> TaxRules:
    return store.parse_rules(SEED.read_text())


def money(value: float) -> object:
    return pytest.approx(value, abs=0.005)


def test_ss_taxation_mfj(rules: TaxRules) -> None:
    # provisional 30,000 + 20,000 = 50,000; 0.85 * (50,000 - 44,000) = 5,100
    # plus min(0.5 * 12,000, 0.5 * 40,000) = 6,000 -> 11,100
    assert taxable_social_security(40_000, 30_000, "mfj", rules) == money(11_100.00)


def test_ss_taxation_below_threshold_zero(rules: TaxRules) -> None:
    # provisional 10,000 + 15,000 = 25,000 <= 32,000
    assert taxable_social_security(30_000, 10_000, "mfj", rules) == 0


def test_ss_taxation_middle_tier_single(rules: TaxRules) -> None:
    # provisional 20,000 + 10,000 = 30,000; 0.5 * (30,000 - 25,000) = 2,500
    assert taxable_social_security(20_000, 20_000, "single", rules) == money(2_500.00)


def test_ss_taxation_capped_at_85pct(rules: TaxRules) -> None:
    # provisional 120,000; 0.85 * 76,000 + 6,000 = 70,600 > 0.85 * 40,000 = 34,000
    assert taxable_social_security(40_000, 100_000, "mfj", rules) == money(34_000.00)


def test_rmd_age_75(rules: TaxRules) -> None:
    # 500,000 / 24.6 = 20,325.203...
    assert rmd(500_000, 75, rules) == money(20_325.20)


def test_rmd_over_120_uses_last_row(rules: TaxRules) -> None:
    # 10,000 / 2.0
    assert rmd(10_000, 123, rules) == money(5_000.00)


def test_rmd_start_age(rules: TaxRules) -> None:
    assert rmd_start_age(1963, rules) == 75
    assert rmd_start_age(1955, rules) == 73
    assert rmd_start_age(1959, rules) == 73
    assert rmd_start_age(1960, rules) == 75
    assert rmd_start_age(1950, rules) == 72


def test_federal_tax_zero_below_deduction(rules: TaxRules) -> None:
    result = federal_tax(30_000, 0, TaxUnit("mfj", (60, 58), 2026), rules)
    assert result.taxable_income == 0
    assert result.tax == 0
    assert result.marginal_rate == 0


def test_federal_tax_mfj_with_senior_deduction(rules: TaxRules) -> None:
    # deduction 32,200 + 1,650 + 6,000 (MAGI 120,000 < 150,000) = 39,850
    # taxable 80,150; tax 0.10 * 24,800 + 0.12 * 55,350 = 2,480 + 6,642 = 9,122
    result = federal_tax(120_000, 0, TaxUnit("mfj", (66, 64), 2026), rules)
    assert result.taxable_income == money(80_150.00)
    assert result.tax == money(9_122.00)
    assert result.marginal_rate == 0.12


def test_federal_tax_senior_deduction_phases_out(rules: TaxRules) -> None:
    # senior 6,000 - 0.06 * (100,000 - 75,000) = 4,500
    # deduction 16,100 + 2,050 + 4,500 = 22,650; taxable 77,350
    # tax 1,240 + 0.12 * 38,000 + 0.22 * 26,950 = 1,240 + 4,560 + 5,929 = 11,729
    result = federal_tax(100_000, 0, TaxUnit("single", (67,), 2026), rules)
    assert result.taxable_income == money(77_350.00)
    assert result.tax == money(11_729.00)
    assert result.marginal_rate == 0.22


def test_federal_tax_senior_deduction_ends_after_last_year(rules: TaxRules) -> None:
    # 2029 > 2028: deduction 16,100 + 2,050 = 18,150; taxable 81,850
    # tax 1,240 + 4,560 + 0.22 * 31,450 = 1,240 + 4,560 + 6,919 = 12,719
    result = federal_tax(100_000, 0, TaxUnit("single", (67,), 2029), rules)
    assert result.taxable_income == money(81_850.00)
    assert result.tax == money(12_719.00)


def test_ltcg_zero_rate_inside_bracket(rules: TaxRules) -> None:
    # ordinary taxable 50,000 - 32,200 = 17,800; total 57,800 <= 98,900
    # tax is ordinary only: 0.10 * 17,800 = 1,780
    result = federal_tax(50_000, 40_000, TaxUnit("mfj", (60, 60), 2026), rules)
    assert result.taxable_income == money(57_800.00)
    assert result.tax == money(1_780.00)


def test_ltcg_stacks_on_ordinary(rules: TaxRules) -> None:
    # ordinary taxable 67,800: 2,480 + 0.12 * 43,000 = 7,640
    # ltcg 50,000 from 67,800 to 117,800: 31,100 at 0%, 18,900 at 15% = 2,835
    result = federal_tax(100_000, 50_000, TaxUnit("mfj", (60, 60), 2026), rules)
    assert result.taxable_income == money(117_800.00)
    assert result.tax == money(10_475.00)
    assert result.marginal_rate == 0.12


def test_leftover_deduction_reduces_ltcg(rules: TaxRules) -> None:
    # 20,000 + 20,000 - 32,200 = 7,800 taxable, all ltcg at 0%
    result = federal_tax(20_000, 20_000, TaxUnit("mfj", (60, 60), 2026), rules)
    assert result.taxable_income == money(7_800.00)
    assert result.tax == 0
    assert result.marginal_rate == 0


def test_bracket_top_fills_12pct(rules: TaxRules) -> None:
    unit = TaxUnit("mfj", (66, 64), 2026)
    # 100,800 + 32,200 + 1,650 + 6,000 = 140,650 (MAGI below 150,000, full senior)
    top = bracket_top(0.12, unit, rules)
    assert top == money(140_650.00)
    at_top = federal_tax(top, 0, unit, rules)
    assert at_top.taxable_income == money(100_800.00)
    assert at_top.marginal_rate == 0.12
    assert federal_tax(top + 1, 0, unit, rules).marginal_rate == 0.22


def test_bracket_top_inside_senior_phaseout(rules: TaxRules) -> None:
    unit = TaxUnit("mfj", (66, 66), 2026)
    # x - 35,500 - 2 * (6,000 - 0.06 * (x - 150,000)) = 211,400
    # 1.12 x = 211,400 + 35,500 + 12,000 + 18,000 = 276,900; x = 247,232.142857
    top = bracket_top(0.22, unit, rules)
    assert top == money(247_232.14)
    assert federal_tax(top, 0, unit, rules).marginal_rate == 0.22
    assert federal_tax(top + 1, 0, unit, rules).marginal_rate == 0.24


def test_bracket_top_past_senior_phaseout(rules: TaxRules) -> None:
    # 403,550 + 35,500 = 439,050, above the 250,000 phase-out end
    unit = TaxUnit("mfj", (66, 66), 2026)
    assert bracket_top(0.24, unit, rules) == money(439_050.00)


def test_bracket_top_with_ltcg(rules: TaxRules) -> None:
    # ltcg 10,000 puts MAGI over 75,000: x - 18,150 - (6,000 - 0.06 * (x - 65,000))
    # = 50,400; 1.06 x = 50,400 + 18,150 + 6,000 + 3,900 = 78,450; x = 74,009.43
    unit = TaxUnit("single", (67,), 2026)
    top = bracket_top(0.12, unit, rules, ltcg=10_000)
    assert top == money(74_009.43)
    assert federal_tax(top, 10_000, unit, rules).marginal_rate == 0.12
    assert federal_tax(top + 1, 10_000, unit, rules).marginal_rate == 0.22


def test_bracket_top_without_senior_deduction(rules: TaxRules) -> None:
    # nobody 65+: 100,800 + 32,200 = 133,000
    assert bracket_top(0.12, TaxUnit("mfj", (60, 60), 2026), rules) == money(133_000)
    # 2029 is past last_year: 50,400 + 16,100 + 2,050 = 68,550
    assert bracket_top(0.12, TaxUnit("single", (67,), 2029), rules) == money(68_550)


def test_bracket_top_rejects_top_bracket(rules: TaxRules) -> None:
    with pytest.raises(ValueError, match="no limit"):
        bracket_top(0.37, TaxUnit("mfj", (66, 66), 2026), rules)


def test_rules_for_year_inflates_thresholds(rules: TaxRules) -> None:
    later = rules_for_year(rules, 2030, 0.025)
    factor = 1.025**4  # 1.103812890625
    assert later.year == 2030
    # 32,200 * 1.103812890625 = 35,542.78
    assert later.standard_deduction["mfj"] == money(32_200 * factor)
    assert later.standard_deduction["mfj"] == money(35_542.78)
    # 100,800 * 1.103812890625 = 111,264.34
    assert later.federal_brackets["mfj"][1].up_to == money(111_264.34)
    assert later.federal_brackets["mfj"][-1].up_to is None
    assert later.additional_65["single"] == money(2_050 * factor)
    assert later.ltcg_brackets["mfj"][0].up_to == money(98_900 * factor)
    assert later.irmaa["single"][1].magi_over == money(109_000 * factor)
    assert later.irmaa["single"][1].part_b_monthly == money(284.10 * factor)
    assert later.irmaa["single"][1].part_d_monthly == money(14.50 * factor)
    assert later.part_b_base_monthly == money(202.90 * factor)
    assert later.colorado.retirement_subtraction[1].cap == money(24_000 * factor)
    under_65 = later.colorado.ss_full_subtraction_under_65
    assert under_65 is not None
    assert under_65.agi_limit["mfj"] == money(95_000 * factor)
    # not inflated
    assert later.federal_brackets["mfj"][1].rate == 0.12
    assert later.ss_taxation_thresholds == rules.ss_taxation_thresholds
    assert later.senior_deduction == rules.senior_deduction
    assert later.uniform_lifetime_table == rules.uniform_lifetime_table
    assert later.ss_reduction == rules.ss_reduction
    assert later.colorado.rate == rules.colorado.rate
    # the original is untouched
    assert rules.standard_deduction["mfj"] == 32_200


def test_rules_for_year_same_or_earlier_unchanged(rules: TaxRules) -> None:
    assert rules_for_year(rules, 2026, 0.025) is rules
    assert rules_for_year(rules, 2025, 0.025) is rules


def test_colorado_subtraction_caps_by_age(rules: TaxRules) -> None:
    # AGI 150,000 > 95,000, so the 60-year-old's Social Security shares the cap.
    # age 66: 20,000 ss in full + min(30,000, 24,000) = 44,000
    # age 60: min(10,000 + 15,000, 20,000) = 20,000
    # (110,000 - 64,000) * 0.044 = 2,024
    tax = colorado_tax(
        110_000,
        150_000,
        [PersonIncome(20_000, 30_000), PersonIncome(10_000, 15_000)],
        TaxUnit("mfj", (66, 60), 2026),
        rules,
    )
    assert tax == money(2_024.00)


def test_colorado_under_65_ss_full_when_agi_at_limit(rules: TaxRules) -> None:
    # AGI 75,000 <= 75,000: 10,000 ss + min(15,000, 20,000) = 25,000
    # (50,000 - 25,000) * 0.044 = 1,100
    income = [PersonIncome(10_000, 15_000)]
    unit = TaxUnit("single", (60,), 2026)
    assert colorado_tax(50_000, 75_000, income, unit, rules) == money(1_100.00)


def test_colorado_under_65_ss_shares_cap_above_agi_limit(rules: TaxRules) -> None:
    # AGI 80,000 > 75,000: min(25,000, 20,000) = 20,000; 30,000 * 0.044 = 1,320
    income = [PersonIncome(10_000, 15_000)]
    unit = TaxUnit("single", (60,), 2026)
    assert colorado_tax(50_000, 80_000, income, unit, rules) == money(1_320.00)


def test_colorado_under_65_rule_starts_in_first_year(rules: TaxRules) -> None:
    # 2024 < 2025: no full subtraction; same 1,320 as above the AGI limit
    income = [PersonIncome(10_000, 15_000)]
    unit = TaxUnit("single", (60,), 2024)
    assert colorado_tax(50_000, 70_000, income, unit, rules) == money(1_320.00)


def test_colorado_no_subtraction_under_55(rules: TaxRules) -> None:
    # 40,000 * 0.044 = 1,760
    income = [PersonIncome(5_000, 10_000)]
    unit = TaxUnit("single", (50,), 2026)
    assert colorado_tax(40_000, 45_000, income, unit, rules) == money(1_760.00)


def test_colorado_tax_floors_at_zero(rules: TaxRules) -> None:
    income = [PersonIncome(30_000, 30_000)]
    unit = TaxUnit("single", (70,), 2026)
    assert colorado_tax(20_000, 60_000, income, unit, rules) == 0


def test_irmaa_zero_below_first_tier(rules: TaxRules) -> None:
    assert irmaa_annual(200_000, "mfj", 2, rules) == 0
    # exactly 218,000 is not over 218,000
    assert irmaa_annual(218_000, "mfj", 2, rules) == 0


def test_irmaa_second_tier_mfj(rules: TaxRules) -> None:
    # (405.80 - 202.90 + 37.50) * 12 = 240.40 * 12 = 2,884.80 per person, * 2
    assert irmaa_annual(300_000, "mfj", 2, rules) == money(5_769.60)


def test_irmaa_top_tier_boundary(rules: TaxRules) -> None:
    # just under 500,000: (649.20 - 202.90 + 83.30) * 12 = 529.60 * 12 = 6,355.20
    assert irmaa_annual(499_999.99, "single", 1, rules) == money(6_355.20)
    # exactly 500,000 is in the top tier: (689.90 - 202.90 + 91.00) * 12 = 6,936
    assert irmaa_annual(500_000, "single", 1, rules) == money(6_936.00)
    # exactly 750,000 mfj, two people: 6,936 * 2 = 13,872
    assert irmaa_annual(750_000, "mfj", 2, rules) == money(13_872.00)
    assert irmaa_annual(749_999.99, "mfj", 2, rules) == money(12_710.40)
