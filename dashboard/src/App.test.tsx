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

  it("opens the profile page from the sidebar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("{}", { status: 404 }))),
    );
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Profile" }));
    expect(await screen.findByLabelText("First name")).toBeTruthy();
  });

  it("opens the plan page from the sidebar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("{}", { status: 409 }))),
    );
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Plan" }));
    expect(await screen.findByText("Complete your profile first")).toBeTruthy();
  });

  it("opens the rules page from the sidebar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("{}", { status: 500 }))),
    );
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Rules" }));
    expect(await screen.findByRole("heading", { name: "Rules" })).toBeTruthy();
  });

  it("opens the statements page from the sidebar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("[]"))),
    );
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Statements" }));
    expect(await screen.findByRole("heading", { name: "Statements" })).toBeTruthy();
  });
});
