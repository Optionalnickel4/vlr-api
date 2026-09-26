// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from "vitest";
import { act, createElement as h } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { SiteShell } from "./SiteShell";
import { PageContainer } from "./PageContainer";
import { Breadcrumbs } from "./Breadcrumbs";
import { DEBOUNCE_MS } from "./PlayerSearch";

const route = vi.hoisted(() => ({ pathname: "/" }));
vi.mock("next/navigation", () => ({ usePathname: () => route.pathname }));
// Do not fetch ticker data here. Its lifecycle has dedicated regression tests.
vi.mock("./StatTicker", () => ({ StatTicker: () => h("div", { "data-testid": "ticker" }) }));

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: Root | undefined;
let container: HTMLDivElement | undefined;
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  container?.remove();
  root = undefined;
  container = undefined;
  vi.restoreAllMocks();
  vi.useRealTimers();
  route.pathname = "/";
});

function shell() {
  return h(SiteShell, null, h(PageContainer, { title: "Test page", children: "Content" }));
}
function markup() {
  const element = document.createElement("div");
  element.innerHTML = renderToStaticMarkup(shell());
  return element;
}

it.each(["/", "/schedule", "/results", "/stats", "/rankings", "/news"])("marks only %s active and renders one shared search", (pathname) => {
  route.pathname = pathname;
  const element = markup();
  const nav = element.querySelector('nav[aria-label="Primary"]')!;
  expect(nav.querySelectorAll("a")).toHaveLength(6);
  expect(nav.querySelectorAll('[aria-current="page"]')).toHaveLength(1);
  expect(nav.querySelector('[aria-current="page"]')?.getAttribute("href")).toBe(pathname);
  expect(element.querySelectorAll('[role="combobox"]')).toHaveLength(1);
  expect(element.querySelectorAll("header")).toHaveLength(1);
  expect(element.querySelectorAll('[data-testid="ticker"]')).toHaveLength(1);
});

it.each(["/match/123", "/team/42", "/player/9", "/unknown"])("does not mark a false primary destination on %s", (pathname) => {
  route.pathname = pathname;
  expect(markup().querySelector('nav[aria-label="Primary"] [aria-current]')).toBeNull();
});

it("puts the skip link first and targets the single focusable main landmark", () => {
  const element = markup();
  expect(element.querySelector("a")?.getAttribute("href")).toBe("#main-content");
  expect(element.querySelectorAll("main")).toHaveLength(1);
  expect(element.querySelector("main")?.id).toBe("main-content");
  expect(element.querySelector("main")?.getAttribute("tabindex")).toBe("-1");
  expect(element.querySelectorAll("h1")).toHaveLength(1);
});

it.each([
  ["match", ["/"]], ["team", ["/", "/rankings"]], ["player", ["/", "/stats"]],
] as const)("renders %s breadcrumbs with a non-link current page", (kind, hrefs) => {
  const element = document.createElement("div");
  element.innerHTML = renderToStaticMarkup(h(Breadcrumbs, { kind, label: "Current identity" }));
  expect(Array.from(element.querySelectorAll("a"), a => a.getAttribute("href"))).toEqual(hrefs);
  expect(element.querySelector('[aria-current="page"]')?.textContent).toBe("Current identity");
  expect(element.querySelector('[aria-current="page"]')?.tagName).toBe("SPAN");
});

it.each(["debouncing", "in flight"])("resets search on navigation while %s without remounting the ticker", async (phase) => {
  vi.useFakeTimers();
  let resolve!: (r: Response) => void;
  const pending = new Promise<Response>(yes => { resolve = yes; });
  const fetcher = vi.spyOn(globalThis, "fetch").mockReturnValue(pending);
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  await act(async () => root!.render(shell()));
  const ticker = container.querySelector('[data-testid="ticker"]');
  const input = container.querySelector("input")!;
  await act(async () => {
    Object.defineProperty(input, "value", { writable: true, value: "TenZ" });
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  if (phase === "in flight") await act(async () => { await vi.advanceTimersByTimeAsync(DEBOUNCE_MS); });
  route.pathname = "/news";
  await act(async () => root!.render(shell()));
  await act(async () => { await vi.advanceTimersByTimeAsync(DEBOUNCE_MS); });
  if (phase === "debouncing") expect(fetcher).not.toHaveBeenCalled();
  else {
    expect(fetcher.mock.calls[0][1]?.signal?.aborted).toBe(true);
    await act(async () => resolve(new Response(JSON.stringify({ data: [{ id: "9", alias: "TenZ" }], stale: false }))));
  }
  expect(container.querySelector("input")?.value).toBe("");
  expect(container.querySelector('[role="listbox"]')).toBeNull();
  expect(container.querySelector('[data-testid="ticker"]')).toBe(ticker);
  expect(container.querySelectorAll('[role="combobox"]')).toHaveLength(1);
  expect(container.querySelector('nav[aria-label="Primary"] [aria-current]')?.getAttribute("href")).toBe("/news");
});
