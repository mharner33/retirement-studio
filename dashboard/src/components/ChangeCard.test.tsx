import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ChangeCard as Card } from "../types";
import { ChangeCard } from "./ChangeCard";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const card: Card = {
  id: 7,
  reason: "Work two more years",
  status: "proposed",
  error: null,
  lines: [
    { label: "Wages (you)", kind: "money", old: 60000, new: 70000 },
    { label: "Retirement age (you)", kind: "age", old: 63, new: 65 },
    { label: "Return rate", kind: "rate", old: 0.05, new: 0.045 },
    { label: "One-time expense 2030: Roof", kind: "money", old: null, new: 12000 },
  ],
};

function stub(status: number, body: unknown): { calls: string[] } {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${path}`);
      return Promise.resolve(new Response(JSON.stringify(body), { status }));
    }),
  );
  return { calls };
}

describe("ChangeCard", () => {
  it("shows each line with old and new values", () => {
    render(<ChangeCard card={card} onChange={vi.fn()} />);
    expect(screen.getByText("Work two more years")).toBeTruthy();
    expect(screen.getByText("$60,000.00")).toBeTruthy();
    expect(screen.getByText("$70,000.00")).toBeTruthy();
    expect(screen.getByText("63")).toBeTruthy();
    expect(screen.getByText("65")).toBeTruthy();
    expect(screen.getByText("5.0%")).toBeTruthy();
    expect(screen.getByText("4.5%")).toBeTruthy();
    expect(screen.getByText("None")).toBeTruthy();
  });

  it("posts to the apply route and reports the new card", async () => {
    const { calls } = stub(200, { ...card, status: "applied" });
    const onChange = vi.fn();
    render(<ChangeCard card={card} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await vi.waitFor(() => {
      expect(onChange).toHaveBeenCalledWith({ ...card, status: "applied" });
    });
    expect(calls).toEqual(["POST /api/chat/changes/7/apply"]);
  });

  it("posts to the dismiss route", async () => {
    const { calls } = stub(200, { ...card, status: "dismissed" });
    render(<ChangeCard card={card} onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await vi.waitFor(() => {
      expect(calls).toEqual(["POST /api/chat/changes/7/dismiss"]);
    });
  });

  it("shows the message of a 422", async () => {
    stub(422, { detail: "self.plan_to_age: too low" });
    render(<ChangeCard card={card} onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect((await screen.findByRole("alert")).textContent).toBe("self.plan_to_age: too low");
    expect(screen.getByRole("button", { name: "Apply" })).toBeTruthy();
  });

  it("shows the message of a 409", async () => {
    stub(409, { detail: "The profile changed since this was proposed." });
    render(<ChangeCard card={card} onChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "The profile changed since this was proposed.",
    );
  });

  it("shows two lines with the same label", () => {
    const twice: Card = {
      ...card,
      lines: [
        { label: "One-time expense 2030: Roof", kind: "money", old: 5000, new: null },
        { label: "One-time expense 2030: Roof", kind: "money", old: 6000, new: null },
      ],
    };
    const errors = vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(<ChangeCard card={twice} onChange={vi.fn()} />);
    expect(screen.getAllByText("One-time expense 2030: Roof")).toHaveLength(2);
    expect(errors).not.toHaveBeenCalled();
    errors.mockRestore();
  });

  it("shows Applied and Dismissed without buttons", () => {
    const { rerender } = render(
      <ChangeCard card={{ ...card, status: "applied" }} onChange={vi.fn()} />,
    );
    expect(screen.getByText("Applied")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<ChangeCard card={{ ...card, status: "dismissed" }} onChange={vi.fn()} />);
    expect(screen.getByText("Dismissed")).toBeTruthy();
  });
});
