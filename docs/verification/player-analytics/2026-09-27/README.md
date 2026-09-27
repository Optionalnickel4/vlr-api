# Player analytics preview follow-up — September 27, 2026

The port 3100 preview now renders player **3799** (Notuud, selected from NA stats
in the preceding bounded-probe pass) with dimensions, banked history, agent stats
and recent matches. The adapter omission was real; the data was not wholly absent.
Fix commit: `2881275`. No new frontend application changes were needed: the rebuilt
preview also picks up the already-committed `R`/`Rnd` compatibility correction.

## Layer-by-layer diagnosis

| Feature | API :8000 before | Adapter :8101 before | Next loader/proxy before | Port 3100 after |
| --- | --- | --- | --- | --- |
| Dimensions | 200; all four numeric fields | 503; route unsupported | Server-only `getPlayerDimensions` tried NA then EU, both failed | Four bars and radar, NA/all cohort |
| Trends | 200; object, zero rated points | 503; route unsupported | `/api/trends/player/3799` returned 200 with empty stale/error envelope | 20 rated captures, rating 1.98, flat-history explanation |
| Agent stats | 200; three rows with `Rnd`/`R` | 200; passed through unchanged | `getPlayer` and `/api/player/3799` preserved three rows; old built headline missed aliases | Three rows, 504 known rounds, Sova, 1.98 headline rating, ACS 228 |
| Recent matches | 200; five embedded match rows | 200; passed through unchanged | Normalized five matches correctly | Five match rows at both widths |

The backend worker started September 17 and has not loaded the previous aggregation
fix. Its zero-rated-points response is not evidence that history was never captured.
The new read-only adapter uses the repository's corrected pure aggregation over
existing Postgres snapshots and returns **20** rated points. No migration, backfill,
cache flush, extra source scrape or fabricated history was needed for recovery.

The Next player server component calls `getPlayer`, `getPlayerTrend` and
`getPlayerDimensions`; the last loader calls the adapter directly and has no separate
Next dimensions proxy. The player and trend proxy routes preserve their normal
`{data, stale, error?}` contracts; HTTP 200 alone is insufficient to infer success.
`normalizePlayerDimensions` and `normalizePlayerTrend` preserve the recovered fields.
The existing frontend correctly suppresses the trend line because the ratings are
flat, while retaining the exact captures behind the disclosure. Name, team and role
remain unavailable where source detail lacks them. No invented identity is added.

## Bounded observations

`probe.py` imports the documented `scripts.probe_api.request` helper. The initial
pass made **8 sequential GETs**, two seconds apart: 3 to the authorized backend,
3 to the old adapter and 2 to Next proxy routes. Each had a 90-second deadline and
2 MB decoded-body cap; it stops on timeout, transport failure, 429 or Retry-After.
No retries, redirects, timeouts or live failure injection occurred. The follow-up
used `--skip-backend` for **5** sequential adapter/proxy GETs; it did not repeat
source-triggering backend requests. Two extra isolated-adapter GETs verified the
new analytics before updating the staging preview. Browser page requests use
normal application fan-out only against the cache/SELECT-only adapter; they cannot
scrape VLR.gg. This was not a load test.

| Layer / route | Before status / ms | After status / ms | After shape |
| --- | --- | --- | --- |
| API `/api/v1/player/3799` | 200 / 9.0 | Not repeated | Object: 3 agent rows, 5 matches |
| API `/api/v1/trends/player/3799?days=90` | 200 / 9.5 | Not restarted/repeated | Object: 0 rated points in deployed worker |
| API `/api/v1/players/3799/dimensions?region=na&timespan=all` | 200 / 3.9 | Not repeated | Object: 4 dimensions |
| Adapter `/api/v1/player/3799` | 200 / 2.6 | 200 / 11.8 | Bare detail unchanged |
| Adapter `/api/v1/trends/player/3799?days=90` | 503 / 1.7 | 200 / 54.4 | Bare object, 20 rated points |
| Adapter `/api/v1/players/3799/dimensions?region=na&timespan=all` | 503 / 2.0 | 200 / 3.7 | Bare object, 4 numeric dimensions |
| Next `/api/player/3799` | 200 / 8.0 | 200 / 50.2 | Envelope, 1 detail, 3 agent rows, 5 matches |
| Next `/api/trends/player/3799?days=90` | 200 / 5.5, unavailable envelope | 200 / 11.6 | Envelope, 1 trend with 20 points |

Exact shapes, UTC times, freshness headers and envelope flags are in `before.json`
and `after.json`. Backend responses exposed Date but no cache freshness indicator.
Adapter detail reported `X-VLR-Cache: fresh` and `Cache-Control: no-store`; analytics
match the API's header behavior and do not manufacture freshness or capture dates.
All summaries omit raw payloads, source error text and credentials.

## Fix and isolated failure checks

`scripts/preview_api.py` versions the formerly temporary adapter and preserves its
listing/search/team/detail behavior. Added dimensions read only the selected Redis
cohort and call the shared pure `compute_dimensions`. Missing/empty cohort is 503;
a player absent from a populated cached cohort is 404, enabling the existing NA→EU
fallback. Unlike the public API, the adapter never refreshes to confirm absence.

Added player trends execute `SET TRANSACTION READ ONLY` before SELECT and share
`build_player_response`. No snapshots is 404. Existing snapshots with no parseable
rating produce a successful empty series. The adapter imports no application
lifespan, initializes no schema, runs no scheduler and exposes no fixture/reset
routes. A route-handler deadline cancels storage work after eight seconds. The
first middleware-based deadline prototype left a child task running; the final
handler wrapper and elapsed-time regression verify actual cancellation. Validation
errors keep their HTTP status and unexpected storage errors do not leak details.

Sixteen new isolated tests cover NA/EU computation compatibility, missing/malformed
cohorts, missing members, validation-before-storage, read-only transactions,
missing/unrated/one-point histories, timeouts, failure redaction, no refresh calls,
verbatim agent/match pass-through and rejection of POST. Existing frontend tests
cover fallback, stale versus absent dimensions, flat/thin history and alias handling.
No failure injection touched a running service.

## Chromium and verification

Real player 3799 was viewed at **1440 × 1000** and **390 × 1000** before and after,
with no response mocks. `browser-before.json` records the old unavailable analytics
and old headline. `browser-isolated.json` records the fixed build on 3101/8103;
`browser-after.json` records the final serving 3100/8101 preview.

Both final widths show three agent rows, five match rows, twenty accessible rating
captures after opening the disclosure, four percentile bars and the radar. The
percentile labels are Firepower 29th, Entry 31st, Consistency 94th and Clutch 46th
within NA. Both show the honest flat-history notice, zero page errors and no page
horizontal overflow. Tables scroll within their own keyboard-focusable containers;
the final harness uses ArrowRight and waits for scrolling (End was not a horizontal
scroll assertion). Mobile and desktop screenshots were inspected/retained under
`/tmp/vlr-analytics-preview-*.png`, not published as promotional assets.

Final checks all passed: **284 backend tests**, **348 frontend tests**, frontend
lint, TypeScript and an isolated webpack production build. Logs and exact commands
are in `logs/`, `checks.py`, and `checks.json`. Existing Starlette/httpx, Vite CJS and
React act warnings remain. The build excludes .env/.next and points build-time API
fetches at an unreachable local origin. No production build directory was touched.

## Preview scope and reproduction

Only staging preview PIDs 140919 (8101 adapter) and 153938 (3100 frontend) were
replaced, after isolated tests/build/browser validation. New preview PIDs are
158317/158318. Production API PID 61821 and frontend PID 308 retain their original
start times. The preview frontend runs the immutable build directory recorded in
`operations.json`, points at `http://127.0.0.1:8101/api/v1`, and has blank Twitch
credentials. The old temporary adapter file is left intact as historical evidence;
the new process imports `scripts.preview_api:app`. Temporary 3101/8103 processes
were stopped. `.gitignore` and the untracked plan retain their original hashes.

From the repo root:

```sh
PYTHONPATH=. .venv/bin/python docs/verification/player-analytics/2026-09-27/probe.py \
  --skip-backend --output /tmp/player-analytics.json
.venv/bin/pytest -q tests/test_preview_api.py
```

Omit `--skip-backend` only when another bounded comparison is needed. The harness
uses the one selected ID, not an ID scan. For browser reproduction, use the local
Playwright install with `PLAYWRIGHT_BROWSERS_PATH=/tmp/vlr-browser-tools/browsers`,
`LD_LIBRARY_PATH=/tmp/vlr-browser-tools/sysroot/usr/lib/x86_64-linux-gnu` and
`FONTCONFIG_FILE=/tmp/vlr-browser-tools/fonts.conf`, then run:

```sh
node docs/verification/player-analytics/2026-09-27/browser.cjs \
  http://10.0.0.21:3100 /tmp/player-browser.json inspect
```

See `scripts/README.md` for isolated adapter startup. Never run failure fixtures in
this preview. The existing GitHub connection publishes reviewed commits with tree
hash verification and a non-force branch update because shell HTTPS credentials
are unavailable.

## Remaining gaps

Production still needs a separately authorized deployment to load the prior
`R`/`Rnd` fix; this task did not restart it. One real player was sampled, not every
player/region. EU fallback, absent cohorts/players, unreadable storage and empty
history were tested only with isolated fixtures. Cache expiration remains an honest
503 in this cache-only preview. Flat history is intentionally not charted. Source
identity fields remain missing, and earlier match-series-score/proxy-timeout/public
launch questions are outside this focused player-analytics pass.
