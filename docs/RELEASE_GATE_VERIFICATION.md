# Release gate verification — 2026-09-27

Application under test: **`9301682c4165d7507e49d6ad7678d14ca9df377e`**. No application or live configuration changes were necessary for the tested deadlines; no application fix commit was created. Evidence and reproducible review harnesses are in [verification/release-gates/2026-09-27](verification/release-gates/2026-09-27/). The recommendation remains **NO-GO**: cold-cache staging now passes for the selected sample; exact rollback provenance, effective ingress configuration and durable capacity remain unresolved.

| Gate | Result | Pass criteria | Outstanding requirement |
| --- | --- | --- | --- |
| Rollback provenance | **Unresolved; frontend artifact restore passes** | Attested source/runtime/configuration for both running services, recoverable artifacts, isolated restore, data-preserving rollback | Recover the exact old backend source/runtime from an owner-held deployment artifact or machine backup; attest source/runtime correspondence. Current disk HEAD cannot identify the old worker |
| Ingress deadlines | **Unresolved; application tests pass** | Inspect effective configuration for every ingress hop and prove compatible deadlines/streaming without modifying live ingress | Read Caddy LXC configuration and version, imports/global options, effective JSON and Cloudflare settings; verify an isolated copy of that topology |
| Cold-cache staging | **Pass for three selected core details** | Empty isolated caches, sequential bounded real-source reads, populated cold/warm API responses, successful browser outcomes, no production writes | Broader sampling/load testing is not claimed; browser outcomes were measured after API warming |
| Build/backup capacity | **Unresolved; build, database and frontend restore tests pass** | Measured build peak; verified backups; adequate durable simultaneous artifact/restore space and operating reserve | At least 674,842,774 additional free bytes for the measured lower bound, plus the missing backend artifact/environment and durable off-host backup destination |

## 1. Rollback provenance

**Commands/configuration evidence:** `systemctl show vlr-api vlr-frontend -p MainPID -p ExecMainStartTimestamp -p FragmentPath -p DropInPaths`; read the two installed unit files and hash them; GET the strictly read-only `/api/v1/status`; inspect `.next/BUILD_ID`, build metadata and Git reflog; attempt read-only `/proc/<pid>/{cwd,exe,maps}` access. See `baseline.json`, `provenance-ingress.json`, and the prior review's `configuration.json`.

- API remains PID 61821, September 17 11:10:09 UTC. Frontend remains PID 308, September 3 04:02:56 UTC. Installed units are `/etc/systemd/system/vlr-api.service` and `/etc/systemd/system/vlr-frontend.service`; neither has drop-ins. Both use root and the `/opt/vlr-api` paths already recorded in the release review.
- API still reports `commit: "unknown"`. Access to both processes' executable/cwd/maps is denied. No memory attachment, signal, restart or debugging injection was used to extract a revision.
- The September 17 source revision remains bounded by `32e7e23bbf1435163f0660ed74196a4704eff51a` and the potentially then-uncommitted `139378cb7505c6257c7b69da3491e382c4ebf0bc` change. Neither is proven to equal the loaded worker. The old compiled frontend still has BUILD_ID `5RXlwj7jwc2eDLWI_-439`, but no attested source-commit manifest. The current on-disk dependencies likewise cannot establish what modules the old process originally loaded.
- Environment-file names: `/opt/vlr-api/.env` and `/opt/vlr-api/frontend/.env`. Backend variable names: `VLR_DATABASE_URL`, `VLR_REDIS_URL`, `VLR_USER_AGENT`, `VLR_MIN_REQUEST_INTERVAL`, `VLR_ENABLE_SCHEDULER`. Frontend names: `VLR_API_BASE`, `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `TWITCH_FEATURED`; the frontend unit also supplies `PATH`. Values are not included in Git or this report. Exact private copies retain the original configuration for later authorized rollback.

**Recovered artifact:** `archive_frontend.py` created a new private archive of production `.next`, `node_modules`, package/lock files, Next configuration and public assets. It did not copy current application source as if it were the old API. Archive size: **215,041,425 bytes**; SHA-256 **`cfabf6b2d94faf3d253bcdbb5191c10b0fe725d00ba3a992891de53ad992a5b6`**. All **25,776 regular files** match source hashes. Exact environment and unit copies are private, outside Git, under a mode-0700 parent; files containing configuration secrets are mode 0600.

`restore_frontend.py` extracted the archive to `/tmp/vlr-gates-9301682/restored-app`, then compared every regular-file hash: **zero mismatches**. It restored the old BUILD_ID. The restored `node_modules/next/dist/bin/next start -H 127.0.0.1 -p 3112` served homepage HTTP 200 and a static asset whose bytes matched its restored file. Runtime API origin was deliberately unreachable and Twitch disabled, so this was an artifact/startup smoke, not a production-data journey. It was stopped and the expanded copy removed after verification. The compressed artifact remains at `/home/builder/vlr-gates-private/frontend-rollback.tar.gz`; the manifest and protected configuration copies are alongside it. This directory is on the same limited root filesystem, not off-host backup storage.

**Rollback procedure and verification boundary:**

1. Before any cutover, retrieve an attested old backend source+Python runtime artifact and its manifest. Reproduce its health and dependency checks against isolated storage. **Stop here while that artifact is missing**; neither a historical Git guess nor current source is an exact rollback.
2. Verify the preserved frontend archive checksum, extract to a separate durable rollback directory, compare its manifest and BUILD_ID, and use its restored dependencies. Do not run `npm ci` over the artifact or replace it with a new build from an unproven source revision.
3. For a future authorized rollback, drain traffic, stop frontend, then API. Restore saved unit definitions or reviewed overrides pointing to the attested backend and restored frontend; preserve original protected environment files. Reload unit definitions only if changed. Start API, verify health/dependency checks and one scheduler, then start frontend and verify the old BUILD_ID/assets before reopening traffic.
4. **Keep PostgreSQL and Redis running and retain all current data.** Do not restore the pre-release database, delete cache keys, undo schema or backfill data. The candidate preserves old payload/schema compatibility; additional retained/lease keys can remain and leases expire. A database restore is a separate disaster-recovery decision, not application rollback.

Steps 2's extraction/hash check and isolated frontend startup were actually tested. A full backend rollback and service switch were **not** tested and are **not** asserted to pass. An owner-held historical LXC snapshot/deployment bundle may close the provenance gap without changing production; privileged read access alone would not necessarily recover source that has already been overwritten.

## 2. Ingress deadlines

The owner confirms **Caddy on a separate LXC** serves `https://val.jushosting.dev`. DNS resolves to `104.21.70.245` and `172.67.140.254`, inside [Cloudflare's published IPv4 ranges](https://www.cloudflare.com/ips-v4/). This supports an inferred Cloudflare edge; it does not reveal zone rules or origin routing. A TLS-only `openssl s_client -connect val.jushosting.dev:443 -servername val.jushosting.dev -brief` handshake verified TLS 1.3 and a `jushosting.dev` certificate. No application request was sent through the public site to provoke cache refreshes.

The best-supported path is:

```text
Browser -> Cloudflare edge [inferred from DNS; effective settings unknown]
        -> Caddy on separate LXC [owner confirmed; upstream/rules unknown]
        -> Next :3000 [installed local frontend; remote Caddy target unverified]
        -> server-side loader/proxy -> FastAPI :8000 -> Redis/Postgres/VLR
```

There is no Caddy executable/service/configuration on this application host, and no provided access to its LXC. Thus Caddy routing, network proxy/tunnel hops, timeouts and buffering cannot be attested. The topology is no longer treated as possibly direct-LAN-only; the earlier review's absence of a local proxy never proved absence of an external one.

**Configured application limits, read from pinned source:** `frontend/src/lib/vlr.ts` defines 90,000 ms for initial detail-page upstream reads, including headers/body, and 10,000 ms for ordinary loaders/proxies. `app/api/v1/routes.py` wraps detail cache/refresh in an 80-second deadline. History persistence after cache publication has a five-second budget. API Uvicorn uses one worker; no additional request-duration override is present in the installed ExecStart. These limits are application behavior, not proxy defaults.

**Actual isolated tests:** `staging_backend.py` in fixture mode used the real candidate FastAPI routes/parser and private Redis/Postgres, with saved HTML replacing VLR transport. Candidate compiled Next ran on loopback 3111 and the private API on 8111. No live upstream calls were made for deadline tests.

| Test | Observed result | Pass criterion |
| --- | --- | --- |
| Healthy 12-second fixture via FastAPI | 200 bare match object in **12,045.4 ms** | Valid response beyond the former 10-second limit, within 80 seconds |
| Healthy fixture through Next/browser | Loading at **203 ms**, populated match at **12,566 ms**, HTTP 200, zero page errors | Prompt loading and successful completion, no premature 10-second failure |
| Hung refresh through real FastAPI detail route | **504** in **80,002.6 ms**, `{"detail": string}` shape | Finite 80-second backend deadline, no indefinite request |
| HTTP service bypassing backend route deadline, through Next/browser | Loading at **150 ms**, unavailable state at **90,305 ms**, HTTP 200, zero page errors | Independent 90-second frontend deadline and honest failure UI |

The final case deliberately bypassed the backend route only in the private harness; it proves Next's own limit rather than remeasuring FastAPI's 80 seconds. The initial direct-API test accidentally inherited httpx's five-second idle timeout; those failed attempts are retained in `deadline-api-initial.json`. `deadline_probe.py` disables that client idle timeout while retaining the helper's 95-second whole-request deadline; the corrected results above are from that rerun. No application setting or assertion was weakened.

**Ingress pass criteria and next action:** obtain Caddy's version, `systemctl cat caddy`, site block plus imports/global options, and locally inspected effective adapted/runtime JSON, with secrets redacted. Inspect upstream routing, HTTP transport `response_header_timeout`/`read_timeout`, server write/idle limits, response buffers/flush behavior, retry policy and any tunnel settings. Obtain effective Cloudflare settings too. Reproduce that configuration on an isolated proxy and point it at the private 12-second/80-second/90-second scenarios. Require prompt streamed loading and no edge cutoff before the application's intended response. If an effective setting conflicts, make a separately reviewed configuration fix and test it in isolation; do not reload live Caddy in this task.

[Caddy documents](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) no default timeout for response headers/next backend read, but those defaults do not establish this LXC's configuration. [Cloudflare currently documents](https://developers.cloudflare.com/fundamentals/reference/connection-limits/) a 125-second proxy read timeout; that published value alone is not evidence of this zone's effective path. A 120-second direct cold rankings/events refresh leaves little edge margin and differs from the 80-second detail path. Prior generic 150-second proxy guidance cannot override a preceding edge limit. **No live configuration fix is justified from an unknown configuration, and no full-ingress pass is inferred from localhost tests.**

## 3. Cold-cache staging

**Commands/configuration evidence:** create a private UTF8 PostgreSQL cluster with `initdb`, Unix socket only on logical port 55439, no TCP listener; create a new `cold` database. Start a private Redis Unix socket with TCP and persistence disabled. Start `staging_backend.py` in cold mode with the pinned archive on `PYTHONPATH`; run `cold_probe.py`, which reuses `scripts.probe_api.request`. Scheduler is disabled; all storage overrides point to the new private instances. Redis starts with **zero keys**. No production cache is deleted, copied into staging or refreshed by this test.

Real HTTP transport permits only the three selected numeric detail paths, at most six HTTP requests including possible redirects, and at most one redirect per call. Actual network requests are serialized and spaced at least two seconds. The staging retry setting permits one attempt; a source error/backoff closes the source budget. This tests successful cold behavior without generating retries against VLR. The API probe issues at most six requests, two seconds apart, with a 300-second total bound, 90-second outer per-request bound, 2 MB API-body cap, no redirects and no retries. Its cold-pass client also retained httpx's five-second idle bound; every observed response was much faster, with no timeout. Finite 80/90-second testing used the corrected separate deadline harness.

| Detail | Cold API ms / status | Warm API ms / status | Shape | Warm browser outcome at 390px |
| --- | --- | --- | --- | --- |
| Match 753445 | **171.8 / 200** | **6.7 / 200** | Bare object with identity, teams/maps/scoreboard fields | Populated at **299 ms**, 10 table rows |
| Team 8877 | **71.6 / 200** | **2.3 / 200** | Bare object with identity/roster/results fields | Populated at **499 ms**, 15 table rows |
| Player 3799 | **34.1 / 200** | **2.1 / 200** | Bare object with agent-stat and match arrays | Populated at **6,123 ms**, 9 table rows including thin new history |

Exactly **three** real upstream HTTP requests occurred, all 200: `/753445`, `/team/8877`, `/player/3799/`. Warm API calls generated none. After the API checks a private sentinel disabled all future source transport, and `browser.cjs` opened each page once against the candidate Next build on loopback 3110. All three had zero page errors and no horizontal overflow. Browser completion was measured on warmed detail keys; it is not a separate cold-browser timing claim. Optional cohort requests were blocked, so dimensions could be unavailable; the player wait includes optional-loader failure handling. Existing upstream caches/CDN may explain fast source responses: “cold” here means our staging Redis/database, not VLR's CDN.

**Risk remaining:** this is a small completed-match/team/player sample, not proof for every entity, cache-expiry race, live state, upstream outage or concurrent load. Initial-page slow behavior is covered by the isolated fixture test above. No source values were repaired or invented; missing fields stay missing. This closes the review's representative real cold-detail validation gate, not a broad availability SLA.

## 4. Build and backup capacity

**Database backup/restore commands:** `backup.py` opens a repeatable-read, read-only production transaction, exports its snapshot, measures database size and counts all public tables, then invokes `pg_dump -Fc --no-owner --no-acl --snapshot=<snapshot>` into a new private file. Authentication is passed privately, never printed. `pg_restore --list` validates the archive; `pg_restore --exit-on-error --no-owner --no-acl` restores into **`restored` on the private Unix socket**, never the production server. The fresh dump does not overwrite an existing backup.

| Measurement | Observed |
| --- | --- |
| Source database size | 46,167,731 bytes |
| New compressed dump | **9,901,311 bytes**, SHA-256 `4c50d9f02a7a408e7816be4d439647ef5e3976dcac5ef4bec74f4da9e5ee8d4c` |
| Restore result | Exit 0; 38 archive entries; restored DB 45,029,043 bytes |
| Consistent snapshot vs restored table counts | Match results **1,572**; player snapshots **14,792**; ranking snapshots **106,077**; team snapshots **1,009** — all match |
| Frontend rollback archive / expanded restore | 215,041,425 / 648,491,491 logical bytes; all file hashes verified |
| Clean isolated production build | **25.04 s**, sampled process-tree RSS peak **702,152,704 bytes**, sampled `.next` logical peak **94,716,374 bytes** |
| Build disk budget | 383,733,760 bytes free after removing only this task's stopped prior build; sampled minimum **287,748,096**; final **287,571,968** |
| Durable space after backup/build work | **287,531,008 bytes available** on root before cleanup |
| Safe cleanup of review-only dependencies | Removed the separate 712,368,128-byte npm-ci directory after all private Next servers stopped; production dependencies, source, `.next` and backups retained |
| Final durable space | **999,481,344 bytes available** after that cleanup; `/tmp` is memory-backed and is not a durable backup volume |

`final_checks.py` runs serially and samples process-tree RSS/disk at approximately 0.5-second intervals. These are observed sampled peaks, not a bound on every transient allocation; reserve is required. Lint peaked at 670,052,352 bytes RSS. The preflight host had about 4 GiB RAM and an already-full 1 GiB swap. The successful sequential build does not authorize simultaneous browsers/restores/builds or heavy work during serving load.

**Measured headroom for the proposed separate-release/restore procedure:** expanded frontend restore **648,491,491** + isolated Postgres database **45,029,043** + a deliberately explicit **256 MiB operating reserve** = **961,955,990 bytes** before candidate dependencies. Initial durable free space was only 509,181,952 bytes; it dropped to 287,531,008 after retaining the backups. To leave the host safer, the review's redundant **712,368,128-byte** npm-ci directory was removed after testing. Source and the successful compiled `.next` remain, but a future isolated build/release must reinstall its pinned dependencies. Including that reinstall gives **1,674,324,118 free bytes required**, versus **999,481,344 available** after cleanup: a **674,842,774-byte shortfall**. This is the budget for the proposed independent release and restore workspaces, not a claim that every possible deployment layout requires the same duplication. It excludes the missing backend artifact/virtualenv, PostgreSQL cluster overhead, future growth and off-host backup capacity. Provision a durable volume with at least 2 GiB usable space as a starting point, then repeat the budget against the actual recovered artifacts. See `temporary-cleanup.json` and `capacity-inventory.json`.

The restored frontend and database fit only in temporary storage during this exercise. Both were verified, stopped and removed to release memory. Compressed backups/configuration remain under `/home/builder/vlr-gates-private`; move them securely to a separately verified durable backup destination as a future operator action. They are not in Git. Redis's existing `/var/lib/redis/dump.rdb` is not readable by this account; no `SAVE`, `BGSAVE`, replication snapshot, cache flush or persistence change was issued. Redis backup recoverability is therefore **not** asserted. Normal application rollback continues to preserve the running Redis and PostgreSQL data.

**Pass criteria not met:** provision enough durable space for both releases, recovery work and reserve; obtain the missing backend artifact; verify backup retention outside this nearly full root volume. If a recoverable Redis disk backup is required for the deployment's disaster-recovery policy, have an authorized operator copy and verify the existing persistence artifact without changing the live cache. Do not use the passing temporary restores as a durable-capacity pass.

## Final checks, cleanup and recommendation

Fresh final checks on the pinned archive: **284 backend tests, 348 frontend tests (25 files), lint, TypeScript, and clean webpack production build all pass**. No application code changed, so no new production-code regression test was needed; the existing deadline/cache/history suites ran in full. All **511 tracked archive file blobs** still match the pinned Git commit after verification.

`final-preservation.json` confirms unchanged production PIDs/start times, unit-file hashes, environment-file bytes, `.gitignore`, and the untracked plan. All private HTTP servers, Redis and PostgreSQL are stopped. The three source GETs wrote only private staging storage. Production interaction consisted of configuration/artifact reads, a read-only database snapshot/dump, a read-only status GET and a public TLS handshake. No live proxy changes, production detail refreshes, schema changes, cache mutations or service restarts were performed by this task. Normal production scheduler activity was not stopped or rolled back.

**NO-GO remains for three gates.** There is no executable production cutover authorized or claimed ready. The existing release review's service order/data-preserving procedure remains conditional. The next concrete work is: recover the backend deployment artifact; supply read access to the separate Caddy/edge configuration; provision and verify durable capacity/backup storage. Browser/content polish is separate and does not close those gates.
