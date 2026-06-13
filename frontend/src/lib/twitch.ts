// Twitch data layer — the project's first EXTERNAL API integration.
//
// SERVER-SIDE ONLY. The client secret never reaches the browser: every Twitch
// call lives here, behind the force-dynamic /api/streamers route + a server
// component. Mirrors the vlr.ts contract — graceful-empty on ANY failure (no
// creds, token error, Helix down, nobody live) collapses to an empty bar, never
// a thrown page, never an error strip.
//
// Flow: live matches → their Twitch channel logins ∪ TWITCH_FEATURED env handles
// → Helix /streams (live-only, batched) → keep Valorant-only → server-shuffle
// ONCE at request time (hydration-safe: one order computed on the server and
// sent identically to client; never re-rolled in React render).

import { getLive, getMatch, parseNumeric } from "@/lib/vlr";
import type { ApiResponse, FeaturedStream } from "@/types/vlr";

const TOKEN_URL = "https://id.twitch.tv/oauth2/token";
const HELIX_STREAMS = "https://api.twitch.tv/helix/streams";
const VALORANT_GAME = "valorant"; // Helix game_name "VALORANT", matched lowercased
const HELIX_MAX_LOGINS = 100; // Helix caps user_login params per /streams call

/** How many live matches we pull detail for to harvest their stream logins.
 *  Bounded so the fan-out stays cheap (rarely more than a couple live at once). */
export const STREAMERS_MATCH_SAMPLE = 8;

function creds(): { id: string; secret: string } | null {
  const id = process.env.TWITCH_CLIENT_ID;
  const secret = process.env.TWITCH_CLIENT_SECRET;
  return id && secret ? { id, secret } : null;
}

function strOrNull(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const s = String(value);
  return s === "" ? null : s;
}

/** Case-insensitive dedupe, normalized to lowercase (Twitch user_login is
 *  case-insensitive), first-seen order preserved. Empties dropped. */
export function dedupeLogins(logins: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of logins) {
    const login = (raw ?? "").trim().toLowerCase();
    if (!login || seen.has(login)) continue;
    seen.add(login);
    out.push(login);
  }
  return out;
}

/** Custom featured handles from TWITCH_FEATURED (comma-separated), cleaned. */
export function featuredLogins(): string[] {
  return dedupeLogins((process.env.TWITCH_FEATURED ?? "").split(","));
}

// ---- app access token (client-credentials grant) ----------------------------
// Cached in module memory with its expiry (tokens are app-wide, not per-user).
// Refresh on expiry OR on a 401 from Helix (the force path).

interface CachedToken {
  token: string;
  expiresAt: number; // epoch ms, already shaved by a safety margin
}
let cachedToken: CachedToken | null = null;

/** Test-only: clear the in-memory token cache between cases. */
export function resetTwitchTokenCache(): void {
  cachedToken = null;
}

/** App access token via client-credentials grant. Returns the cached token while
 *  valid; `force` bypasses the cache (used once after a Helix 401). Returns null
 *  when creds are missing or the grant fails — callers degrade to empty. */
async function getAppToken(force = false): Promise<string | null> {
  const c = creds();
  if (!c) return null;
  const now = Date.now();
  if (!force && cachedToken && cachedToken.expiresAt > now) return cachedToken.token;
  try {
    const res = await fetch(TOKEN_URL, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        client_id: c.id,
        client_secret: c.secret,
        grant_type: "client_credentials",
      }),
      cache: "no-store",
    });
    if (!res.ok) return null;
    const json = (await res.json()) as {
      access_token?: string;
      expires_in?: number;
    };
    if (!json.access_token) return null;
    const ttlMs = (parseNumeric(json.expires_in) ?? 3600) * 1000;
    // refresh a minute early so an in-flight request never races expiry.
    cachedToken = {
      token: json.access_token,
      expiresAt: now + Math.max(ttlMs - 60_000, 0),
    };
    return cachedToken.token;
  } catch {
    return null;
  }
}

// ---- Helix /streams ----------------------------------------------------------

function toFeaturedStream(row: Record<string, unknown>): FeaturedStream {
  const login = String(row.user_login ?? "").toLowerCase();
  return {
    login,
    displayName: strOrNull(row.user_name),
    viewers: parseNumeric(row.viewer_count), // null-not-NaN
    title: strOrNull(row.title),
    game: strOrNull(row.game_name),
    thumbnail: strOrNull(row.thumbnail_url),
    url: `https://www.twitch.tv/${login}`,
  };
}

/** Which of `logins` are LIVE right now (one batched Helix call, ≤100 logins).
 *  Helix returns ONLY live channels, so the result is already the live subset.
 *  Refreshes the token once on a 401, then retries. Empty array on any failure,
 *  missing creds, or nobody live. */
export async function getStreams(logins: string[]): Promise<FeaturedStream[]> {
  const wanted = dedupeLogins(logins).slice(0, HELIX_MAX_LOGINS);
  if (wanted.length === 0) return [];
  const c = creds();
  if (!c) return [];

  const url = `${HELIX_STREAMS}?${wanted
    .map((l) => `user_login=${encodeURIComponent(l)}`)
    .join("&")}`;
  const call = (token: string) =>
    fetch(url, {
      headers: { "Client-Id": c.id, Authorization: `Bearer ${token}` },
      cache: "no-store",
    });

  try {
    let token = await getAppToken();
    if (!token) return [];
    let res = await call(token);
    if (res.status === 401) {
      token = await getAppToken(true); // stale/revoked token — force a refresh once
      if (!token) return [];
      res = await call(token);
    }
    if (!res.ok) return [];
    const json = (await res.json()) as { data?: unknown };
    const rows = Array.isArray(json.data)
      ? (json.data as Record<string, unknown>[])
      : [];
    return rows.map(toFeaturedStream);
  } catch {
    return [];
  }
}

// ---- pure transforms (Valorant filter + shuffle) ----------------------------

/** Keep only streams whose game_name is Valorant (case-insensitive). A featured
 *  streamer belongs in the event bar only while actually playing Valorant — no
 *  Just Chatting / other titles. */
export function valorantOnly(streams: FeaturedStream[]): FeaturedStream[] {
  return streams.filter((s) => (s.game ?? "").toLowerCase() === VALORANT_GAME);
}

/** Small deterministic PRNG (mulberry32) so a given seed reproduces an order in
 *  tests. The loader seeds it from Math.random() at REQUEST TIME on the server. */
export function mulberry32(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Fisher–Yates shuffle driven by a provided RNG. Pure: returns a new array,
 *  never mutates the input. HYDRATION-CRITICAL contract: the loader calls this
 *  ONCE server-side per request with a fresh seed, so the bar order is random
 *  per load yet computed a single time and sent identically to SSR + client.
 *  Never call it (or Math.random) in React render — that reintroduces a
 *  hydration mismatch. A seeded rng makes the result deterministic + testable. */
export function shuffle<T>(items: T[], rng: () => number): T[] {
  const a = items.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---- orchestration loader (graceful-empty) ----------------------------------

/** The featured-streamers loader. Fans out: live matches → their Twitch logins
 *  ∪ TWITCH_FEATURED → Helix (live-only) → Valorant-only → server-shuffled once.
 *  Server-side, request-time (the route is force-dynamic) so the order is fresh
 *  per load but identical across SSR + hydration. Graceful-empty on ANY failure
 *  → empty bar, never an error strip. */
export async function getFeaturedStreamers(): Promise<ApiResponse<FeaturedStream>> {
  try {
    // (a) channels from currently-LIVE matches — the match center already knows
    // what's live; pull each live match's detail for its `streams` logins.
    const live = await getLive();
    const liveIds = live.data
      .map((m) => m.id)
      .filter((id): id is string => Boolean(id))
      .slice(0, STREAMERS_MATCH_SAMPLE);
    const details = await Promise.all(liveIds.map((id) => getMatch(id)));
    const fromMatches = details.flatMap((d) => d.data).flatMap((m) => m.streams);

    // (b) ∪ custom featured handles from env. Dedupe across both (case-insensitive).
    const logins = dedupeLogins([...fromMatches, ...featuredLogins()]);
    if (logins.length === 0) return { data: [], stale: live.stale };

    // Helix returns only the LIVE ones; then keep Valorant-only.
    const liveStreams = valorantOnly(await getStreams(logins));

    // ONE server-side shuffle at request time (NOT in render → hydration-safe).
    const seed = (Math.random() * 0x100000000) >>> 0;
    const data = shuffle(liveStreams, mulberry32(seed));
    return { data, stale: live.stale };
  } catch (err) {
    return { data: [], stale: true, error: String(err) };
  }
}
