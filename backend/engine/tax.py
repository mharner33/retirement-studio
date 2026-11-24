"""Pure tax functions over a `TaxRules` set. Amounts are annual US dollars."""

from dataclasses import dataclass

from backend.rules.models import (
    AgeCap,
    Bracket,
    FilingStatus,
    IrmaaTier,
    TaxRules,
)

SENIOR_AGE = 65  # age for the additional and senior deductions


@dataclass(frozen=True)
class TaxUnit:
    """Who files and when. `ages` are each filer's age at the end of `year`."""

    filing: FilingStatus
    ages: tuple[int, ...]
    year: int

    @property
    def people_65_plus(self) -> int:
        return sum(age >= SENIOR_AGE for age in self.ages)


@dataclass(frozen=True)
class FederalTax:
    taxable_income: float
    tax: float
    marginal_rate: float


@dataclass(frozen=True)
class PersonIncome:
    """One person's federally taxable Social Security and other retirement
    income (pensions, annuities, IRA and 401(k) withdrawals, Roth conversions)."""

    taxable_ss: float
    retirement_income: float


def taxable_social_security(
    ss: float, other_income: float, filing: FilingStatus, rules: TaxRules
) -> float:
    """Taxable part of benefits (26 U.S.C. 86). `other_income` is AGI without
    Social Security plus tax-exempt interest."""
    base1, base2 = rules.ss_taxation_thresholds[filing]
    provisional = other_income + 0.5 * ss
    if provisional <= base1:
        return 0.0
    if provisional <= base2:
        return min(0.5 * (provisional - base1), 0.5 * ss)
    tier1 = min(0.5 * (base2 - base1), 0.5 * ss)
    return min(0.85 * (provisional - base2) + tier1, 0.85 * ss)


def _senior_deduction(magi: float, unit: TaxUnit, rules: TaxRules) -> float:
    senior = rules.senior_deduction
    if senior is None or unit.year > senior.last_year:
        return 0.0
    excess = max(0.0, magi - senior.phaseout_start[unit.filing])
    each = max(0.0, senior.amount_per_person - senior.phaseout_rate * excess)
    return each * unit.people_65_plus


def _fixed_deduction(unit: TaxUnit, rules: TaxRules) -> float:
    return (
        rules.standard_deduction[unit.filing]
        + rules.additional_65[unit.filing] * unit.people_65_plus
    )


def _tax_in_range(low: float, high: float, brackets: list[Bracket]) -> float:
    """Tax on the slice of income between `low` and `high` under `brackets`."""
    tax = 0.0
    floor = 0.0
    for bracket in brackets:
        ceiling = float("inf") if bracket.up_to is None else bracket.up_to
        overlap = min(high, ceiling) - max(low, floor)
        if overlap > 0:
            tax += overlap * bracket.rate
        floor = ceiling
    return tax


def _marginal_rate(ordinary_taxable: float, brackets: list[Bracket]) -> float:
    if ordinary_taxable <= 0:
        return 0.0
    return next(
        b.rate for b in brackets if b.up_to is None or ordinary_taxable <= b.up_to
    )


def federal_tax(
    ordinary: float, ltcg: float, unit: TaxUnit, rules: TaxRules
) -> FederalTax:
    """Federal income tax.

    `ordinary` is gross ordinary income (including taxable Social Security);
    `ltcg` is long-term gains and qualified dividends. MAGI for the senior
    deduction phase-out is taken as `ordinary + ltcg`. Deductions reduce
    ordinary income first; gains are stacked on top of ordinary taxable income.
    `marginal_rate` is the ordinary bracket rate of the next dollar, or 0 when
    ordinary taxable income is zero; it ignores the senior phase-out.
    """
    deduction = _fixed_deduction(unit, rules) + _senior_deduction(
        ordinary + ltcg, unit, rules
    )
    taxable = round(max(0.0, ordinary + ltcg - deduction), 2)
    ordinary_taxable = round(max(0.0, ordinary - deduction), 2)
    brackets = rules.federal_brackets[unit.filing]
    tax = _tax_in_range(0.0, ordinary_taxable, brackets) + _tax_in_range(
        ordinary_taxable, taxable, rules.ltcg_brackets[unit.filing]
    )
    return FederalTax(taxable, tax, _marginal_rate(ordinary_taxable, brackets))


def bracket_top(
    rate: float, unit: TaxUnit, rules: TaxRules, ltcg: float = 0.0
) -> float:
    """Gross ordinary income at which ordinary taxable income reaches the top
    of the bracket taxed at `rate`, given `ltcg` of gains alongside it.

    Solves `x - deduction(x) = up_to`, where the senior deduction falls by
    `phaseout_rate` per person for each dollar of MAGI (`x + ltcg`) above the
    phase-out start. The left side rises with `x`, so the answer lies in exactly
    one of three pieces: full senior deduction, phasing out, or fully gone.
    """
    up_to = next(b.up_to for b in rules.federal_brackets[unit.filing] if b.rate == rate)
    if up_to is None:
        raise ValueError(f"the {rate} bracket has no limit")
    target = up_to + _fixed_deduction(unit, rules)
    senior = rules.senior_deduction
    people = unit.people_65_plus
    if senior is None or people == 0 or unit.year > senior.last_year:
        return target
    start = senior.phaseout_start[unit.filing] - ltcg
    end = start + senior.amount_per_person / senior.phaseout_rate
    full = target + senior.amount_per_person * people
    if full <= start:
        return full
    if target >= end:
        return target
    slope = senior.phaseout_rate * people
    return (full + slope * start) / (1 + slope)


def colorado_tax(
    federal_taxable: float,
    federal_agi: float,
    income: list[PersonIncome],
    unit: TaxUnit,
    rules: TaxRules,
) -> float:
    """Colorado income tax: flat rate on federal taxable income less the
    pension and annuity subtraction.

    `income[i]` belongs to the person aged `unit.ages[i]`. Each person has a
    cap by age (none under 55). That person's taxable Social Security is
    subtracted in full at `ss_full_subtraction_min_age` or older, or from
    `first_year` on at `min_age` or older when `federal_agi` is at or under the
    filing status limit; otherwise it shares the cap with other retirement
    income. The caller splits household taxable Social Security between people.
    """
    co = rules.colorado
    ss_full_age = co.ss_full_subtraction_min_age
    under_65 = co.ss_full_subtraction_under_65
    if (
        under_65 is not None
        and unit.year >= under_65.first_year
        and federal_agi <= under_65.agi_limit[unit.filing]
    ):
        ss_full_age = under_65.min_age
    subtraction = 0.0
    for age, person in zip(unit.ages, income, strict=True):
        cap = _cap_for_age(age, co.retirement_subtraction)
        if age >= ss_full_age:
            subtraction += person.taxable_ss + min(person.retirement_income, cap)
        else:
            subtraction += min(person.taxable_ss + person.retirement_income, cap)
    return co.rate * max(0.0, federal_taxable - subtraction)


def _cap_for_age(age: int, caps: list[AgeCap]) -> float:
    return next(
        (
            c.cap
            for c in caps
            if c.min_age <= age and (c.max_age is None or age <= c.max_age)
        ),
        0.0,
    )


def irmaa_annual(
    magi_two_years_prior: float,
    filing: FilingStatus,
    people_65_plus: int,
    rules: TaxRules,
) -> float:
    """Yearly Medicare surcharge above the standard Part B premium, Parts B
    and D, for everyone on Medicare. A tier applies when MAGI is over its
    `magi_over`; the top tier also applies at exactly its threshold (CMS)."""
    tiers = rules.irmaa[filing]
    tier = next(t for t in reversed(tiers) if _in_tier(magi_two_years_prior, t, tiers))
    monthly = tier.part_b_monthly - rules.part_b_base_monthly + tier.part_d_monthly
    return monthly * 12 * people_65_plus


def _in_tier(magi: float, tier: IrmaaTier, tiers: list[IrmaaTier]) -> bool:
    if tier is tiers[-1]:
        return magi >= tier.magi_over
    return magi > tier.magi_over or tier is tiers[0]


def rmd(balance: float, age: int, rules: TaxRules) -> float:
    """Required minimum distribution; ages over the table use its last row."""
    table = rules.uniform_lifetime_table
    return balance / table[min(age, max(table))]


def rmd_start_age(birth_year: int, rules: TaxRules) -> int:
    return next(
        r.age
        for r in rules.rmd_start_ages
        if r.born_from <= birth_year and (r.born_to is None or birth_year <= r.born_to)
    )


def rules_for_year(rules: TaxRules, year: int, inflation: float) -> TaxRules:
    """Rules for a later year with dollar thresholds inflated by
    `(1 + inflation) ** (year - rules.year)`. Rates, Social Security taxation
    thresholds, the RMD tables, the senior deduction (statutory) and Social
    Security reduction factors stay as they are. Same or earlier years return
    `rules` itself. Amounts are not rounded the way the IRS rounds them."""
    if year <= rules.year:
        return rules
    factor = (1 + inflation) ** (year - rules.year)

    def brackets(
        table: dict[FilingStatus, list[Bracket]],
    ) -> dict[str, list[dict[str, float | None]]]:
        return {
            filing: [
                {"rate": b.rate, "up_to": None if b.up_to is None else b.up_to * factor}
                for b in rows
            ]
            for filing, rows in table.items()
        }

    data = rules.model_dump()
    data["year"] = year
    data["federal_brackets"] = brackets(rules.federal_brackets)
    data["ltcg_brackets"] = brackets(rules.ltcg_brackets)
    for key in ("standard_deduction", "additional_65"):
        data[key] = {f: v * factor for f, v in data[key].items()}
    data["part_b_base_monthly"] *= factor
    for rows in data["irmaa"].values():
        for tier in rows:
            for key in ("magi_over", "part_b_monthly", "part_d_monthly"):
                tier[key] *= factor
    colorado = data["colorado"]
    for cap in colorado["retirement_subtraction"]:
        cap["cap"] *= factor
    if colorado["ss_full_subtraction_under_65"] is not None:
        limits = colorado["ss_full_subtraction_under_65"]["agi_limit"]
        for filing in limits:
            limits[filing] *= factor
    return TaxRules.model_validate(data)
