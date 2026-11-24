import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

function mockFetch(ok: boolean): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      ok
        ? Promise.resolve(new Response(JSON.stringify({ status: "ok" })))
        : Promise.reject(new Error("down")),
    ),
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: false })),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows the backend as up", async () => {
    mockFetch(true);
    render(<App />);
    expect(await screen.findByText("Backend is up")).toBeTruthy();
  });

  it("shows the backend as down when the request fails", async () => {
    mockFetch(false);
    render(<App />);
    expect(await screen.findByText("Backend is down")).toBeTruthy();
  });

  it("shows the backend as down on an error status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("x", { status: 500 }))),
    );
    render(<App />);
    expect(await screen.findByText("Backend is down")).toBeTruthy();
  });

  it("toggles the theme", async () => {
    mockFetch(true);
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Dark theme" }));
    expect(document.documentElement.dataset["theme"]).toBe("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
    fireEvent.click(screen.getByRole("button", { name: "Light theme" }));
    expect(document.documentElement.dataset["theme"]).toBe("light");
  });
});
