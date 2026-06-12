# Phase 6 — status dashboard

A self-describing status page for vlr-api: static project progress (phases, tests,
commit) + live read-only service status. Served by the app itself at `GET /status`
(HTML) backed by `GET /api/v1/status` (JSON).

## Hard constraints (do not violate)
- **READ-ONLY.** The status route reads cache/db only. It MUST NOT call any
  `refresh_*` / scraper / service-orchestration code. Same rule as every other router.
- Layer discipline: HTML + JSON routes live in `app/api/v1/` (or a thin `app/api/`
  for the root HTML). Data gathering goes through `app/core/{db,cache}` helpers, not
  inline SQL scattered in the router.
- Tests must not hit the network and must not require a live Postgres/Redis to pass —
  mock/fake the db + cache layer and assert on response *shape and invariants*, not
  on volatile counts/timestamps. (Consistent with the project's fixture philosophy.)
- No new heavy deps. Render HTML with a plain f-string/template in-module — do NOT
  add Jinja2 or a frontend build. One self-contained HTML string is fine.

## Part 1 — scheduler last-run tracking
Each scheduled job records completion so the status page can show "last ran".

- On **successful** completion of each job, write a Redis key:
  `vlr:lastrun:<job_name>` = ISO-8601 UTC timestamp. No TTL (must survive to be read
  later). Use the existing cache/Redis client in `app/core/cache`.
- Implement as a single helper `record_job_run(job_name: str)` called at the end of
  each job in `app/jobs/`, OR (cleaner) a small wrapper/decorator that wraps each
  scheduled callable and records on success only. Pick one; do not write the key on
  failure.
- Job names: use the existing cadence names already registered with APScheduler
  (live_upcoming, results, rankings, events, news — match whatever the scheduler
  actually registers; read app/jobs/ for the real names, don't invent).

## Part 2 — live status data (read-only JSON)
`GET /api/v1/status` returns JSON. Gather via read-only calls:

```
{
  "service": "vlr-api",
  "commit": "<short sha>",          # see Part 4 — from committed metadata, not git at runtime
  "deploy": {"lxc": 289, "host": "192.168.1.35"},
  "checks": {
    "postgres": true/false,         # SELECT 1; false on any exception, never raise
    "redis": true/false             # PING; false on any exception, never raise
  },
  "history": [
    {"table": "match_results",      "rows": <int>, "newest": "<iso|null>"},
    {"table": "ranking_snapshots",  "rows": <int>, "newest": "<iso|null>"},
    {"table": "player_snapshots",   "rows": <int>, "newest": "<iso|null>"},
    {"table": "team_snapshots",     "rows": <int>, "newest": "<iso|null>"}
  ],
  "cache_keys": [                    # the known cache keys + remaining TTL seconds
    {"key": "rankings", "ttl": <int|null>},
    {"key": "results",  "ttl": <int|null>},
    {"key": "live",     "ttl": <int|null>},
    {"key": "news",     "ttl": <int|null>},
    {"key": "events",   "ttl": <int|null>}
  ],
  "scheduler": [                     # last + next run per job
    {"job": "results", "last_run": "<iso|null>", "next_run": "<iso|null>"}
    # ... one per registered job
  ]
}
```

Rules for gathering:
- Each row-count uses `SELECT count(*), max(<ts_col>)` per history table. Use the
  real timestamp column each model already has (created_at / captured_at — check the
  models, don't assume). Wrap in try/except → on failure that table reports
  `rows: null, newest: null`, and `checks.postgres` reflects the failure. One bad
  table must not 500 the whole endpoint.
- `cache_keys` uses Redis `TTL` on the actual cache key names the project uses (read
  app/core/cache + services for the real key strings — the list above is indicative,
  use the real ones). TTL of -2 (missing) → report `ttl: null`; -1 (no expiry) →
  report as is or null, your call, document it.
- `scheduler` reads `vlr:lastrun:<job>` (Part 1) for last_run, and APScheduler's
  `scheduler.get_jobs()[].next_run_time` for next_run. If the scheduler isn't running
  in this process (VLR_ENABLE_SCHEDULER=false, multi-worker), next_run is null but
  last_run still resolves from Redis — handle both.

## Part 3 — HTML page (`GET /status`)
- Plain text/html response. Single self-contained string: inline CSS, no external JS
  build, no CDN dependency required for it to function. A little vanilla JS to fetch
  `/api/v1/status` and populate is fine; page must still render (with a "loading"
  state) if JS is off or the JSON call fails.
- Sections, in order:
  1. Header: service name, deploy target, commit sha.
  2. Summary tiles: phases shipped, tests passing, history table count (from static
     metadata, Part 4).
  3. Phase list: each phase name + one-line description + shipped check.
  4. Live status: postgres/redis up/down, per-table rows + newest age, cache key
     warmth (ttl), scheduler last/next per job.
- Keep it legible and plain. No framework. Render ages human-friendly client-side
  (e.g. "2h 14m ago") from the ISO timestamps; round everything.
- Degrade gracefully: if `/api/v1/status` fails, show the static half and a clear
  "live status unavailable" notice rather than a broken page.

## Part 4 — static project metadata
Committed source of truth so it versions with the code. Create
`app/status_meta.py`:

```python
COMMIT = "1d22037"          # bump manually per release, or read from a build-stamp file
TESTS_PASSING = 52          # bump when you add tests
PHASES = [
    {"n": 1, "name": "league listings",   "desc": "results, upcoming/live, rankings, events, news + history", "shipped": True},
    {"n": 2, "name": "player detail",      "desc": "on-demand fetch + PlayerSnapshot history",                 "shipped": True},
    {"n": 3, "name": "team detail",        "desc": "on-demand fetch + TeamSnapshot history",                   "shipped": True},
    {"n": 4, "name": "team trends",        "desc": "rating trend joined with results",                         "shipped": True},
    {"n": 5, "name": "results backfill",   "desc": "team-page results into match_results, id-join",            "shipped": True},
    {"n": 6, "name": "status dashboard",   "desc": "this page",                                                "shipped": True},
]
HISTORY_TABLES = ["match_results", "ranking_snapshots", "player_snapshots", "team_snapshots"]
```
Do NOT compute TESTS_PASSING at runtime. It's a committed constant.
Optionally have COMMIT read a `BUILD_SHA` env / build-stamp file written at deploy
time, falling back to the constant — your call, keep it simple.

## Tests (TDD — write first)
- `GET /api/v1/status` returns 200 and the documented JSON shape, with db+cache faked.
- When the faked db raises on one table, that table reports null rows/newest and the
  endpoint still returns 200 (no 500), and `checks.postgres` is false.
- When Redis PING fails (faked), `checks.redis` is false and the endpoint still 200s.
- `record_job_run` writes `vlr:lastrun:<job>` with a parseable ISO timestamp and no
  TTL (assert against a fake/in-memory redis).
- The status route triggers NO scraper/service refresh calls (assert the orchestration
  layer is never invoked — e.g. patch it and assert not called). This guards the
  read-only invariant.
- `GET /status` returns 200 text/html containing the static phase names (smoke).

## Deploy / wiring
- Register both routes. `/api/v1/status` on the v1 router; `/status` (and optionally
  `/`) returning HTML.
- No new systemd unit, no migration. Ships with `git pull && systemctl restart vlr-api`.
- Reachable at vlr.jushosting.dev/status through existing Caddy. Public, read-only,
  no secrets in the payload — confirm nothing sensitive (passwords, tokens, internal
  hostnames beyond the already-known LXC IP) leaks into the JSON.

## Out of scope
- No auth/gating (public by decision).
- No historical charts on the page (that's the later dashboard/correlation work).
- No auto-refresh polling loop beyond a single fetch on load (optional manual refresh
  button is fine).
