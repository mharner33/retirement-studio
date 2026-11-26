import { describe, expect, it } from "vitest";
import { formatCompact, formatPercent, formatUsd } from "./format";

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

describe("formatPercent", () => {
  it("floors to one decimal so only a true 1.0 shows 100.0%", () => {
    expect(formatPercent(0.9996)).toBe("99.9%");
    expect(formatPercent(1)).toBe("100.0%");
    expect(formatPercent(0.996)).toBe("99.6%");
    expect(formatPercent(0.57)).toBe("57.0%");
  });
});

describe("formatCompact", () => {
  it("formats thousands and millions", () => {
    expect(formatCompact(0)).toBe("$0");
    expect(formatCompact(264_900)).toBe("$265K");
    expect(formatCompact(1_250_000)).toBe("$1.3M");
  });

  it("rolls values just under a million into millions", () => {
    expect(formatCompact(999_600)).toBe("$1.0M");
  });

  it("puts the minus sign before the dollar sign", () => {
    expect(formatCompact(-264_900)).toBe("-$265K");
    expect(formatCompact(-1_250_000)).toBe("-$1.3M");
  });
});
