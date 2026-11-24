import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatUsd } from "../format";
import type { YearRow } from "../types";
import { KIND_LABELS, sum } from "./kinds";

const KINDS = ["pretax", "roth", "taxable", "cash", "hsa"] as const;

function compact(n: number): string {
  if (n === 0) {
    return "$0";
  }
  return n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` : `$${String(Math.round(n / 1000))}K`;
}

export function BalanceChart({ rows }: Readonly<{ rows: YearRow[] }>) {
  const kinds = KINDS.filter((k) => rows.some((r) => (r.balances[k] ?? 0) > 0));
  const data = rows.map((r) => ({ year: r.year, ...r.balances }));
  return (
    <section className="card wide">
      <h2>Balances by account type</h2>
      <ul className="legend" aria-label="Account types">
        {kinds.map((k) => (
          <li key={k}>
            <span className="swatch" style={{ background: `var(--series-${k})` }} />
            {KIND_LABELS[k]}
          </li>
        ))}
      </ul>
      <div
        className="chart"
        role="img"
        aria-label={`Stacked balances from ${String(rows[0]?.year)} to ${String(rows[rows.length - 1]?.year)}, ending at ${formatUsd(sum(rows[rows.length - 1]?.balances ?? {}))}. The year table has the same numbers.`}
      >
        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
            <CartesianGrid stroke="var(--divider)" vertical={false} />
            <XAxis
              dataKey="year"
              stroke="var(--text-secondary)"
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={28}
              tickMargin={6}
            />
            <YAxis
              stroke="var(--text-secondary)"
              tickLine={false}
              axisLine={false}
              tickFormatter={compact}
              width={64}
            />
            <Tooltip
              formatter={(v) => formatUsd(Number(v))}
              contentStyle={{
                background: "var(--card-bg)",
                border: 0,
                borderRadius: 12,
                color: "var(--text)",
              }}
              itemStyle={{ color: "var(--text)" }}
              labelStyle={{ color: "var(--text-secondary)" }}
            />
            {kinds.map((k) => (
              <Area
                key={k}
                type="monotone"
                dataKey={k}
                name={KIND_LABELS[k]}
                stackId="balances"
                fill={`var(--series-${k})`}
                fillOpacity={0.9}
                stroke="var(--card-bg)"
                strokeWidth={2}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
