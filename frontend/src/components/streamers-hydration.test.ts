// @vitest-environment happy-dom
//
// Hydration guard for the featured-streamers band. The bar order is randomized
// PER LOAD, but the shuffle happens once in the data layer (server-side, request
// time) — never in render. So for a given (already-shuffled) props array the
// component must SSR and hydrate to identical markup with no mismatch. This is
// the exact failure class we must not reintroduce: if the order were rolled in
// render (Math.random), SSR and client would diverge and React would warn here.

import { afterEach, describe, expect, it, vi } from "vitest";
import { createElement as h } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";

import { FeaturedStreamers } from "@/components/FeaturedStreamers";
import type { FeaturedStream } from "@/types/vlr";

afterEach(() => vi.restoreAllMocks());

async function hydrationErrors(element: ReturnType<typeof h>): Promise<string[]> {
  const html = renderToString(element);
  const container = document.createElement("div");
  container.innerHTML = html;

  const seen: string[] = [];
  const spy = vi.spyOn(console, "error").mockImplementation((...args) => {
    seen.push(args.map(String).join(" "));
  });
  const root = hydrateRoot(container, element, {
    onRecoverableError: (e) => seen.push(String(e)),
  });
  await new Promise((r) => setTimeout(r, 0));
  root.unmount();
  spy.mockRestore();

  return seen.filter((m) =>
    /hydrat|did not match|didn't match|server rendered|server-rendered|attributes/i.test(m),
  );
}

function mkStream(login: string, viewers: number | null): FeaturedStream {
  return {
    login,
    displayName: login.toUpperCase(),
    viewers,
    title: `${login} title`,
    game: "VALORANT",
    thumbnail: null,
    url: `https://www.twitch.tv/${login}`,
  };
}

describe("featured-streamers hydration (server band, no render-time randomness)", () => {
  it("SSR == hydrate for a fixed shuffled order (incl. null viewers → dash)", async () => {
    const streams = [
      mkStream("mooda", 3336),
      mkStream("kaydop", 2547),
      mkStream("onlyrgx", null), // dash, never NaN
    ];
    const errors = await hydrationErrors(h(FeaturedStreamers, { streams }));
    expect(errors).toEqual([]);
  });

  it("empty set hydrates cleanly (the band renders nothing)", async () => {
    const errors = await hydrationErrors(h(FeaturedStreamers, { streams: [] }));
    expect(errors).toEqual([]);
  });
});
