import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Household, PlanOption, PlanResult, YearRow } from "../types";
import { PlanPage } from "./PlanPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function option(label: string, over: Partial<PlanOption> = {}): PlanOption {
  return {
    strategy: {
      conversion_target: "12",
      convert_from_age: 65,
      convert_to_age: 70,
      withdrawal_order: "pretax_first",
      claim_ages: [70, 62],
      extra_spending: 0,
    },
    label,
    lifetime_tax: 250000,
    after_tax_end: 1162337.62,
    shortfall_year: null,
    success_rate: 0.996,
    safe_extra: 33900,
    ...over,
  };
}

function row(year: number): YearRow {
  return {
    year,
    ages: [63, 61],
    social_security: 0,
    pension: 0,
    rmd: 0,
    conversion: 1250,
    withdrawals: { cash: 40000, pretax: 59740.61, taxable: 0 },
    spending: 75000,
    federal_tax: 1000,
    state_tax: 250,
    irmaa: 0,
    balances: { cash: 0, taxable: 265000, pretax: 890000, roth: 63600, hsa: 0 },
    shortfall: 0,
  };
}

const plan: PlanResult = {
  rules_file: "retirement_rules_2026-01-01.md",
  rules_stale: false,
  top: [option("Fill 12% bracket 65-70, pretax first, claim 70/62"), option("Second strategy")],
  baseline: option("No conversions, pretax first, claim 70/62", {
    lifetime_tax: 200000,
    after_tax_end: 1130107.82,
    success_rate: 0.95,
  }),
  best_rows: Array.from({ length: 22 }, (_, i) => row(2026 + i)),
};

function profile(aca: boolean): Household {
  return {
    spending: { bridge_is_aca: aca },
    assumptions: { heir_tax_rate: 0.22 },
  } as Household;
}

function stub(planRes: () => Response, prof: () => Response): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string) => Promise.resolve(path === "/api/plan" ? planRes() : prof())),
  );
}

const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status });

describe("PlanPage", () => {
  it("shows a waiting message while the plan loads", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => undefined)),
    );
    render(<PlanPage />);
    expect(screen.getByText("Calculating plan")).toBeTruthy();
  });

  it("renders the headline from the plan", async () => {
    stub(
      () => json(plan),
      () => json(profile(false)),
    );
    render(<PlanPage />);
    const head = await screen.findByRole("region", { name: "Best plan" });
    expect(
      within(head).getByText("Fill 12% bracket 65-70, pretax first, claim 70/62"),
    ).toBeTruthy();
    expect(within(head).getByText("$250,000.00")).toBeTruthy();
    expect(within(head).getByText("$1,162,337.62")).toBeTruthy();
    expect(head.textContent).toContain("You can safely spend $33,900.00 more per year.");
    expect(head.textContent).toContain("Works in 99.6% of market paths");
  });

  it("compares strategies with both measures and explains the baseline", async () => {
    stub(
      () => json(plan),
      () => json(profile(false)),
    );
    render(<PlanPage />);
    const table = await screen.findByRole("table", { name: "Strategy comparison" });
    expect(within(table).getAllByRole("row")).toHaveLength(1 + 2 + 1);
    expect(within(table).getByText("$1,130,107.82")).toBeTruthy();
    expect(within(table).getByText("95.0%")).toBeTruthy();
    expect(screen.getByText(/after a 22% tax/)).toBeTruthy();
  });

  it("formats the year table in dollars", async () => {
    stub(
      () => json(plan),
      () => json(profile(false)),
    );
    render(<PlanPage />);
    const table = await screen.findByRole("table", { name: "Year by year" });
    expect(within(table).getAllByRole("row")).toHaveLength(23);
    expect(within(table).getAllByText("$1,250.00").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("63 / 61").length).toBeGreaterThan(0);
  });

  it("shows the ACA notice only when the bridge is ACA", async () => {
    stub(
      () => json(plan),
      () => json(profile(true)),
    );
    render(<PlanPage />);
    expect(await screen.findByText(/may reduce your ACA premium subsidy/)).toBeTruthy();
    cleanup();
    stub(
      () => json(plan),
      () => json(profile(false)),
    );
    render(<PlanPage />);
    await screen.findByRole("region", { name: "Best plan" });
    expect(screen.queryByText(/ACA premium subsidy/)).toBeNull();
  });

  it("shows the stale rules notice", async () => {
    stub(
      () => json({ ...plan, rules_stale: true }),
      () => json(profile(false)),
    );
    render(<PlanPage />);
    expect(await screen.findByText("Rules are out of date")).toBeTruthy();
  });

  it("hides the stale notice when the rules are current", async () => {
    stub(
      () => json(plan),
      () => json(profile(false)),
    );
    render(<PlanPage />);
    await screen.findByRole("region", { name: "Best plan" });
    expect(screen.queryByText("Rules are out of date")).toBeNull();
  });

  it("aborts the plan request when it unmounts", () => {
    const fetchMock = vi.fn(() => new Promise<Response>(() => undefined));
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<PlanPage />);
    const init = (fetchMock.mock.calls as unknown as [string, RequestInit][])[0]?.[1];
    expect(init?.signal?.aborted).toBe(false);
    unmount();
    expect(init?.signal?.aborted).toBe(true);
  });

  it("shows the headline figures in the number font", async () => {
    stub(
      () => json(plan),
      () => json(profile(false)),
    );
    render(<PlanPage />);
    const head = await screen.findByRole("region", { name: "Best plan" });
    expect(head.querySelectorAll("p .num")).toHaveLength(2);
  });

  it("asks for a profile on 409", async () => {
    stub(
      () => json({ detail: "No profile" }, 409),
      () => json({ detail: "x" }, 404),
    );
    render(<PlanPage />);
    expect(await screen.findByText("Complete your profile first")).toBeTruthy();
  });

  it("reports other failures", async () => {
    stub(
      () => json({ detail: "boom" }, 500),
      () => json(profile(false)),
    );
    render(<PlanPage />);
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("could not be calculated");
    });
  });
});
