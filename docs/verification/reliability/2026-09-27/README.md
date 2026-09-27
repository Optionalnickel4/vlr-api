# Detail reliability evidence — September 27, 2026

See the [current audit follow-up](../../../BROADCAST_PREDEPLOYMENT_AUDIT.md#detail-reliability-follow-up--current-results).

- `audit-review.json` records the reviewed five-commit file scope; `push-audit.json` records local/remote HEAD equality after their ordinary push.
- `check-results.json`, `checks.py`, and `logs/` retain final commands, timestamps and exit codes. Frontend tests: 346; backend: 260. Focused logs cover detail deadline/persistence and existing live behavior. Trailing blank lines in log copies were stripped.
- `before-requests.json` and `after-requests.json`: 32 HTTP observations each. The pre-edit API process retained its imported baseline implementation; the post-edit process imported the fix. “Cold” means cleared **private Redis**, not an empty database. Postgres history remains to exercise real persistence/deduplication. A “warm” request after a failed scrape is merely a second request; no false cached-success inference should be made.
- `before-body-hashes.json` / `after-body-hashes.json`: matching SHA-256 of canonical sorted JSON for successful raw match/team/player detail bodies.
- `before-browser.json` / `after-browser.json`: Chromium against separate baseline/fixed optimized Next builds and the isolated backend. Browser routes stub ticker/live-feed requests to isolate the primary detail; optional server-side analytics still execute. Player dimensions can take two successive 10-second attempts. Screenshots use saved HTML, **not current player/team data**.
- `queue.json`: nine concurrent, different cold match IDs using fast saved HTML and the unchanged real 1.5-second throttle; three healthy requests exceed 10 seconds.
- `hung.json`: actual wall-clock 80-second API limit against a 120-second simulated response. Automated tests separately scale the backend deadline and use fake timers for the frontend's 90-second headers/body deadlines and unchanged 10-second background limit.
- `real-browser.json`: real-cache preview attempts and their limitations. `production-log-summary.json`: no relevant production journal entries accessible in the sampled window; no production incident conclusion follows.
- `operations.json`: final 135-file preview parity, health checks, unchanged production PID/start times, and byte preservation of `.gitignore` and the saved untracked plan.

## Isolation and reproduction

`fixture_backend.py` overrides Redis, Postgres, VLR origin and scheduler settings **before importing the application**. It runs real API/service/parser/database code. All VLR HTML requests use `httpx.MockTransport`; only committed `tests/fixtures` HTML is read. The private backend offers `/_audit/reset` solely for this harness and asserts its private Redis URL before clearing it. Do not install this harness into production.

Create `/tmp/vlr-reliability/{pg/socket,redis,logs,screenshots}`. Start a temporary UTF-8 PostgreSQL 17 cluster under `pg/data` with `initdb -A trust --no-locale -E UTF8`, then `pg_ctl ... -o "-k /tmp/vlr-reliability/pg/socket -p 55432 -c listen_addresses=''" start`. Start Redis with `--port 0 --unixsocket /tmp/vlr-reliability/redis/redis.sock --unixsocketperm 700 --save '' --appendonly no`. The fixed script assumes local role `builder`; adapt this only within the temporary cluster if reproducing as another OS user. No production DSN/cache port is used.

Run the backend from the chosen source tree using `PYTHONPATH=<tree> <venv>/bin/python fixture_backend.py`. Use a checkout of `519bec9` for baseline API/frontend builds and the reliability commit for after. The only HTTP listener is loopback 8102; Uvicorn lifespan is disabled, and schema setup is performed explicitly on the private database. Write `fast` to `/tmp/vlr-reliability/scenario` before launch. Wait for `/health` before clients start.

Run `reproduce.py before` or `after`; do not run scenario-mutating suites concurrently. `body_hashes.py`, `cold_queue.py`, and `hung.py` reproduce the other request measurements. The hung test reserves match ID 9900, independently of the scenario file. Separate Next instances on loopback 3101 (before) / 3102 (after) use `VLR_API_BASE=http://127.0.0.1:8102/api/v1`, with Twitch credentials blank. Browser scripts require the existing `/tmp/vlr-browser-tools` Playwright/Chromium setup and fonts/library environment. Production 3100 remains connected to the independent read-only 8101 adapter.

Early harness runs needed an HTTPX text-property correction, connection-close on deliberate 500 cases, a rename to avoid shadowing Python's `queue` module, and explicit waits for final streamed page content. Measurements here are the completed corrected runs. The temporary comparison frontends, fixture API, Redis and Postgres were stopped after verification. Two selected screenshots are in `docs/screenshots/reliability`; no failed or redundant captures are included.
