import { useEffect, useState } from "react";
import { ApiError, getJson } from "../api";
import { BalanceChart } from "../components/BalanceChart";
import { StrategyTable } from "../components/StrategyTable";
import { YearTable } from "../components/YearTable";
import { formatPercent, formatUsd } from "../format";
import type { Household, PlanResult } from "../types";

type State =
  | { kind: "loading" }
  | { kind: "no-profile" }
  | { kind: "failed" }
  | { kind: "ready"; plan: PlanResult; profile: Household | null };

async function loadProfile(signal: AbortSignal): Promise<Household | null> {
  try {
    return await getJson<Household>("/api/profile", signal);
  } catch {
    return null;
  }
}

export function PlanPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    Promise.all([getJson<PlanResult>("/api/plan", signal), loadProfile(signal)]).then(
      ([plan, profile]) => {
        setState({ kind: "ready", plan, profile });
      },
      (err: unknown) => {
        if (!signal.aborted) {
          setState({
            kind: err instanceof ApiError && err.status === 409 ? "no-profile" : "failed",
          });
        }
      },
    );
    return () => {
      controller.abort();
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <section className="card">
        <h2>Plan</h2>
        <p className="secondary" role="status">
          Calculating plan
        </p>
      </section>
    );
  }
  if (state.kind === "no-profile") {
    return (
      <section className="card">
        <h2>Plan</h2>
        <p className="secondary">Complete your profile first</p>
      </section>
    );
  }
  if (state.kind === "failed") {
    return (
      <section className="card">
        <h2>Plan</h2>
        <p className="error" role="alert">
          The plan could not be calculated. Try again in a moment.
        </p>
      </section>
    );
  }

  const { plan, profile } = state;
  const best = plan.top[0];
  const heirRate = profile?.assumptions.heir_tax_rate ?? null;
  return (
    <>
      <h2>Plan</h2>
      {plan.rules_stale && (
        <p className="notice" role="note">
          Rules are out of date
        </p>
      )}
      {profile?.spending.bridge_is_aca === true && (
        <p className="notice" role="note">
          Roth conversions before 65 may reduce your ACA premium subsidy. This plan does not include
          it.
        </p>
      )}
      {best && (
        <section className="card wide" aria-label="Best plan">
          <p className="secondary">Best plan</p>
          <p className="headline">{best.label}</p>
          <dl className="facts">
            <div>
              <dt>Lifetime tax</dt>
              <dd className="num">{formatUsd(best.lifetime_tax)}</dd>
            </div>
            <div>
              <dt>After-tax money at the end</dt>
              <dd className="num">{formatUsd(best.after_tax_end)}</dd>
            </div>
          </dl>
          <p>
            You can safely spend <span className="num">{formatUsd(best.safe_extra)}</span> more per
            year.
          </p>
          <p className="secondary">
            Works in <span className="num">{formatPercent(best.success_rate)}</span> of market paths
          </p>
        </section>
      )}
      <StrategyTable top={plan.top} baseline={plan.baseline} heirRate={heirRate} />
      <BalanceChart rows={plan.best_rows} />
      <YearTable rows={plan.best_rows} />
    </>
  );
}
