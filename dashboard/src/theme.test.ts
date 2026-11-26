import { afterEach, describe, expect, it, vi } from "vitest";
import { applyTheme, initialTheme } from "./theme";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("theme", () => {
  it("prefers the stored theme", () => {
    localStorage.setItem("theme", "dark");
    expect(initialTheme()).toBe("dark");
  });

  it("falls back to the system preference", () => {
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: true })),
    );
    expect(initialTheme()).toBe("dark");
  });

  it("falls back to light when storage throws", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
    });
    vi.stubGlobal(
      "matchMedia",
      vi.fn(() => ({ matches: false })),
    );
    expect(initialTheme()).toBe("light");
  });

  it("sets data-theme on the html element", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset["theme"]).toBe("dark");
  });
});
