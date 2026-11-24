# Retirement rules for tax year 2026

Seed rules file checked into the repo. Figures were copied from the official pages listed under each section on 2026-11-24. Filing statuses covered: single and married filing jointly (mfj). Dollar amounts are annual unless marked monthly.

## Federal income tax brackets

Taxable income thresholds for 2026, as amended by the One, Big, Beautiful Bill Act (OBBBA). Each bracket's rate applies to income up to `up_to`; the top bracket has no limit.

| Rate | Single, up to | MFJ, up to |
| ---- | ------------- | ---------- |
| 10% | $12,400 | $24,800 |
| 12% | $50,400 | $100,800 |
| 22% | $105,700 | $211,400 |
| 24% | $201,775 | $403,550 |
| 32% | $256,225 | $512,450 |
| 35% | $640,600 | $768,700 |
| 37% | no limit | no limit |

Source: IRS Rev. Proc. 2025-32, section 4.01, https://www.irs.gov/pub/irs-drop/rp-25-32.pdf

## Standard deduction and age-65 additional amount

- Standard deduction: $16,100 single, $32,200 mfj.
- Additional amount for each person age 65 or older (or blind): $2,050 if unmarried, $1,650 per qualifying spouse if married.

Source: IRS Rev. Proc. 2025-32, section 4.14, https://www.irs.gov/pub/irs-drop/rp-25-32.pdf

## Enhanced deduction for seniors (temporary)

- $6,000 for each person age 65 or older by the end of the year ($12,000 for a married couple filing jointly when both qualify). Married couples must file jointly.
- Phases out by 6% of modified AGI above $75,000 single or $150,000 mfj (Schedule 1-A, Part V: line 34 multiplies the excess by 6%, and the result is subtracted from $6,000 per person).
- Applies to tax years 2025 through 2028. Not indexed for inflation.

Sources:
- https://www.irs.gov/newsroom/check-your-eligibility-for-the-new-enhanced-deduction-for-seniors
- https://www.irs.gov/pub/irs-pdf/f1040s1a.pdf

## Long-term capital gains and qualified dividends

| Rate | Single, up to | MFJ, up to |
| ---- | ------------- | ---------- |
| 0% | $49,450 | $98,900 |
| 15% | $545,500 | $613,700 |
| 20% | no limit | no limit |

Source: IRS Rev. Proc. 2025-32, section 4.03 (maximum zero rate and 15 percent rate amounts), https://www.irs.gov/pub/irs-drop/rp-25-32.pdf

## Social Security taxation thresholds

Provisional income thresholds for including benefits in income (up to 50% above the first figure, up to 85% above the second). These are set by statute (26 U.S.C. 86) and are not indexed for inflation.

- Single: $25,000 and $34,000.
- MFJ: $32,000 and $44,000.

Source: https://www.irs.gov/publications/p915

## Required minimum distributions

Start age by year of birth under SECURE 2.0 section 107:

- Born 1951 through 1959: age 73. The statute names both 73 and 75 for people born in 1959; the IRS proposed regulations (published with the 2024 final regulations) set 73 for that year.
- Born 1960 or later: age 75.

Owners born before 1951 already passed their start age (70½ or 72) before this tool's first plan year and are not listed.

Uniform Lifetime Table (Table III) distribution periods for 2026, ages 72 to 120 (120 covers "120 and over").

Sources:
- IRS Pub 590-B (2025), Appendix B, Table III, https://www.irs.gov/pub/irs-pdf/p590b.pdf
- Internal Revenue Bulletin 2024-33 (T.D. 10001 and REG-103529-23), https://www.irs.gov/pub/irs-irbs/irb24-33.pdf

## Medicare Part B premium and IRMAA

The 2026 standard Part B premium is $202.90 per month. Higher-income beneficiaries pay a larger Part B premium and a Part D surcharge (added to their plan premium), set by modified AGI from two years earlier (2024 tax returns for 2026). In the JSON, `part_b_monthly` is the total Part B premium per person and `part_d_monthly` is the Part D income-related adjustment per person. A tier applies when MAGI is greater than `magi_over`; CMS writes the top tier as "greater than or equal to" $500,000 single and $750,000 mfj.

| Single MAGI over | MFJ MAGI over | Part B monthly | Part D add-on monthly |
| ---------------- | ------------- | -------------- | --------------------- |
| $0 | $0 | $202.90 | $0.00 |
| $109,000 | $218,000 | $284.10 | $14.50 |
| $137,000 | $274,000 | $405.80 | $37.50 |
| $171,000 | $342,000 | $527.50 | $60.40 |
| $205,000 | $410,000 | $649.20 | $83.30 |
| $500,000 | $750,000 | $689.90 | $91.00 |

Source: CMS fact sheet "2026 Medicare Parts A & B Premiums and Deductibles", https://www.cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-deductibles

## Social Security claiming adjustments

- Own benefit claimed before full retirement age: reduced 5/9 of 1% for each of the first 36 months early, and 5/12 of 1% for each further month.
- Spousal benefit claimed before full retirement age: reduced 25/36 of 1% for each of the first 36 months early, and 5/12 of 1% for each further month.
- Delayed retirement credits for people born after January 1, 1943: 2/3 of 1% per month from full retirement age to age 70, which is 8% per year.

Sources:
- 20 CFR 404.410, https://www.ecfr.gov/current/title-20/chapter-III/part-404/subpart-E/section-404.410
- 20 CFR 404.313, https://www.ecfr.gov/current/title-20/chapter-III/part-404/subpart-C/section-404.313
- SSA overview pages (same figures): https://www.ssa.gov/oact/quickcalc/earlyretire.html and https://www.ssa.gov/benefits/retirement/planner/delayret.html

## Colorado

- Flat income tax rate: 4.4%. The Colorado DOR rate table lists 4.4% for 2025 and does not yet list 2026; the DOR 2026 estimated tax worksheet (DR 0104EP) uses 4.4%. A temporary TABOR rate cut, if triggered for 2026, would be announced later.
- Pension and annuity subtraction, per person: up to $20,000 at ages 55 to 64, up to $24,000 at 65 or older (age at the end of the year). For joint filers each spouse has their own cap.
- Social Security: at 65 or older, all federally taxable Social Security can be subtracted. At 55 to 64, Social Security counts toward the $20,000 cap, except that from 2025 on it can be subtracted in full when AGI is $75,000 or less (single) or $95,000 or less (joint). The JSON does not yet hold this income test, so the engine treats Social Security under 65 as part of the $20,000 cap.

Sources:
- https://tax.colorado.gov/individual-income-tax-guide
- https://tax.colorado.gov/sites/default/files/documents/DR_0104EP_2026.pdf
- https://tax.colorado.gov/income-tax-topics-social-security-pensions-and-annuities

## Figures

```json
{
  "year": 2026,
  "sources": [
    "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
    "https://www.irs.gov/newsroom/check-your-eligibility-for-the-new-enhanced-deduction-for-seniors",
    "https://www.irs.gov/pub/irs-pdf/f1040s1a.pdf",
    "https://www.irs.gov/publications/p915",
    "https://www.irs.gov/pub/irs-pdf/p590b.pdf",
    "https://www.irs.gov/pub/irs-irbs/irb24-33.pdf",
    "https://www.cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-deductibles",
    "https://www.ecfr.gov/current/title-20/chapter-III/part-404/subpart-E/section-404.410",
    "https://www.ecfr.gov/current/title-20/chapter-III/part-404/subpart-C/section-404.313",
    "https://tax.colorado.gov/individual-income-tax-guide",
    "https://tax.colorado.gov/sites/default/files/documents/DR_0104EP_2026.pdf",
    "https://tax.colorado.gov/income-tax-topics-social-security-pensions-and-annuities"
  ],
  "federal_brackets": {
    "single": [
      {"rate": 0.10, "up_to": 12400},
      {"rate": 0.12, "up_to": 50400},
      {"rate": 0.22, "up_to": 105700},
      {"rate": 0.24, "up_to": 201775},
      {"rate": 0.32, "up_to": 256225},
      {"rate": 0.35, "up_to": 640600},
      {"rate": 0.37, "up_to": null}
    ],
    "mfj": [
      {"rate": 0.10, "up_to": 24800},
      {"rate": 0.12, "up_to": 100800},
      {"rate": 0.22, "up_to": 211400},
      {"rate": 0.24, "up_to": 403550},
      {"rate": 0.32, "up_to": 512450},
      {"rate": 0.35, "up_to": 768700},
      {"rate": 0.37, "up_to": null}
    ]
  },
  "standard_deduction": {"single": 16100, "mfj": 32200},
  "additional_65": {"single": 2050, "mfj": 1650},
  "senior_deduction": {
    "amount_per_person": 6000,
    "phaseout_start": {"single": 75000, "mfj": 150000},
    "phaseout_rate": 0.06,
    "last_year": 2028
  },
  "ltcg_brackets": {
    "single": [
      {"rate": 0.0, "up_to": 49450},
      {"rate": 0.15, "up_to": 545500},
      {"rate": 0.20, "up_to": null}
    ],
    "mfj": [
      {"rate": 0.0, "up_to": 98900},
      {"rate": 0.15, "up_to": 613700},
      {"rate": 0.20, "up_to": null}
    ]
  },
  "ss_taxation_thresholds": {"single": [25000, 34000], "mfj": [32000, 44000]},
  "rmd_start_ages": [
    {"born_from": 1951, "born_to": 1959, "age": 73},
    {"born_from": 1960, "born_to": null, "age": 75}
  ],
  "uniform_lifetime_table": {
    "72": 27.4, "73": 26.5, "74": 25.5, "75": 24.6, "76": 23.7,
    "77": 22.9, "78": 22.0, "79": 21.1, "80": 20.2, "81": 19.4,
    "82": 18.5, "83": 17.7, "84": 16.8, "85": 16.0, "86": 15.2,
    "87": 14.4, "88": 13.7, "89": 12.9, "90": 12.2, "91": 11.5,
    "92": 10.8, "93": 10.1, "94": 9.5, "95": 8.9, "96": 8.4,
    "97": 7.8, "98": 7.3, "99": 6.8, "100": 6.4, "101": 6.0,
    "102": 5.6, "103": 5.2, "104": 4.9, "105": 4.6, "106": 4.3,
    "107": 4.1, "108": 3.9, "109": 3.7, "110": 3.5, "111": 3.4,
    "112": 3.3, "113": 3.1, "114": 3.0, "115": 2.9, "116": 2.8,
    "117": 2.7, "118": 2.5, "119": 2.3, "120": 2.0
  },
  "part_b_base_monthly": 202.90,
  "irmaa": {
    "single": [
      {"magi_over": 0, "part_b_monthly": 202.90, "part_d_monthly": 0.00},
      {"magi_over": 109000, "part_b_monthly": 284.10, "part_d_monthly": 14.50},
      {"magi_over": 137000, "part_b_monthly": 405.80, "part_d_monthly": 37.50},
      {"magi_over": 171000, "part_b_monthly": 527.50, "part_d_monthly": 60.40},
      {"magi_over": 205000, "part_b_monthly": 649.20, "part_d_monthly": 83.30},
      {"magi_over": 500000, "part_b_monthly": 689.90, "part_d_monthly": 91.00}
    ],
    "mfj": [
      {"magi_over": 0, "part_b_monthly": 202.90, "part_d_monthly": 0.00},
      {"magi_over": 218000, "part_b_monthly": 284.10, "part_d_monthly": 14.50},
      {"magi_over": 274000, "part_b_monthly": 405.80, "part_d_monthly": 37.50},
      {"magi_over": 342000, "part_b_monthly": 527.50, "part_d_monthly": 60.40},
      {"magi_over": 410000, "part_b_monthly": 649.20, "part_d_monthly": 83.30},
      {"magi_over": 750000, "part_b_monthly": 689.90, "part_d_monthly": 91.00}
    ]
  },
  "ss_reduction": {
    "own_first_36_per_month": 0.005555555555555556,
    "own_after_per_month": 0.004166666666666667,
    "spousal_first_36_per_month": 0.006944444444444444,
    "spousal_after_per_month": 0.004166666666666667,
    "delayed_credit_per_year": 0.08
  },
  "colorado": {
    "rate": 0.044,
    "retirement_subtraction": [
      {"min_age": 55, "max_age": 64, "cap": 20000},
      {"min_age": 65, "max_age": null, "cap": 24000}
    ],
    "ss_full_subtraction_min_age": 65
  }
}
```
