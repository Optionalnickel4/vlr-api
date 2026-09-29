// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, createElement as h } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";
import { StatTicker } from "./StatTicker";
import type { ApiResponse, MatchWireItem } from "@/types/vlr";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const LIVE: MatchWireItem = {
  id: "live:753445", kind: "live", href: "/match/753445", status: "LIVE",
  event: "Champions", context: "Abyss · Round 8", time: null, winnerId: null,
  teams: [
    { id: "13576", name: "JD Gaming", shortName: "JDG", logo: "https://cdn/jdg.png", score: 0 },
    { id: "1184", name: "FUT Esports", shortName: "FUT", logo: "https://cdn/fut.png", score: 1 },
  ],
};

function json(body: unknown): Response {
  return Response.json(body);
}

async function mountIsland() {
  const element = h(StatTicker);
  const ssrHtml = renderToString(element);
  const container = document.createElement("div");
  container.innerHTML = ssrHtml;
  const seen: string[] = [];
  const spy = vi.spyOn(console, "error").mockImplementation((...args) => seen.push(args.map(String).join(" ")));
  const root = hydrateRoot(container, element, { onRecoverableError: error => seen.push(String(error)) });
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  spy.mockRestore();
  return { container, root, ssrHtml, hydrationErrors: seen.filter(message => /hydrat|did not match|server rendered/i.test(message)) };
}

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

describe("Match Wire island", () => {
  it("hydrates from an identical empty first render", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ data: [], stale: false } satisfies ApiResponse<MatchWireItem>));
    const { root, ssrHtml, hydrationErrors } = await mountIsland();
    expect(ssrHtml).toBe("");
    expect(hydrationErrors).toEqual([]);
    await act(async () => root.unmount());
  });

  it("renders the server-curated live item after mount", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ data: [LIVE], stale: false } satisfies ApiResponse<MatchWireItem>));
    const { container, root } = await mountIsland();
    expect(container.textContent).toContain("MATCH WIRE");
    expect(container.textContent).toContain("JD Gaming");
    expect(container.querySelector('a[href="/match/753445"]')).toBeTruthy();
    await act(async () => root.unmount());
  });

  it("retains last-good scores and marks the wire stale after a failed refresh", async () => {
    vi.useFakeTimers();
    let fail = false;
    vi.spyOn(globalThis, "fetch").mockImplementation(async () => fail
      ? json({ data: [], stale: true, error: "offline" })
      : json({ data: [LIVE], stale: false }));
    const element = h(StatTicker);
    const container = document.createElement("div");
    const root = hydrateRoot(container, element);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(container.textContent).toContain("JD Gaming");
    fail = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(container.textContent).toContain("JD Gaming");
    expect(container.textContent).toContain("STALE");
    await act(async () => root.unmount());
  });
});
