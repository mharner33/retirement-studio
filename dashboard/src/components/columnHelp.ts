/** How each Year by year column is worked out, in column order. */
export const COLUMN_HELP: readonly { label: string; help: string }[] = [
  {
    label: "Year",
    help: "The calendar year. The plan starts this year and runs to the later of your plan-to ages.",
  },
  {
    label: "Ages",
    help: "Each person's age that year (year minus birth year), you / spouse. A dash means that person is past their plan-to age.",
  },
  {
    label: "Social Security",
    help: "Both benefits together. Each comes from your SSA estimates at 62, full retirement age and 70, read at your claim age (in-between ages are on a straight line between estimates), then raised each year by the COLA in Assumptions. Includes any spousal top-up. After a death the survivor keeps the larger benefit.",
  },
  {
    label: "Withdrawals",
    help: "What was taken from each account type to cover that year's spending, health premiums and taxes beyond wages, Social Security, pensions and required minimum distributions. The best plan's withdrawal order decides which accounts go first. Required minimum distributions themselves are not included here.",
  },
  {
    label: "Roth conversion",
    help: "Pre-tax money moved to Roth that year. During its conversion ages, the best plan converts up to the top of a tax bracket or to just under the first Medicare surcharge (IRMAA) level. The tax it causes is in the Tax column.",
  },
  {
    label: "Tax",
    help: "Federal income tax plus Colorado income tax plus the Medicare IRMAA surcharge. IRMAA is based on income from two years earlier.",
  },
  {
    label: "Spending",
    help: "Essential plus discretionary spending, plus any one-time expenses that year, raised each year by inflation in Assumptions. Health premiums (COBRA, bridge coverage, Medicare Part B) are paid on top and not included.",
  },
  {
    label: "End balance",
    help: "All accounts together at year end: after contributions, withdrawals and conversions, then grown at the return rate in Assumptions. Cash grows at inflation.",
  },
];
