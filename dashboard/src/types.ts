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

export interface RuleChange {
  path: string;
  old: string;
  new: string;
}

export interface RulesStatus {
  current_file: string;
  current_date: string | null;
  age_days: number | null;
  stale: boolean;
  pending_file: string | null;
  changes: RuleChange[];
}

export interface ExtractedAccount {
  kind: "pretax" | "roth" | "taxable" | "cash" | "hsa";
  owner_hint: string;
  owner: "self" | "spouse";
  label: string;
  balance: number;
  cost_basis: number | null;
  last4: string | null;
}

export interface ExtractedAccountStatement {
  doc_type: "account";
  institution: string;
  statement_date: string;
  accounts: ExtractedAccount[];
}

export interface ExtractedSs {
  doc_type: "social_security";
  statement_date: string;
  person: "self" | "spouse" | null;
  monthly_at_62: number;
  monthly_at_fra: number;
  fra_age: string;
  monthly_at_70: number;
}

export type ExtractedDocument = ExtractedAccountStatement | ExtractedSs;

export interface UploadResult {
  filename: string;
  id: number | null;
  error: string | null;
}

export interface StatementRow {
  id: number;
  filename: string;
  status: "uploaded" | "reading" | "pending_review" | "no_text" | "accepted";
  extracted: ExtractedDocument | null;
  created_at: string;
}

export interface Source {
  kind: "engine" | "rules" | "web";
  label: string;
  url: string | null;
}

export interface ChangeLine {
  label: string;
  kind: "money" | "age" | "rate";
  old: number | null;
  new: number | null;
}

export interface ChangeCard {
  id: number;
  reason: string;
  status: "proposed" | "applied" | "dismissed";
  lines: ChangeLine[];
  error: string | null;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
  sources: Source[];
  unchecked: boolean;
  changes: ChangeCard[];
}

export interface ChatState {
  status: "idle" | "working" | "failed";
  step: string | null;
  messages: ChatMessage[];
}
