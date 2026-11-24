import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Household } from "../types";
import { ProfilePage } from "./ProfilePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const person = {
  first_name: "Alex",
  birth_date: "1963-06-15",
  retirement_age: 63,
  plan_to_age: 82,
  wages: 120000,
  contribution_401k: 20000,
  ss_at_62: 2200,
  ss_at_fra: 3100,
  ss_at_70: 3900,
  ss_claim_age: null,
  pension_annual: 0,
  pension_start_age: null,
  pension_survivor_pct: 0,
};

const household: Household = {
  self: person,
  spouse: null,
  state: "CO",
  accounts: [
    {
      id: "a1",
      kind: "pretax",
      owner: "self",
      label: "401(k)",
      balance: 900000,
      cost_basis: 0,
      last4: "1234",
      as_of: "2026-11-01",
    },
  ],
  spending: {
    essential: 60000,
    discretionary: 15000,
    cobra_monthly: 1800,
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

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

function stubApi(get: Response, put?: Response) {
  const fn = vi.fn((_path: string, init: RequestInit) =>
    Promise.resolve(init.method === "PUT" && put ? put : get.clone()),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

function lastPutBody(fn: ReturnType<typeof stubApi>): Household {
  const call = fn.mock.calls.find(([, init]) => init.method === "PUT");
  return JSON.parse(call?.[1].body as string) as Household;
}

describe("ProfilePage wizard", () => {
  it("advances through the steps and keeps values", async () => {
    stubApi(json(404, { detail: "Not Found" }));
    render(<ProfilePage />);
    const name = await screen.findByLabelText<HTMLInputElement>("First name");
    fireEvent.change(name, { target: { value: "Alex" } });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "Add spouse" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByLabelText<HTMLInputElement>("First name").value).toBe("Alex");
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });

  it("adds and removes the spouse section", async () => {
    stubApi(json(404, { detail: "Not Found" }));
    render(<ProfilePage />);
    await screen.findByLabelText("First name");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Add spouse" }));
    expect(screen.getByLabelText("First name")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove spouse" }));
    expect(screen.getByRole("button", { name: "Add spouse" })).toBeTruthy();
  });

  it("saves the household from the last step", async () => {
    const fn = stubApi(json(404, {}), json(200, household));
    render(<ProfilePage />);
    await screen.findByLabelText("First name");
    for (let i = 0; i < 5; i += 1) {
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
    }
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Profile saved")).toBeTruthy();
    const body = lastPutBody(fn);
    expect(body.self.plan_to_age).toBe(82);
    expect(body.spouse).toBeNull();
    expect(body.assumptions.return_rate).toBeCloseTo(0.06);
    expect(body.state).toBe("CO");
  });

  it("shows a 422 message and returns to the step with the field", async () => {
    const detail = [{ loc: ["body", "self", "first_name"], msg: "Field required" }];
    stubApi(json(404, {}), json(422, { detail }));
    render(<ProfilePage />);
    await screen.findByLabelText("First name");
    for (let i = 0; i < 5; i += 1) {
      fireEvent.click(screen.getByRole("button", { name: "Next" }));
    }
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Field required")).toBeTruthy();
    expect(screen.getByLabelText("First name")).toBeTruthy();
  });

  it("shows an error when the profile cannot be loaded", async () => {
    stubApi(json(500, {}));
    render(<ProfilePage />);
    expect(await screen.findByText("Could not load the profile")).toBeTruthy();
  });
});

describe("ProfilePage editor", () => {
  it("shows every section with saved values, money formatted", async () => {
    stubApi(json(200, household));
    render(<ProfilePage />);
    const you = await screen.findByRole("group", { name: "You" });
    expect(within(you).getByLabelText<HTMLInputElement>("First name").value).toBe("Alex");
    const account = screen.getByRole("group", { name: "Account 1" });
    expect(within(account).getByLabelText<HTMLInputElement>("Balance").value).toBe("$900,000.00");
    expect(screen.getByLabelText<HTMLInputElement>("Return rate (%)").value).toBe("6");
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
  });

  it("saves edits, and shows a 422 message next to the field", async () => {
    const detail = [{ loc: ["body", "accounts", 0, "balance"], msg: "Input should be >= 0" }];
    const fn = stubApi(json(200, household), json(422, { detail }));
    render(<ProfilePage />);
    const account = await screen.findByRole("group", { name: "Account 1" });
    const balance = within(account).getByLabelText("Balance");
    fireEvent.focus(balance);
    fireEvent.change(balance, { target: { value: "-5" } });
    fireEvent.blur(balance);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await within(account).findByText("Input should be >= 0")).toBeTruthy();
    expect(lastPutBody(fn).accounts[0]?.balance).toBe(-5);
  });

  it("adds and removes accounts, one-time costs and the spouse", async () => {
    stubApi(json(200, household));
    render(<ProfilePage />);
    await screen.findByRole("group", { name: "Account 1" });
    fireEvent.click(screen.getByRole("button", { name: "Add account" }));
    expect(screen.getByRole("group", { name: "Account 2" })).toBeTruthy();
    fireEvent.click(
      within(screen.getByRole("group", { name: "Account 2" })).getByRole("button", {
        name: "Remove account",
      }),
    );
    expect(screen.queryByRole("group", { name: "Account 2" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Add one-time cost" }));
    expect(screen.getByLabelText("Year")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove one-time cost" }));
    expect(screen.queryByLabelText("Year")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Add spouse" }));
    expect(screen.getByRole("group", { name: "Spouse" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove spouse" }));
    expect(screen.queryByRole("group", { name: "Spouse" })).toBeNull();
  });
});

describe("ProfilePage fields", () => {
  it("edits every field and sends the changes", async () => {
    const fn = stubApi(
      json(200, { ...household, spouse: { ...person, first_name: "Sam" } }),
      json(200, household),
    );
    render(<ProfilePage />);
    await screen.findByRole("group", { name: "Account 1" });
    fireEvent.click(screen.getByRole("button", { name: "Add one-time cost" }));
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "taxable" } });
    for (const box of screen.getAllByRole("textbox")) {
      fireEvent.focus(box);
      fireEvent.change(box, { target: { value: "7" } });
      fireEvent.blur(box);
    }
    for (const box of screen.getAllByRole("spinbutton")) {
      fireEvent.change(box, { target: { value: "70" } });
    }
    for (const select of screen.getAllByRole("combobox")) {
      fireEvent.change(select, { target: { value: "spouse" } });
    }
    fireEvent.click(screen.getByRole("checkbox"));
    const income = within(screen.getByRole("group", { name: "Your income" }));
    fireEvent.change(income.getByLabelText("Claiming age (blank lets the plan choose)"), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByLabelText("Cost basis"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Profile saved");
    const body = lastPutBody(fn);
    expect(body.spending.bridge_is_aca).toBe(true);
    expect(body.accounts[0]?.owner).toBe("spouse");
    expect(body.self.ss_claim_age).toBeNull();
    expect(body.spending.one_time[0]?.year).toBe(70);
    expect(body.mask_terms).toEqual(["7"]);
  });

  it("reports a save failure that is not a validation error", async () => {
    stubApi(json(200, household), json(500, {}));
    render(<ProfilePage />);
    await screen.findByRole("group", { name: "Account 1" });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Could not save the profile")).toBeTruthy();
  });
});
