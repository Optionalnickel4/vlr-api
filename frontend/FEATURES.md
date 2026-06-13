# frontend — feature tracker (roadmap / backlog)

The single place to see what's **planned**, **in-progress**, and **parked** for the
broadcast dashboard. Completed work is logged in `../PROGRESS.md` (the build journal) —
this file is the forward-looking backlog. Keep entries to *what it is*, *why it's not
done*, and any *dependency / open decision*. When an item ships, move its record to
`PROGRESS.md` and drop it here.

---

## North star — vision & context

> **This section is vision/context, not committed scope.** It anchors decisions and
> priorities; it is **not a task list**. The backlog below is the actual scope.

**"ESPN for Valorant."** The goal is a broadcast-quality esports site: live scores,
standings, team & player pages, match box scores, news, and watch-live integration —
**plus the analysis layer on top of the raw data** (rating trends, form, notable-performance
curation, upset detection) that a raw data mirror like VLR.gg structurally can't provide.
**The differentiation is context and narrative around the data, not the data alone.**

**What this implies for priorities:**
- **Player-driven content is core ESPN territory.** Player pages — with the **player-trends
  API built first** — are on the **critical path**, not a nice-to-have.
- **Reliability/uptime matters** for a site people actually check. The frontend must become a
  proper **managed service** (systemd, production build), not a dev process. This elevates the
  systemd-service infra task.
- **The differentiation surfaces already built** (team rating-trends, stat-ticker
  notable-performance curation) **are the actual product, not garnish** — keep investing there.

**Multi-game future (CS2/CSGO is the likely second game):**
- Architecture should **not actively prevent** a second game, but **do not abstract for it
  prematurely.** The current patterns — per-source scrapers with selectors isolated in
  `selectors.py`, the `{data, stale, error}` envelope, the data-layer boundary — are already
  game-agnostic. A second game = a **new scraper** targeting its source with its own selectors
  feeding the **same patterns**, not a rewrite.
- **Light-touch guidance only:** avoid hardcoding `"valorant"` into things that are conceptually
  a *game dimension*, where keeping it general is cheap. **No refactor needed now.**
- **Intel for when CS is scoped:** the CS equivalent of VLR.gg is **HLTV.org**, which is
  significantly more aggressive about anti-scraping (Cloudflare, rate limits) than VLR. The
  second game will be a **harder scrape** than the first.

---

## Status at a glance

| Item | Status | Blocked on |
|------|--------|------------|
| News page (`/news`) | Planned (small) | — (endpoint already serves it; frontend-only) |
| Player detail page (`/player/[id]`) | Planned | — lean now (data layer exists); fuller needs player-trends API |
| Player index / directory | Planned (larger) | **net-new API — no list-players / stats endpoint yet** |
| Stat ticker (lower-third) | ✅ Shipped (see `PROGRESS.md`) | — (curated; no new scraping) |
| Stat ticker — live-match mode | Planned (enhancement) | — frontend-only for verified stats; clutch/ace need new scrape |
| Featured streamers (top) | ✅ Shipped (see `PROGRESS.md`) | — (decision resolved: VLR streams scrape + Helix live status) |
| Team-page W/L display | Parked refinement | regional-fetch-vs-no-records decision |
| Rankings streak + win-rate% | Parked (API-side gap) | net-new scraping + schema |
| Player trend endpoint | Parked (API-side gap) | API build (extend team-trend pattern) |
| Live match-detail verification | ✅ Verified / closed | — |

---

## Planned — to build

### News page — `/news`
Promote the existing `NewsPanel` (currently a panel on the match center, slice 4) to a
dedicated `/news` route with a **nav link**, showing a fuller feed than the home-page panel.
**Frontend-only — the news endpoint already serves this.** Small slice.
- **Scope:** new route + nav entry; reuse the slice-4 `getNews` loader + `NewsPanel` (or a
  longer-list variant). No new data layer, no API change.

### Player detail page — `/player/[id]`
The carved-out slice. The data layer (`getPlayer`/`normalizePlayer`, `player.json` fixture)
already exists from slice 1 — this is **page + components only**.
- **Lean version (shippable now):** identity/detail + per-agent stat table + recent matches.
- **Notes:** TenZ = id `9`, `?timespan=all`. `agent_stats` keys are display-cased with
  colons — read **verbatim**, do not normalize.
- **Fuller version depends on a net-new API phase (player trends):** a rating trend line
  would match the team-page differentiation surface (slice 5). Per the ESPN north-star,
  **player-driven content is core**, so this is on the critical path — but the trend line
  needs the parked **player-trend endpoint** (see API-side gaps below) built first.

### Player index / directory (optional, larger)
A browsable player landing/list page to navigate into individual `/player/[id]` pages.
- **NET-NEW API WORK — not a frontend-only slice** like the two above. There is **no
  "list players" or region-wide stats endpoint** in vlr-api yet (the stats leaderboard was
  explicitly **omitted** in an earlier slice as having no vlr-api source).
- **Action:** **decide scope + build the API first.** Until a list/stats source exists,
  there's nothing for a directory to read — sequence the API phase before any UI.

### Stat ticker — live-match mode (enhancement to the shipped ticker)
Today the ticker is a **static, server-rendered** curated all-events tape (ACS / upsets /
movers / trends). **Enhancement:** when a match is **LIVE**, the ticker switches to a
live-updating mode focused on the live game; when nothing is live it stays static. **Poll
ONLY while a game is live** — cross-event "notable" stats change slowly, only in-game stats
change fast.
- **Polling blueprint = `LiveMatches`:** SSR-seed → poll the live match-detail endpoint
  (`/api/match/[id]` already exists, `force-dynamic`) while live → keep last-good on a failed
  poll; revert to the static tape when the live set empties.
- **HYDRATION-CRITICAL (same trap class as the match-page fix):** the seeded shuffle/order
  must carry into the **first client render unchanged**; live updates happen **post-mount
  only**. No `Math.random` / `Date.now` divergence between SSR and hydrate.
- **Visual:** "live now playing" — LIVE accent/pulse, focuses on the live match; reverts to
  the curated all-events tape otherwise. Broadcast-authentic.
- **Candidate live stats — verified against the Phase 7 match-detail shape** (all from the
  EXISTING scrape unless noted):
  - ✅ **Top performer now** — highest live **ACS** (`stats.ACS.value`, both teams).
    *Caveat:* R/ACS/ADR read **null early-live** (computed late — see the partial live
    fixture); fall back to K/D/A, which populate immediately.
  - ✅ **Current map score + round number** — per-map `scores [t1,t2]` + the latest played
    round's `round` / cumulative `score` from the round timeline.
  - ✅ **Win streak (consecutive rounds)** — derive from per-round `winner` (1|2) in the
    timeline. Pure computation, no new data.
  - ✅ **Momentum — "won X of last Y"** — windowed over the same round `winner` sequence.
  - ✅ **First-blood leader** — scoreboard **FK** column (map / all-maps total; FB leader =
    max FK).
  - ✅ **Veto / decider recap** on a freshly-started map — header `veto` strip + per-map
    `picked`/`decider`; "freshly started" detectable when a map's rounds are still mostly
    unplayed (`winner` null).
  - ❌ **Clutch / ace flags — NOT derivable from the current scrape.** `round.outcome` is the
    win CONDITION (`elim`/`boom`/`defuse`/`time`), not a 1vX clutch or 5K ace; per-round
    player kills aren't scraped (scoreboard `K` is a per-map total). **Needs net-new scraping**
    (round-by-round player events) — sequence an API phase before this one stat.
- **Scope:** frontend-only for the ✅ items (the live match-detail endpoint already serves the
  shape); only the ❌ clutch/ace item is gated on net-new API scraping.

> **Featured streamers — top-of-screen — ✅ SHIPPED** (writeup in `../PROGRESS.md`).
> The open data-source decision was resolved by doing **both**: route (a) the
> backend now scrapes the Twitch channels VLR lists on the match page (the
> `streams` field), **and** route (b) the frontend calls Twitch **Helix** for who's
> actually live + viewers + title. The two channel sources (live-match channels ∪
> the `TWITCH_FEATURED` env handles) are unioned, then filtered Valorant-only. The
> project's first external API integration; the Twitch secret stays server-side.

---

## Parked — already built, refinement only

### Team pages — `/team/[id]` W/L display
The page itself is **DONE** (slice 5: detail + rating-trend sparkline + roster + results
join). Parked refinement only:
- **Open decision:** the world rankings view (`?region=all`) structurally has **no W/L
  column**; regional views (e.g. `/rankings/north-america`) do. Decide whether the UI
  fetches a regional view to show records, or accepts that world rankings carry none.
  Currently logged, not built.

---

## Parked — API-side gaps (consolidated from `PROGRESS.md`)

These are upstream/API-repo blockers that **limit the frontend features above**. They are
not frontend work — sequence them in the API repo before any UI that would render them.

- **Rankings streak + win-rate%** — not scraped at all. No field, selector, or schema slot
  in `app/scrapers/rankings.py`. Net-new scraping + schema work. Blocks richer
  team/ranking displays. *(W/L itself is resolved — the regional record split landed in the
  2026-06-10 repair pass; only the world-vs-regional UI decision above remains.)*
- **Player trend endpoint** — the "extend the team-trend pattern to players" work was never
  built API-side. Until it exists, a player page can show detail + snapshot but **no trend
  line**. Blocks the trend portion of Player pages above.

---

## Parked — verification items

- **Live match-detail** — ✅ **verified in the wild** (FUT vs NRG live render confirmed).
  Marked verified / closed rather than open.
