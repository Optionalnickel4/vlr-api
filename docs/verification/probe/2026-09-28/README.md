# Direct backend pass — September 28, 2026

Work was performed only on `v2`, starting at
`4f8cc004734342868ef2de8515d19059e13ffe6d`. Backend changes are committed separately
as **6725057**. No merge, branch checkout, push, production restart/deployment,
cache reset, Caddy edit, or frontend change was performed. Pre-existing modified
`.gitignore` and untracked `docs/SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md` were left
untouched and excluded from commits. Local branches were `master` and `v2`; there
was no local `main` ref. No default-branch ref was changed.

Read `CLAUDE.md`, `scripts/README.md`, the September 27 probe README, application
wiring, API routes, scrapers/selectors, search/refresh/trend services and relevant
tests. No root/ancestor AGENTS.md was found; frontend-only instructions were not
applicable. CLAUDE's statement that routes never trigger scrapes is outdated:
actual routes delegate cache-miss refreshes to services. The probe instructions
explicitly account for that behavior. Tests use fixtures/mocks and no live I/O.

## Live coverage and limits

Target: **http://10.0.0.21:8000**, directly, without frontend or preview adapters.
All **33 API requests** returned HTTP 200: 14 initial, 9 follow-up, one historical
identity comparator, and 9 final. There were no timeouts, transport failures,
429s, Retry-After headers, retries, or redirects. See [route-table.md](route-table.md)
for each route's shape, count and whole-request timing, and JSON for UTC start
times, bounded nested shapes and allowlisted headers. No full API/upstream
responses, secrets, cookies or exception payloads are retained.

Initial limits: 14 requests, 600 seconds total, 90 seconds/request, 2 MB decoded
body, two seconds after each completion. Follow-up: at most 9 requests/480 seconds,
60 seconds/request, 2 MB, three seconds apart. Comparator: one API request with
60 seconds/2 MB, followed after three seconds by one upstream request. Final:
9 requests/300 seconds, 60 seconds/request, 2 MB, three seconds apart. Each API
pass stops on timeout/transport failure, 429 or Retry-After. Known selected
details were revisited only for targeted field inspection/final verification;
there was no cache flush or repeated request for an unavailable ID.

IDs selected from the current initial listings:

- Match **753445**, first numeric results ID (same as September 27).
- Team **8877**, first numeric rankings ID (same as September 27).
- Player **36245**, first numeric NA/all stats ID (September 27 selected 3799).
- Player **3799** was used once separately as a clearly labeled September 27
  comparator, not claimed as the current listing selection.

Initial listings: 50 results, 30 upcoming, **0 live**, 128 rankings, 100 stats,
30 news and 70 events (previously 74). These are time-specific counts, not a
completeness/freshness guarantee. Initial responses ranged from 1.8 to 2370.8 ms.
Populated searches used names obtained from the selected detail responses:
`N4RRATE` returned one DB hit (36245); `Karmine Corp` returned two DB hits (12255,
8877). No autocomplete cache-miss query was added merely to exercise fallback.

Three additional upstream GETs used the application's shared-client accessor,
its truthful User-Agent and throttle, but streamed once without retry/redirect:
`/player/36245/?timespan=all`, `/753445`, and `/player/3799/?timespan=all`.
Each had a 45-second deadline and 2 MB body bound, with three-second spacing.
All returned 200; [upstream.json](upstream.json) and
[identity-compare.json](identity-compare.json) record timing and selected facts.
Only a match header and one recent-result card were saved as scoped test fixtures
(trailing line whitespace normalized), not entire upstream pages.

## Findings: source versus served behavior

| Finding | Classification and evidence | Action |
| --- | --- | --- |
| Match 753445 series scores null | **Confirmed backend parser defect in source and live.** Upstream header explicitly contains 0:2 in `.sp-hide`; old source only selects `.js-spoiler`. | Support both containers, require a complete numeric pair; preserve integer/null score shape and winner rules. Never infer series scores from map rounds. |
| Player recent results omit date | **Confirmed source data omission**, not an upstream gap. Current result card 753459 displays `2026/09/25 7:25 am`; old source/live omit it. | Add nullable `matches[].date` display string; preserve node separation and existing fields. No timezone or ISO timestamp inferred. This is recent results, not an expansion of `/history/player`. |
| Player 3799 missing real name/current team | **Expected missing upstream data.** API and current parser agree; real-name element exists but is empty, and no Current Teams heading exists. | Keep nulls. Do not borrow a past team or invent a name. |
| Player 36245 identity/history | Current upstream and live provide alias, real name, country and current club; live has 21 agent rows and five recent results with opponent/result/score/event. `/history/player?limit=3` returns populated identity/stats capture records. | No identity-selector rewrite warranted. Historical snapshots do not store full match lists. |
| Player trend 36245 has zero points | **Serving behavior lacks existing source fix a251c99.** A READ ONLY transaction read 27 snapshots, all inside 90 days; source produces 27 rated points. More decisively, the same three history rows returned by port 8000 produce three points in source while its trend returns zero. | Do not duplicate the existing R/Rnd alias fix or invent history. Deployment parity remains open. |
| `/teams` and `/players` empty without q | **Expected contract:** these are search endpoints, not directories; fewer than two normalized characters deliberately returns an empty envelope. | No listing conversion. Populated DB-backed search verified as above. |
| Player upstream 404 becomes 500 | **Source/test-confirmed defect**, not live-probed with a made-up ID. Existing team/match handlers already translate `VlrNotFound`; player did not. | Return consistent player 404. Tests retain 500 for unrelated scrape errors and 504 for deadline expiry. |
| Empty live list | **Valid empty state**, not an outage. Health/status succeed and other listings populate. | No fabricated live match or failure. In-progress score rendering remains unverified live. |
| Freshness headers absent | All responses supplied Date/Content-Type, but no allowlisted freshness/cache headers. Stats/search report stale=false/error=null. Current source rankings/events explicitly set X-VLR-Cache and Cache-Control; live did not. | Another source/serving behavior mismatch. Freshness otherwise unknown; latency, Date, dependency health and global scheduler state do not establish per-entity age. |
| Dimensions/team trends | Dimensions 36245 returns four numeric fields, empty low_confidence; team 8877 trend has 720 points and nine results. | Successful observed shapes, not a guarantee for other IDs/cohorts or metric accuracy. |

The final direct check still served `[null, null]` match scores, no `date` keys in
five player recent results, and an empty player trend. That is **not** a live
verification of the new fixes. Source/fixture tests establish the score/date/404
changes; the same-API-history-row comparison establishes source trend behavior.
Warm cached details may lack new additive fields until their normal refresh even
after code is deployed. No cache migration or fabricated history is needed.

## Service identity limitation

Initial read-only systemd inspection reported PID **61821**, started September 17
11:10:09 UTC. Inspection after final API checks reported PID **176198**, started
September 28 **14:26:46 UTC**, active/running, NRestarts=0. The interface owns
10.0.0.21 and port 8000 is listening; socket process ownership was not visible.
The lifecycle change was **not initiated by this pass**. Its cause was not
established; filtered read-only journal inspection exposed no matching systemd
lifecycle events. Do not describe the entire pass as one unchanged process.
[service-state.json](service-state.json) records only safe metadata.

Status returned `commit: unknown`, Redis=true and Postgres=true before and after
the change. Exact imported revision is unverified. The response mismatches
prove lack of parity with current source; service start time alone does not
identify deployed code. Neither health 200 nor all-200 probes prove that the
latest fixes are loaded.

## Tests and commands

Repository/service inspections included:

```sh
pwd
git status --short
git branch --show-current
git log -5 --format='%h %s'
systemctl show vlr-api --property=MainPID,ActiveState,SubState,ExecMainStartTimestamp --no-pager
systemctl show vlr-api --property=MainPID,ActiveState,SubState,ExecMainStartTimestamp,WorkingDirectory,FragmentPath,NRestarts,Restart --no-pager
ss -ltnp 'sport = :8000'
ip -brief address
```

Exact probe commands, run from the repo root in this order:

```sh
.venv/bin/python scripts/probe_api.py --base-url http://10.0.0.21:8000 --output docs/verification/probe/2026-09-28/api.json
PYTHONPATH=. .venv/bin/python docs/verification/probe/2026-09-28/followup.py
PYTHONPATH=. .venv/bin/python /tmp/vlr-upstream-inspect.py
PYTHONPATH=. .venv/bin/python /tmp/vlr-history-check.py
PYTHONPATH=. .venv/bin/python docs/verification/probe/2026-09-28/identity_compare.py
PYTHONPATH=. .venv/bin/python docs/verification/probe/2026-09-28/final_check.py
```

The two temporary scripts are retained verbatim as [upstream_capture.py](upstream_capture.py)
and [history_source.py](history_source.py); substitute those paths to reproduce.
The upstream script creates temporary DOM excerpts and prints bounded excerpts;
the history script uses SET TRANSACTION READ ONLY, a 10-second SQL statement
limit and at most 1000 selected-player rows. It opens no application lifespan or
scheduler. Reproduction reruns real GETs and overwrites evidence: do not run all
passes repeatedly or in parallel. Test fixtures were reduced from the temporary
excerpts to the header and first result card only.

```sh
.venv/bin/pytest -q tests/test_match_detail.py tests/test_scrapers.py tests/test_detail_reliability.py > /tmp/vlr-red-tests.log 2>&1
.venv/bin/pytest -q tests/test_match_detail.py tests/test_scrapers.py tests/test_detail_reliability.py tests/test_player_trends.py tests/test_search.py tests/test_dimensions.py tests/test_probe_api.py
.venv/bin/pytest -q > /tmp/vlr-backend-tests.log 2>&1
.venv/bin/pytest -q > /tmp/vlr-backend-tests-final.log 2>&1
.venv/bin/pytest -q tests/test_status.py > docs/verification/probe/2026-09-28/logs/status-tests.log 2>&1
.venv/bin/pytest -q tests/test_match_detail.py tests/test_scrapers.py
git diff --check
```

TDD: five expected failures before fixes (scores, dates, player 404), 59 passes.
The first implementation exposed date/time text-node concatenation; preserving
separation fixed it. Focused combined suite then passed **137 tests**. One
additional upcoming-score regression was added before the full run. The first
full suite had 304 passes and one existing receipt-test isolation failure: its
fake `app` inherited real `app.*` modules imported by other tests. The test now
isolates that package and restores sys.modules afterwards; production receipt
validation is unchanged. Final full suite: **305 passed**, one existing
Starlette/httpx deprecation warning. Status metadata was updated to 305 and its
six tests passed; normalized fixture excerpts passed all 43 scraper/detail tests.
Logs retain both the failure and successful full run. No frontend tests/builds
were run, because no frontend changes were made.

## Remaining work and later deployment

Review and explicitly deploy the `v2` backend artifact later, including the
already-committed history alias and freshness changes; this pass did not deploy.
Record an actual build identity, then repeat a small direct check after normal
cache refresh/expiry. Do not flush production caches to force visible success.
The player 404 behavior is source-tested only, and autocomplete fallback,
multiple regions/windows, unknown cohorts, in-progress matches and resilience
under a real outage were not load-tested or fault-injected. No per-entity capture
time is available on most bare routes; leave freshness unknown until backed by
acquisition metadata. Date display strings have no inferred timezone. Search
can return multiple matching teams and must not silently pick the first for
Jarvis. A short [Jarvis design proposal](JARVIS_DESIGN.md) covers stable shape,
authentication, rate limits, freshness, failures and service reuse. **No new
Jarvis endpoint was implemented.**
