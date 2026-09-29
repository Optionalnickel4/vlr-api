// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from "vitest";
import { act, createElement as h } from "react";
import { createRoot, type Root } from "react-dom/client";
import { LiveMatches } from "./LiveMatches";
import { StatTicker } from "./StatTicker";
import { TickerTape } from "./TickerTape";
import { TeamCrest } from "./TeamCrest";
import { BroadcastMatch } from "./BroadcastMatch";
import type { LiveMatch, MatchWireItem } from "@/types/vlr";
(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: Root;
let container: HTMLDivElement;
async function mount(element: React.ReactNode) {
  container = document.createElement("div"); document.body.append(container); root = createRoot(container);
  await act(async () => { root.render(element); });
}
const item: MatchWireItem = { id: "upcoming:42", kind: "upcoming", href: "/match/42", status: "UPCOMING", event: "Test event", context: "Group", time: "7:00 PM", winnerId: null, teams: [
  { id: "1", name: "Alpha", shortName: "ALP", logo: "https://cdn/alpha.png", score: null },
  { id: "2", name: "Beta", shortName: "BET", logo: "https://cdn/beta.png", score: null },
] };
const json = (data: unknown) => new Response(JSON.stringify({ data, stale: false }));
afterEach(async () => {
  if (root) await act(async () => root.unmount());
  container?.remove();
  vi.restoreAllMocks(); vi.useRealTimers();
});
it("does not overlap ticker cycles and cancels the deadline and request on unmount", async () => {
  vi.useFakeTimers();
  let resolve!: (response: Response) => void;
  const fetcher = vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise(r => { resolve = r; }));
  await mount(h(StatTicker));
  const signal = fetcher.mock.calls[0][1]?.signal;
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  expect(fetcher).toHaveBeenCalledTimes(1); expect(signal?.aborted).toBe(true);
  await act(async () => root.unmount());
  expect(vi.getTimerCount()).toBe(0);
  await act(async () => { resolve(json([item])); });
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});
it("keeps the last successful tape after a failed static refresh", async () => {
  vi.useFakeTimers(); let failed = false;
  vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
    if (failed) throw new Error("offline");
    return json(String(input).includes("ticker") ? [item] : []);
  });
  await mount(h(StatTicker)); expect(container.textContent).toContain("Alpha");
  failed = true;
  await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
  expect(container.textContent).toContain("Alpha");
});
it("offers a pause control and hides the duplicate tape from assistive technology", async () => {
  await mount(h(TickerTape, { items: [item] }));
  const button = container.querySelector("button")!;
  expect(button.getAttribute("aria-pressed")).toBe("false");
  await act(async () => button.click());
  expect(button.getAttribute("aria-pressed")).toBe("true");
  expect(container.querySelector<HTMLElement>(".vlr-ticker-track")!.style.animationPlayState).toBe("paused");
  expect(container.querySelector(".ticker-duplicate")?.getAttribute("aria-hidden")).toBe("true");
  expect(container.querySelector('a[href="/match/42"]')?.getAttribute("aria-label")).toContain("Alpha versus Beta");
});
it("temporarily pauses for hover and keyboard focus, then resumes", async () => {
  await mount(h(TickerTape, { items: [item] }));
  const section = container.querySelector("section")!;
  const track = container.querySelector<HTMLElement>(".vlr-ticker-track")!;
  await act(async () => section.dispatchEvent(new Event("pointerover", { bubbles: true })));
  expect(track.style.animationPlayState).toBe("paused");
  await act(async () => section.dispatchEvent(new Event("pointerout", { bubbles: true })));
  expect(track.style.animationPlayState).toBe("running");
  const link = container.querySelector<HTMLAnchorElement>(".wire-entry")!;
  await act(async () => link.focus());
  expect(track.style.animationPlayState).toBe("paused");
  await act(async () => link.blur());
  expect(track.style.animationPlayState).toBe("running");
});
it("manual pause survives hover leave and reduced motion removes the looping copy", async () => {
  const original = window.matchMedia;
  window.matchMedia = vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  await mount(h(TickerTape, { items: [item] }));
  expect(container.querySelector("section")?.getAttribute("data-reduced-motion")).toBe("true");
  expect(container.querySelector(".ticker-duplicate")).toBeNull();
  const button = container.querySelector("button")!;
  await act(async () => button.click());
  await act(async () => container.querySelector("section")!.dispatchEvent(new Event("pointerout", { bubbles: true })));
  expect(container.querySelector<HTMLElement>(".vlr-ticker-track")!.style.animationPlayState).toBe("paused");
  window.matchMedia = original;
});
it("uses a provided crest and falls back to initials when the image fails", async () => {
  await mount(h(TeamCrest, { name: "Test Team", logo: "https://example.test/crest.png" }));
  const img = container.querySelector("img")!;
  expect(img.getAttribute("src")).toBe("https://example.test/crest.png");
  expect(img.getAttribute("alt")).toBe("");
  await act(async () => img.dispatchEvent(new Event("error")));
  expect(container.querySelector("img")).toBeNull(); expect(container.textContent).toBeTruthy();
  expect(container.querySelector("span")?.className).not.toContain("https:");
});
it("keeps actual live scores and the match action visible in the broadcast stale state", async () => {
  const match: LiveMatch = { id: "42", team1: "Alpha", team2: "Beta", score1: 3, score2: 2, event: "Test event", series: "Final", url: null };
  await mount(h(BroadcastMatch, { match, stale: true }));
  expect(container.querySelector('[aria-label="Score 3 to 2"]')).not.toBeNull();
  expect(container.querySelector('[role="status"]')?.textContent).toContain("last successful scores");
  expect(container.querySelector("a")?.getAttribute("href")).toBe("/match/42");
});

it("shows a prominent unavailable state without falsely featuring an upcoming match", async () => {
  await mount(h(LiveMatches, { broadcast: true, initial: { data: [], stale: true, error: "Unavailable" }, confirmedEmptyFallback: h("p", null, "Next fixture") }));
  expect(container.querySelector(".bc-feature-unavailable")).not.toBeNull();
  expect(container.textContent).toContain("Live updates unavailable");
  expect(container.textContent).not.toContain("Next fixture");
  expect(container.querySelector("a")?.getAttribute("href")).toBe("/schedule");
});
