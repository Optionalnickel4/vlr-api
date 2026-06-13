// Featured-streamers (Twitch) tests. The Twitch layer is the project's first
// external integration, so these assert the CONTRACT — token-flow shape, the
// channel-set union + case-insensitive dedupe, the Valorant-only filter,
// viewer_count coercion (null-not-NaN), graceful-empty on any failure, and the
// server-side-once shuffle (seedable/deterministic, never in render). No live
// network: every fetch is mocked and routed by URL.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  dedupeLogins,
  getFeaturedStreamers,
  getStreams,
  mulberry32,
  resetTwitchTokenCache,
  shuffle,
  valorantOnly,
} from "@/lib/twitch";
import type { FeaturedStream } from "@/types/vlr";

// ---- tiny fetch mock router (by URL substring) ------------------------------

type Handler = (url: string, init?: RequestInit) => unknown; // -> json body, or throws/Response
const TOKEN = "id.twitch.tv/oauth2/token";
const HELIX = "api.twitch.tv/helix/streams";
const VLR_LIVE = "/matches/live";
const VLR_MATCH = "/match/";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** Install a fetch that dispatches by URL substring to the given handlers. A
 *  handler may return a plain object (→ 200 JSON) or a Response (for non-2xx). */
function routeFetch(handlers: Partial<Record<string, Handler>>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((async (
    input: string | URL | Request,
    init?: RequestInit,
  ) => {
    const url = String(input);
    for (const [needle, handler] of Object.entries(handlers)) {
      if (handler && url.includes(needle)) {
        const out = handler(url, init);
        return out instanceof Response ? out : jsonResponse(out);
      }
    }
    throw new Error(`unrouted fetch: ${url}`);
  }) as typeof fetch);
}

const TOKEN_OK = () => ({ access_token: "app-token", expires_in: 3600 });

/** A Helix /streams row (only the fields we read). */
function helixRow(p: Partial<Record<string, unknown>> & { user_login: string }) {
  return {
    user_login: p.user_login,
    user_name: p.user_name ?? p.user_login,
    viewer_count: "viewer_count" in p ? p.viewer_count : 1000,
    title: p.title ?? `${p.user_login} stream`,
    game_name: p.game_name ?? "VALORANT",
    thumbnail_url: p.thumbnail_url ?? "https://t/x.jpg",
  };
}

beforeEach(() => {
  resetTwitchTokenCache();
  vi.stubEnv("TWITCH_CLIENT_ID", "test-client-id");
  vi.stubEnv("TWITCH_CLIENT_SECRET", "test-secret");
  vi.stubEnv("TWITCH_FEATURED", "");
  vi.stubEnv("VLR_API_BASE", "http://127.0.0.1:8000/api/v1");
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

// ---- token flow + getStreams ------------------------------------------------

describe("getStreams (token flow + live mapping)", () => {
  it("posts a client-credentials grant then queries Helix with the bearer token", async () => {
    const spy = routeFetch({
      [TOKEN]: TOKEN_OK,
      [HELIX]: () => ({ data: [helixRow({ user_login: "tarik" })] }),
    });

    const streams = await getStreams(["tarik"]);

    // token call shape: POST, x-www-form-urlencoded, the three grant params
    const tokenCall = spy.mock.calls.find((c) => String(c[0]).includes(TOKEN))!;
    expect(tokenCall).toBeTruthy();
    const init = tokenCall[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(String((init.headers as Record<string, string>)["content-type"])).toContain(
      "application/x-www-form-urlencoded",
    );
    const body = String(init.body);
    expect(body).toContain("grant_type=client_credentials");
    expect(body).toContain("client_id=test-client-id");
    expect(body).toContain("client_secret=test-secret");

    // helix call shape: Client-Id + Bearer auth header
    const helixCall = spy.mock.calls.find((c) => String(c[0]).includes(HELIX))!;
    const hHeaders = (helixCall[1] as RequestInit).headers as Record<string, string>;
    expect(hHeaders["Client-Id"]).toBe("test-client-id");
    expect(hHeaders.Authorization).toBe("Bearer app-token");

    expect(streams.map((s) => s.login)).toEqual(["tarik"]);
    expect(streams[0].url).toBe("https://www.twitch.tv/tarik");
  });

  it("batches all logins into ONE Helix call (deduped, lowercased)", async () => {
    const spy = routeFetch({
      [TOKEN]: TOKEN_OK,
      [HELIX]: () => ({ data: [] }),
    });
    await getStreams(["S0mcs", "tarik", "s0mcs"]); // dup differing only in case
    const helixUrl = String(spy.mock.calls.find((c) => String(c[0]).includes(HELIX))![0]);
    expect(helixUrl).toContain("user_login=s0mcs");
    expect(helixUrl).toContain("user_login=tarik");
    // exactly two user_login params (the case-dup collapsed)
    expect(helixUrl.match(/user_login=/g)).toHaveLength(2);
  });

  it("coerces viewer_count to a number or null — never NaN", async () => {
    routeFetch({
      [TOKEN]: TOKEN_OK,
      [HELIX]: () => ({
        data: [
          helixRow({ user_login: "good", viewer_count: 4200 }),
          helixRow({ user_login: "stringy", viewer_count: "1234" }),
          helixRow({ user_login: "bad", viewer_count: "n/a" }),
          helixRow({ user_login: "missing", viewer_count: undefined }),
        ],
      }),
    });
    const byLogin = Object.fromEntries(
      (await getStreams(["good", "stringy", "bad", "missing"])).map((s) => [s.login, s.viewers]),
    );
    expect(byLogin.good).toBe(4200);
    expect(byLogin.stringy).toBe(1234);
    expect(byLogin.bad).toBeNull(); // not NaN
    expect(byLogin.missing).toBeNull();
    for (const v of Object.values(byLogin)) expect(Number.isNaN(v as number)).toBe(false);
  });

  it("refreshes the token once on a 401 and retries", async () => {
    let helixHits = 0;
    const spy = routeFetch({
      [TOKEN]: TOKEN_OK,
      [HELIX]: () => {
        helixHits += 1;
        return helixHits === 1
          ? jsonResponse({}, 401) // first call: stale token
          : { data: [helixRow({ user_login: "shanks_ttv" })] };
      },
    });
    const streams = await getStreams(["shanks_ttv"]);
    expect(streams.map((s) => s.login)).toEqual(["shanks_ttv"]);
    expect(helixHits).toBe(2); // retried after refresh
    // token fetched twice: initial + forced refresh
    expect(spy.mock.calls.filter((c) => String(c[0]).includes(TOKEN))).toHaveLength(2);
  });

  it("graceful-empty: missing creds → [] and no network", async () => {
    vi.stubEnv("TWITCH_CLIENT_ID", "");
    const spy = routeFetch({ [TOKEN]: TOKEN_OK, [HELIX]: () => ({ data: [] }) });
    expect(await getStreams(["tarik"])).toEqual([]);
    expect(spy).not.toHaveBeenCalled();
  });

  it("graceful-empty: token grant fails → [] (Helix never queried)", async () => {
    const spy = routeFetch({
      [TOKEN]: () => jsonResponse({}, 500),
      [HELIX]: () => ({ data: [helixRow({ user_login: "tarik" })] }),
    });
    expect(await getStreams(["tarik"])).toEqual([]);
    expect(spy.mock.calls.some((c) => String(c[0]).includes(HELIX))).toBe(false);
  });

  it("graceful-empty: empty login set → [] without calling Twitch", async () => {
    const spy = routeFetch({ [TOKEN]: TOKEN_OK, [HELIX]: () => ({ data: [] }) });
    expect(await getStreams([])).toEqual([]);
    expect(spy).not.toHaveBeenCalled();
  });
});

// ---- pure transforms: dedupe / Valorant filter / shuffle --------------------

describe("dedupeLogins (channel-set union + case-insensitive dedupe)", () => {
  it("lowercases, drops empties, preserves first-seen order, collapses case dups", () => {
    expect(
      dedupeLogins(["valorant_br", "  Tarik ", "TARIK", "", "valorant_br", "S0mcs"]),
    ).toEqual(["valorant_br", "tarik", "s0mcs"]);
  });
});

describe("valorantOnly (event bar is Valorant-only)", () => {
  it("keeps Valorant streams, drops Just Chatting / other games", () => {
    const streams: FeaturedStream[] = [
      mkStream("a", "VALORANT"),
      mkStream("b", "Just Chatting"),
      mkStream("c", "valorant"), // case-insensitive
      mkStream("d", "Counter-Strike 2"),
      mkStream("e", null),
    ];
    expect(valorantOnly(streams).map((s) => s.login)).toEqual(["a", "c"]);
  });
});

describe("shuffle (server-side once, seedable/deterministic — never in render)", () => {
  const items = [1, 2, 3, 4, 5, 6, 7, 8];

  it("is a pure permutation (same multiset, input untouched)", () => {
    const input = items.slice();
    const out = shuffle(input, mulberry32(123));
    expect(out).toHaveLength(items.length);
    expect([...out].sort((a, b) => a - b)).toEqual(items);
    expect(input).toEqual(items); // not mutated
  });

  it("is deterministic per seed — the SAME order is reproducible (one server roll, sent to both SSR + client)", () => {
    expect(shuffle(items, mulberry32(42))).toEqual(shuffle(items, mulberry32(42)));
  });

  it("different seeds generally produce different orders (the per-load randomization)", () => {
    expect(shuffle(items, mulberry32(1))).not.toEqual(shuffle(items, mulberry32(99999)));
  });
});

// ---- orchestration: union → Helix → Valorant → shuffle ----------------------

describe("getFeaturedStreamers (union, filter, graceful-empty)", () => {
  it("unions live-match channels with TWITCH_FEATURED, keeps Valorant-only", async () => {
    vi.stubEnv("TWITCH_FEATURED", "tarik, s0mcs"); // s0mcs also comes from the live match
    let helixUrl = "";
    routeFetch({
      [VLR_LIVE]: () => [{ id: "100", teams: [], scores: [] }],
      [VLR_MATCH]: () => ({ id: "100", teams: [], maps: [], streams: ["valorant", "S0mcs"] }),
      [TOKEN]: TOKEN_OK,
      [HELIX]: (url) => {
        helixUrl = url;
        return {
          data: [
            helixRow({ user_login: "valorant", viewer_count: 50000 }),
            helixRow({ user_login: "tarik", game_name: "Just Chatting" }), // dropped by filter
            helixRow({ user_login: "s0mcs", viewer_count: 800 }),
          ],
        };
      },
    });

    const res = await getFeaturedStreamers();

    // union queried Helix: valorant ∪ s0mcs (from match) ∪ tarik (env), deduped
    expect(helixUrl).toContain("user_login=valorant");
    expect(helixUrl).toContain("user_login=s0mcs");
    expect(helixUrl).toContain("user_login=tarik");
    expect(helixUrl.match(/user_login=/g)).toHaveLength(3);

    // Valorant-only kept; tarik (Just Chatting) filtered out
    expect(res.data.map((s) => s.login).sort()).toEqual(["s0mcs", "valorant"]);
    expect(res.stale).toBe(false);
  });

  it("nothing live + empty featured → empty set, Twitch never called", async () => {
    const spy = routeFetch({
      [VLR_LIVE]: () => [],
      [TOKEN]: TOKEN_OK,
      [HELIX]: () => ({ data: [] }),
    });
    const res = await getFeaturedStreamers();
    expect(res.data).toEqual([]);
    expect(spy.mock.calls.some((c) => String(c[0]).includes(HELIX))).toBe(false);
  });

  it("graceful-empty: everything down → { data: [], stale: true }, never throws", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await getFeaturedStreamers();
    expect(res.data).toEqual([]);
    expect(res.stale).toBe(true);
  });
});

// ---- helper -----------------------------------------------------------------

function mkStream(login: string, game: string | null): FeaturedStream {
  return {
    login,
    displayName: login,
    viewers: 100,
    title: "t",
    game,
    thumbnail: null,
    url: `https://www.twitch.tv/${login}`,
  };
}
