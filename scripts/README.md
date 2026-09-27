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
The existing preview on 3100 uses its cache-only adapter on 8101, which does not
implement every API route. Report this distinction; do not reconfigure it merely
to make a check pass. See [real-data evidence](../docs/verification/probe/2026-09-27/README.md).
