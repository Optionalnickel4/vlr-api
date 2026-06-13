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
| Player pages (`/player/[id]`) | Planned | — (data layer exists; page + components only) |
| Stat ticker (lower-third) | ✅ Shipped (see `PROGRESS.md`) | — (curated; no new scraping) |
| Featured streamers (top) | ✅ Shipped (see `PROGRESS.md`) | — (decision resolved: VLR streams scrape + Helix live status) |
| Team-page W/L display | Parked refinement | regional-fetch-vs-no-records decision |
| Rankings streak + win-rate% | Parked (API-side gap) | net-new scraping + schema |
| Player trend endpoint | Parked (API-side gap) | API build (extend team-trend pattern) |
| Live match-detail verification | ✅ Verified / closed | — |

---

## Planned — to build

### Player pages — `/player/[id]`
Player detail + `PlayerSnapshot` + per-agent stat table. **Lightest remaining slice:**
the data layer (`getPlayer`/`normalizePlayer`, `player.json` fixture) already exists from
slice 1 — this is **page + components only**.
- **Notes:** TenZ = id `9`, `?timespan=all`. `agent_stats` keys are display-cased with
  colons — read **verbatim**, do not normalize.
- **Limit:** can show detail + snapshot but **no trend line** until the player-trend
  endpoint exists (see parked API gap below).

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
