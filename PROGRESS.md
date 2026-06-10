# vlr-api — progress

Counts here mirror `app/status_meta.py` (the committed source of truth). Keep them
in sync: bump both in the same commit.

- **Phases shipped:** 6 / 6
- **Tests passing:** 72
- **Commit:** 1d22037

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

- **Stack:** Next 16.2.7 · React 19.2.4 · TypeScript · Tailwind v4 · Framer Motion 12 · Vitest 2
- **Slices done:** 6 / 7 (slice 5 scoped to team detail + trend; player-detail page carved out — see below)
- **Frontend tests passing:** 32 (Vitest, transforms vs committed real fixtures)

## Slices

- [x] **Slice 1 — scaffold + data layer + fixtures**
- [x] **Slice 2 — broadcast primitives + design tokens**
- [x] **Slice 3 — results + upcoming + live**
- [x] **Slice 4 — rankings + news**
- [x] **Slice 5 — team detail + trend** (player-detail page carved out to a follow-up)
- [x] **Slice 6 — match-detail page** (this slice; built against the REAL Phase 7 endpoint — not a stub)
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
