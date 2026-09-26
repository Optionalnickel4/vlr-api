// @vitest-environment happy-dom
//
// Behavior + hydration guard for the PlayerSearch client island. Covers:
//   1. normalizePlayerSearch pure transform (db row, vlr row, graceful empty).
//   2. SSR↔hydrate parity — empty state produces identical markup (no mismatch).
//   3. <2-char input returns empty — fetch is NOT called below MIN_QUERY_LEN.
//   4. Debounce fires once — rapid input coalesces to a single fetch after DEBOUNCE_MS.
//   5. Dropdown renders alias + team from a successful response.
//   6. Error state renders the error field from the envelope.

import { afterEach, describe, expect, it, vi } from "vitest";
import { createElement as h, act } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";

import { PlayerSearch, MIN_QUERY_LEN, DEBOUNCE_MS } from "@/components/PlayerSearch";
import type { ApiResponse, PlayerSearchResult } from "@/types/vlr";
import { normalizePlayerSearch } from "@/lib/vlr";

// React needs this flag to run act() cleanly outside React Testing Library.
(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

/** Render+hydrate with real timers (SSR parity tests). */
async function mountIsland() {
  const element = h(PlayerSearch);
  const ssrHtml = renderToString(element);
  const container = document.createElement("div");
  container.innerHTML = ssrHtml;

  const seen: string[] = [];
  const spy = vi.spyOn(console, "error").mockImplementation((...args) => {
    seen.push(args.map(String).join(" "));
  });
  const root = hydrateRoot(container, element, {
    onRecoverableError: (e) => seen.push(String(e)),
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  spy.mockRestore();

  const hydrationErrors = seen.filter((m) =>
    /hydrat|did not match|didn't match|server rendered|server-rendered|attributes/i.test(m),
  );
  return { container, root, ssrHtml, hydrationErrors };
}

/** Render+hydrate with fake timers already active (interaction tests). */
function mountIslandFake() {
  const element = h(PlayerSearch);
  const container = document.createElement("div");
  container.innerHTML = renderToString(element);
  const root = hydrateRoot(container, element);
  return { container, root };
}

/** Dispatch a React-compatible input event after setting the element value. */
function fireInput(input: HTMLInputElement, value: string) {
  Object.defineProperty(input, "value", { writable: true, value });
  input.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

// ── pure transform ────────────────────────────────────────────────────────────

describe("normalizePlayerSearch", () => {
  it("maps a db row correctly", () => {
    const [r] = normalizePlayerSearch([
      { id: "9", alias: "TenZ", team: "Sentinels", country: "CA", source: "db" },
    ]);
    expect(r.id).toBe("9");
    expect(r.alias).toBe("TenZ");
    expect(r.team).toBe("Sentinels");
    expect(r.source).toBe("db");
  });

  it("maps a vlr fallback row with source vlr", () => {
    const [r] = normalizePlayerSearch([
      { id: "42", alias: "yay", team: null, country: null, source: "vlr" },
    ]);
    expect(r.source).toBe("vlr");
    expect(r.team).toBeNull();
  });

  it("returns empty array for non-array input (graceful)", () => {
    expect(normalizePlayerSearch(null)).toEqual([]);
    expect(normalizePlayerSearch({})).toEqual([]);
  });
});

// ── SSR ↔ hydrate parity ─────────────────────────────────────────────────────

describe("PlayerSearch island — SSR ↔ hydrate parity", () => {
  it("renders identically on server and client with zero hydration errors", async () => {
    const { ssrHtml, hydrationErrors, root } = await mountIsland();
    // Empty initial state: just the search input, no dropdown open
    expect(ssrHtml).toContain("Search players");
    expect(hydrationErrors).toEqual([]);
    await act(async () => root.unmount());
  });
});

// ── min-length guard ──────────────────────────────────────────────────────────

describe(`PlayerSearch island — <${MIN_QUERY_LEN} chars returns empty, no fetch`, () => {
  it("does not call fetch when input is below MIN_QUERY_LEN", async () => {
    vi.useFakeTimers();
    const spy = vi.spyOn(globalThis, "fetch");

    const { container, root } = mountIslandFake();
    await act(async () => {}); // flush mount effects

    const input = container.querySelector("input")!;
    await act(async () => {
      fireInput(input, "T");
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 50);
    });

    expect(spy).not.toHaveBeenCalled();
    expect(container.querySelector('[role="listbox"]')).toBeNull();
    await act(async () => root.unmount());
  });
});

// ── debounce ─────────────────────────────────────────────────────────────────

describe("PlayerSearch island — debounce", () => {
  it("fires exactly one fetch after rapid input, not one per keystroke", async () => {
    vi.useFakeTimers();
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        json({ data: [], stale: false } satisfies ApiResponse<PlayerSearchResult>),
      );

    const { container, root } = mountIslandFake();
    await act(async () => {}); // flush mount

    const input = container.querySelector("input")!;

    // Rapid successive keystrokes within the debounce window
    await act(async () => { fireInput(input, "Te"); });
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    await act(async () => { fireInput(input, "Ten"); });
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    await act(async () => { fireInput(input, "TenZ"); });

    // Before the debounce elapses: no fetch yet
    expect(spy).not.toHaveBeenCalled();

    // After the full debounce: exactly one fetch for the final value
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
    });
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("q=TenZ"),
      expect.anything(),
    );
    await act(async () => root.unmount());
  });
});

// ── dropdown content ──────────────────────────────────────────────────────────

describe("PlayerSearch island — dropdown renders alias + team", () => {
  it("shows alias and team name in results after fetch resolves", async () => {
    vi.useFakeTimers();
    const results: PlayerSearchResult[] = [
      { id: "9", alias: "TenZ", team: "Sentinels", country: "CA", source: "db" },
      { id: "42", alias: "yay", team: "NRG", country: "US", source: "vlr" },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      json({ data: results, stale: false } satisfies ApiResponse<PlayerSearchResult>),
    );

    const { container, root } = mountIslandFake();
    await act(async () => {}); // flush mount

    const input = container.querySelector("input")!;
    await act(async () => { fireInput(input, "TenZ"); });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
    });
    // flush resolved promise
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await Promise.resolve(); });

    const html = container.innerHTML;
    expect(html).toContain("TenZ");
    expect(html).toContain("Sentinels");
    expect(html).toContain("yay");
    expect(html).toContain("NRG");
    // VLR-sourced row gets the source indicator; DB row does not emit one
    expect(html).toContain("vlr");
    await act(async () => root.unmount());
  });
});

// ── error state ───────────────────────────────────────────────────────────────

describe("PlayerSearch island — error state", () => {
  it("renders the error message from the envelope", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      json({
        data: [],
        stale: true,
        error: "upstream timeout",
      } satisfies ApiResponse<PlayerSearchResult>),
    );

    const { container, root } = mountIslandFake();
    await act(async () => {}); // flush mount

    const input = container.querySelector("input")!;
    await act(async () => { fireInput(input, "TenZ"); });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(DEBOUNCE_MS + 10);
    });
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await Promise.resolve(); });

    expect(container.innerHTML).toContain("upstream timeout");
    await act(async () => root.unmount());
  });
});

// These deferred fetches intentionally ignore AbortSignal to exercise the
// generation guard independently of the browser's cancellation behavior.
function deferred() {
  let resolve!: (value: Response) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<Response>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const player = (id: string, alias: string) => ({ id, alias, team: null, country: null, source: "db" });
async function startSearch(input: HTMLInputElement, query: string) {
  await act(async () => fireInput(input, query));
  await act(async () => { await vi.advanceTimersByTimeAsync(DEBOUNCE_MS); });
}
async function key(input: HTMLInputElement, value: string) {
  await act(async () => { input.dispatchEvent(new KeyboardEvent("keydown", { key: value, bubbles: true, cancelable: true })); });
}

describe("PlayerSearch request ownership and keyboard behavior", () => {
  it.each(["success", "failure"])("ignores an older %s after newer results arrive", async (outcome) => {
    vi.useFakeTimers();
    const old = deferred();
    const next = deferred();
    const fetcher = vi.spyOn(globalThis, "fetch").mockReturnValueOnce(old.promise).mockReturnValueOnce(next.promise);
    const { container, root } = mountIslandFake();
    await act(async () => {});
    const input = container.querySelector("input")!;
    await startSearch(input, "old");
    await startSearch(input, "new");
    expect((fetcher.mock.calls[0][1]?.signal as AbortSignal).aborted).toBe(true);
    await act(async () => next.resolve(json({ data: [player("2", "New player")], stale: false })));
    await act(async () => {
      if (outcome === "success") old.resolve(json({ data: [player("1", "Old player")], stale: false }));
      else old.reject(new Error("old request failed"));
    });
    expect(container.querySelector('[role="option"]')?.textContent).toContain("New player");
    expect(container.textContent).not.toContain("Old player");
    expect(container.textContent).not.toContain("old request failed");
    expect(container.querySelector('[role="status"]')?.textContent).toContain("1 player found");
    await act(async () => root.unmount());
  });

  it.each(["clear", "escape", "blur", "outside"])("does not reopen after %s during a request", async (action) => {
    vi.useFakeTimers();
    const pending = deferred();
    const fetcher = vi.spyOn(globalThis, "fetch").mockReturnValue(pending.promise);
    const { container, root } = mountIslandFake();
    await act(async () => {});
    const input = container.querySelector("input")!;
    await startSearch(input, "TenZ");
    if (action === "clear") await act(async () => fireInput(input, ""));
    if (action === "escape") await key(input, "Escape");
    if (action === "blur") await act(async () => input.dispatchEvent(new FocusEvent("focusout", { bubbles: true })));
    if (action === "outside") await act(async () => document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true })));
    expect((fetcher.mock.calls[0][1]?.signal as AbortSignal).aborted).toBe(true);
    await act(async () => pending.resolve(json({ data: [player("9", "TenZ")], stale: false })));
    expect(input.getAttribute("aria-expanded")).toBe("false");
    expect(container.querySelector('[role="listbox"]')).toBeNull();
    expect(container.querySelector('[role="status"]')?.textContent).toBe("");
    await act(async () => root.unmount());
  });

  it("cleans up a pending debounce on unmount", async () => {
    vi.useFakeTimers();
    const fetcher = vi.spyOn(globalThis, "fetch");
    const { container, root } = mountIslandFake();
    await act(async () => {});
    await act(async () => fireInput(container.querySelector("input")!, "TenZ"));
    await act(async () => root.unmount());
    await act(async () => { await vi.advanceTimersByTimeAsync(DEBOUNCE_MS); });
    expect(fetcher).not.toHaveBeenCalled();
  });

  it("aborts an in-flight request on unmount and ignores its delayed completion", async () => {
    vi.useFakeTimers();
    const pending = deferred();
    const fetcher = vi.spyOn(globalThis, "fetch").mockReturnValue(pending.promise);
    const { container, root } = mountIslandFake();
    await act(async () => {});
    await startSearch(container.querySelector("input")!, "TenZ");
    await act(async () => root.unmount());
    expect((fetcher.mock.calls[0][1]?.signal as AbortSignal).aborted).toBe(true);
    await act(async () => pending.resolve(json({ data: [player("9", "TenZ")], stale: false })));
    expect(container.innerHTML).toBe("");
  });

  it("moves the active option with arrows and opens that player with Enter", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ data: [player("9", "TenZ"), player("42", "yay")], stale: false }));
    const { container, root } = mountIslandFake();
    document.body.append(container);
    await act(async () => {});
    const input = container.querySelector("input")!;
    input.focus();
    await startSearch(input, "TenZ");
    const options = container.querySelectorAll('[role="option"]');
    expect(options).toHaveLength(2);
    expect(input.getAttribute("aria-controls")).toBe(container.querySelector('[role="listbox"]')?.id);
    await key(input, "ArrowUp");
    expect(input.getAttribute("aria-activedescendant")).toBe(options[1].id);
    await key(input, "ArrowDown");
    expect(options[0].getAttribute("aria-selected")).toBe("true");
    await key(input, "ArrowDown");
    expect(options[1].getAttribute("aria-selected")).toBe("true");
    expect(options[0].getAttribute("aria-selected")).toBe("false");
    expect(options[1].className).toContain("ring-accent");
    expect(document.activeElement).toBe(input);
    await key(input, "Enter");
    expect(window.location.pathname).toBe("/player/42");
    expect(input.getAttribute("aria-expanded")).toBe("false");
    await act(async () => root.unmount());
    container.remove();
  });

  it("Escape clears results and Enter cannot navigate to a dismissed option", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ data: [player("999", "TenZ")], stale: false }));
    const { container, root } = mountIslandFake();
    await act(async () => {});
    const input = container.querySelector("input")!;
    await startSearch(input, "TenZ");
    await key(input, "ArrowDown");
    await key(input, "Escape");
    expect(input.value).toBe("");
    expect(input.hasAttribute("aria-activedescendant")).toBe(false);
    const previous = window.location.href;
    await key(input, "Enter");
    expect(window.location.href).toBe(previous);
    await act(async () => root.unmount());
  });
});
