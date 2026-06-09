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
- **Slices done:** 1 / 7
- **Frontend tests passing:** 22 (Vitest, transforms vs committed real fixtures)

## Slices

- [x] **Slice 1 — scaffold + data layer + fixtures** (this slice)
- [ ] **Slice 2 — broadcast primitives + design tokens**
- [ ] **Slice 3 — results + upcoming + live**
- [ ] **Slice 4 — rankings + news**
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
- [x] **Banked:** `frontend/OPEN-ITEM-team-detail-500.md` — `/team/{id}` 500 on unknown ids is an upstream-404 → `raise_for_status` API bug; frontend already guards it
- **Verified deployment notes:** `?region=all` IS accepted (200, 130 teams); `/team/2` works (200) — it's *unknown* ids (`1`/`120`/`1001`) that 500
