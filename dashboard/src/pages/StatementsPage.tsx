import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getJson, postForm, postJson } from "../api";
import type { ExtractedDocument, StatementRow, UploadResult } from "../types";
import { StatementReview } from "./StatementReview";

const STATUS_LABELS: Record<StatementRow["status"], string> = {
  uploaded: "Uploaded",
  reading: "Reading",
  pending_review: "Ready to review",
  no_text: "No text found",
  accepted: "Accepted",
};

const POLL_MS = 3000;

const GENERIC_ERROR = "Something went wrong. Try again in a moment.";

function errorText(err: unknown): string {
  if (!(err instanceof ApiError)) return GENERIC_ERROR;
  if (typeof err.detail === "string") return err.detail;
  if (Array.isArray(err.detail)) {
    const first: unknown = err.detail[0];
    if (typeof first === "object" && first !== null && "msg" in first) {
      const msg: unknown = first.msg;
      if (typeof msg === "string") return msg;
    }
  }
  return GENERIC_ERROR;
}

function StatementTable({ rows }: Readonly<{ rows: StatementRow[] | null }>) {
  if (rows === null) {
    return (
      <p className="secondary" role="status">
        Loading statements
      </p>
    );
  }
  if (rows.length === 0) {
    return <p className="secondary">No statements yet.</p>;
  }
  return (
    <div className="table-wrap">
      <table aria-label="Statements">
        <thead>
          <tr>
            <th scope="col">File</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <th scope="row">{r.filename}</th>
              <td>{STATUS_LABELS[r.status]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StatementsPage() {
  const [rows, setRows] = useState<StatementRow[] | null>(null);
  const [results, setResults] = useState<UploadResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [discarded, setDiscarded] = useState<ReadonlySet<number>>(new Set());
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const zone = useRef<HTMLDivElement>(null);

  const reload = useCallback(async (): Promise<void> => {
    try {
      setRows(await getJson<StatementRow[]>("/api/statements"));
    } catch (err) {
      setError(errorText(err));
    }
  }, []);

  const reading = rows?.some((r) => r.status === "reading") ?? false;

  useEffect(() => {
    const controller = new AbortController();
    getJson<StatementRow[]>("/api/statements", controller.signal).then(setRows, (err: unknown) => {
      if (!controller.signal.aborted) setError(errorText(err));
    });
    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!reading) return undefined;
    const timer = setInterval(() => {
      void reload();
    }, POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [reading, reload]);

  const upload = useCallback(
    async (files: File[]): Promise<void> => {
      if (files.length === 0) return;
      const form = new FormData();
      for (const file of files) form.append("files", file);
      setBusy(true);
      try {
        setResults(await postForm<UploadResult[]>("/api/statements", form));
        setError(null);
      } catch (err) {
        setError(errorText(err));
      }
      setBusy(false);
      await reload();
    },
    [reload],
  );

  useEffect(() => {
    const target = zone.current;
    if (!target) return undefined;
    const over = (e: Event): void => {
      e.preventDefault();
      setDragging(true);
    };
    const leave = (): void => {
      setDragging(false);
    };
    const drop = (e: Event): void => {
      e.preventDefault();
      setDragging(false);
      void upload(Array.from((e as globalThis.DragEvent).dataTransfer?.files ?? []));
    };
    target.addEventListener("dragover", over);
    target.addEventListener("dragleave", leave);
    target.addEventListener("drop", drop);
    return () => {
      target.removeEventListener("dragover", over);
      target.removeEventListener("dragleave", leave);
      target.removeEventListener("drop", drop);
    };
  }, [upload]);

  async function extractAll(ids: number[]): Promise<void> {
    setBusy(true);
    const messages: string[] = [];
    for (const id of ids) {
      try {
        await postJson(`/api/statements/${String(id)}/extract`);
      } catch (err) {
        messages.push(errorText(err));
      }
    }
    setError(messages[0] ?? null);
    setBusy(false);
    await reload();
  }

  async function accept(id: number, document: ExtractedDocument): Promise<void> {
    setBusy(true);
    try {
      await postJson(`/api/statements/${String(id)}/accept`, document);
      setError(null);
    } catch (err) {
      setError(errorText(err));
    }
    setBusy(false);
    await reload();
  }

  const uploaded = (rows ?? []).filter((r) => r.status === "uploaded");
  const reviews = (rows ?? []).filter(
    (r) => r.status === "pending_review" && r.extracted !== null && !discarded.has(r.id),
  );

  return (
    <>
      <h2>Statements</h2>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <section className="card wide" aria-label="Upload">
        <div
          className={dragging ? "dropzone dragging" : "dropzone"}
          aria-label="Drop PDF statements here"
          role="group"
          ref={zone}
        >
          <p>Drop PDF statements here</p>
          <button
            type="button"
            className="primary"
            disabled={busy}
            onClick={() => {
              input.current?.click();
            }}
          >
            Choose files
          </button>
          <input
            ref={input}
            type="file"
            multiple
            accept="application/pdf"
            aria-label="Choose files"
            hidden
            onChange={(e) => {
              void upload(Array.from(e.target.files ?? []));
              e.target.value = "";
            }}
          />
        </div>
        {results.length > 0 && (
          <ul aria-label="Upload results" className="results">
            {results.map((r, i) => (
              <li key={`${String(i)}-${r.filename}`} className={r.error ? "error" : undefined}>
                {`${r.filename}: ${r.error ?? "Saved"}`}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="card wide" aria-label="Statement list">
        <h3>Your statements</h3>
        <StatementTable rows={rows} />
        <div className="actions">
          <button
            type="button"
            className="primary"
            disabled={busy || uploaded.length === 0}
            onClick={() => {
              void extractAll(uploaded.map((r) => r.id));
            }}
          >
            Extract all
          </button>
        </div>
      </section>
      {reviews.map((r) =>
        r.extracted === null ? null : (
          <StatementReview
            key={r.id}
            id={r.id}
            filename={r.filename}
            document={r.extracted}
            busy={busy}
            onAccept={(doc) => {
              void accept(r.id, doc);
            }}
            onDiscard={() => {
              setDiscarded(new Set([...discarded, r.id]));
            }}
          />
        ),
      )}
    </>
  );
}
