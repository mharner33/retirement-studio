import { useCallback, useEffect, useState } from "react";
import { ApiError, deleteRequest, getJson, postJson } from "../api";
import { ChangeCard } from "../components/ChangeCard";
import type { ChangeCard as Card, ChatMessage, ChatState, Source } from "../types";

const POLL_MS = 2000;

function SourceList({ sources }: Readonly<{ sources: Source[] }>) {
  return (
    <p className="chat-sources secondary">
      Sources:{" "}
      {sources.map((s, i) => (
        <span key={`${s.label}-${String(i)}`}>
          {i > 0 && ", "}
          {s.kind === "web" && s.url ? (
            <a href={s.url} target="_blank" rel="noreferrer">
              {s.label}
            </a>
          ) : (
            s.label
          )}
        </span>
      ))}
    </p>
  );
}

function Message({
  message,
  onCard,
}: Readonly<{ message: ChatMessage; onCard: (card: Card) => void }>) {
  const mine = message.role === "user";
  return (
    <article className={mine ? "chat-message mine" : "chat-message"}>
      <h3>{mine ? "You" : "Studio"}</h3>
      <p className="chat-text">{message.text}</p>
      {message.sources.length > 0 && <SourceList sources={message.sources} />}
      {message.unchecked && <p className="secondary">Some figures could not be checked.</p>}
      {message.changes.map((card) => (
        <ChangeCard key={card.id} card={card} onChange={onCard} />
      ))}
    </article>
  );
}

export function ChatPage() {
  const [chat, setChat] = useState<ChatState | null>(null);
  const [noProfile, setNoProfile] = useState(false);
  const [failed, setFailed] = useState(false);
  const [actionError, setActionError] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async (signal?: AbortSignal): Promise<void> => {
    try {
      setChat(await getJson<ChatState>("/api/chat", signal));
      setFailed(false);
    } catch {
      if (!signal?.aborted) setFailed(true);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getJson("/api/profile", controller.signal).then(
      () => reload(controller.signal),
      (err: unknown) => {
        if (err instanceof ApiError && err.status === 404) setNoProfile(true);
        else void reload(controller.signal);
      },
    );
    return () => {
      controller.abort();
    };
  }, [reload]);

  const working = chat?.status === "working";

  useEffect(() => {
    if (!working) return undefined;
    const timer = setInterval(() => {
      void reload();
    }, POLL_MS);
    return () => {
      clearInterval(timer);
    };
  }, [working, reload]);

  async function send(): Promise<void> {
    setBusy(true);
    setActionError(false);
    try {
      await postJson("/api/chat/messages", { text: draft.trim() });
      setDraft("");
    } catch (err) {
      if (err instanceof ApiError && err.detail === "No profile saved") setNoProfile(true);
      else if (!(err instanceof ApiError && err.status === 409)) setActionError(true);
    }
    await reload();
    setBusy(false);
  }

  async function restart(): Promise<void> {
    setBusy(true);
    setActionError(false);
    try {
      await deleteRequest("/api/chat");
    } catch {
      setActionError(true);
    }
    await reload();
    setBusy(false);
  }

  function replaceCard(card: Card): void {
    setChat((current) =>
      current === null
        ? current
        : {
            ...current,
            messages: current.messages.map((m) => ({
              ...m,
              changes: m.changes.map((c) => (c.id === card.id ? card : c)),
            })),
          },
    );
  }

  if (noProfile) {
    return (
      <section className="card">
        <h2>Chat</h2>
        <p className="secondary">Complete your profile first</p>
      </section>
    );
  }

  return (
    <>
      <h2>Chat</h2>
      {actionError && (
        <p className="error" role="alert">
          That did not go through. Try again in a moment.
        </p>
      )}
      {failed && (
        <p className="error" role="alert">
          The chat could not be reached. Try again in a moment.
        </p>
      )}
      <section className="card wide chat" aria-label="Conversation">
        {chat?.messages.map((m) => (
          <Message key={m.id} message={m} onCard={replaceCard} />
        ))}
        {working && (
          <p className="secondary" role="status">
            {chat.step ?? "Working on it"}
          </p>
        )}
        {chat?.status === "failed" && (
          <p className="error" role="alert">
            This reply did not finish. Ask again.
          </p>
        )}
      </section>
      <section className="card wide chat-compose" aria-label="Ask">
        <textarea
          rows={3}
          placeholder="Ask about your plan"
          aria-label="Ask about your plan"
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
          }}
        />
        <div className="actions">
          <button
            type="button"
            className="primary"
            disabled={busy || working || draft.trim() === ""}
            onClick={() => {
              void send();
            }}
          >
            Send
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={busy || working}
            onClick={() => {
              void restart();
            }}
          >
            New conversation
          </button>
        </div>
      </section>
    </>
  );
}
