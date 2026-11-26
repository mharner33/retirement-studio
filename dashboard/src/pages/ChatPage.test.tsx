import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatMessage, ChatState } from "../types";
import { ChatPage } from "./ChatPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const reply: ChatMessage = {
  id: 2,
  role: "assistant",
  text: "Retiring at 65 adds $12,000.00 a year.",
  sources: [
    { kind: "engine", label: "Plan run", url: null },
    { kind: "web", label: "Medicare costs", url: "https://www.medicare.gov/costs" },
  ],
  unchecked: false,
  changes: [
    {
      id: 9,
      reason: "Work two more years",
      status: "proposed",
      error: null,
      lines: [{ label: "Wages (you)", kind: "money", old: 60000, new: 70000 }],
    },
  ],
};

const ask: ChatMessage = {
  id: 1,
  role: "user",
  text: "Can Alex retire at 65",
  sources: [],
  unchecked: false,
  changes: [],
};

interface Server {
  state: ChatState;
  profile: number;
  posts: { path: string; method: string; body: unknown }[];
  onPost?: (server: Server) => void;
}

function serve(server: Server): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (path === "/api/profile") {
        return Promise.resolve(new Response("{}", { status: server.profile }));
      }
      if (method === "GET") return Promise.resolve(new Response(JSON.stringify(server.state)));
      server.posts.push({
        path,
        method,
        body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      server.onPost?.(server);
      return Promise.resolve(
        method === "DELETE"
          ? new Response(null, { status: 204 })
          : new Response("{}", { status: 202 }),
      );
    }),
  );
}

function newServer(state: ChatState, profile = 200): Server {
  const server: Server = { state, profile, posts: [] };
  serve(server);
  return server;
}

function button(name: string): HTMLButtonElement {
  const el = screen.getByRole("button", { name });
  if (!(el instanceof HTMLButtonElement)) throw new Error("not a button");
  return el;
}

const idle = (messages: ChatMessage[]): ChatState => ({ status: "idle", step: null, messages });

beforeEach(() => {
  vi.useRealTimers();
});

describe("ChatPage", () => {
  it("renders the conversation with sources and a change card", async () => {
    newServer(idle([ask, reply]));
    render(<ChatPage />);
    expect(await screen.findByText("Retiring at 65 adds $12,000.00 a year.")).toBeTruthy();
    expect(screen.getByText("Can Alex retire at 65")).toBeTruthy();
    expect(screen.getByText("Studio")).toBeTruthy();
    expect(screen.getByText("Plan run")).toBeTruthy();
    const link = screen.getByRole("link", { name: "Medicare costs" });
    expect(link.getAttribute("href")).toBe("https://www.medicare.gov/costs");
    expect(screen.getByText("$70,000.00")).toBeTruthy();
    expect(screen.queryByText("Some figures could not be checked.")).toBeNull();
  });

  it("shows the unchecked note only when unchecked", async () => {
    newServer(idle([{ ...reply, unchecked: true }]));
    render(<ChatPage />);
    expect(await screen.findByText("Some figures could not be checked.")).toBeTruthy();
  });

  it("sends, clears the box, shows the step and polls until idle", async () => {
    const server = newServer(idle([]));
    render(<ChatPage />);
    const box = await screen.findByPlaceholderText("Ask about your plan");
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    server.onPost = (s) => {
      s.state = { status: "working", step: "Running the plan", messages: [ask] };
    };
    fireEvent.change(box, { target: { value: "Can Alex retire at 65" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Send" }));
      await Promise.resolve();
    });
    await vi.waitFor(() => {
      expect(screen.getByText("Running the plan")).toBeTruthy();
    });
    expect(server.posts[0]).toEqual({
      path: "/api/chat/messages",
      method: "POST",
      body: { text: "Can Alex retire at 65" },
    });
    expect(box instanceof HTMLTextAreaElement ? box.value : null).toBe("");
    expect(button("Send").disabled).toBe(true);

    server.state = idle([ask, reply]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    await vi.waitFor(() => {
      expect(screen.getByText("Retiring at 65 adds $12,000.00 a year.")).toBeTruthy();
    });
    expect(screen.queryByText("Running the plan")).toBeNull();
  });

  it("disables Send while working and says Working on it without a step", async () => {
    newServer({ status: "working", step: null, messages: [ask] });
    render(<ChatPage />);
    expect(await screen.findByText("Working on it")).toBeTruthy();
    const box = screen.getByPlaceholderText("Ask about your plan");
    fireEvent.change(box, { target: { value: "More" } });
    expect(button("Send").disabled).toBe(true);
    expect(button("New conversation").disabled).toBe(true);
  });

  it("keeps Send disabled for a blank box", async () => {
    newServer(idle([]));
    render(<ChatPage />);
    await screen.findByPlaceholderText("Ask about your plan");
    expect(button("Send").disabled).toBe(true);
  });

  it("shows the failed message", async () => {
    newServer({ status: "failed", step: null, messages: [ask] });
    render(<ChatPage />);
    expect(await screen.findByText("This reply did not finish. Ask again.")).toBeTruthy();
  });

  it("New conversation calls DELETE /api/chat and empties the page", async () => {
    const server = newServer(idle([ask, reply]));
    render(<ChatPage />);
    await screen.findByText("Studio");
    server.onPost = (s) => {
      s.state = idle([]);
    };
    fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
    await vi.waitFor(() => {
      expect(screen.queryByText("Studio")).toBeNull();
    });
    expect(server.posts).toEqual([{ path: "/api/chat", method: "DELETE", body: undefined }]);
  });

  it("asks for a profile when none is saved", async () => {
    newServer(idle([]), 404);
    render(<ChatPage />);
    expect(await screen.findByText("Complete your profile first")).toBeTruthy();
  });

  it("asks for a profile when Send gets a 409", async () => {
    const server = newServer(idle([]));
    render(<ChatPage />);
    const box = await screen.findByPlaceholderText("Ask about your plan");
    vi.stubGlobal(
      "fetch",
      vi.fn((_path: string, init?: RequestInit) =>
        Promise.resolve(
          init?.method === "POST"
            ? new Response(JSON.stringify({ detail: "No profile saved" }), { status: 409 })
            : new Response(JSON.stringify(server.state)),
        ),
      ),
    );
    fireEvent.change(box, { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Complete your profile first")).toBeTruthy();
  });

  it("keeps the error visible when Send fails and the reload succeeds", async () => {
    const server = newServer(idle([]));
    render(<ChatPage />);
    const box = await screen.findByPlaceholderText("Ask about your plan");
    vi.stubGlobal(
      "fetch",
      vi.fn((_path: string, init?: RequestInit) =>
        Promise.resolve(
          init?.method === "POST"
            ? new Response("{}", { status: 500 })
            : new Response(JSON.stringify(server.state)),
        ),
      ),
    );
    fireEvent.change(box, { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect((await screen.findByRole("alert")).textContent).toBe(
      "That did not go through. Try again in a moment.",
    );
    await vi.waitFor(() => {
      expect(button("Send").disabled).toBe(false);
    });
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});
