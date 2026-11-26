import { useContext, type ReactNode } from "react";
import { ErrorsContext } from "./errors";
import { MoneyInput } from "./MoneyInput";

interface FieldProps {
  label: string;
  path: string;
  children: ReactNode;
}

function Field({ label, path, children }: Readonly<FieldProps>) {
  const error = useContext(ErrorsContext)[path];
  return (
    <div className="field">
      <label>
        <span>{label}</span>
        {children}
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

interface TextFieldProps {
  label: string;
  path: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "date";
}

export function TextField({
  label,
  path,
  value,
  onChange,
  type = "text",
}: Readonly<TextFieldProps>) {
  return (
    <Field label={label} path={path}>
      <input
        type={type}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
        }}
      />
    </Field>
  );
}

interface NumberFieldProps {
  label: string;
  path: string;
  value: number;
  onChange: (value: number) => void;
}

export function NumberField({ label, path, value, onChange }: Readonly<NumberFieldProps>) {
  return (
    <Field label={label} path={path}>
      <input
        className="num"
        type="number"
        value={value}
        onChange={(e) => {
          onChange(Number(e.target.value));
        }}
      />
    </Field>
  );
}

interface OptionalNumberFieldProps {
  label: string;
  path: string;
  value: number | null;
  onChange: (value: number | null) => void;
}

export function OptionalNumberField({
  label,
  path,
  value,
  onChange,
}: Readonly<OptionalNumberFieldProps>) {
  return (
    <Field label={label} path={path}>
      <input
        className="num"
        type="number"
        value={value ?? ""}
        onChange={(e) => {
          onChange(e.target.value === "" ? null : Number(e.target.value));
        }}
      />
    </Field>
  );
}

interface MoneyFieldProps {
  label: string;
  path: string;
  value: number;
  onChange: (value: number) => void;
}

export function MoneyField({ label, path, value, onChange }: Readonly<MoneyFieldProps>) {
  return (
    <Field label={label} path={path}>
      <MoneyInput value={value} onChange={onChange} />
    </Field>
  );
}

export function PercentField({ label, path, value, onChange }: Readonly<NumberFieldProps>) {
  return (
    <Field label={`${label} (%)`} path={path}>
      <input
        className="num"
        type="number"
        step="any"
        value={Number((value * 100).toFixed(4))}
        onChange={(e) => {
          onChange(Number(e.target.value) / 100);
        }}
      />
    </Field>
  );
}

interface SelectFieldProps<T extends string> {
  label: string;
  path: string;
  value: T;
  options: readonly { value: T; text: string }[];
  onChange: (value: T) => void;
}

export function SelectField<T extends string>({
  label,
  path,
  value,
  options,
  onChange,
}: Readonly<SelectFieldProps<T>>) {
  return (
    <Field label={label} path={path}>
      <select
        value={value}
        onChange={(e) => {
          const picked = options.find((o) => o.value === e.target.value);
          if (picked) onChange(picked.value);
        }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.text}
          </option>
        ))}
      </select>
    </Field>
  );
}

interface CheckFieldProps {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
}

export function CheckField({ label, value, onChange }: Readonly<CheckFieldProps>) {
  return (
    <div className="field">
      <label className="check">
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => {
            onChange(e.target.checked);
          }}
        />
        <span>{label}</span>
      </label>
    </div>
  );
}
