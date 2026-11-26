import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { YearRow } from "../types";
import { COLUMN_HELP } from "./columnHelp";
import { YearTable } from "./YearTable";

afterEach(cleanup);

const row: YearRow = {
  year: 2030,
  ages: [63, null],
  social_security: 88476.34,
  pension: 0,
  rmd: 0,
  conversion: 0,
  withdrawals: { pretax: 1000 },
  spending: 75000,
  federal_tax: 1000,
  state_tax: 250,
  irmaa: 0,
  balances: { pretax: 890000 },
  shortfall: 0,
};

function helpButton(label: string): HTMLElement {
  return screen.getByRole("button", { name: `How ${label} is worked out` });
}

describe("YearTable column help", () => {
  it("has a help button on every column, closed at first", () => {
    render(<YearTable rows={[row]} />);
    expect(COLUMN_HELP).toHaveLength(8);
    for (const c of COLUMN_HELP) {
      expect(helpButton(c.label).getAttribute("aria-expanded")).toBe("false");
      expect(screen.getByRole("columnheader", { name: new RegExp(`^${c.label}`) })).toBeTruthy();
    }
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("opens one explanation at a time and toggles it closed", () => {
    render(<YearTable rows={[row]} />);
    fireEvent.click(helpButton("Social Security"));
    expect(helpButton("Social Security").getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("note").textContent).toContain("Both benefits together.");

    fireEvent.mouseDown(helpButton("Tax"));
    fireEvent.click(helpButton("Tax"));
    expect(screen.getAllByRole("note")).toHaveLength(1);
    expect(screen.getByRole("note").textContent).toContain("Medicare IRMAA surcharge");

    fireEvent.mouseDown(helpButton("Tax"));
    fireEvent.click(helpButton("Tax"));
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("closes on Escape and returns focus to the button", () => {
    render(<YearTable rows={[row]} />);
    fireEvent.click(helpButton("Spending"));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("note")).toBeNull();
    expect(document.activeElement).toBe(helpButton("Spending"));
  });

  it("closes on a click elsewhere", () => {
    render(<YearTable rows={[row]} />);
    fireEvent.click(helpButton("End balance"));
    fireEvent.mouseDown(screen.getByRole("table", { name: "Year by year" }));
    expect(screen.queryByRole("note")).toBeNull();
  });

  it("ignores other keys while open", () => {
    render(<YearTable rows={[row]} />);
    fireEvent.click(helpButton("Ages"));
    fireEvent.keyDown(document, { key: "a" });
    expect(screen.getByRole("note").textContent).toContain("A dash means");
  });
});
