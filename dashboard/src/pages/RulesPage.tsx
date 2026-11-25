import { useEffect, useState } from "react";
import { ApiError, getJson, getText, postJson } from "../api";
import type { RulesStatus } from "../types";

function sources(markdown: string): string[] {
  const urls = markdown.match(/https:\/\/[^\s)"'<>\],]+/g) ?? [];
  return [...new Set(urls.map((u) => u.replace(/[.;:]$/, "")))];
}

function notRefreshed(markdown: string): string[] {
  return markdown
    .split(/^## /m)
    .slice(1)
    .flatMap((section) => {
      const lines = section.split("\n");
      const note = lines.find((l) => l.startsWith("Not refreshed on "));
      if (note === undefined) {
        return [];
      }
      const reason = note.slice(note.indexOf(":") + 1).trim();
      return [`${(lines[0] ?? "").trim()} (${reason.replace(/\.$/, "")})`];
    });
}

interface Loaded {
  status: RulesStatus;
  urls: string[];
  stale: string[];
}

async function load(): Promise<Loaded> {
  const status = await getJson<RulesStatus>("/api/rules/status");
  const [current, pending] = await Promise.all([
    getText(`/api/rules/${status.current_file}`),
    status.pending_file === null
      ? Promise.resolve("")
      : getText(`/api/rules/${status.pending_file}`),
  ]);
  return { status, urls: sources(current), stale: notRefreshed(pending) };
}

function errorText(err: unknown): string {
  return err instanceof ApiError && typeof err.detail === "string"
    ? err.detail
    : "Something went wrong. Try again in a moment.";
}

export function RulesPage() {
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [kept, setKept] = useState(false);
  const [started, setStarted] = useState(false);

  async function reload(): Promise<void> {
    try {
      setData(await load());
      setError(null);
    } catch (err) {
      setError(errorText(err));
    }
  }

  useEffect(() => {
    load().then(setData, (err: unknown) => {
      setError(errorText(err));
    });
  }, []);

  async function accept(file: string): Promise<void> {
    try {
      await postJson(`/api/rules/${file}/accept`);
    } catch (err) {
      setError(errorText(err));
      return;
    }
    await reload();
  }

  async function refresh(): Promise<void> {
    try {
      await postJson("/api/rules/refresh");
      setStarted(true);
      setError(null);
    } catch (err) {
      setError(errorText(err));
    }
  }

  if (!data) {
    return (
      <section className="card">
        <h2>Rules</h2>
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : (
          <p className="secondary" role="status">
            Loading rules
          </p>
        )}
      </section>
    );
  }

  const { status, urls, stale } = data;
  const pendingFile = kept ? null : status.pending_file;
  return (
    <>
      <h2>Rules</h2>
      {status.stale && (
        <p className="notice" role="note">
          Rules are out of date
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <section className="card wide" aria-label="Current rules">
        <h3>Current rules</h3>
        <dl className="facts">
          <div>
            <dt>Rules date</dt>
            <dd className="num">{status.current_date ?? "Unknown"}</dd>
          </div>
          <div>
            <dt>Age</dt>
            <dd className="num">
              {status.age_days === null ? "Unknown" : `${String(status.age_days)} days old`}
            </dd>
          </div>
        </dl>
        <h3>Sources</h3>
        <ul aria-label="Sources" className="sources">
          {urls.map((u) => (
            <li key={u} className="num">
              {u}
            </li>
          ))}
        </ul>
        <div className="actions">
          <button
            type="button"
            className="primary"
            onClick={() => {
              void refresh();
            }}
          >
            Refresh rules
          </button>
          {started && (
            <p className="secondary" role="status">
              Research started. Check back in a few minutes.
            </p>
          )}
        </div>
      </section>
      {pendingFile && (
        <section className="card wide" aria-label="Pending review">
          <h3>Review new rules</h3>
          <div className="table-wrap">
            <table aria-label="Pending changes">
              <thead>
                <tr>
                  <th scope="col">Path</th>
                  <th scope="col">Current</th>
                  <th scope="col">New</th>
                </tr>
              </thead>
              <tbody>
                {status.changes.map((c) => (
                  <tr key={c.path}>
                    <th scope="row" className="num">
                      {c.path}
                    </th>
                    <td className="num">{c.old}</td>
                    <td className="num">{c.new}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {stale.length > 0 && <p className="secondary">{`Not refreshed: ${stale.join(", ")}`}</p>}
          <div className="actions">
            <button
              type="button"
              className="primary"
              onClick={() => {
                void accept(pendingFile);
              }}
            >
              Accept
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                setKept(true);
              }}
            >
              Keep current
            </button>
          </div>
        </section>
      )}
    </>
  );
}
