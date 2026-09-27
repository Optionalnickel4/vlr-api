import { afterEach, expect, it, vi } from "vitest";
import { fetchUpstream, getLive, getRankings } from "./vlr";

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

it.each(["headers", "body"])("bounds upstream %s waits and preserves the failure envelope", async phase => {
  vi.useFakeTimers();
  let signal: AbortSignal | undefined;
  vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
    signal = options?.signal as AbortSignal;
    const pending = () => new Promise<never>((_resolve, reject) => {
      signal!.addEventListener("abort", () => reject(new Error("aborted")));
    });
    if (phase === "headers") return pending();
    const response = new Response("[]");
    vi.spyOn(response, "json").mockImplementation(pending);
    return Promise.resolve(response);
  });
  const result = getLive();
  await vi.advanceTimersByTimeAsync(10_000);
  expect(signal?.aborted).toBe(true);
  expect(await result).toMatchObject({ data: [], stale: true, error: expect.stringContaining("timed out") });
  expect(vi.getTimerCount()).toBe(0);
});

it("clears the deadline after success", async () => {
  vi.useFakeTimers();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]"));
  expect(await fetchUpstream("/matches/live")).toEqual([]);
  expect(vi.getTimerCount()).toBe(0);
});

it.each([null, {}, { data: [], stale: true, error: "offline" }, [null], [{}]])(
  "rejects malformed upstream live data rather than reporting no matches: %j", async body => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(body)));
    expect(await getLive()).toMatchObject({ data: [], stale: true, error: expect.any(String) });
  },
);

it("accepts a genuine empty upstream live list", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("[]"));
  expect(await getLive()).toEqual({ data: [], stale: false });
});

it("preserves partial live cards whose team/score arrays are not filled yet", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([{ id: "1", teams: [], scores: [] }])));
  expect(await getLive()).toMatchObject({ data: [{ id: "1", team1: null, score1: null }], stale: false });
});

it.each(["fresh", "stale"])("propagates the %s cache header without changing the raw payload contract", async state => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response("[]", { headers: { "X-VLR-Cache": state } }));
  expect(await getRankings("europe")).toEqual({ data: [], stale: state === "stale" });
  expect(await fetchUpstream("/events")).toEqual([]);
});
