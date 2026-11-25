import { useState } from "react";
import { ApiError, postJson } from "../api";
import { formatPercent, formatUsd } from "../format";
import type { ChangeCard as Card, ChangeLine } from "../types";

function formatValue(line: ChangeLine, value: number | null): string {
  if (value === null) return "None";
  if (line.kind === "money") return formatUsd(value);
  if (line.kind === "rate") return formatPercent(value);
  return String(value);
}

const DONE: Record<Exclude<Card["status"], "proposed">, string> = {
  applied: "Applied",
  dismissed: "Dismissed",
};

export function ChangeCard({
  card,
  onChange,
}: Readonly<{ card: Card; onChange: (card: Card) => void }>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(action: "apply" | "dismiss"): Promise<void> {
    setBusy(true);
    try {
      onChange(await postJson<Card>(`/api/chat/changes/${String(card.id)}/${action}`));
      setError(null);
    } catch (err) {
      setError(
        err instanceof ApiError && typeof err.detail === "string"
          ? err.detail
          : "Something went wrong. Try again in a moment.",
      );
      setBusy(false);
    }
  }

  return (
    <section className="change-card" aria-label="Proposed change">
      <p>{card.reason}</p>
      <ul className="change-lines">
        {card.lines.map((line, i) => (
          <li key={i}>
            <span>{line.label}</span>
            <span className="num">
              <span>{formatValue(line, line.old)}</span>
              {" → "}
              <span>{formatValue(line, line.new)}</span>
            </span>
          </li>
        ))}
      </ul>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {card.status === "proposed" ? (
        <div className="actions">
          <button
            type="button"
            className="primary"
            disabled={busy}
            onClick={() => {
              void act("apply");
            }}
          >
            Apply
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => {
              void act("dismiss");
            }}
          >
            Dismiss
          </button>
        </div>
      ) : (
        <p className="secondary">{DONE[card.status]}</p>
      )}
    </section>
  );
}
