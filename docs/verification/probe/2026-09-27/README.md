# Real API probe and detail journeys — September 27, 2026

This pass used the authorized `http://10.0.0.21:8000` API on branch `v2`.
The endpoint is authorized for future VLR-API builds too. See the reusable
[probe instructions](../../../../scripts/README.md).

## Coverage and observations

Routes were inspected in `app/main.py`, `app/api/v1/routes.py` and
`app/api/status_html.py` before probing. `/health` is liveness; `/api/v1/status`
reads dependency/history/cache/scheduler state without refreshing. `/` and
`/status` expose the HTML dashboard and were inspected in source, not requested.
GET listings/details can scrape on cache miss; the client does not bypass the
shared upstream throttle (1.5 seconds minimum). The production process predates
recent source changes, so source inspection is not proof of deployed behavior.

The default pass made 14 sequential GETs, two seconds apart, with a 90-second
whole-request deadline, 600-second run budget and 2 MB response limit. No retries,
redirects, timeouts, 429s or unavailable responses occurred. Follow-up analytics
made three more sequential GETs with the same per-request deadline and spacing.
No raw payloads, cookie headers or exception text are retained.

| Endpoint (under /api/v1 unless noted) | HTTP | State | Time ms | Shape / count |
| --- | --- | --- | --- | --- |
| `/health` | 200 | populated | 5.7 | object |
| `/api/v1/status` | 200 | populated | 23.2 | object |
| `/api/v1/matches/results` | 200 | populated | 3.3 | array / 50 |
| `/api/v1/matches/upcoming` | 200 | populated | 2.7 | array / 30 |
| `/api/v1/matches/live` | 200 | empty | 96.4 | array / 0 |
| `/api/v1/rankings` | 200 | populated | 178.7 | array / 128 |
| `/api/v1/stats?region=na&timespan=all` | 200 | populated | 6.7 | object / 100 |
| `/api/v1/news` | 200 | populated | 2.2 | array / 30 |
| `/api/v1/events` | 200 | populated | 159.0 | array / 74 |
| `/api/v1/teams` | 200 | empty | 2.1 | object / 0 |
| `/api/v1/players` | 200 | empty | 2.2 | object / 0 |
| `/api/v1/match/753445` | 200 | populated | 173.5 | object |
| `/api/v1/team/8877` | 200 | populated | 113.4 | object |
| `/api/v1/player/3799` | 200 | populated | 43.5 | object |
| `/api/v1/trends/player/3799` | 200 | populated | 14.1 | object |
| `/api/v1/players/3799/dimensions?region=na&timespan=all` | 200 | populated | 3.5 | object |
| `/api/v1/trends/team/8877` | 200 | populated | 16.7 | object |

All 17 API responses supplied Date and application/json Content-Type. None
supplied the allowlisted freshness/cache headers, including X-VLR-Cache,
Cache-Control, Age, ETag or Last-Modified. Freshness is therefore unknown beyond
explicit stats/search envelope booleans. Do not infer cache hits from low latency.
The stats envelope reported stale=false and no error. Empty live matches can be
normal; blank searches intentionally return empty and do not test populated search.

Selected IDs came from the first valid numeric ID in each real listing:
match **753445** (results), team **8877** (rankings), player **3799** (NA stats).
Match detail had two teams and two maps but null series scores; team detail had
nine roster entries, five results and one upcoming match; player detail had three
agent rows and five matches. Player trend returned an object with zero rated
points; dimensions returned numeric scores. A populated object is not a claim
that every nested field is usable.

## Browser validation and investigation

Chromium at 1440 × 1000 followed actual links on port 3100:

| Journey | Listing ms | Click to detail ms | Result |
| --- | --- | --- | --- |
| Results → /match/753445 | 234 | 479 | Match report loaded |
| Rankings → /team/8877 | 153 | 384 | Karmine Corp loaded |
| Stats → /player/3799 | 134 | 427 | Notuud loaded |

All three had zero page errors and no horizontal overflow. These are desktop,
time-specific observations, not a new accessibility/mobile audit. Match rendering
reported unavailable round results for some rounds. Team loaded without notices.
Player identity lacked name/team; history and cohort panels showed unavailable.

The unchanged 3100 process runs `/tmp/vlr-preview/reliability-final`, with
`VLR_API_BASE=http://127.0.0.1:8101/api/v1` verified from only that environment key.
Its adapter is cache-only and does not implement player trends or dimensions;
these panels' unavailable states are preview coverage gaps, not API outages.
Direct API probes of both routes returned 200. The adapter implements team trends.
No preview/production service was reconfigured to hide these limitations.

The browser also exposed a concrete application defect: the player table showed
rounds/rating while the headline claimed rounds and rating were unavailable.
A single bounded cache-only GET confirmed real `agent_stats.stats` keys were
`Use, Rnd, R, ACS, K:D, KAST, ADR, KPR, APR, FK:FD, K, D, A, FK, FD`.
Frontend headline/agent selection and backend history aggregation recognized only
`RND` / `Rating`. Backend aggregation consequently discarded these rated snapshots.

The fix accepts the observed `Rnd` / `R` aliases only when historical keys are
absent. Raw payloads, stored snapshots, table columns, response envelopes and
rounding/fallback rules remain unchanged. Existing history benefits at read time;
no migration/backfill/cache flush is needed. Focused isolated tests cover weighted
results, main-agent selection, round coverage, no raw-row mutation, legacy-key
precedence and explicit missing values. Missing match series scores were not
changed without current upstream HTML evidence.

## Final fix verification

Probe commit `fbe5517` is separate from application fix `a251c99`.
The shell lacked HTTPS push credentials, so the connected repository-owner GitHub
account published separate commits through Git objects. Uploaded source trees
were checked against the reviewed local trees; branch publication uses a
non-force update. Commit IDs above are the published objects.
All final checks passed: **268 backend tests**, **348 frontend tests in 25 files**,
frontend ESLint, TypeScript and isolated webpack production build. Existing
Starlette/httpx deprecation, Vite CJS and React act warnings remain.

The final isolated build was started only on loopback 3101, using the existing
cache-only adapter. `fixed-browser.json` confirms real player 3799 now shows
504 known rounds, Sova, 1.98 rating and 228 weighted ACS, with no page errors or
horizontal overflow (209 ms page load). The former unweighted headline was 225.
This is a real cached payload; no response interception or failure injection was
used in either browser. The temporary 3101 process was stopped. Tests inject
failures only through HTTPX MockTransport or existing isolated mocks.
The first fixed-browser harness used an incorrect expected integer ACS (227);
the corrected check asserts the actual rounded weighted value, 228.

`fixed-browser.cjs` reproduces the single-route check after starting the isolated
build directory from `checks.json` with Next start, hostname 127.0.0.1, port 3101,
`VLR_API_BASE=http://127.0.0.1:8101/api/v1` and blank Twitch credentials. Use the
same browser environment below and stop only that temporary process afterwards.
Production 8000/3000 and preview 3100 retain their original PID/start times.

## Evidence and reproduction

- `api.json`: default bounded pass, selected IDs, shapes, headers and timings.
- `analytics.json` / `analytics.py`: three explicit direct-API follow-ups. Run from
  the repo root with `PYTHONPATH=. .venv/bin/python docs/verification/probe/2026-09-27/analytics.py`.
- `browser.json` / `browser.cjs`: existing 3100 click journeys, using the local
  `/tmp/vlr-browser-tools` Playwright installation. Launch with
  `PLAYWRIGHT_BROWSERS_PATH=/tmp/vlr-browser-tools/browsers`,
  `LD_LIBRARY_PATH=/tmp/vlr-browser-tools/sysroot/usr/lib/x86_64-linux-gnu` and
  `FONTCONFIG_FILE=/tmp/vlr-browser-tools/fonts.conf`. IDs are this pass's selections;
  use a new probe's selections for a future pass. Screenshots remain temporary QA
  artifacts, not cleared promotional assets.
- `checks.py`, `checks.json`, `logs/`: final complete checks. Build copies frontend
  source/config into a new temporary directory, excludes .env/.next, reuses installed
  dependencies, blanks Twitch credentials and uses an unreachable API origin to
  avoid API traffic during build. It does not touch the serving build.

## Remaining gaps

No claim of all IDs, all regions, fresh-cache status, live-match behavior, populated
search, news article details, every history route or deployment parity. The direct
API and 3100 keep their existing imported/build versions. Fix validation uses the
isolated build and tests, not a production deployment. Production has not loaded
the backend fix; 3100 has not loaded the frontend fix. The player analytics adapter
gap, absent source identity fields and match series-score provenance remain open.
