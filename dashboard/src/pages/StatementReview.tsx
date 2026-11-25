import { useState } from "react";
import { MoneyInput } from "../components/MoneyInput";
import { KIND_LABELS } from "../components/kinds";
import type { ExtractedAccount, ExtractedDocument, ExtractedSs } from "../types";

interface Props {
  filename: string;
  document: ExtractedDocument;
  busy: boolean;
  onAccept: (document: ExtractedDocument) => void;
  onDiscard: () => void;
}

const OWNERS = { self: "You", spouse: "Spouse" } as const;

function AccountRows({
  accounts,
  onChange,
}: Readonly<{ accounts: ExtractedAccount[]; onChange: (next: ExtractedAccount[]) => void }>) {
  function edit(i: number, patch: Partial<ExtractedAccount>): void {
    onChange(accounts.map((a, j) => (j === i ? { ...a, ...patch } : a)));
  }
  return (
    <div className="table-wrap">
      <table aria-label="Accounts found" className="review-table">
        <thead>
          <tr>
            <th scope="col">Type</th>
            <th scope="col">Owner</th>
            <th scope="col">Label</th>
            <th scope="col">Balance</th>
            <th scope="col">Cost basis</th>
          </tr>
        </thead>
        <tbody>
          {accounts.map((a, i) => {
            const n = String(i + 1);
            return (
              <tr key={`${a.label}-${n}`}>
                <td>
                  <select
                    aria-label={`Type, account ${n}`}
                    value={a.kind}
                    onChange={(e) => {
                      edit(i, { kind: e.target.value as ExtractedAccount["kind"] });
                    }}
                  >
                    {Object.entries(KIND_LABELS).map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    aria-label={`Owner, account ${n}`}
                    value={a.owner}
                    onChange={(e) => {
                      edit(i, { owner: e.target.value as ExtractedAccount["owner"] });
                    }}
                  >
                    {Object.entries(OWNERS).map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    aria-label={`Label, account ${n}`}
                    value={a.label}
                    onChange={(e) => {
                      edit(i, { label: e.target.value });
                    }}
                  />
                </td>
                <td>
                  <MoneyInput
                    aria-label={`Balance, account ${n}`}
                    value={a.balance}
                    onChange={(balance) => {
                      edit(i, { balance });
                    }}
                  />
                </td>
                <td>
                  <MoneyInput
                    aria-label={`Cost basis, account ${n}`}
                    value={a.cost_basis ?? 0}
                    onChange={(cost_basis) => {
                      edit(i, { cost_basis });
                    }}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SocialSecurityFields({
  doc,
  onChange,
}: Readonly<{ doc: ExtractedSs; onChange: (next: ExtractedSs) => void }>) {
  return (
    <>
      <fieldset className="section">
        <legend>Whose statement is this?</legend>
        {(["self", "spouse"] as const).map((who) => (
          <label key={who} className="check">
            <input
              type="radio"
              name="person"
              checked={doc.person === who}
              onChange={() => {
                onChange({ ...doc, person: who });
              }}
            />
            {OWNERS[who]}
          </label>
        ))}
      </fieldset>
      <div className="field-row">
        {(
          [
            ["Monthly at 62", "monthly_at_62"],
            ["Monthly at full retirement age", "monthly_at_fra"],
            ["Monthly at 70", "monthly_at_70"],
          ] as const
        ).map(([label, key]) => (
          <div key={key} className="field">
            <label>
              <span>{label}</span>
              <MoneyInput
                aria-label={label}
                value={doc[key]}
                onChange={(value) => {
                  onChange({ ...doc, [key]: value });
                }}
              />
            </label>
          </div>
        ))}
      </div>
    </>
  );
}

export function StatementReview({
  filename,
  document,
  busy,
  onAccept,
  onDiscard,
}: Readonly<Props>) {
  const [draft, setDraft] = useState<ExtractedDocument>(document);
  const needsPerson = draft.doc_type === "social_security" && draft.person === null;
  return (
    <section className="card wide" aria-label={`Review ${filename}`}>
      <h3>{filename}</h3>
      {draft.doc_type === "account" ? (
        <AccountRows
          accounts={draft.accounts}
          onChange={(accounts) => {
            setDraft({ ...draft, accounts });
          }}
        />
      ) : (
        <SocialSecurityFields doc={draft} onChange={setDraft} />
      )}
      <p className="secondary">Nothing is saved until you accept.</p>
      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={busy || needsPerson}
          onClick={() => {
            onAccept(draft);
          }}
        >
          Accept
        </button>
        <button type="button" className="secondary-button" onClick={onDiscard}>
          Discard
        </button>
      </div>
    </section>
  );
}
