// @vitest-environment happy-dom
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, createElement as h } from "react";
import { createRoot, type Root } from "react-dom/client";
import { LiveMatches } from "./LiveMatches";
import type { ApiResponse, LiveMatch } from "@/types/vlr";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const match: LiveMatch = {
  id: "1", team1: "Alpha", team2: "Bravo", score1: 3, score2: 2,
  series: null, event: "Masters", url: null,
};
const good = (score = 3): ApiResponse<LiveMatch> => ({ data: [{ ...match, score1: score }], stale: false });
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
let root: Root;
let container: HTMLDivElement;

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Unexpected fetch"));
  container = document.createElement("div");
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  vi.restoreAllMocks();
  vi.useRealTimers();
});
async function mount(initial = good()) {
  await act(async () => root.render(h(LiveMatches, { initial })));
}
async function advance(ms: number) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}

it.each([
  ["HTTP error", () => Promise.resolve(json(good(9), 503))],
  ["network error", () => Promise.reject(new Error("offline"))],
  ["error envelope", () => Promise.resolve(json({ data: [], stale: true, error: "offline" }))],
  ["error despite stale false", () => Promise.resolve(json({ ...good(9), error: "offline" }))],
  ["malformed JSON", () => Promise.resolve(new Response("not json"))],
  ["invalid envelope", () => Promise.resolve(json({ data: {} }))],
  ["invalid row", () => Promise.resolve(json({ data: [{}], stale: false }))],
  ["invalid score", () => Promise.resolve(json({ data: [{ ...match, score1: "9" }], stale: false }))],
])("keeps latest successful scores after %s and recovers", async (_, failure) => {
  const fetch = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json(good(5)))
    .mockImplementationOnce(failure)
    .mockResolvedValueOnce(json(good(7)));
  await mount();
  await advance(30_000);
  expect(container.innerHTML).toContain('aria-label="Score 5 to 2"');
  await advance(30_000);
  expect(container.innerHTML).toContain('aria-label="Score 5 to 2"');
  expect(container.querySelector('[role="status"]')?.textContent).toContain("last successful scores");
  await advance(30_000);
  expect(container.innerHTML).toContain('aria-label="Score 7 to 2"');
  expect(container.querySelector('[role="status"]')).toBeNull();
  expect(fetch).toHaveBeenCalledTimes(3);
});

it("clears old scores only for a genuine successful empty list", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ data: [], stale: false }));
  await mount();
  await advance(30_000);
  expect(container.textContent).toContain("No live matches right now.");
  expect(container.textContent).not.toContain("Alpha");
  expect(container.querySelector('[role="status"]')).toBeNull();
});

it("does not claim no live matches when initial data is unavailable", async () => {
  await mount({ data: [], stale: true, error: "offline" });
  expect(container.textContent).toContain("unavailable");
  expect(container.textContent).not.toContain("No live matches right now.");
});

it("aborts a timed-out poll, retains scores, then retries", async () => {
  let signal: AbortSignal | undefined;
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementationOnce((_url, options) => {
    signal = options?.signal as AbortSignal;
    return new Promise((_resolve, reject) => signal!.addEventListener("abort", () => reject(new Error("aborted"))));
  }).mockResolvedValueOnce(json(good(8)));
  await mount();
  await advance(30_000);
  await advance(15_000);
  expect(signal?.aborted).toBe(true);
  expect(container.innerHTML).toContain('aria-label="Score 3 to 2"');
  expect(container.querySelector('[role="status"]')).not.toBeNull();
  await advance(30_000);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(container.innerHTML).toContain('aria-label="Score 8 to 2"');
});

it("never overlaps a delayed poll or applies its result after the deadline", async () => {
  let resolve!: (value: Response) => void;
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementationOnce(() => new Promise(r => { resolve = r; }))
    .mockResolvedValueOnce(json(good(8)));
  await mount();
  await advance(30_000);
  await advance(90_000); // deliberately non-cooperative transport ignores abort
  expect(fetch).toHaveBeenCalledTimes(1);
  await act(async () => { resolve(json(good(99))); });
  expect(container.innerHTML).toContain('aria-label="Score 3 to 2"');
  await advance(29_999);
  expect(fetch).toHaveBeenCalledTimes(1);
  await advance(1);
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("aborts and clears timers on unmount without rescheduling a delayed response", async () => {
  let resolve!: (value: Response) => void;
  let signal: AbortSignal | undefined;
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation((_url, options) => {
    signal = options?.signal as AbortSignal;
    return new Promise(r => { resolve = r; });
  });
  await mount();
  await advance(30_000);
  await act(async () => root.unmount());
  expect(signal?.aborted).toBe(true);
  await act(async () => resolve(json(good(99))));
  await advance(120_000);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});

it("switches live → confirmed empty → live without replacing the poller", async () => {
  const fetcher = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ data: [], stale: false }))
    .mockResolvedValueOnce(json(good(7)));
  await act(async () => root.render(h(LiveMatches, {
    initial: good(), confirmedEmptyFallback: h("div", null, "Next scheduled match"),
  })));
  expect(container.textContent).toContain("Alpha");
  expect(container.textContent).not.toContain("Next scheduled match");
  await advance(30_000);
  expect(container.textContent).toContain("No live matches right now.");
  expect(container.textContent).toContain("Next scheduled match");
  expect(container.textContent).not.toContain("Alpha");
  await advance(30_000);
  expect(container.innerHTML).toContain('aria-label="Score 7 to 2"');
  expect(container.textContent).not.toContain("Next scheduled match");
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("does not feature an upcoming match until an unavailable live source confirms empty", async () => {
  vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(json({ data: [], stale: true, error: "offline" }))
    .mockResolvedValueOnce(json({ data: [], stale: false }))
    .mockResolvedValueOnce(json({}, 503));
  await act(async () => root.render(h(LiveMatches, {
    initial: { data: [], stale: true, error: "offline" },
    confirmedEmptyFallback: h("div", null, "Next scheduled match"),
  })));
  expect(container.textContent).not.toContain("Next scheduled match");
  await advance(30_000);
  expect(container.textContent).toContain("unavailable");
  expect(container.textContent).not.toContain("Next scheduled match");
  await advance(30_000);
  expect(container.textContent).toContain("Next scheduled match");
  await advance(30_000);
  expect(container.textContent).not.toContain("Next scheduled match");
  expect(container.textContent).not.toContain("No live matches right now.");
  expect(container.textContent).toContain("unavailable");
});
