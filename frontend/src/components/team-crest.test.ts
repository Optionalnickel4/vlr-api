// @vitest-environment happy-dom
import { act, createElement as h } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { TeamCrest } from "./TeamCrest";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | undefined;
let host: HTMLDivElement | undefined;

afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  host?.remove();
  root = undefined;
  host = undefined;
  vi.useRealTimers();
});

async function render(props: Parameters<typeof TeamCrest>[0]) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root!.render(h(TeamCrest, props)));
  return host;
}

it("renders a real source logo in a fixed, contained box", async () => {
  const node = await render({ name: "JD Gaming", logo: "https://cdn/jdg.png", size: "ticker" });
  const image = node.querySelector("img")!;
  expect(image.getAttribute("src")).toContain("https://cdn/jdg.png");
  expect(image.getAttribute("alt")).toBe("");
  expect(node.querySelector('[data-team-logo="true"]')?.getAttribute("style")).toContain("24px");
});

it("uses stable initials when no usable logo exists", async () => {
  const node = await render({ name: "FUT Esports", logo: null, size: "row" });
  expect(node.querySelector("img")).toBeNull();
  expect(node.querySelector('[data-team-fallback="true"]')?.textContent).toBe("FE");
});

it("falls back after an image load failure", async () => {
  const node = await render({ name: "LOUD", logo: "https://cdn/broken.png", size: "card" });
  await act(async () => node.querySelector("img")!.dispatchEvent(new Event("error")));
  expect(node.querySelector("img")).toBeNull();
  expect(node.querySelector('[data-team-fallback="true"]')?.textContent).toBe("LOU");
});

it("can expose one informative accessible label when no adjacent name exists", async () => {
  const node = await render({ name: "Sentinels", logo: null, labelMode: "informative" });
  expect(node.querySelector('[aria-label="Sentinels team identity"]')).toBeTruthy();
});

it("retries transient failures twice with a cache-busting URL then stops", async () => {
  vi.useFakeTimers();
  const node = await render({ name: "LOUD", logo: "https://cdn/logo.png?version=1#crest" });
  await act(async () => node.querySelector("img")!.dispatchEvent(new Event("error")));
  expect(node.querySelector("img")).toBeNull();
  await act(async () => vi.advanceTimersByTime(1000));
  expect(node.querySelector("img")!.src).toContain("version=1&_vlr_retry=1#crest");
  await act(async () => node.querySelector("img")!.dispatchEvent(new Event("error")));
  await act(async () => vi.advanceTimersByTime(3000));
  expect(node.querySelector("img")!.src).toContain("_vlr_retry=2");
  await act(async () => node.querySelector("img")!.dispatchEvent(new Event("error")));
  await act(async () => vi.advanceTimersByTime(60000));
  expect(node.querySelector("img")).toBeNull();
  expect(vi.getTimerCount()).toBe(0);
});

it("cancels a failed source retry when the team logo changes", async () => {
  vi.useFakeTimers();
  const node = await render({ name: "Old", logo: "https://cdn/old.png" });
  await act(async () => node.querySelector("img")!.dispatchEvent(new Event("error")));
  await act(async () => root!.render(h(TeamCrest, { name: "New", logo: "https://cdn/new.png" })));
  expect(node.querySelector("img")!.src).toBe("https://cdn/new.png");
  await act(async () => vi.advanceTimersByTime(10000));
  expect(node.querySelector("img")!.src).toBe("https://cdn/new.png");
});
