export interface Person {
  first_name: string;
  birth_date: string;
  retirement_age: number;
  plan_to_age: number;
  wages: number;
  contribution_401k: number;
  ss_at_62: number;
  ss_at_fra: number;
  ss_at_70: number;
  ss_claim_age: number | null;
  pension_annual: number;
  pension_start_age: number | null;
  pension_survivor_pct: number;
}

export type AccountKind = "pretax" | "roth" | "taxable" | "cash" | "hsa";

export interface Account {
  id: string;
  kind: AccountKind;
  owner: "self" | "spouse";
  label: string;
  balance: number;
  cost_basis: number;
  last4: string | null;
  as_of: string;
}

export interface OneTime {
  year: number;
  amount: number;
  label: string;
}

export interface Spending {
  essential: number;
  discretionary: number;
  cobra_monthly: number;
  bridge_monthly: number;
  bridge_is_aca: boolean;
  one_time: OneTime[];
}

export interface Assumptions {
  return_rate: number;
  inflation: number;
  ss_cola: number;
  volatility: number;
  heir_tax_rate: number;
}

export interface Household {
  self: Person;
  spouse: Person | null;
  state: "CO";
  accounts: Account[];
  spending: Spending;
  assumptions: Assumptions;
  home_value: number;
  mask_terms: string[];
}

export interface Strategy {
  conversion_target: "none" | "12" | "22" | "24" | "irmaa1";
  convert_from_age: number;
  convert_to_age: number;
  withdrawal_order: string;
  claim_ages: [number, number | null];
  extra_spending: number;
}

export interface PlanOption {
  strategy: Strategy;
  label: string;
  lifetime_tax: number;
  after_tax_end: number;
  shortfall_year: number | null;
  success_rate: number;
  safe_extra: number;
}

export interface YearRow {
  year: number;
  ages: (number | null)[];
  social_security: number;
  pension: number;
  rmd: number;
  conversion: number;
  withdrawals: Record<string, number>;
  spending: number;
  federal_tax: number;
  state_tax: number;
  irmaa: number;
  balances: Record<string, number>;
  shortfall: number;
}

export interface PlanResult {
  rules_file: string;
  rules_stale: boolean;
  top: PlanOption[];
  baseline: PlanOption;
  best_rows: YearRow[];
}
