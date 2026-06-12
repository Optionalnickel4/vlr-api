# frontend — feature tracker (roadmap / backlog)

The single place to see what's **planned**, **in-progress**, and **parked** for the
broadcast dashboard. Completed work is logged in `../PROGRESS.md` (the build journal) —
this file is the forward-looking backlog. Keep entries to *what it is*, *why it's not
done*, and any *dependency / open decision*. When an item ships, move its record to
`PROGRESS.md` and drop it here.

## Status at a glance

| Item | Status | Blocked on |
|------|--------|------------|
| Player pages (`/player/[id]`) | Planned | — (data layer exists; page + components only) |
| Stat ticker (lower-third) | Planned | curated-vs-random decision |
| Featured streamers (top) | Planned | **data-source decision (must resolve first)** |
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

### Stat ticker — bottom-of-screen lower-third
Horizontal scrolling marquee of notable stats aggregated from **existing** endpoints
(top ACS from live/recent matches, rating-trend deltas, upset results, leaderboard
movers). Presentation layer over data we already serve — **no new scraping**.
- **Open decision:** curated "notable performances" vs. random selection — **lean curated**.

### Featured streamers — top-of-screen
Twitch streams for the live event.
- **OPEN DECISION (resolve before building):**
  - **(a)** Scrape the streams VLR already lists on the event/match pages we scrape —
    cheap, no new integration.
  - **(b)** Twitch Helix API for who's-live + viewers + thumbnails — needs a Twitch app
    (client ID/secret, OAuth app-token flow).
- **Note:** a Twitch integration may already exist in the **Synapse dashboard** — lift
  credentials / pattern from there if going route (b).

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
