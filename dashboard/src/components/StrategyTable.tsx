import { formatPercent, formatUsd } from "../format";
import type { PlanOption } from "../types";

interface Props {
  top: PlanOption[];
  baseline: PlanOption;
  heirRate: number | null;
}

function OptionRow({ option, baseline }: Readonly<{ option: PlanOption; baseline: boolean }>) {
  return (
    <tr className={baseline ? "baseline" : undefined}>
      <th scope="row">{option.label}</th>
      <td className="num">{formatUsd(option.lifetime_tax)}</td>
      <td className="num">{formatUsd(option.after_tax_end)}</td>
      <td className="num">{formatPercent(option.success_rate)}</td>
      <td className="num">{formatUsd(option.safe_extra)}</td>
    </tr>
  );
}

export function StrategyTable({ top, baseline, heirRate }: Readonly<Props>) {
  const tax = heirRate === null ? "a tax" : `a ${String(Math.round(heirRate * 100))}% tax`;
  return (
    <section className="card wide">
      <h2>Compare strategies</h2>
      <div className="table-wrap">
        <table aria-label="Strategy comparison">
          <thead>
            <tr>
              <th scope="col">Strategy</th>
              <th scope="col">Lifetime tax</th>
              <th scope="col">After-tax money at the end</th>
              <th scope="col">Market paths that work</th>
              <th scope="col">Safe extra per year</th>
            </tr>
          </thead>
          <tbody>
            {top.map((o) => (
              <OptionRow key={o.label} option={o} baseline={false} />
            ))}
            <OptionRow option={baseline} baseline />
          </tbody>
        </table>
      </div>
      <p className="secondary">
        After-tax money counts pre-tax balances left at the plan-to age after {tax}. A plan with no
        conversions often pays less tax but ends with less after-tax money.
      </p>
    </section>
  );
}
