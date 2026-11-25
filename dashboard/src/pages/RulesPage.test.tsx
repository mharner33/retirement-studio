import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RulesStatus } from "../types";
import { RulesPage } from "./RulesPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const current: RulesStatus = {
  current_file: "retirement_rules_2026-01-01.md",
  current_date: "2026-01-01",
  age_days: 327,
  stale: true,
  pending_file: null,
  changes: [],
};

const pending: RulesStatus = {
  ...current,
  stale: false,
  pending_file: "retirement_rules_2026-11-24.md",
  changes: [{ path: "federal.brackets.single.0.up_to", old: "12400", new: "12500" }],
};

const CURRENT_MD = `Source: https://www.irs.gov/pub/irs-drop/rp-25-32.pdf.
- https://www.irs.gov/publications/p915
- (https://www.irs.gov/publications/p915)
`;

const PENDING_MD = `## Federal
Figures here.

## Colorado

Not refreshed on 2026-11-24: source unavailable.
`;

interface Server {
  status: RulesStatus;
  calls: { path: string; method: string }[];
  accept?: Response;
}

function serve(server: Server): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      server.calls.push({ path, method });
      if (path === "/api/rules/status") {
        return Promise.resolve(new Response(JSON.stringify(server.status)));
      }
      if (path.endsWith("/accept")) {
        return Promise.resolve(
          server.accept ?? new Response(JSON.stringify({ ...current, stale: false })),
        );
      }
      if (path === "/api/rules/refresh") {
        return Promise.resolve(new Response("{}", { status: 202 }));
      }
      const md = path.includes("2026-11-24") ? PENDING_MD : CURRENT_MD;
      return Promise.resolve(new Response(md));
    }),
  );
}

describe("RulesPage", () => {
  it("shows the current date, age and stale banner", async () => {
    serve({ status: current, calls: [] });
    render(<RulesPage />);
    expect(await screen.findByText("Rules are out of date")).toBeTruthy();
    expect(screen.getByText("2026-01-01")).toBeTruthy();
    expect(screen.getByText("327 days old")).toBeTruthy();
  });

  it("hides the stale banner for current rules", async () => {
    serve({ status: { ...current, stale: false, age_days: 10 }, calls: [] });
    render(<RulesPage />);
    await screen.findByText("10 days old");
    expect(screen.queryByText("Rules are out of date")).toBeNull();
  });

  it("lists each source URL once", async () => {
    serve({ status: current, calls: [] });
    render(<RulesPage />);
    const list = await screen.findByRole("list", { name: "Sources" });
    const items = within(list).getAllByRole("listitem");
    expect(items.map((i) => i.textContent)).toEqual([
      "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
      "https://www.irs.gov/publications/p915",
    ]);
  });

  it("shows no review section without a pending file", async () => {
    serve({ status: current, calls: [] });
    render(<RulesPage />);
    await screen.findByText("327 days old");
    expect(screen.queryByRole("table", { name: "Pending changes" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  });

  it("shows the pending changes and the sections that were not refreshed", async () => {
    serve({ status: pending, calls: [] });
    render(<RulesPage />);
    const table = await screen.findByRole("table", { name: "Pending changes" });
    expect(within(table).getByText("federal.brackets.single.0.up_to")).toBeTruthy();
    expect(within(table).getByText("12500")).toBeTruthy();
    expect(await screen.findByText("Not refreshed: Colorado (source unavailable)")).toBeTruthy();
  });

  it("omits the not-refreshed line when every section was checked", async () => {
    serve({ status: pending, calls: [] });
    vi.stubGlobal(
      "fetch",
      vi.fn((path: string) =>
        Promise.resolve(
          new Response(path === "/api/rules/status" ? JSON.stringify(pending) : "## Federal\n"),
        ),
      ),
    );
    render(<RulesPage />);
    await screen.findByRole("table", { name: "Pending changes" });
    expect(screen.queryByText(/Not refreshed/)).toBeNull();
  });

  it("accepts the pending file and refreshes the status", async () => {
    const server: Server = { status: pending, calls: [] };
    serve(server);
    render(<RulesPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Accept" }));
    server.status = { ...current, stale: false, current_date: "2026-11-24", age_days: 0 };
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
    });
    expect(server.calls).toContainEqual({
      path: "/api/rules/retirement_rules_2026-11-24.md/accept",
      method: "POST",
    });
    expect(await screen.findByText("2026-11-24")).toBeTruthy();
  });

  it("shows the backend message when accept fails", async () => {
    serve({
      status: pending,
      calls: [],
      accept: new Response(JSON.stringify({ detail: "Rules file is already accepted" }), {
        status: 409,
      }),
    });
    render(<RulesPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Accept" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Rules file is already accepted");
  });

  it("keeps the current rules without calling the backend", async () => {
    const server: Server = { status: pending, calls: [] };
    serve(server);
    render(<RulesPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Keep current" }));
    expect(screen.queryByRole("table", { name: "Pending changes" })).toBeNull();
    expect(server.calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("starts a refresh", async () => {
    const server: Server = { status: current, calls: [] };
    serve(server);
    render(<RulesPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Refresh rules" }));
    expect(await screen.findByText("Research started. Check back in a few minutes.")).toBeTruthy();
    expect(server.calls).toContainEqual({ path: "/api/rules/refresh", method: "POST" });
  });

  it("shows an error when the status cannot be loaded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("x", { status: 500 }))),
    );
    render(<RulesPage />);
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
