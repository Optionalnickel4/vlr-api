# vlr-api — progress

Counts here mirror `app/status_meta.py` (the committed source of truth). Keep them
in sync: bump both in the same commit.

- **Phases shipped:** 11 / 11
- **Tests passing:** 124
- **Commit:** 9ee985b

## vlr-api repair pass (2026-06-10) — three bundled selector/endpoint fixes

Container-verified through the app's httpx client (never curl). Resolves the three
deferred vlr-api gaps logged in the frontend slices below.

1. **W/L selector drift (rankings) — RESOLVED.** Root cause found via live markup:
   vlr split rankings into a **world** view (`/rankings`, `?region=all`) that dropped
   the W/L column entirely, and **regional** pages (`/rankings/<full-region-slug>`,
   e.g. `north-america`) that still carry it in `div.rank-item-record`. The selector
   hadn't been renamed — the data simply isn't on the world view the frontend defaults
   to. Fix: parser now splits the record ("74–35", en-dash) into clean `wins`/`losses`
   numeric fields (robust to dash/label variants), targeting the record summary node —
   never the per-match `mod-win`/`mod-loss` dots (the concatenation trap). World view →
   record/wins/losses null (valid). Verified: `/rankings/north-america` → G2 Esports
   `74–35` → wins 74, losses 35. Tests: `+2` (regional record split + world-view null).
2. **Phase 7 match-detail scoreboard selectors — BUILT.** New `app/scrapers/match_detail.py`
   + selectors for `table.wf-table-inset.mod-overview` (8 per match: per-map × per-team
   + all-maps aggregate). Every value cell reads `span.mod-both`, NEVER raw `td.text()`
   (which concatenates the three side-split spans: K=13 renders raw as "1385" — coerces
   fine, silently wrong). `mod-t`/`mod-ct` (attack/defense) preserved. `parse_numeric` +
   new `parse_percent` (KAST/HS%) in `_util.py`, null-not-NaN. Tested against BOTH banked
   fixtures: partial (R/ACS/ADR empty → null) and filled (all populated). Tests: `+9`.
3. **Team-endpoint 404 handler (Bug A) — RESOLVED.** `app/core/http.py` raises a domain
   `VlrNotFound` on an upstream 404 (final, not retried); the `/team/{id}` route maps it
   to a clean HTTP 404 instead of the old unhandled-`raise_for_status` 500. Verified live:
   `/team/1` → `VlrNotFound` → 404; `/team/2` → 200 (Sentinels, full roster + results).
   Tests: `+3`. (Bug B / id 1001 was already resolved — SQL_ASCII re-encode.)

> Note: the running uvicorn predates this pass; a `systemctl restart vlr-api` is needed
> to surface these on the live HTTP endpoints. The code + container-level verification
> (through the app's httpx client, per the repair rules) are complete.

## Phases

- [x] **Phase 1 — league listings** — results, upcoming/live, rankings, events, news + history
- [x] **Phase 2 — player detail** — on-demand fetch + PlayerSnapshot history
- [x] **Phase 3 — team detail** — on-demand fetch + TeamSnapshot history
- [x] **Phase 4 — team trends** — rating trend joined with results
- [x] **Phase 5 — results backfill** — team-page results into match_results, id-join
- [x] **Phase 6 — status dashboard** — self-describing status page (this phase)
- [x] **Phase 7 — match detail** — rich `/match/{id}` endpoint (header/maps/scoreboards/round timeline + `streams` Twitch channel logins), `refresh_match`, `VlrNotFound` → 404
- [x] **Phase 8 — player trends** — rating/ACS trend over banked `PlayerSnapshot` history (rounds-weighted overall), `/trends/player/{id}`, no new scraper/table
- [x] **Phase 9 — player pre-scrape** — twice-daily scheduler job banks a `PlayerSnapshot` for every player in the next ~48h of matches (cache-gated), so trend history accumulates instead of waiting for on-demand views
- [x] **Phase 10 — player search** — `GET /players?q=` hybrid: DB-first over `PlayerSnapshot` (clean read), VLR autocomplete fallback only on a DB miss (cached like the detail endpoints); self-healing as Phase 9 banks more
- [x] **Phase 11 — live match auto-refresh** — 30s scheduler job re-scrapes each LIVE match's detail + status-aware short cache TTL (live=30s, completed=10m); the match page polls `/api/match/[id]` while live so scores/stats/timeline update without a reload

## Phase 11 — live match auto-refresh

A live match detail used to freeze: cached scrape-on-miss at `ttl_matches=600s`,
no job refreshing it, page server-rendered with no polling → 0:0/stale until a
manual reload outlived the TTL. Three coordinated parts make it self-update.

- [x] **Scheduler job (`refresh_live_matches`, every 30s)** — reads the live list
  from cache (repopulates it on a miss, since `CACHE_LIVE` is written on a longer
  cadence than its own TTL) and re-scrapes each currently-LIVE match's detail via
  `refresh_match`, overwriting its cache. Bounded by the live list (0–4 matches),
  `max_instances=1`. Registered in `build_scheduler()` + `status_meta.JOBS` (as
  `live_matches`) + `_tracked` records `vlr:lastrun:live_matches` — surfaces on
  `/status`. No-op when nothing is live.
- [x] **Status-aware TTL (`refresh_match`)** — a LIVE match caches SHORT
  (`ttl_live`, ~30s) so reads never serve 10-min-stale rounds; a completed match
  keeps the long `ttl_matches`. The job refreshes; the short TTL is the backstop.
- [x] **Page polls while live (`LiveMatchDetail` island)** — the `/match/[id]`
  body is now a client island that SSR-seeds from `initial`, and while
  `status === "live"` polls `/api/match/[id]` every 30s, re-rendering the scorebug
  / scoreboard / round timeline; keeps last-good on a failed poll and STOPS once
  the match finals (reverts to the static long-cached render). Hydration-safe:
  state seeds from `initial`, updates only post-mount — SSR == first client render
  (mirrors the stat-ticker island; the MapTabs tab selection survives a poll).
- [x] Tests: backend `tests/test_live_refresh.py` (**+6**, 118 → 124): live→short
  TTL, completed/unknown→long TTL, job refreshes only live ids (null skipped),
  empty-list no-op, cache-miss repopulate. Frontend `live-match-detail.test.ts`
  (**+4**, 124 → 128): SSR↔hydrate parity on a live seed, poll-updates-scorebug,
  stop-on-final, never-polls-completed. `test_status` JOBS list updated.
- [x] Verified on the container against the REAL live match 670473: the live list
  had expired → the job repopulated it and refreshed **1** live match;
  `vlr:lastrun:live_matches` recorded; `vlr:match:670473` now carries the **short
  TTL** (≤30s, was 600s) with live data (`status:live`, Split 13-3). `tsc`/`eslint`/
  `next build` clean.

## Phase 10 — player search (`GET /api/v1/players?q=`)

A search box source: type a name → that player's `/player/{id}`. Hybrid, and the
architecture rule holds — DB is primary (clean read over our own banked data); VLR
is touched ONLY on a DB miss and cached like the scrape-on-miss detail endpoints,
never per-keystroke.

- [x] **Primary — DB** (`app/services/search.py`): `db_search_stmt` is a pure,
  compile-assertable statement — `DISTINCT ON (player_id)` with `ORDER BY player_id,
  captured_at DESC` (latest snapshot per player), `WHERE alias ILIKE %q% OR real_name
  ILIKE %q%`, capped (`RESULT_CAP=12`). Min-length guard (`≥2`) so a single letter
  never scans. Returns `{id, alias, team, country, source:"db"}`.
- [x] **Fallback — VLR autocomplete** (only on a DB miss): `vlr_fallback` fetches
  `/search/auto/?term=<q>` via the app's throttled client, `parse_vlr_autocomplete`
  pulls player entries (`value`=alias, id from `/player/(\d+)/`) and skips the
  category headers / events / teams. Cached per casefolded term (`vlr:search:{term}`,
  `ttl_search=600`) so a repeated miss doesn't re-hit vlr. `source:"vlr"`.
- [x] **Self-healing flywheel**: a fallback hit returns immediately; clicking through
  to `/player/{id}` banks a `PlayerSnapshot` via the existing route, so the player is
  DB-searchable (`source:"db"`) next time. The fallback never eagerly fetches full
  player pages.
- [x] **Graceful** (`{data, stale, error}` envelope): DB error → empty + stale +
  error (never 500); VLR fallback failure → the empty DB result, gracefully; too-short
  / empty query → valid empty.
- [x] Route `GET /players` (`app/api/v1/routes.py`) delegates to the service (the
  router itself only reads; the service owns the conditional scrape). `ttl_search`
  added to config.
- [x] Tests (`tests/test_search.py`, **+11**, 107 → 118): compiled DB statement shape
  (ILIKE on both name columns, DISTINCT-ON latest-per-player, cap), autocomplete parse
  (player extraction, category/event/team skip, dedupe, cap, bad-JSON→empty),
  min-length guard (no DB touch), DB-hit-skips-fallback, empty-DB→fallback, fallback
  cache (2nd identical miss doesn't re-fetch), DB-error + fallback-error graceful.
- [x] Verified on the container through the app (real DB + real VLR, never curl):
  `?q=tenz` and `?q=ten` → DB hit (TenZ id 9, `source:db`, no cache write);
  `?q=demon1` (not banked) → VLR fallback → Demon1 **id 26171** (+ "LEV Demon1",
  "Lil Demon1"), `source:vlr`, and `vlr:search:demon1` cached with ttl ≈ 600s;
  `?q=t` → empty/valid. Fallback cache confirmed live (only the miss wrote a key).

## Phase 9 — player pre-scrape (scheduler job)

Phase 8 made player trends queryable, but the history was THIN (snapshots only
accrued when someone opened a player page). This job seeds that history ahead of
time. **No new scraper, no new table, no new endpoint** — it orchestrates the
existing match/team/player fetch paths on a schedule.

- [x] `prefetch_upcoming_players` (`app/services/refresh.py`): twice-daily job.
  Pulls `/matches`, keeps the **non-TBD** upcoming matches inside a ~48h window
  (`eta_to_hours`, weeks counted), and for each does ONE match-detail fetch →
  participant player IDs off the scoreboard (`participant_ids_from_match`), with a
  fallback to the two header team IDs → team-page rosters (`roster_ids_from_team`,
  active players only) when the lineup isn't posted yet. De-dupes to unique IDs.
- [x] **CACHE-GATED snapshot** (the load-bearing invariant): `refresh_player`
  writes a snapshot on EVERY call with no internal dedup, so the job replicates the
  route's gate — `cache_get(vlr:player:{id})`; present → SKIP (fetched recently
  on-demand or by a prior run within `ttl_players`=1h, snapshot already exists),
  absent → `refresh_player`. Snapshots never duplicate within/across runs and the
  job cooperates with on-demand views. Logs matches scanned / fetched / skipped.
- [x] Scheduler registration mirrored in all three places: `build_scheduler()` adds
  `_tracked("player_prefetch", …)` as a **cron** job (`hour="5,17"` UTC, twice
  daily, `max_instances=1` so a long run never overlaps); `status_meta.JOBS` gains
  `"player_prefetch"` so it surfaces on `/status`; `_tracked` records
  `vlr:lastrun:player_prefetch` on success.
- [x] Tests (`tests/test_prefetch.py`, **+10**, 97 → 107): pure shaping (eta parse
  incl. the `1w 1d`=192h trap, TBD-skip, window filter, scoreboard ID extraction +
  dedupe, staff-excluded roster fallback) and the **cache gate** — asserts
  `refresh_player` is NOT called for a cache-present player, all-cached → zero
  refreshes, and the no-lineup → team-roster fallback. `test_status` JOBS list
  updated for the new job.
- [x] Verified on the container through the app (real fetches, never curl): one
  tracked run scanned **4** real ≤48h matches → **40** unique players → **40**
  fetched, **0** skipped, **0** failed; `player_snapshots` grew **6 → 46** (+40,
  == fetched); `vlr:lastrun:player_prefetch` recorded. An immediate **second run**
  (cache now warm) → **40 skipped, 0 fetched, 46 → 46** — proving the gate prevents
  duplicate-row corruption.

## Phase 8 — player trends

The player analog of Phase 4's team rating trend. READ-ONLY over banked
`player_snapshots` — **no new scraper, no new table**. Same coercion discipline:
the per-agent stat values (`Rating`/`ACS`/`RND`) are raw TEXT, coerced numerically
and defensively at read time, ordered on `captured_at`, never string-compared.

- [x] `GET /api/v1/trends/player/{id}` (route) — mirrors `/trends/team/{id}` shape;
  reuses the existing `coerce_float`/`coerce_int`/`_chrono_key` helpers in
  `app/services/trends.py`. No snapshots at all for the id → clean **404** (the
  `/history/player` pattern, never an unhandled 500); thin/young history → a valid
  empty series with an honest `note`, no crash.
- [x] **Aggregation** (`aggregate_player_stats`): a snapshot is per-agent, so each
  capture collapses into ONE **rounds-weighted overall** rating + ACS across its
  agent rows (a 4000-round main agent dominates a 14-round off-pick). An agent row
  contributes only when its `Rating` parses; ACS is weighted independently
  (null-on-a-row never drops the rating); a snapshot with no parseable rating is
  skipped, not invented. VLR shows only the current split — the drift over time is
  the net-new signal.
- [x] **Response shape** (`build_player_response`, pure/DB-free): `player_id`,
  `player`, `team`, `window_days`, `rating_trend` (time-ordered points of
  `{captured_at, rating, acs, rounds}`), `rating_change`, `acs_change`, `summary`
  (points / current+peak rating / current+peak ACS — NUMERIC max, never a string
  max). Identity resolves from ALL rows so a player whose history predates the
  window still gets a name; the trend respects the window cutoff.
- [x] Tests (`tests/test_player_trends.py`, **+18**, 79 → 97): rounds-weighted
  aggregation · string→number coercion · unparseable-rating row skipped · None when
  no row parses · RND fallback weight · ACS-null-keeps-rating · chronological order
  on scrambled input · **lexical-trap on ACS** (`"998"`/`"1024"`/`"1003"` → numeric
  peak 1024, not string max `"998"`) · `metric_change` last−first / `<2` → None ·
  full response + summary · empty/young → valid empty + note · window cutoff.
- [x] Verified on the container through the app (real DB + routes, never curl):
  `player_trend("9")` (TenZ) → 2 points, rounds-weighted rating **1.15**, ACS
  **251.8** (9298 rounds), `rating_change` 0.0 (two captures ~24h apart on
  `timespan=all` cumulative stats → drift ≈ 0, honestly thin); route returns
  **200** (full shape incl. `acs_change`), nonexistent id → **404**, `days=0` →
  **422**. **Banked player history is still THIN**: `player_snapshots` holds 3 rows
  across 2 players (id 9 ×2, id 123 ×1) — the trend is real but sparse until more
  `/player/{id}` fetches accumulate captures.

## Phase 6 — status dashboard

- [x] `app/status_meta.py` — committed COMMIT / TESTS_PASSING / PHASES / HISTORY_TABLES / JOBS / DEPLOY
- [x] Part 1 — scheduler last-run tracking: `record_job_run` + success-only `_tracked` wrapper, persistent `vlr:lastrun:<job>` key (no TTL)
- [x] Part 2 — read-only JSON `GET /api/v1/status`: checks, history rows/newest, cache-key TTLs, scheduler last/next
- [x] `app/core/db.py` — `check_db()` + `count_and_newest()` (per-table count(*), max(captured_at); SQL stays out of the router)
- [x] `app/core/cache.py` — `get_last_run()`, `ping()`, `cache_ttl()` (all swallow errors, never raise)
- [x] Part 3 — HTML `GET /status` (and `/`): broadcast style, static half server-side, JS fills live half, degrades gracefully
- [x] Part 4 — static project metadata committed, not computed at runtime
- [x] Tests (`tests/test_status.py`, 6): JSON shape · one bad table → null not 500 · redis down → 200 · `record_job_run` ISO + no TTL · read-only invariant (no refresh ever called) · HTML smoke

---

# frontend — broadcast dashboard (`frontend/`)

Next.js broadcast dashboard living in `frontend/` (same repo, same container).
Consumes vlr-api server-side at `http://127.0.0.1:8000/api/v1`. Conventions live in
`frontend/CLAUDE.md`. Built in vertical slices; **stop & review at each boundary.**

> This file is the build journal (completed work). For what's **planned / in-progress /
> parked**, see the forward-looking backlog: `frontend/FEATURES.md`.

- **Stack:** Next 16.2.7 · React 19.2.4 · TypeScript · Tailwind v4 · Framer Motion 12 · Vitest 2
- **Slices done:** 6 / 7 + stat-ticker + featured-streamers + player-detail page (slice 5 scoped to team detail + trend; the carved-out player-detail page now shipped — see below)
- **Frontend tests passing:** 128 (Vitest — transforms vs committed real fixtures + SSR→hydrate guards + ticker curation + Twitch data-layer + player-trend/page + player-card aggregates + live-map scorebug + live-match poll island)

## Slices

- [x] **Slice 1 — scaffold + data layer + fixtures**
- [x] **Slice 2 — broadcast primitives + design tokens**
- [x] **Slice 3 — results + upcoming + live**
- [x] **Slice 4 — rankings + news**
- [x] **Slice 5 — team detail + trend** (player-detail page carved out to a follow-up)
- [x] **Slice 6 — match-detail page** (this slice; built against the REAL Phase 7 endpoint — not a stub)
- [x] **Stat ticker** (broadcast lower-third; presentation aggregate over existing endpoints)
- [x] **Featured streamers** (top-of-screen watch-live bar; first external API — Twitch Helix)
- [x] **Player detail page** (the slice-5 carve-out; leads with agent stats, Phase 8 trend secondary)
- [ ] **Slice 7 — visual polish pass**

## Slice 1 — scaffold + data layer + fixtures

- [x] `create-next-app` into `frontend/` (`--src-dir`, `@/*` alias, TS, Tailwind v4); Vitest + Framer Motion added
- [x] Root `.gitignore`: `frontend/node_modules/`, `frontend/.next/`, `frontend/.env*` (keep `.env.example`)
- [x] `frontend/.env.example` with `VLR_API_BASE`; `next.config.ts` `allowedDevOrigins` for LAN IP
- [x] Real response fixtures captured from the running vlr-api → `frontend/src/lib/__fixtures__/` (results, upcoming, live[empty out-of-season], rankings, news, player/9, team/2, trends/team/2; lists trimmed to 8 real items)
- [x] `src/types/vlr.ts` — domain types + `ApiResponse<T>`
- [x] `src/lib/vlr.ts` — `fetchUpstream` boundary, `parseNumeric` (null-not-NaN), transforms, graceful-empty loaders
- [x] `src/lib/vlr.test.ts` — 22 Vitest tests asserting invariants (envelope, indexing, verbatim agent_stats keys, news split + fallback, numeric coercion, graceful-empty); no network
- [x] **Banked:** `frontend/OPEN-ITEM-team-detail-500.md` — `/team/{id}` 500 is TWO bugs: (A) nonexistent id → vlr 404 → unhandled `raise_for_status`; (B) real team w/ non-ASCII roster → vlr 200, scrape OK, but `team_snapshots` INSERT 500s because the Postgres cluster is **SQL_ASCII**-encoded (confirmed). Frontend guards both.
- **Verified deployment notes:** `?region=all` IS accepted (200, 130 teams); `/team/2` works (200)

## Slice 2 — broadcast primitives + design tokens

Read the `frontend-design` skill first. Aesthetic is LOCKED broadcast style; tokens
harmonized with the palette already shipped on the API status page
(`app/api/status_html.py`) so dashboard + status read as one product.

- [x] `globals.css` — Tailwind v4 `@theme` tokens: ground/surfaces (`bg`/`panel`/`panel-2`/`line`), ink ramp (`ink`/`mut`/`dim`), meaning (`up`=green, `down`=red LIVE/loss, `warn`, `accent`=teal); atmospheric gradient ground; CSS-only `vlr-pulse` keyframes
- [x] `layout.tsx` — fonts via `next/font/google`: Saira Condensed (display), Saira (body), JetBrains Mono (numerics); metadata
- [x] Primitives in `src/components/`: `Panel` + `SectionHeading`, `Badge` (tones), `LiveBadge` (red pulse), `ScoreDisplay` (winner=green, loser=dim, null=dash, undecided=ink), `TableShell` (uppercase dim heads, right-aligned mono stat cells); `src/lib/cn.ts` helper
- [x] `app/page.tsx` — primitives preview (illustrative demo values, NOT real data; replaced by the real match center in slice 3)
- [x] Verified: `tsc` clean · `next build` clean (fonts + tokens resolve) · 22 Vitest tests still green · server smoke (HTTP 200, broadcast content + Saira present)

## Slice 3 — results + upcoming + live (match center)

- [x] Route handlers `src/app/api/matches/{results,upcoming,live}/route.ts` — thin, `force-dynamic`, return the data-layer `{data,stale,error}` envelope; server-side fetch only
- [x] `MatchCard` — broadcast scorebug row (TEAM · score:score · TEAM, winner green on finals, LIVE/countdown/final marker, event+series, links out to vlr.gg source)
- [x] `MatchSection` — titled module (Panel + heading + count) with graceful empty/stale states
- [x] `LiveMatches` — client island seeded by SSR, polls `/api/matches/live` every 30s (upstream live TTL), keeps last good data on a failed poll
- [x] `app/page.tsx` — match center: Live (polling) + Upcoming + Results, all fetched server-side; replaces the primitives preview
- [x] Verified against the now-healthy vlr-api: `tsc` clean · `next build` clean · 22 Vitest green · smoke — routes return envelopes (results n=50, upcoming n=50, live n=0 empty/valid), SSR page renders real data incl. accented "LEVIATÁN" (clean post-UTF8-fix)

## Slice 4 — rankings + news

- [x] Route handlers `src/app/api/{rankings,news}/route.ts` — thin, `force-dynamic`, return the data-layer `{data,stale,error}` envelope; server-side fetch only. `rankings` passes `?region=` through (defaults `all`)
- [x] `RankingsPanel` — lean broadcast table of EXACTLY the four fields vlr-api serves: rank / team / region / rating (`TableShell`, rank+rating right-aligned mono). rank+rating coerced via `parseNumeric` in the data layer; nothing sorts on the raw string (Phase 4 string-sort trap)
- [x] `NewsPanel` — headline feed as stacked lower-thirds; headline from `title` only, the split date+author sit in a separate dim footer (label-bleed guard), each row links out to vlr.gg
- [x] Both rendered in `app/page.tsx` below the match center, server-side fetched, graceful empty/stale (empty is valid, not an error)
- [x] Test added — news **label-bleed guard**: every headline is free of `•`/`by `/the parsed date/the parsed author (23 total, prior 22 still green)
- [x] **Scoped deliberately lean** (see decision below): no W/L/streak/win-rate columns, no `parsePercent` helper, no API-side scraper changes

### Deferred vlr-api gaps (API-side, not frontend — sequence BEFORE any column that would render them)

The rankings endpoint serves only rank/team/country/rating. Two distinct upstream gaps mean a richer rankings table can't be built honestly yet; both are API-side fixes for their own tasks, out of the frontend slice boundary:

1. **W/L returns `null` — selector drift.** The scraper has a slot (`RANK_RECORD = "div.rank-item-record"` → `record`) but it no longer matches current vlr.gg markup, so `record` is always `null`. Same selector-drift bug class as the Phase 7 match-detail scoreboard work. Fix + verify on container, then W/L can surface.
2. **streak and win-rate% are not scraped at all.** No field, no selector, no schema slot anywhere in `app/scrapers/rankings.py`. Net-new scraping + schema work before either can exist.

Note: the "`33%` won't parse without %-stripping" finding is real but belongs to **Phase 7 match-detail** (KAST/HS% scoreboard cells), not rankings — rankings has no percentage column. The `parsePercent` helper lands there, where it's actually consumed, not here.

## Slice 5 — team detail + trend

The differentiation surface: a `/team/[id]` page combining team detail (name /
region / roster) with the rating-trend line **joined to** its results over the same
window — the combined view the public vlrggapi never served (vlr.gg only shows
*current* rating). Built + verified against id `2` (Sentinels): trend returns 10
rating points + 5 results (W:3 L:2), rating line drawn, accented opponent "LEVIATÁN"
renders clean (post-UTF8-fix).

- [x] `src/app/team/[id]/page.tsx` — `force-dynamic` server component; awaits the
  async route param, fetches `getTeam(id)` + `getTeamTrend(id)` server-side (browser
  never touches vlr-api). Team identity header (name / tag / region badge).
- [x] Thin route handlers `src/app/api/team/[id]/route.ts` + `api/trends/team/[id]/route.ts`
  — `force-dynamic`, return the `{data, stale, error}` envelope; trend passes `?days=` through.
- [x] `Sparkline` — dependency-free inline-SVG rating line (polyline + area + endpoint
  dot); tone = direction (green up / red down / dim flat). Values arrive numeric +
  time-ordered from the data layer; min/max math runs on numbers (no string-sort trap).
- [x] `TeamTrendPanel` — sparkline + summary (change / current / peak / window W/L) +
  upstream `note`. Three graceful states: errored ("trend unavailable"), young history
  (<2 points → honest "history still young", no fake flat line), real series.
- [x] `TeamResultsPanel` — the results join as a recent-results list, each row tagged
  W/L with the broadcast color signal; links to the vlr.gg match; graceful-empty.
- [x] `TeamRosterPanel` — roster as a `TableShell` (players first, staff under a divider,
  captain badge); aliases link to vlr.gg player pages.
- [x] **Graceful error path (mandatory):** the data layer's `load()` catch turns an
  upstream 500 into `{data:[], stale:true, error}`; the page detects no team detail and
  renders a page-level "Couldn't load this team" state — **HTTP 200, not a crash, not a
  Next error boundary.** Live-verified by hitting a 500-ing id (`/team/1`).
- [x] `RankingsPanel` team names now link to `/team/{id}` (the "click a ranked team → its
  page" nav the error path protects); kept the locked ink color, accent only on hover.
- [x] Coercion at the read boundary: rating/rank via `parseNumeric` (null-not-NaN). The
  trend line is **time-ordered on the real `captured_at` timestamp** in `normalizeTrend`
  (sort added) — never lexical, never on the rating value.
- [x] Tests +3 (23 → 26): results-join verdicts valid · **time-ordering invariant** (a
  scrambled series with a lexical-trap rating set must order chronologically) · empty/garbage
  trend → valid empty, no throw. Existing 23 still green.
- [x] Verified: `tsc` clean · `next build` clean (all 3 new routes dynamic) · 26 Vitest
  green · live smoke — `/team/2` renders detail+trend+results; `/team/1` renders the
  graceful error state (HTTP 200).
- **Carved out of this pass:** the **player-detail page** (`/player/[id]`). The data layer
  (`getPlayer`/`normalizePlayer`, `player.json` fixture) already exists from slice 1; only
  the page/components remain. Done next; this slice stayed focused on the team trend — the
  actual differentiation surface.

### Deferred vlr-api gap #3 — team-endpoint 500 on certain ids (Bug A, the 404 handler)

The `/team/{id}` (and on some ids the trend) endpoint still 500s for **ids vlr.gg has no
page for** — e.g. `/team/1` → upstream **404** → unhandled `resp.raise_for_status()` →
generic 500 (Bug A in `frontend/OPEN-ITEM-team-detail-500.md`). These ids are reachable
from normal nav (a ranked team click), so the frontend guards every one (graceful "couldn't
load this team"). **Fix (API repo):** catch `httpx.HTTPStatusError` (404) in
`fetch_team`/`get_html` and raise `HTTPException(404)` instead of 500.

**Correction to the slice prompt's premise:** the prompt expected **id `1001`/Heretics to
500** with an open question (vlr 404 vs scraper parse failure). Verified on the container this
pass: `/team/1001` **and** `/trends/team/1001` now both return **200** (Heretics, 11-man roster
incl. the accented analyst name). That was **Bug B (SQL_ASCII persist)** — already **resolved**
(DB re-encoded UTF8, see OPEN-ITEM). So the open question is answered for 1001, and the *only*
remaining team-endpoint 500 is Bug A (the 404 handler above).

**Bundle this Bug-A fix into the same vlr-api selector/endpoint repair pass** as the two
slice-4 gaps: the W/L `rank-item-record` selector drift and the Phase 7 match-detail scoreboard
selectors — all one HTML-drift / endpoint-hardening sweep, verified on the container.

## Slice 6 — match-detail page (built against the real Phase 7 endpoint)

The internal `/match/[id]` page, rebuilt fresh against vlr-api's real shape (NOT a stub,
NOT ported from vlrggapi field names). Verified live against match `684612` (LEVIATÁN 2:1
Global Esports, Masters London).

**Premise correction (same class as Bug B / the W/L drift):** the slice prompt said "the
match-detail API was built this session." It wasn't — only the *scoreboard scraper*
(`app/scrapers/match_detail.py`, mod-overview selectors) existed, returning flat
`scoreboards` with no header/maps/veto, and there was **no route, service, or cache key**.
So this slice first **built the backend `/match/{id}` endpoint**, then the frontend.

**Backend (API, this slice):**
- `app/scrapers/match_detail.py` rebuilt to the rich shape: header (event, series, status,
  format, teams + ids + series score + `won`), veto strip, per-map list (name, picked/decider,
  `[team1,team2]` map score), per-map per-team player rows, the aggregate "All Maps", and the
  **round timeline** (per round: winner 1|2, side t/ct, outcome elim/boom/defuse/time,
  cumulative score). Scoreboard cells still read `span.mod-both` (never the concatenation),
  KAST/HS% via `parse_percent`, empty live cells → null.
- `refresh_match` + `CACHE_MATCH` (on-demand, no history snapshot) + `GET /match/{id}` route
  (VlrNotFound → clean 404). Tests: `tests/test_match_detail.py` rewritten to the rich shape
  (header/maps/rounds + the concatenation/percent/empty-cell invariants), 9 → 12.
- Backend suite: 72 → **75**. `systemctl restart vlr-api` applied so the live endpoint serves it.

**Frontend (this slice):**
- Types `MatchDetail/MatchMap/MatchRound/MatchStatCell/...`; `normalizeMatch` + `getMatch`
  loader (single object → one-element list; stat `value` re-coerced via `parseNumeric`,
  null-not-NaN; KAST/HS% arrive as bare numbers with `both` keeping "59%" for display).
- `src/app/match/[id]/page.tsx` — force-dynamic server component; thin `api/match/[id]` handler;
  graceful "couldn't load this match" on 404/error (HTTP 200, no crash).
- Components: `MatchHeader` (scorebug + veto + "Open on VLR.gg"), `MapTabs` (client island,
  one tab per map + All Maps, picked/decider marked; allowedDevOrigins already has 192.168.1.35),
  `PlayerStatsTable` (R/ACS/K/D/A/+−/KAST/ADR/HS%/FK/FD; empty → dash), `RoundTimeline`
  (green/red square strip per team, omits gracefully if a map has no rounds).
- **Round data IS exposed** (the endpoint serves it), so the timeline is real — nothing faked.
- Match cards in the center now link to the internal `/match/{id}` (was: out to vlr.gg); the
  source link moved onto the detail page. Fixture `match.json` (real 684612 response) committed.
- Verified: `tsc` clean · `next build` clean (`/match/[id]` + `/api/match/[id]` dynamic) · Vitest
  26 → **32** · live smoke `/match/684612` renders header + map tabs + both scoreboards + round
  strip; `/match/000000` → graceful error; home cards land internally (100 `/match/` links, 0
  vlr.gg match links).

## Player card header (`/player/[id]` restructure)

Restructured the player page to lead with an ESPN-style **player card** above the
agent table. Grounding (real markup, Boo id 1144): VLR exposes **no totals row —
only per-agent rows**, so the card's headline aggregates are computed in the data
layer, ROUNDS-WEIGHTED (same approach as the Phase 8 trend service).

- [x] `playerOverall` / `signatureAgent` (`lib/vlr.ts`, pure + tested): three
  headline numbers — overall **Rating** + **ACS** rounds-weighted across agents
  (weight by RND, fall back to 1, skip rows that don't parse), and **K/D** as
  summed ΣK/ΣD (not a mean of per-agent ratios). A 5881-round Omen dominates a
  15-round Harbor — naive avg would read 0.92, weighted reads 1.01. parseNumeric
  throughout (dash, never NaN). Signature agent = most-played row + usage % verbatim.
- [x] `PlayerCard` (`components/PlayerCard.tsx`): identity (alias, real name,
  team→`/team/{id}`, country) · weighted headline stat line · signature-agent chip
  ("OMEN · 48%") · recent-form W/L dots (most-recent-first, win-green/loss-red) ·
  compact rating Sparkline that shrinks to the slim young-history note when thin
  (the degenerate-flat gate — never a fake line). Pure broadcast chroma, same card
  vocabulary as team/match pages. Page is now card → full 14-agent table → recent
  matches; the standalone `PlayerTrendPanel` is folded into the card (deleted).
- [x] Tests `+10` (105 → 115): rounds-weighted overall (heavy agent dominates,
  not naive), K/D summed aggregate, RND fallback weight, unparseable-row skip,
  empty→null, real-fixture invariants, signature-agent pick + usage parse; page
  test asserts the card headline (`K/D` vs the table's `K:D`), Main chip, Form
  strip, real weighted number. Existing trend young-note + graceful-error intact.
- [x] Verified: `tsc`/`eslint`/`next build` clean · Vitest 115 green · live smoke
  `/player/1144` (Boo): card shows **Rating 1.01 / K/D 1.01 / ACS 186** (matches the
  weighted compute, rejects naive 0.92), **OMEN · 48%** chip, form **L-W-W-W-W…**
  dots, young-history trend note (no fake line); the full 14-agent table intact
  below, order card → table → matches.

## Player detail page (`/player/[id]`) — the slice-5 carve-out

Mirrors the team-detail page, but inverted to match where the data is RICH. Player
trend history is THIN at launch (snapshots only accrue when a player page is
fetched, which didn't exist until now — TenZ has 2 points, most players 0–1), so
the page **leads with the per-agent stat table** and treats the Phase 8 rating/ACS
trend as a SECONDARY panel that honestly shows the young/flat state until captures
build up.

- [x] `src/app/player/[id]/page.tsx` — force-dynamic server component; fetches
  `getPlayer` + the new `getPlayerTrend` in parallel; identity header (alias, real
  name, team→`/team/{id}`, country); page-level graceful error ("couldn't load this
  player", HTTP 200) when detail is absent — same philosophy as the team page.
- [x] Thin route handlers `/api/player/[id]` + `/api/trends/player/[id]` ({data,
  stale, error} envelope, `?days=` passthrough, graceful-empty on upstream fail).
- [x] Data layer: `normalizePlayerTrend` + `getPlayerTrend` (parseNumeric
  null-not-NaN; trend time-ordered on `captured_at`, never on rating/ACS value);
  `shouldRenderTrendLine` generalized with a per-scale `epsilon` arg +
  `PLAYER_FLAT_EPSILON` (0.03 — a player rating moves in hundredths, not hundreds).
- [x] Components: `PlayerStatsPanel` (headline; per-agent table, agent_stats keys
  VERBATIM, column order from the data, wide-scroll), `PlayerMatchesPanel` (recent
  matches, W/L chroma), `PlayerTrendPanel` (reuses Sparkline + the young/flat note;
  rating line + rating/ACS change·current·peak).
- [x] Entry points wired: team roster aliases + match-detail scoreboard names now
  link INTERNALLY to `/player/{id}` (id-preferred, vlr.gg fallback only when no id);
  SiteHeader `/players` nav left a documented placeholder (no league-wide players
  index endpoint yet — deliberately not a dead link).
- [x] Tests `+8` (97 → **105**): `normalizePlayerTrend` (numeric coercion, captured_at
  ordering w/ string-sort trap on ACS, empty/garbage), player-scale `shouldRenderTrendLine`,
  and a page guard (`src/app/player.test.ts`: verbatim agent keys render, thin trend →
  young/flat note not a fake `<svg>` line, upstream fail → graceful error).
- [x] Verified: `tsc` clean · `eslint` clean · `next build` clean (`/player/[id]` +
  both API routes dynamic) · Vitest 105 green · live smoke `/player/9` (TenZ) — 200,
  identity + agent stats (verbatim `K:D`/`KAST`, value `263.8`), trend shows the
  honest **flat** note (2 identical-rating points → no fake line, no svg), team link
  internal; `/player/999999999` → graceful unavailable (200); team page roster → 9
  `/player/` links, match page scoreboard → 10.

## Stat ticker — broadcast lower-third (presentation aggregate, no new scraping)

The bottom-of-screen scrolling marquee of **curated** notable stats. Pure presentation
over endpoints we already serve — zero new upstream surface (decision from `FEATURES.md`:
**curated, not random**).

- **Curation (`buildTicker`, pure + tested):** aggregates already-normalized inputs into a
  flat, render-ready `TickerItem[]`. Four notable-stat kinds, each behind an explicit gate
  (exported consts, so "notable" is a contract, not a vibe):
  - **TOP ACS** — headline single-map ACS per sampled match detail, gated `>= 250`.
  - **UPSET** — a decided result whose winner is ranked `>= 3` spots **below** the loser
    (results × rankings name-join).
  - **MOVER** — leaderboard rank climb/drop `>= 2` positions across a team's trend window.
  - **TREND** — a notable rating swing (`|Δ| >= 15`) when the rank held flat.
  - One item per team (mover preferred over trend → no double-count); fixed order
    (upsets → ACS → movers/trends); de-duped on source-derived id; capped at 12.
- **Hydration-safe by construction:** `buildTicker` is deterministic (no clock, no
  randomness); the scroll is **pure CSS** (`vlr-marquee` keyframes, track rendered twice,
  `-50%` translate for a seamless loop; `prefers-reduced-motion` holds it still). `StatTicker`
  is a server component. Values pre-formatted in the data layer — **dash, never NaN**.
- **`getTicker` orchestration:** force-dynamic `api/ticker` route + a data-layer loader that
  fans out (bounded: ≤4 match details, ≤6 top-team trends) over the **same** loaders the
  match center already uses. Graceful-empty on any failure; an empty tape **hides** the
  ticker (honest neutral state, never an error strip). Mounted at the bottom of the match
  center (server-rendered via the same `getTicker()` call).
- Verified: `tsc` clean · `eslint` clean · `next build` clean (`/api/ticker` dynamic) ·
  Vitest 32 → **55** (18 new ticker tests: per-gate curation, ordering, one-per-team,
  dash-not-NaN, empty-state, graceful-empty).

## Featured streamers — watch-live bar (first external API integration)

The top-of-match-center broadcast band of **Twitch channels live now** for the event.
This is the project's **first external API integration** — and it resolved the long-open
`FEATURES.md` data-source decision by doing **both** routes, each where it fits best:

**Backend (the channel SOURCE — route (a), already shipped in Phase 7's streams scrape):**
- `app/scrapers/match_detail.py` parses the match page's `.match-streams-container`: the
  embeddable `.mod-embed` entries carry `data-site-id` = the bare Twitch login (e.g.
  `valorant_br`), read directly (fallback: last path segment of the external `twitch.tv/…`
  href). **Twitch-only** (YouTube/SOOP/etc. lack `data-site-id` → skipped), case-insensitive
  **dedupe**, empty list valid. Surfaced as the `streams` field on `GET /match/{id}`. No new
  fetch / scheduler / endpoint — rides the existing match-page fetch. Backend tests 75 → **79**.

**Frontend (the LIVE STATUS — route (b), Twitch Helix):**
- `src/lib/twitch.ts` — the Twitch data layer, **server-side ONLY** (the client secret never
  reaches the browser). App access token via **client-credentials grant**, cached in memory
  with its expiry, refreshed on expiry **or** once on a Helix 401. `getStreams(logins)` batches
  all logins into one Helix `/streams` call (≤100), returns only the LIVE subset, `viewer_count`
  via `parseNumeric` (null-not-NaN).
- **Channel set = live-match channels ∪ `TWITCH_FEATURED`** (custom handles), deduped
  case-insensitively, then **Valorant-only** filtered (no Just Chatting / other games in the
  event bar). **Hydration-safe shuffle:** a seedable Fisher–Yates applied **once server-side at
  request time** (`mulberry32`), never in render — one order computed on the server and sent
  identically to SSR + client (the match center is `force-dynamic`, so each load reshuffles
  without a hydration mismatch — the exact failure class we'd just fixed).
- `getFeaturedStreamers` orchestration + thin `force-dynamic` `/api/streamers` route returning
  the `{data, stale, error}` envelope. **Graceful-empty on ANY failure** (no creds, token error,
  Helix down, nothing live) → empty bar, never an error strip. `FeaturedStreamers.tsx` server
  component, LOCKED chroma (`LiveBadge` red, teal hover, red viewer count); each entry =
  channel, viewer count, truncated title, link to `twitch.tv/<login>`. Empty → renders `null`
  (hides), like the ticker. Mounted at the top of the match center.
- `MatchDetail` gains `streams[]`; `normalizeMatch` wires it through.
- Verified: `tsc` clean · `eslint` clean (my files) · `next build` clean (`/api/streamers`
  dynamic) · Vitest 55 → **72** (token-flow shape, union + case-insensitive dedupe, Valorant
  filter, viewer-count null-not-NaN, 401-refresh, graceful-empty paths, shuffle
  deterministic-per-seed/permutation, end-to-end union→filter, + an SSR→hydrate guard). Live
  smoke vs real Twitch: token + Helix 200; with `TWITCH_FEATURED` pointed at live Valorant
  channels the bar renders + reshuffles per load; with the real featured set (none live this
  moment) the bar hides — both valid.

## Infra — frontend is now a managed systemd service

The frontend stopped being a hand-started dev process and became a **proper managed service**
(the reliability/uptime step the `FEATURES.md` north star calls for):

- **`vlr-frontend.service`** (systemd, `User=vlr`, `WorkingDirectory=/opt/vlr-api/frontend`,
  `ExecStart=/usr/bin/npm run start` → `next start`, `Restart=always`, ordered `After=vlr-api`).
  Runs the **production build**, not `next dev`. ⚠️ The unit lives at
  `/etc/systemd/system/vlr-frontend.service` — **outside the repo**, so it can't be tracked in
  place; its full contents are pasted into `DEPLOY.md` for reproducibility on a container rebuild.
- **`start-services.sh`** (repo root, now tracked) — one operator entrypoint for both units:
  `start` / `stop` (web-first) / `restart` (rebuild frontend then restart both) / `build`
  (rebuild + restart web only) / `status`.
- **Ownership fixed** `root` → `vlr` on `frontend/` (the service user must own the build output
  + `node_modules`), and **`frontend/.env` tightened to `640`** (Twitch secret: owner-rw,
  group-r, world-none).
- See `DEPLOY.md` → "9. frontend (Next.js) service" for the full setup + the unit file contents.
