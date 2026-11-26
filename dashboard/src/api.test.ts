import { afterEach, describe, expect, it, vi } from "vitest";
import { getJson, postJson, putJson } from "./api";

afterEach(() => vi.unstubAllGlobals());

function stub(status: number, body: unknown) {
  const fn = vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status })));
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("api", () => {
  it("gets json", async () => {
    stub(200, { a: 1 });
    expect(await getJson<{ a: number }>("/api/x")).toEqual({ a: 1 });
  });

  it("puts json with a body", async () => {
    const fn = stub(200, { ok: true });
    await putJson("/api/x", { b: 2 });
    expect(fn).toHaveBeenCalledWith("/api/x", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: '{"b":2}',
    });
  });

  it("posts without a body", async () => {
    const fn = stub(200, {});
    await postJson("/api/x");
    expect(fn).toHaveBeenCalledWith("/api/x", { method: "POST", headers: {}, body: undefined });
  });

  it("throws on an error status", async () => {
    stub(500, {});
    await expect(getJson("/api/x")).rejects.toThrow("500");
  });
});

describe("api errors", () => {
  it("exposes the status and the detail of an error response", async () => {
    stub(422, { detail: [{ loc: ["body", "x"], msg: "bad" }] });
    await expect(putJson("/api/x", {})).rejects.toMatchObject({
      status: 422,
      detail: [{ loc: ["body", "x"], msg: "bad" }],
    });
  });

  it("has no detail when the body is not json", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response("oops", { status: 502 }))),
    );
    await expect(getJson("/api/x")).rejects.toMatchObject({ status: 502, detail: undefined });
  });
});
