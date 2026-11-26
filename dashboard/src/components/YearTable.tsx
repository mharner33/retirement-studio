import { useCallback, useState } from "react";
import { formatUsd } from "../format";
import type { YearRow } from "../types";
import { ColumnHelp } from "./ColumnHelp";
import { COLUMN_HELP } from "./columnHelp";
import { KIND_LABELS, sum } from "./kinds";

function Withdrawals({ row }: Readonly<{ row: YearRow }>) {
  const parts = Object.entries(row.withdrawals).filter(([, v]) => v > 0);
  if (parts.length === 0) {
    return <>{formatUsd(0)}</>;
  }
  return (
    <>
      {parts.map(([kind, v]) => (
        <div key={kind}>
          {formatUsd(v)} <span className="secondary-inline">{KIND_LABELS[kind] ?? kind}</span>
        </div>
      ))}
    </>
  );
}

export function YearTable({ rows }: Readonly<{ rows: YearRow[] }>) {
  const [open, setOpen] = useState<string | null>(null);
  const close = useCallback(() => {
    setOpen(null);
  }, []);
  return (
    <section className="card wide">
      <h2>Year by year</h2>
      <div className="table-wrap">
        <table aria-label="Year by year">
          <thead>
            <tr>
              {COLUMN_HELP.map((c) => (
                <th scope="col" key={c.label}>
                  <ColumnHelp
                    label={c.label}
                    help={c.help}
                    open={open === c.label}
                    onToggle={() => {
                      setOpen(open === c.label ? null : c.label);
                    }}
                    onClose={close}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.year}>
                <th scope="row" className="num">
                  {r.year}
                </th>
                <td className="num">{r.ages.map((a) => a ?? "-").join(" / ")}</td>
                <td className="num">{formatUsd(r.social_security)}</td>
                <td className="num">
                  <Withdrawals row={r} />
                </td>
                <td className="num">{formatUsd(r.conversion)}</td>
                <td className="num">{formatUsd(r.federal_tax + r.state_tax + r.irmaa)}</td>
                <td className="num">{formatUsd(r.spending)}</td>
                <td className="num">{formatUsd(sum(r.balances))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
