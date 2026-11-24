import type { ReactNode } from "react";
import {
  CheckField,
  MoneyField,
  NumberField,
  OptionalNumberField,
  PercentField,
  SelectField,
  TextField,
} from "../components/fields";
import type { Account, AccountKind, Assumptions, Household, Person, Spending } from "../types";
import { blankAccount } from "./profileForm";

const KINDS: readonly { value: AccountKind; text: string }[] = [
  { value: "pretax", text: "Pre-tax (401(k), traditional IRA)" },
  { value: "roth", text: "Roth" },
  { value: "taxable", text: "Taxable brokerage" },
  { value: "cash", text: "Cash" },
  { value: "hsa", text: "HSA" },
];

const OWNERS = [
  { value: "self", text: "You" },
  { value: "spouse", text: "Spouse" },
] as const;

function Section({ title, children }: Readonly<{ title: string; children: ReactNode }>) {
  return (
    <fieldset className="card section">
      <legend>{title}</legend>
      {children}
    </fieldset>
  );
}

interface PersonProps {
  title: string;
  path: "self" | "spouse";
  person: Person;
  onChange: (person: Person) => void;
}

export function PersonSection({ title, path, person, onChange }: Readonly<PersonProps>) {
  const set = <K extends keyof Person>(key: K, value: Person[K]): void => {
    onChange({ ...person, [key]: value });
  };
  return (
    <Section title={title}>
      <TextField
        label="First name"
        path={`${path}.first_name`}
        value={person.first_name}
        onChange={(v) => {
          set("first_name", v);
        }}
      />
      <TextField
        label="Birth date"
        type="date"
        path={`${path}.birth_date`}
        value={person.birth_date}
        onChange={(v) => {
          set("birth_date", v);
        }}
      />
      <NumberField
        label="Retirement age"
        path={`${path}.retirement_age`}
        value={person.retirement_age}
        onChange={(v) => {
          set("retirement_age", v);
        }}
      />
      <NumberField
        label="Plan to age"
        path={`${path}.plan_to_age`}
        value={person.plan_to_age}
        onChange={(v) => {
          set("plan_to_age", v);
        }}
      />
    </Section>
  );
}

export function IncomeSection({ title, path, person, onChange }: Readonly<PersonProps>) {
  const set = <K extends keyof Person>(key: K, value: Person[K]): void => {
    onChange({ ...person, [key]: value });
  };
  return (
    <Section title={title}>
      <MoneyField
        label="Wages per year"
        path={`${path}.wages`}
        value={person.wages}
        onChange={(v) => {
          set("wages", v);
        }}
      />
      <MoneyField
        label="401(k) contributions per year (with match)"
        path={`${path}.contribution_401k`}
        value={person.contribution_401k}
        onChange={(v) => {
          set("contribution_401k", v);
        }}
      />
      <MoneyField
        label="Social Security per month at 62"
        path={`${path}.ss_at_62`}
        value={person.ss_at_62}
        onChange={(v) => {
          set("ss_at_62", v);
        }}
      />
      <MoneyField
        label="Social Security per month at full retirement age"
        path={`${path}.ss_at_fra`}
        value={person.ss_at_fra}
        onChange={(v) => {
          set("ss_at_fra", v);
        }}
      />
      <MoneyField
        label="Social Security per month at 70"
        path={`${path}.ss_at_70`}
        value={person.ss_at_70}
        onChange={(v) => {
          set("ss_at_70", v);
        }}
      />
      <OptionalNumberField
        label="Claiming age (blank lets the plan choose)"
        path={`${path}.ss_claim_age`}
        value={person.ss_claim_age}
        onChange={(v) => {
          set("ss_claim_age", v);
        }}
      />
      <MoneyField
        label="Pension per year"
        path={`${path}.pension_annual`}
        value={person.pension_annual}
        onChange={(v) => {
          set("pension_annual", v);
        }}
      />
      <OptionalNumberField
        label="Pension start age"
        path={`${path}.pension_start_age`}
        value={person.pension_start_age}
        onChange={(v) => {
          set("pension_start_age", v);
        }}
      />
      <PercentField
        label="Pension kept by survivor"
        path={`${path}.pension_survivor_pct`}
        value={person.pension_survivor_pct}
        onChange={(v) => {
          set("pension_survivor_pct", v);
        }}
      />
    </Section>
  );
}

interface AccountsProps {
  accounts: Account[];
  onChange: (accounts: Account[]) => void;
}

export function AccountsSection({ accounts, onChange }: Readonly<AccountsProps>) {
  const update = (i: number, patch: Partial<Account>): void => {
    onChange(accounts.map((a, j) => (j === i ? { ...a, ...patch } : a)));
  };
  return (
    <>
      {accounts.map((a, i) => (
        <fieldset key={a.id} className="card section">
          <legend>{`Account ${String(i + 1)}`}</legend>
          <TextField
            label="Label"
            path={`accounts.${String(i)}.label`}
            value={a.label}
            onChange={(v) => {
              update(i, { label: v });
            }}
          />
          <SelectField
            label="Type"
            path={`accounts.${String(i)}.kind`}
            value={a.kind}
            options={KINDS}
            onChange={(v) => {
              update(i, { kind: v });
            }}
          />
          <SelectField
            label="Owner"
            path={`accounts.${String(i)}.owner`}
            value={a.owner}
            options={OWNERS}
            onChange={(v) => {
              update(i, { owner: v });
            }}
          />
          <MoneyField
            label="Balance"
            path={`accounts.${String(i)}.balance`}
            value={a.balance}
            onChange={(v) => {
              update(i, { balance: v });
            }}
          />
          {a.kind === "taxable" && (
            <MoneyField
              label="Cost basis"
              path={`accounts.${String(i)}.cost_basis`}
              value={a.cost_basis}
              onChange={(v) => {
                update(i, { cost_basis: v });
              }}
            />
          )}
          <TextField
            label="Last 4 digits"
            path={`accounts.${String(i)}.last4`}
            value={a.last4 ?? ""}
            onChange={(v) => {
              update(i, { last4: v === "" ? null : v });
            }}
          />
          <TextField
            label="Balance as of"
            type="date"
            path={`accounts.${String(i)}.as_of`}
            value={a.as_of}
            onChange={(v) => {
              update(i, { as_of: v });
            }}
          />
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              onChange(accounts.filter((_, j) => j !== i));
            }}
          >
            Remove account
          </button>
        </fieldset>
      ))}
      <button
        type="button"
        className="secondary-button"
        onClick={() => {
          onChange([...accounts, blankAccount(accounts)]);
        }}
      >
        Add account
      </button>
    </>
  );
}

interface SpendingProps {
  spending: Spending;
  onChange: (spending: Spending) => void;
}

export function SpendingSection({ spending, onChange }: Readonly<SpendingProps>) {
  const set = <K extends keyof Spending>(key: K, value: Spending[K]): void => {
    onChange({ ...spending, [key]: value });
  };
  return (
    <Section title="Spending">
      <MoneyField
        label="Essential spending per year"
        path="spending.essential"
        value={spending.essential}
        onChange={(v) => {
          set("essential", v);
        }}
      />
      <MoneyField
        label="Discretionary spending per year"
        path="spending.discretionary"
        value={spending.discretionary}
        onChange={(v) => {
          set("discretionary", v);
        }}
      />
      <MoneyField
        label="COBRA premium per month"
        path="spending.cobra_monthly"
        value={spending.cobra_monthly}
        onChange={(v) => {
          set("cobra_monthly", v);
        }}
      />
      <MoneyField
        label="Bridge insurance per month"
        path="spending.bridge_monthly"
        value={spending.bridge_monthly}
        onChange={(v) => {
          set("bridge_monthly", v);
        }}
      />
      <CheckField
        label="Bridge insurance is an ACA plan"
        value={spending.bridge_is_aca}
        onChange={(v) => {
          set("bridge_is_aca", v);
        }}
      />
      {spending.one_time.map((item, i) => (
        <div key={i} className="one-time">
          <NumberField
            label="Year"
            path={`spending.one_time.${String(i)}.year`}
            value={item.year}
            onChange={(v) => {
              set(
                "one_time",
                spending.one_time.map((o, j) => (j === i ? { ...o, year: v } : o)),
              );
            }}
          />
          <MoneyField
            label="Cost"
            path={`spending.one_time.${String(i)}.amount`}
            value={item.amount}
            onChange={(v) => {
              set(
                "one_time",
                spending.one_time.map((o, j) => (j === i ? { ...o, amount: v } : o)),
              );
            }}
          />
          <TextField
            label="What for"
            path={`spending.one_time.${String(i)}.label`}
            value={item.label}
            onChange={(v) => {
              set(
                "one_time",
                spending.one_time.map((o, j) => (j === i ? { ...o, label: v } : o)),
              );
            }}
          />
          <button
            type="button"
            className="secondary-button"
            onClick={() => {
              set(
                "one_time",
                spending.one_time.filter((_, j) => j !== i),
              );
            }}
          >
            Remove one-time cost
          </button>
        </div>
      ))}
      <button
        type="button"
        className="secondary-button"
        onClick={() => {
          set("one_time", [
            ...spending.one_time,
            { year: new Date().getFullYear() + 1, amount: 0, label: "" },
          ]);
        }}
      >
        Add one-time cost
      </button>
    </Section>
  );
}

interface AssumptionsProps {
  household: Household;
  onChange: (household: Household) => void;
}

const RATES: readonly { key: keyof Assumptions; label: string }[] = [
  { key: "return_rate", label: "Return rate" },
  { key: "inflation", label: "Inflation" },
  { key: "ss_cola", label: "Social Security cost-of-living increase" },
  { key: "volatility", label: "Volatility" },
  { key: "heir_tax_rate", label: "Heir tax rate" },
];

export function AssumptionsSection({ household, onChange }: Readonly<AssumptionsProps>) {
  return (
    <Section title="Assumptions">
      {RATES.map(({ key, label }) => (
        <PercentField
          key={key}
          label={label}
          path={`assumptions.${key}`}
          value={household.assumptions[key]}
          onChange={(v) => {
            onChange({ ...household, assumptions: { ...household.assumptions, [key]: v } });
          }}
        />
      ))}
      <MoneyField
        label="Home value"
        path="home_value"
        value={household.home_value}
        onChange={(v) => {
          onChange({ ...household, home_value: v });
        }}
      />
      <div className="field">
        <label>
          <span>Terms to hide from the model (comma separated)</span>
          <input
            type="text"
            defaultValue={household.mask_terms.join(", ")}
            onBlur={(e) => {
              onChange({
                ...household,
                mask_terms: e.target.value
                  .split(",")
                  .map((t) => t.trim())
                  .filter((t) => t !== ""),
              });
            }}
          />
        </label>
      </div>
    </Section>
  );
}
