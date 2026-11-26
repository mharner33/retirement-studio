import { describe, expect, it } from "vitest";
import { place } from "./popover";

function rect(left: number, right: number, bottom: number): DOMRect {
  return { left, right, bottom, top: bottom - 20, width: right - left, height: 20 } as DOMRect;
}

describe("place", () => {
  it("lines up with the button's right edge, just below it", () => {
    expect(place(rect(500, 520, 100), 288, 1400)).toEqual({ top: 106, left: 232 });
  });

  it("stays inside the left edge of the window", () => {
    expect(place(rect(40, 60, 100), 288, 390)).toEqual({ top: 106, left: 8 });
  });

  it("stays inside the right edge of the window", () => {
    expect(place(rect(370, 400, 100), 288, 390)).toEqual({ top: 106, left: 94 });
  });
});
