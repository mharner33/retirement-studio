import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { MoneyInput } from "./MoneyInput";

afterEach(cleanup);

function Harness({ start }: Readonly<{ start: number }>) {
  const [value, setValue] = useState(start);
  return (
    <>
      <MoneyInput aria-label="Amount" value={value} onChange={setValue} />
      <output>{String(value)}</output>
    </>
  );
}

describe("MoneyInput", () => {
  it("shows dollars and cents when not focused", () => {
    render(<Harness start={900000} />);
    expect(screen.getByLabelText<HTMLInputElement>("Amount").value).toBe("$900,000.00");
  });

  it("accepts plain digits while focused and formats on blur", () => {
    render(<Harness start={0} />);
    const input = screen.getByLabelText<HTMLInputElement>("Amount");
    fireEvent.focus(input);
    expect(input.value).toBe("");
    fireEvent.change(input, { target: { value: "1250" } });
    expect(input.value).toBe("1250");
    expect(screen.getByText("1250")).toBeTruthy();
    fireEvent.blur(input);
    expect(input.value).toBe("$1,250.00");
  });

  it("shows the stored number as plain digits when focused", () => {
    render(<Harness start={1250.5} />);
    const input = screen.getByLabelText<HTMLInputElement>("Amount");
    fireEvent.focus(input);
    expect(input.value).toBe("1250.5");
  });

  it("keeps a negative value so the backend can reject it", () => {
    render(<Harness start={5} />);
    const input = screen.getByLabelText<HTMLInputElement>("Amount");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "-20" } });
    expect(screen.getByText("-20")).toBeTruthy();
  });
});
