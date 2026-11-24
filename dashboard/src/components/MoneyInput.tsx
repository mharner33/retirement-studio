import { useState, type ComponentProps } from "react";
import { formatUsd } from "../format";

interface Props extends Omit<ComponentProps<"input">, "value" | "onChange" | "type"> {
  value: number;
  onChange: (value: number) => void;
}

export function MoneyInput({ value, onChange, className, ...rest }: Readonly<Props>) {
  const [text, setText] = useState<string | null>(null);

  function edit(raw: string): void {
    setText(raw);
    const parsed = Number(raw.replace(/[$,\s]/g, ""));
    onChange(Number.isFinite(parsed) ? parsed : 0);
  }

  return (
    <input
      {...rest}
      className={`num ${className ?? ""}`.trim()}
      type="text"
      inputMode="decimal"
      value={text ?? formatUsd(value)}
      onFocus={() => {
        setText(value === 0 ? "" : String(value));
      }}
      onChange={(e) => {
        edit(e.target.value);
      }}
      onBlur={() => {
        setText(null);
      }}
    />
  );
}
