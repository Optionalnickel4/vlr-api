# Read-only API probe

Run from the repository root with the existing backend environment:

```sh
.venv/bin/python scripts/probe_api.py \
  --base-url http://10.0.0.21:8000 \
  --output /tmp/vlr-probe.json
```

The owner authorized this endpoint for this pass **and future VLR-API builds**.
The client issues GET only, sequentially, with no retries or redirects. GET cache
misses can still initiate the API's normal throttled VLR.gg scrapes and cache/history
writes. This is an observation tool, not a cache-only guarantee or load test.
Do not reset caches, change services or inject failures into the running API.

Default coverage: `/health`, `/api/v1/status`, results/upcoming/live, rankings,
NA all-time stats, news, events, blank team/player search, then one match/team/player
ID selected from results/rankings/stats. Blank search emptiness is expected; it does
not establish that populated search works. News links lead to VLR.gg; the API has
no article detail endpoint. IDs must be numeric; response URLs are never followed.

Limits (`--help`): 14 requests, 600 seconds total, 90 seconds per entire request
(headers **and streamed body**), 2 MB decoded response per request, two seconds
between completed requests, one detail of each kind. `--details` accepts 0–3;
raise `--max-requests` accordingly (11 + 3 × details for fully populated listings).
Hard ceilings prevent accidental large scans; the interval cannot go below 1.5s.
A timeout, transport failure, HTTP 429 or any Retry-After ends the pass. A timed-out
server may still be working: inspect the report and allow it to settle; do not
immediately rerun. Other HTTP errors are recorded once and coverage continues.

JSON records UTC timestamps, elapsed milliseconds, HTTP status, bounded type/count
shape, populated/empty/unavailable classification, envelope stale/error booleans,
and allowlisted freshness headers. It contains neither raw payloads, error text,
cookies, credentials nor names. Missing freshness headers are **unknown**, not proof
of fresh data. A populated object can still contain missing nested fields: inspect
its shape and the UI. Detail IDs and source paths are retained for reproducibility.
Output is overwritten at the chosen path. Exit 0 means complete coverage without
unavailable responses; exit 1 means unavailable or bounded/incomplete coverage;
CLI usage errors exit 2. Empty data is not automatically a failure.

`request(client, path, deadline, max_bytes)` is reusable for a small, explicit
follow-up set (e.g. selected IDs' trends/dimensions). Keep the same sequential loop,
spacing, stop conditions and fixed request budget. See this pass's
[follow-up harness](../docs/verification/probe/2026-09-27/analytics.py).

Failure/deadline/body-limit tests use `httpx.MockTransport` exclusively:

```sh
.venv/bin/pytest -q tests/test_probe_api.py
```

For browser validation, follow the selected IDs from their listing links once.
The preview on 3100 uses a cache-only adapter; it does not implement every API
route. Report this distinction; do not add live refreshes merely to make a check
pass. See the updated adapter instructions below and [real-data evidence](../docs/verification/probe/2026-09-27/README.md).

# Cache-only frontend preview adapter

`scripts.preview_api:app` versions the standalone adapter formerly kept only at
`/tmp/vlr-preview/read_api.py`. Start it on a **separate loopback preview port**:

```sh
.venv/bin/uvicorn scripts.preview_api:app --host 127.0.0.1 --port 8103 --lifespan off
```

Point an isolated Next build at `http://127.0.0.1:8103/api/v1`. This process imports
no production FastAPI application/lifespan, starts no scheduler, performs no schema
setup and calls no refresh functions. It reads the configured Redis/Postgres; no
fixture hooks or cache mutation endpoints exist. Each route handler has an
8-second cancellation deadline, below the frontend optional-loader deadline.
Do not use this adapter as a replacement production API.

Player analytics now include:

- `/api/v1/players/{id}/dimensions?region=na&timespan=all`: reads only the selected
  cached cohort, shares the API's pure dimension computation and response shape.
  Missing/empty cohort returns 503; absent player in a populated cohort returns
  404. No scrape to confirm absence. NA/EU fallback remains in the Next loader.
- `/api/v1/trends/player/{id}?days=90`: reads banked snapshots in a transaction
  explicitly marked READ ONLY, uses the same pure aggregation as the backend,
  including current `R`/`Rnd` labels. No snapshots returns 404; existing but unrated
  or out-of-window snapshots produce a successful empty trend. Thin/flat history
  stays thin/flat; the adapter does not invent points.
- `/api/v1/player/{id}` continues to pass the cached bare detail verbatim, including
  agent stats and recent matches. No separate dimensions Next proxy is required:
  the player server component calls its dimensions loader directly.

The inherited listing, team-trend and search paths retain their cache/SELECT-only
behavior. Other unsupported paths return 503. Validate a new adapter on its own
port first. Applying it to an explicitly requested staging preview is distinct
from restarting production 8000/3000; keep those production services untouched.

```sh
.venv/bin/pytest -q tests/test_preview_api.py
```

The [player analytics audit](../docs/verification/player-analytics/2026-09-27/README.md)
records the layer comparison, desktop/mobile results and preview process scope.
