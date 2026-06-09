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
