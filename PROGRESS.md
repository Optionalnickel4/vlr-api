# vlr-api — progress

Counts here mirror `app/status_meta.py` (the committed source of truth). Keep them
in sync: bump both in the same commit.

- **Phases shipped:** 6 / 6
- **Tests passing:** 58
- **Commit:** 1d22037

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
- **Slices done:** 4 / 7
- **Frontend tests passing:** 23 (Vitest, transforms vs committed real fixtures)

## Slices

- [x] **Slice 1 — scaffold + data layer + fixtures**
- [x] **Slice 2 — broadcast primitives + design tokens**
- [x] **Slice 3 — results + upcoming + live**
- [x] **Slice 4 — rankings + news** (this slice)
- [ ] **Slice 5 — player detail + team trends** (team detail guarded for the 500)
- [ ] **Slice 6 — match-detail page as stub** (components real, data stubbed; Phase 7)
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
