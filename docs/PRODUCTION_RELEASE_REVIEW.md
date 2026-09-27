# Production release review — 2026-09-27

**Recommendation: NO-GO for production deployment yet.** The candidate passes final tests and build. The follow-up resolved representative real cold-cache staging. Full backend rollback and effective public-ingress deadline attestation remain unresolved. Durable capacity now passes on the enlarged application-host disk; resolve the remaining gates before scheduling a cutover. No production service was restarted or reconfigured. This review authorizes no deployment.

**Exact application release SHA: `9301682c4165d7507e49d6ad7678d14ca9df377e`.** This was both `HEAD` and fetched `origin/v2` at review start. The subsequent review commit contains documentation/evidence only; deploy the pinned application SHA, not a moving branch. Last application change is `2881275832168dd33f34ca0e7f6e5c14c50bff9d` (preview adapter). The aggregation fix that production needs is **`a251c99ade3e8d426e2782ab5d140815db1f33d4`**.

Evidence: [release verification directory](verification/release/2026-09-27/), particularly `runtime-before.json`, `configuration.json`, `parity.json`, `checks-final.json`, `api-smoke.json`, and `preview-analytics-smoke.json`. Existing [broadcast audit](BROADCAST_PREDEPLOYMENT_AUDIT.md) and [analytics trace](verification/player-analytics/2026-09-27/README.md) provide broader controlled/browser coverage; they are not fresh production tests.

## Current gate follow-up

The [gate verification report](RELEASE_GATE_VERIFICATION.md) supersedes the initial gate assessment below and records commands, pass criteria, results and remaining risks. **Application release remains `9301682c4165d7507e49d6ad7678d14ca9df377e`**; no application or live configuration fix was made. The latest documentation commit is separate from that release.

| Gate | Current result |
| --- | --- |
| Rollback provenance | **Unresolved.** Exact old backend remains unattested. A 66,175,718-byte historical backend archive restores with 5,752 matching hashes and serves isolated health/history; a new isolated candidate→fallback Uvicorn switch preserves newer database/cache sentinels and runs a scheduler tick, but schema startup and integrated full-service recovery remain unverified. Frontend restoration passes, including a durable second extraction |
| Ingress deadlines | **Supplied route compatible; effective settings unresolved.** Owner supplies Cloudflare Tunnel `meowth` → Caddy localhost:80 → Next `10.0.0.21:3000`. Public static curl returns 200 through Cloudflare/Caddy with matching bytes. Excerpts are not runtime attestation; existing isolated 12/80/90-second tests remain the deadline evidence |
| Cold-cache staging | **Passed for the selected sample.** Prior match/team/player cold and warm API/browser checks retained; no new VLR contact |
| Build/backup capacity | **Passed for the measured durable layout.** Disk is now 21,024,690,176 bytes; 11,373,678,592 free after durable frontend, backend and database restores. Additional conservative budget 4,616,978,432 includes 2 GiB reserve and leaves 6,756,700,160 bytes |

Previously completed checks pass (not repeated for this documentation-only follow-up): **284 backend tests, 348 frontend tests, lint, TypeScript and a clean isolated webpack production build**. All 511 archived source blobs still match the release SHA. Private test servers are stopped. Production processes, service/environment files, `.gitignore` and the untracked plan remain unchanged. No production detail GET, cache mutation or proxy change was used to close a gate. Backups and exact configuration copies are private under `/home/builder/vlr-gates-private`, never in Git; the earlier tmpfs restores were removed after verification; new durable restore copies remain under `/home/builder/vlr-recovery-check`. The candidate build/source remain; its redundant private `node_modules` was removed after verification to restore host headroom, so reinstall the pinned lockfile before using that isolated directory again.

The conditional deployment sequence below remains a planning reference, **not an executable GO**. Required next actions are recovery and isolated full-service verification of an attested backend artifact, and owner-supplied effective-ingress setting attestation. The [application-only follow-up](RELEASE_GATE_VERIFICATION.md#application-only-recovery-follow-up--2026-09-27) records confidence by source, the executed storage-preserving switch, smallest artifact/deployment changes and narrowly scoped operator collection commands. No Caddy LXC access is requested. Capacity needs no further increase for the measured layout. The gate report specifies the target host, artifact/space requirements, expected effect and reversal; current whole-LXC disk rollback could revert Postgres/Redis and is not an acceptable application rollback. Browser/content polish is optional and cannot replace those actions.

## Latest application-only recovery result

**NO-GO remains.** Fresh read-only systemd/proc/journal observations cannot identify the loaded production source/runtime: service PIDs/start times are unchanged, `/proc` identity reads are denied, and the restricted journal view has no startup entries. The historical bundle remains an identified fallback, not an attested match to production.

The new [recovery evidence](verification/release-recovery/2026-09-27/recovery.json) rechecks **5,752 artifact hashes** and switches isolated single-worker Uvicorn from candidate source to historical source while keeping the same private PostgreSQL and Redis running. Both versions pass health/history and dependency checks; eight scheduler jobs have next-run times and one empty-live-list job completes per process. All four history-table fingerprints, a newer row and newer cache sentinels survive. No database/cache restore occurs during the application switch.

To honor the no-migrations boundary, the harness substitutes a database read check for `init_db`. Therefore normal schema startup, all scheduler refresh paths, systemd switching and integrated restored frontend/backend recovery are **not proven**. Full-service recovery and exact backend provenance stay open. Whole-container rollback could revert newer data and remains unacceptable. Supplied ingress configuration remains compatible; only active Caddy configuration plus applied tunnel/edge-policy receipts can attest effective deadlines. Static curl and source configuration cannot do so.

Only the new recovery harness and documentation/evidence checks ran; previous cold-cache tests and application checks remain valid. Private processes are stopped, protected files and production service identities are unchanged. Latest disk remeasurement is recorded with the new evidence; the additional release budget and reserve still fit.

## What is actually running

| Layer | Observed production | Candidate / staging |
| --- | --- | --- |
| API | `vlr-api.service`, PID 61821, started September 17 at 11:10:09 UTC; one Uvicorn worker on port 8000, no reload | Candidate changes are on disk but are not loaded by this worker |
| Frontend | `vlr-frontend.service`, PID 308, started September 3 at 04:02:56 UTC; Next production server on port 3000 | Staging port 3100, PID 158318, separate compiled build |
| Frontend artifact | `/opt/vlr-api/frontend/.next`, build ID `5RXlwj7jwc2eDLWI_-439`, BUILD_ID timestamp August 26 at 05:25:27 UTC | 134 tracked frontend source/config/asset files match candidate in `/tmp/vlr-analytics-build-64598m15`; new release build independently completed |
| Preview API | Not used by production | PID 158317, loopback 8101, `scripts.preview_api:app`; cache/SELECT-only, no scheduler, schema setup or source refresh |
| Backend identity | `/api/v1/status` reports `commit: "unknown"` | Release identity must be established from pinned checkout + process/artifact evidence, not assumed from current on-disk HEAD |

**An exact production source SHA cannot be honestly attested from this host.** The running API does not report one, its source directory has advanced while the worker remains alive, and the old frontend build has no source-commit manifest. The checkout reflog records `32e7e23bbf1435163f0660ed74196a4704eff51a` before the September 17 map-name fix `139378cb7505c6257c7b69da3491e382c4ebf0bc`. That fix was committed 34 seconds *after* API startup, so it may have been loaded from then-uncommitted source; startup date alone cannot prove inclusion. Team-search routes are present in the old API. The August frontend artifact predates both commits. These are provenance bounds, not an invented production SHA.

All September 26–27 application commits below postdate both running production artifacts. Their absence is supported by process/build dates, source changes, and the explicit aggregation behavior comparison. Full hashes for the entire post-`139378c` range, including documentation commits, are in [commits.txt](verification/release/2026-09-27/commits.txt).

## Changes production lacks

| Exact commit | Missing behavior |
| --- | --- |
| `93ea25ed105b2349a96e262a176241a44cc36906` | Rankings/events retain last successful arrays, coordinate API/scheduler refresh with Redis leases and backoff, disclose freshness; truly cold failure is 503 |
| `ff1af82822f844fcd0b507aa1ffcda7b722bafe6` | Frontend upstream deadlines and live-score retention |
| `ca2ceb9625d395f81a5f52493b3df38033b8275c` | Player-search race protection and keyboard selection |
| `80425dbd3390e401c08269c2ab083f394b891c7b` | Shared accessible site shell |
| `071c627a898721aa39380c91e946366685bce333` | Independently streamed homepage match coverage |
| `d71f3891adc656c75d81309651026bbc1c18c4a4` | Broadcast homepage and fixed responsive ticker |
| `0fa35c488a12d8742ef02eb749c1842781f068d3` | Broadcast match detail |
| `85999edae76f11b8957c1b49863781f12ccab069` | Broadcast team detail |
| `20237af01053fd8a497b05ea09c0df14cb3d441a` | Broadcast player detail |
| `18a128dfb9e5dce985fec6692274e2662767f61e` | Broadcast schedule/results |
| `d9e6c2da9ef8ba9bf2cdea4df9e47294494f0627` | Broadcast regional rankings/stats |
| `5131fd1d10552824d4b788df87f01d8b2b05852c` | Broadcast news feed and reuse inventory |
| `734396091544959fcb732d330a2c6f402f00c85e` | Propagate backend retained-cache headers into frontend stale flags |
| `5b5355b6a0a1cbb524554bde443f9117f92fd061` | Validate live responses, retain last good scores, disclose failure, serialize/abort polling and stop at final |
| `c48b91f3942bd419b58060cfcbb2c9bdec59faa3` | Label retained live ticker statistics as stale |
| `cac586af15db04c0edd61fc7f120f832706bcda1` | Withhold unsupported cross-region upset claims |
| `1eb3dc6218a4b134982b90704ef5fc801657335e` | Initial detail loading: 90-second frontend budget, 80-second backend budget; 5-second best-effort history writes after valid cache publication |
| `a251c99ade3e8d426e2782ab5d140815db1f33d4` | Backend history aggregation and frontend player headline accept current `R`/`Rnd` as well as historical `Rating`/`RND`; historical keys retain precedence |
| `fbe551700b3898c9cee6fe9c19a6674bd2fbf1b0` | Bounded GET-only observation tool; operator tooling, not a production daemon |
| `2881275832168dd33f34ca0e7f6e5c14c50bff9d` | Read-only preview dimensions/trends with an eight-second handler deadline; staging tooling, not a substitute production API |

The prior aggregation fix is **not** merely the adapter fix. Fresh observation of player 3799: production returns zero `rating_trend` points; the corrected adapter reads **20** from the same banked history; the Next preview returns **20** `ratingTrend` points. Dimensions have four numeric fields at both layers. The preview preserves three agent-stat rows and five matches. Applying the backend fix recovers existing captures at read time: no migration, backfill, rescrape or cache flush is required. The frontend also needs rebuilding to fix its headline independently. Flat history should remain disclosed as flat, not rendered as invented movement.

## Configuration and dependencies

Installed units differ from the repository templates: **both run as root**, not template user `vlr`. API WorkingDirectory is `/opt/vlr-api`; ExecStart uses its `.venv/bin/uvicorn app.main:app`, port 8000, one worker. Frontend WorkingDirectory is `/opt/vlr-api/frontend`; ExecStart uses its `node_modules/.bin/next start`, port 3000. Both bind all interfaces and use `Restart=always`, `RestartSec=5`. API orders after network, PostgreSQL and Redis; frontend orders after API. `After=` is ordering, not dependency readiness or a guarantee to start dependencies. Only network is a `Wants=` dependency. No separate scheduler unit is installed; status confirms in-process jobs are scheduled. Do not add another scheduler or increase workers in this release.

Only environment-variable **names** were reported; no values are included:

- Backend `/opt/vlr-api/.env`: `VLR_DATABASE_URL`, `VLR_REDIS_URL`, `VLR_USER_AGENT`, `VLR_MIN_REQUEST_INTERVAL`, `VLR_ENABLE_SCHEDULER`.
- Frontend `/opt/vlr-api/frontend/.env`: `VLR_API_BASE`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `TWITCH_FEATURED`. Frontend unit also sets `PATH`.
- Supported backend overrides: `VLR_BASE_URL`, `VLR_REQUEST_TIMEOUT`, `VLR_MAX_RETRIES`, `VLR_API_PREFIX`, and `VLR_TTL_LIVE`, `VLR_TTL_RESULTS`, `VLR_TTL_MATCHES`, `VLR_TTL_EVENTS`, `VLR_TTL_RANKINGS`, `VLR_TTL_PLAYERS`, `VLR_TTL_TEAMS`, `VLR_TTL_NEWS`, `VLR_TTL_SEARCH`, `VLR_TTL_STATS`. No new environment variable is required by this release.
- `VLR_API_BASE` is server-only and must target the production FastAPI API prefix, never preview 8101. Twitch remains optional. Environment files on disk are readable for name inspection; the root processes' actual environment was not dumped or attested. Validate effective configuration during operator preflight without printing values.

PostgreSQL 17 main and Redis are active. Status reports both healthy. A read-only database query confirms UTF8 for the application database and both templates. Baseline row counts: match results 1,572; ranking snapshots 106,077; player snapshots 14,792; team snapshots 1,009. Counts naturally advance. Redis reports successful RDB persistence, AOF disabled, `noeviction`; recent writes can be newer than its last disk snapshot. Do not restart Redis as part of this application release.

No changes to models, migrations, dependency manifests/lockfile, or deploy templates occur between the old August source baseline and this candidate. API startup still runs existing `create_all` and additive `IF NOT EXISTS` migrations. No release-specific schema change is needed. Existing Redis primary keys and bare JSON values stay compatible; rankings/events add `:retained` and `:refresh` keys. Old code ignores those extra keys on rollback. Retained copies first appear after a successful new-code refresh; do not assume the upgrade instantly seeds every region.

**Reverse proxy:** user-supplied excerpts establish Cloudflare Tunnel `meowth` → Caddy on the same separate LXC (`http://localhost:80`) → Next `10.0.0.21:3000`. A bounded public static curl returned 200 through Cloudflare/Caddy and matched production asset bytes; a Python client received 403, cause unknown. Supplied settings are compatible with the 80/90-second application limits under documented defaults, but omitted/effective configuration and long-response behavior remain unattested. The [gate verification report](RELEASE_GATE_VERIFICATION.md#public-ingress-supplied-configuration-observed-request-remaining-uncertainty) separates owner evidence, public observations and isolated deadline tests. No LXC access or live proxy changes are requested. Ordinary frontend loaders/proxies retain their intentional 10-second budgets.

Backend and frontend are contract-compatible for a brief sequential rollout: backend contracts remain unchanged (bare listings/details plus the existing stats/search envelopes), and frontend routes retain envelopes. **Deploy backend first, then the matching frontend in the same maintenance window** to deliver the complete reliability behavior, stale indication and both aggregation corrections. An atomic simultaneous restart is unnecessary; a frontend-only release leaves backend history/reliability defects, and a backend-only release leaves the old UI/headline.

## Initial verification at the pinned SHA (historical; fresh rerun above)

A clean `git archive` of the exact release SHA was extracted outside production paths (all 511 tracked file blobs reverified unchanged after the checks); no environment files or production `.next` were copied. `npm ci --no-audit --no-fund` installed the committed lockfile. Python 3.13.5, Node 22.23.3 and npm 10.9.9 were used. Python reused the installed virtualenv with the archive first on `PYTHONPATH`; the installed package/version inventory is recorded. Python requirements remain unpinned, so preserve this environment or reproduce its recorded versions rather than upgrading dependencies during cutover.

| Check | Final result |
| --- | --- |
| Backend `python -m pytest -q` | **284 passed**; isolated test Redis only, no production lifespan/scheduler |
| Frontend `npm test` | **348 passed** |
| Frontend `npm run lint` | Passed |
| Frontend `npm run build -- --webpack` | Passed, optimized production build |
| Frontend `tsc --noEmit --incremental false` | Passed after build, including generated route types |

The initial concurrent run had one five-second subprocess timing failure in `test_scheduler_process_and_stale_api_requests_share_lease`; build and TypeScript subsequently hit 360-second limits under severe memory pressure. The first frontend run also exited zero without a complete suite summary, so it was not accepted as full coverage and was repeated. These initial results are retained in the logs, not hidden. The archive/dependencies occupied ~769 MB on memory-backed `/tmp`; moving this review's files to disk and rerunning checks serially resolved them (backend 3.09 seconds). There were no source changes or weakened assertions. No verification children remained after those runs. Existing Starlette/httpx, Vite CJS and React act warnings remain.

The successful build lives at `/home/builder/vlr-release-review-9301682/frontend/.next`. Build-time fetches used an unreachable local endpoint, scheduler/storage settings were isolated, and Twitch was disabled. This validates compilation and graceful unavailable data, not production credentials. The exact production command for this candidate is **`npm run build -- --webpack`**; do not silently substitute the untested default bundler. `next start` serves `.next`; source edits alone are not deployment. Build outside the directory currently served, then switch to a completed artifact.

### Initial bounded smoke observations (superseded where noted above)

The standard probe made 14 sequential GETs to the authorized API: health/status, nine listings/search controls, then selected match 753445, team 8877 and player 3799. All returned 200; latency was 22.7–924.2 ms. Live and blank team/player searches were legitimately empty. Missing freshness headers mean unknown freshness, not proven fresh cache. Request limits: 90 seconds including body, 2 MB decoded body, two-second spacing, 600-second total; no retries/redirects, stop on timeout/transport/backoff. Normal API GETs may trigger throttled refresh and cache/history writes on a miss; no forced miss was introduced.

A separate 12-request sequential pass (300-second total, same per-request/body/spacing bounds) compared two backend analytics routes, two adapter analytics routes, five Next proxy routes, two preview HTML pages and production homepage. It found the 0→20 history difference, populated dimensions/rankings/team/player/trend envelopes, and successful HTML transport. Preview match 753445 returned **200 with unavailable data, `stale: true` and an error**. Its cache had been available in the earlier API pass; this later cache-only observation cannot refresh it. Do not count the HTTP status as a pass. The preview adapter has unsupported routes and deliberately returns unavailable for expired detail keys.

These are cached/read-path smoke checks, **not** forced-cold, concurrent-load, external-edge or new browser-rendering evidence. No cache flush, bulk prewarm, direct source crawl or load test was performed. The earlier desktop/mobile Chromium evidence remains applicable by 134-file preview source parity, but was not rerun here. Production frontend HTML was received; that alone does not validate its UI.

## Gates before deployment — revised

1. **Rollback/provenance — unresolved:** retrieve the exact old backend source/runtime from an owner-held deployment bundle or backup. Current source cannot recreate the old in-memory worker. The preserved frontend archive is independently verified but cannot establish the missing backend revision or the old frontend's source revision. Full rollback is blocked until provenance and isolated backend restoration are proven.
2. **Production path/timeouts — effective settings unresolved:** supplied tunnel/Caddy configuration is compatible, and bounded public static delivery succeeds. Owner attestation of effective omitted/global/edge settings remains necessary to close the stricter ingress gate. Do not infer it from isolated application tests, request LXC access or modify the live proxy.
3. **Real cold-cache staging — resolved for the three-ID sample:** private empty caches and a new database returned populated real match/team/player objects, then fast warm responses; Chromium rendered each warmed page. Exactly three sequential source requests occurred. This is neither a cold-browser measurement nor a load/availability SLA; optional cohort analytics were intentionally prevented from triggering additional source requests.
4. **Capacity — passed for measured durable layout:** the application filesystem was enlarged before this follow-up. Durable frontend/backend/database restore copies fit with 11.374 GB free; a further 4.617 GB budget including 2 GiB reserve leaves 6.757 GB. See the gate report for exact allocations. Off-host backup and Redis disaster recovery remain unverified; neither is claimed by the local restoration tests.

Optional follow-up, **not a reason to modify code in this documentation release**: Firefox/WebKit/screen-reader checks; broader player/region samples; Twitch-enabled preview; source-missing identity/series-score investigation; ticker capture-time metadata; promotional screenshots and editorial polish. Missing source values must stay honestly unavailable. The previous audit records a separate public-launch/content-permission dependency; its scope is not resolved by this technical review. Browser/content polish does not substitute for the unresolved operational gates above, and this review makes no new legal determination.

## Conditional deployment sequence — blocked; future authorized window only

1. Resolve and record all gates. Re-fetch `v2`, verify the candidate still has the exact approved source tree, and pin `9301682c4165d7507e49d6ad7678d14ca9df377e`. A newer application commit requires renewed review. Do not begin while any of the revised gates remains unresolved. Record UTC time, unit files/drop-ins, PID/start times, frontend BUILD_ID, source/artifact checksums, package inventory, scheduler mode, environment **names** and dependency health. Preserve secret files privately with original permissions; do not commit them or print values.
2. Take a consistent custom-format `pg_dump` using existing protected authentication to a new protected backup file on the verified durable layout (and copy off-host if required by disaster-recovery policy); check `pg_restore --list` and test restoration to an isolated database. Capture Redis with the established authenticated RDB backup procedure (e.g. a replication snapshot into a protected backup file), validate it off production, and preserve its configuration/persistence files. Backups contain private data and must stay outside Git. Do not use `FLUSHDB`, `FLUSHALL`, delete `vlr:*`, recreate the database/cluster, or run the destructive fresh-install instructions in README/DEPLOY.
3. Stage an immutable release checkout and a separate virtualenv/dependency directory on a volume with headroom. Install Python with the recorded versions and this release source; run `npm ci`, then `npm run build -- --webpack` in its frontend directory. Keep build-time source calls disabled; supply production runtime configuration securely at service startup. Repeat the final checks on the resulting artifact if dependencies/toolchain differ. Ensure selected release paths are readable by the installed service identity. Save old units and complete rollback artifacts before switching.
4. Prepare exact systemd overrides for the chosen absolute release directories: API WorkingDirectory/ExecStart to the candidate's virtualenv and root; frontend WorkingDirectory/ExecStart to its frontend and Next executable. Keep existing protected EnvironmentFile locations and ports. Preserve one API worker/in-process scheduler. Check units with `systemd-analyze verify`. Do not copy the `User=vlr` template blindly over the installed root units or use a mutable shared virtualenv for both releases.
5. Enter a short maintenance/drain window at the established traffic entry. Stop frontend first to prevent user requests crossing partially changed services. Leave PostgreSQL and Redis running. Confirm PostgreSQL cluster and Redis are healthy before API start; unit ordering alone is insufficient. Stop the old API before starting the new one, preventing duplicate scraping schedulers. Install reviewed overrides and run `systemctl daemon-reload`, then start `vlr-api` only. This is the first step that changes production and is **not performed by this review**.
6. Gate on API readiness: `/health` must return 200 `{"status":"ok"}`; `/api/v1/status` must return an object with `checks.postgres` and `checks.redis` both true, credible nondecreasing history counts, and next-run entries for exactly the expected scheduler jobs. Confirm the new PID/start time, actual executable/working directory and pinned release manifest. If `commit` remains `unknown`, investigate metadata permissions; do not mistake current checkout HEAD for process provenance. Review startup/persistence errors. Existing idempotent schema setup should complete without a migration or data reset.
7. Run one bounded sequential API smoke using `scripts/probe_api.py` with its default limits. Do not loop or flush cache to make it green. Verify rankings/events freshness contract and known player history as below. A cold rankings/events refresh can exceed the frontend's short budget; allow one bounded operator API request with suitable timeout (up to 150 seconds), stop on backoff, then reassess. Retained keys need successful refreshes before they exist; do not perform a bulk region crawl to seed them. Failed checks keep traffic drained and trigger rollback or investigation.
8. Start `vlr-frontend` against the completed matching build. Check a representative listing, match/team/player route and their Next `/api/...` envelopes directly, then through the actual ingress. Check streamed loading, assets, stale notices and the recovered history/headline. Preserve the current cache and history; ordinary scheduler refreshes continue. Do not point production to the cache-only preview or enable fixture hooks.
9. Resume traffic only when both layers meet the response gates. Observe one normal upcoming/live scheduler cycle and verify no duplicated jobs, unexpected 5xx/504 bursts, persistence warnings, memory/disk exhaustion or unavailable populated-detail envelopes. Continue watching slower jobs at their normal schedule; do not force every scheduled scrape. Record final release SHA, build checksum, dependency versions, new PIDs and UTC deployment time.

### Expected response gates

| Check | Expected shape / interpretation |
| --- | --- |
| API health/status | Health object above; status object with service/commit/checks/history/cache_keys/scheduler. HTTP 200 status can still contain failed dependency checks |
| API results/upcoming/live/rankings/events/news | Bare arrays; genuine empty live lists are valid. Rankings/events set `Cache-Control: no-store` and `X-VLR-Cache: fresh` or `stale`; retained stale array is usable but must be disclosed. No available copy after failure: 503 `{"detail": ...}` |
| API stats and team/player search | Existing `{data: [...], stale: boolean, error: string or null}` envelopes; inspect flags, not just status. Blank search is a valid empty control |
| API match/team/player | Bare entity objects with selected identity; absent source fields remain null/missing. Bounded detail timeout: 504 `{"detail": ...}`. Existing unknown-player 500 behavior is unchanged, not a newly promised 404 |
| API player trend | Bare object with `rating_trend` array and snake_case fields; known player 3799 should recover parseable captures rather than zero merely due to `R`/`Rnd`. Exact count is time-dependent |
| API dimensions | Bare object with `firepower`, `entry`, `consistency`, `clutch`; absent membership/history can legitimately be unavailable/404. Do not invent cohort coverage |
| Next API proxies | `{data: [...], stale: boolean, error?: string}`; detail/trend objects are normalized inside the data array, with e.g. `agentStats` and `ratingTrend`. An empty data array plus error/stale is unavailable even at HTTP 200 |
| Browser detail/loading | Loading boundary appears promptly, remains responsive during a slow valid detail, then renders or gives an honest unavailable state. Initial upstream deadline 90 seconds; ordinary loaders/proxies 10 seconds; backend detail 80 seconds; post-cache history 5 seconds. Live polling retains last good scores and labels staleness |

### Rollback

Trigger rollback on failed startup/dependency checks, missing/wrong artifacts, sustained new 5xx/504 or unavailable envelopes on expected populated routes, lost history/headline fields, or resource exhaustion. Do not repeatedly restart or send retry bursts.

1. Drain traffic and stop the new frontend, then stop the new API so its scheduler cannot overlap the fallback.
2. **Blocked until an attested backend is recovered and verified; the historical read-only fallback bundle is insufficient.** Restore the prevalidated old backend artifact+virtualenv and old frontend `.next`+matching dependencies by restoring the saved unit paths/overrides. Restore original protected environment files only if changed during the window. Run `daemon-reload` if unit definitions changed.
3. Leave PostgreSQL and Redis running with current data. No schema reversal, database restore or cache deletion is needed for this release. Extra retained/lease keys are harmless to old code; leases expire naturally. New snapshots remain readable. Restoring a pre-release database would discard legitimate new history and is not normal rollback.
4. Start the fallback API; verify health, dependencies, history counts, one scheduler and its selected artifact. Start fallback frontend; verify old BUILD_ID and representative responses. Then reopen traffic. The old aggregation defect will return on rollback; record this known limitation rather than backfilling or altering data.
5. Preserve failed-release logs and artifact identity privately for diagnosis. Restore data backups only for demonstrated corruption through a separate, deliberate recovery procedure, never as an automatic response to application failure.

## Review boundary (initial review and gate follow-up)

Only review documentation and isolated verification evidence/harnesses are committed. `.gitignore` and `docs/SHARED_NAV_HOMEPAGE_REDESIGN_PLAN.md` remain byte-for-byte unchanged and unstaged. Production unit definitions, environment files, active `.next`, service PIDs/start times and the existing 3100/8101 preview processes were not changed. Runtime reads and normal GET behavior are distinguished from the isolated tests/build. The documentation push is not a deployment.
