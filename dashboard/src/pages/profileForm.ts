import type { Account, Household, Person } from "../types";

export const STEPS = ["You", "Spouse", "Income", "Accounts", "Spending", "Assumptions"] as const;

const INCOME_KEYS = new Set([
  "wages",
  "contribution_401k",
  "ss_at_62",
  "ss_at_fra",
  "ss_at_70",
  "ss_claim_age",
  "pension_annual",
  "pension_start_age",
  "pension_survivor_pct",
]);

export type Errors = Record<string, string>;

export function blankPerson(): Person {
  return {
    first_name: "",
    birth_date: "",
    retirement_age: 65,
    plan_to_age: 82,
    wages: 0,
    contribution_401k: 0,
    ss_at_62: 0,
    ss_at_fra: 0,
    ss_at_70: 0,
    ss_claim_age: null,
    pension_annual: 0,
    pension_start_age: null,
    pension_survivor_pct: 0,
  };
}

export function blankAccount(accounts: Account[]): Account {
  const next = Math.max(0, ...accounts.map((a) => Number(a.id.replace(/\D/g, "")) || 0)) + 1;
  return {
    id: `a${String(next)}`,
    kind: "pretax",
    owner: "self",
    label: "",
    balance: 0,
    cost_basis: 0,
    last4: null,
    as_of: new Date().toISOString().slice(0, 10),
  };
}

export function blankHousehold(): Household {
  return {
    self: blankPerson(),
    spouse: null,
    state: "CO",
    accounts: [],
    spending: {
      essential: 0,
      discretionary: 0,
      cobra_monthly: 0,
      bridge_monthly: 0,
      bridge_is_aca: false,
      one_time: [],
    },
    assumptions: {
      return_rate: 0.06,
      inflation: 0.025,
      ss_cola: 0.025,
      volatility: 0.12,
      heir_tax_rate: 0.22,
    },
    home_value: 0,
    mask_terms: [],
  };
}

interface FieldError {
  loc: unknown[];
  msg: string;
}

function isFieldError(item: unknown): item is FieldError {
  return (
    typeof item === "object" &&
    item !== null &&
    "loc" in item &&
    Array.isArray(item.loc) &&
    "msg" in item &&
    typeof item.msg === "string"
  );
}

export function parseErrors(detail: unknown): Errors {
  const errors: Errors = {};
  if (!Array.isArray(detail)) return errors;
  for (const item of detail) {
    if (isFieldError(item)) errors[item.loc.slice(1).map(String).join(".")] ??= item.msg;
  }
  return errors;
}

export function stepForPath(path: string): number {
  const [root, key] = path.split(".");
  if (root === "self" || root === "spouse") {
    if (INCOME_KEYS.has(key ?? "")) return 2;
    return root === "self" ? 0 : 1;
  }
  if (root === "accounts") return 3;
  if (root === "spending") return 4;
  return 5;
}
