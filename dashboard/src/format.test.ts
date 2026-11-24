import { describe, expect, it } from "vitest";
import { formatUsd } from "./format";

describe("formatUsd", () => {
  it("formats dollars with grouping and cents", () => {
    expect(formatUsd(1250)).toBe("$1,250.00");
  });

  it("puts the minus sign before the dollar sign", () => {
    expect(formatUsd(-75.5)).toBe("-$75.50");
  });

  it("never shows a negative zero", () => {
    expect(formatUsd(-0)).toBe("$0.00");
  });

  it("formats zero", () => {
    expect(formatUsd(0)).toBe("$0.00");
  });
});
