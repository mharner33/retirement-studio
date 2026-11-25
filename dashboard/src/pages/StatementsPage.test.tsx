import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ExtractedDocument, StatementRow, UploadResult } from "../types";
import { StatementsPage } from "./StatementsPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const account: ExtractedDocument = {
  doc_type: "account",
  institution: "Example Bank",
  statement_date: "2026-10-31",
  accounts: [
    {
      kind: "taxable",
      owner_hint: "Alex",
      owner: "self",
      label: "Brokerage",
      balance: 1250,
      cost_basis: 900,
      last4: "1234",
    },
  ],
};

const social: ExtractedDocument = {
  doc_type: "social_security",
  statement_date: "2026-10-01",
  person: null,
  monthly_at_62: 2200,
  monthly_at_fra: 3100,
  fra_age: "67",
  monthly_at_70: 3900,
};

function row(id: number, status: StatementRow["status"], extracted: ExtractedDocument | null) {
  return { id, filename: `s${String(id)}.pdf`, status, extracted, created_at: "2026-11-24" };
}

interface Server {
  rows: StatementRow[];
  uploads: FormData[];
  results: UploadResult[];
  posts: { path: string; body: unknown }[];
}

function serve(server: Server): void {
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (method === "GET") return Promise.resolve(new Response(JSON.stringify(server.rows)));
      if (init?.body instanceof FormData) {
        server.uploads.push(init.body);
        return Promise.resolve(new Response(JSON.stringify(server.results)));
      }
      server.posts.push({
        path,
        body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      return Promise.resolve(new Response("{}", { status: path.endsWith("/extract") ? 202 : 200 }));
    }),
  );
}

function pdf(name: string): File {
  return new File(["%PDF-1.4"], name, { type: "application/pdf" });
}

function newServer(rows: StatementRow[] = [], results: UploadResult[] = []): Server {
  const server = { rows, uploads: [], results, posts: [] };
  serve(server);
  return server;
}

describe("StatementsPage", () => {
  it("sends one multipart request for three dropped files and lists three results", async () => {
    const server = newServer(
      [],
      ["a.pdf", "b.pdf", "c.pdf"].map((filename, i) => ({ filename, id: i + 1, error: null })),
    );
    render(<StatementsPage />);
    const zone = await screen.findByLabelText("Drop PDF statements here");
    fireEvent.drop(zone, {
      dataTransfer: { files: [pdf("a.pdf"), pdf("b.pdf"), pdf("c.pdf")] },
    });
    const results = await screen.findByRole("list", { name: "Upload results" });
    await waitFor(() => {
      expect(within(results).getAllByRole("listitem")).toHaveLength(3);
    });
    expect(server.uploads).toHaveLength(1);
    expect(server.uploads[0]?.getAll("files")).toHaveLength(3);
    expect(results.textContent).toContain("a.pdf: Saved");
  });

  it("uploads from the file input and shows a rejected file's error", async () => {
    newServer(
      [],
      [
        { filename: "a.pdf", id: 1, error: null },
        { filename: "b.pdf", id: null, error: "Already uploaded" },
      ],
    );
    render(<StatementsPage />);
    const input = await screen.findByLabelText("Choose files");
    expect(input.getAttribute("accept")).toBe("application/pdf");
    expect(input.hasAttribute("multiple")).toBe(true);
    fireEvent.change(input, { target: { files: [pdf("a.pdf"), pdf("b.pdf")] } });
    const results = await screen.findByRole("list", { name: "Upload results" });
    await waitFor(() => {
      expect(within(results).getAllByRole("listitem")).toHaveLength(2);
    });
    const items = within(results).getAllByRole("listitem");
    expect(items[0]?.textContent).toBe("a.pdf: Saved");
    expect(items[1]?.textContent).toBe("b.pdf: Already uploaded");
  });

  it("shows status labels, including No text found", async () => {
    newServer([
      row(1, "uploaded", null),
      row(2, "reading", null),
      row(3, "no_text", null),
      row(4, "accepted", account),
    ]);
    render(<StatementsPage />);
    const list = await screen.findByRole("table", { name: "Statements" });
    expect(within(list).getByText("Uploaded")).toBeTruthy();
    expect(within(list).getByText("Reading")).toBeTruthy();
    expect(within(list).getByText("No text found")).toBeTruthy();
    expect(within(list).getByText("Accepted")).toBeTruthy();
  });

  it("starts extraction for every uploaded file", async () => {
    const server = newServer([
      row(1, "uploaded", null),
      row(2, "no_text", null),
      row(3, "uploaded", null),
    ]);
    render(<StatementsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Extract all" }));
    await waitFor(() => {
      expect(server.posts.map((p) => p.path)).toEqual([
        "/api/statements/1/extract",
        "/api/statements/3/extract",
      ]);
    });
  });

  it("sends the edited balance when an account statement is accepted", async () => {
    const server = newServer([row(1, "pending_review", account)]);
    render(<StatementsPage />);
    expect(await screen.findByText("Nothing is saved until you accept.")).toBeTruthy();
    const balance = screen.getByLabelText("Balance, account 1");
    expect((balance as HTMLInputElement).value).toBe("$1,250.00");
    fireEvent.focus(balance);
    fireEvent.change(balance, { target: { value: "2,000.5" } });
    fireEvent.change(screen.getByLabelText("Type, account 1"), { target: { value: "roth" } });
    fireEvent.change(screen.getByLabelText("Owner, account 1"), { target: { value: "spouse" } });
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => {
      expect(server.posts).toHaveLength(1);
    });
    const sent = server.posts[0];
    expect(sent?.path).toBe("/api/statements/1/accept");
    const body = sent?.body as Extract<ExtractedDocument, { doc_type: "account" }>;
    expect(body.accounts[0]).toMatchObject({ balance: 2000.5, kind: "roth", owner: "spouse" });
  });

  it("blocks Accept on a Social Security statement until a person is chosen", async () => {
    const server = newServer([row(2, "pending_review", social)]);
    render(<StatementsPage />);
    const accept = await screen.findByRole("button", { name: "Accept" });
    expect((accept as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Whose statement is this?")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Spouse"));
    fireEvent.focus(screen.getByLabelText("Monthly at 62"));
    fireEvent.change(screen.getByLabelText("Monthly at 62"), { target: { value: "1500" } });
    expect((accept as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(accept);
    await waitFor(() => {
      expect(server.posts).toHaveLength(1);
    });
    expect(server.posts[0]?.body).toMatchObject({ person: "spouse", monthly_at_62: 1500 });
  });

  it("hides the review on Discard without calling the backend", async () => {
    const server = newServer([row(1, "pending_review", account)]);
    render(<StatementsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Discard" }));
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
    expect(server.posts).toHaveLength(0);
  });

  it("shows the backend message when Accept fails", async () => {
    newServer([row(1, "pending_review", account)]);
    vi.stubGlobal(
      "fetch",
      vi.fn((_path: string, init?: RequestInit) =>
        Promise.resolve(
          (init?.method ?? "GET") === "GET"
            ? new Response(JSON.stringify([row(1, "pending_review", account)]))
            : new Response(JSON.stringify({ detail: "Complete your profile first" }), {
                status: 409,
              }),
        ),
      ),
    );
    render(<StatementsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Accept" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Complete your profile first");
  });
});
