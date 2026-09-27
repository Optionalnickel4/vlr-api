# Known VLR baseline proposal — 2026-09-27

**NO-GO for production now.** This package proposes a first controlled transition to a known release, followed by a separately approved second application release. Nothing here authorizes execution. September 17 backend provenance is **unrecoverable from the available evidence**. Stop searching for it. The old process and the historical fallback are not attested application-only rollback targets. Earlier evidence remains historical; its failed provenance gate is superseded by this strategy, not passed.

The source is the on-disk tracked application at `3cf2373` (full SHA in the private `inputs.json`), with a complete per-file inventory and an explicit application patch. There were no uncommitted application changes at packaging. The pre-existing `.gitignore` edit and untracked redesign plan are excluded and untouched. This says nothing about dirty changes that the September 17 worker may have loaded: those are unrecoverable too. The application files match the previously reviewed `9301682` application; new deployment tooling is pinned by this proposal's commit and the retained launcher hash. A future source change requires a new package, never in-place repair of a sealed release.

## Retained package and preparation

Private durable root: `/home/builder/vlr-recovery-check/baseline-20260927`. Public digest/BUILD_ID summary: [artifacts.json](verification/baseline/2026-09-27/artifacts.json). `release.json` inventories backend source, Python interpreter/stdlib/site-packages, frontend source, installed npm dependencies, Node binary, compiled `.next`, assets, font inputs, launcher and metadata. `dependencies.json` hashes actual runtime bytes; `inputs.json` records installed Python versions, Node/npm versions, source commit/dirty patch, lockfile hash through the source inventory and build environment. `system_libraries` pins host shared libraries resolved by `ldd` for Python, Node and native extensions. This is a retained-runtime release, not a promise that unconstrained `pip install` reproduces it. No editable application import points back to `/opt/vlr-api`.

`backend.tar.gz` and `frontend.tar.gz` are checksummed retained archives. The frontend was freshly built with `next build --webpack` inside a networkless namespace. Actual Google CSS/font bytes and source URL digests are retained in `frontend/font-inputs`; CSS paths are mapped to retained local font files for the Next offline loader. No dummy fonts are used. The first Turbopack attempt failed because fonts require network; its log remains. Build logs are private. No backend/VLR requests occurred during build.

Files are made read-only locally. Before cutover, copy the archives, release manifest, inventories, launcher, logs and this proposal to **independently retained immutable storage** (object lock/WORM or administrator-owned snapshot), verify a fresh download and record retention expiry/owner/object IDs/checksums. Local chmod alone is not immutable retention against its owner or disk loss. This off-host retention gate is open. Production release layout is `/opt/vlr-releases/<release-manifest-sha256>/`; extract only verified archives into a new directory, copy the manifest/launcher/inventories, root-own it, remove service-user write access, and run `check_manifest` there. Preserve executable mode on Python/Node. Never build in `/opt/vlr-api/frontend` or call `start-services.sh`.

Reproduction commands (new unique output directory; do not overwrite this package):

```sh
python3 scripts/baseline/package.py /home/builder/vlr-recovery-check/baseline-NEW
python3 scripts/baseline/fonts.py /home/builder/vlr-recovery-check/baseline-NEW/frontend/font-inputs
# Use the networkless build command retained in commands.sh, substituting the new root.
# Review no .env, tokens, credential-bearing URLs or secret build-time values are present.
python3 scripts/baseline/seal.py /home/builder/vlr-recovery-check/baseline-NEW --reviewed-secret-free
```

`seal.py` creates `gate2-input.json` exclusively; it refuses to overwrite an existing input. For a subsequent package retain the old input and choose a new reviewed input file (adjust output location in a reviewed change). Repackaging intentionally yields a new BUILD_ID/checksum. Review copied installed npm bytes against package-lock/`npm ls`; the byte manifest, not a claim about npm provenance, defines this runtime.

## Recovery prerequisites and acceptance

Bubblewrap was absent. Debian `bubblewrap 0.12.0-1~deb13u1` was downloaded and extracted privately at `/home/builder/vlr-baseline-tools/root/usr/bin/bwrap`; namespaces work unprivileged. No host package was installed. Its downloaded package and executable checksums are in the new evidence. Preserve them with the package. Use the explicit PATH below; the harness must not fall back to weaker isolation.

The missing `/home/builder/vlr-recovery-check/gate2-input.json` now describes the **new baseline**, purpose `baseline-rehearsal`, stages `candidate` and `baseline`, each referring to the same sealed backend/frontend inventories. It does not contain a fabricated historical receipt. The old historical mode continues to reject the known fallback checksum. A baseline rehearsal proves restart/recovery of these known artifacts; it cannot prove recovery of the unknown process or qualify an as-yet-unbuilt second release.

```sh
export PATH=/home/builder/vlr-baseline-tools/root/usr/bin:/usr/bin:/bin
python3 scripts/recovery/integrated.py --preflight
python3 scripts/recovery/integrated.py
```

The harness creates its own private mount/PID/network namespace, fresh PostgreSQL 17 UTF8 cluster, Unix-only Redis and HTTP fixture. Normal application lifespan runs `init_db`/additive migrations and one real scheduled fixture results refresh. Both Next/API stages render the unique fixture marker; all four history tables, newer rows, persistent/TTL cache sentinels and continuously running storage are checked across the application-only switch. Graceful scheduler shutdown and runtime/module/BUILD_ID evidence are required. Its only accelerated job is results; this is not full cron workload coverage. See [new evidence](verification/baseline/2026-09-27/assessment.json) for execution result and limitations. No production mounts, environment or network are passed through.

## Gates before first cutover

All are mandatory; a proposal or old measurement is not a pass:

1. Review the exact source/runtime/frontend package and deployment wrapper; complete immutable off-host retention and download/hash validation. Test the **deployment launcher under disposable systemd**, including receipt generation and the actual override files, not only the harness's observation wrapper. Resolve any OS shared-library mismatch before copying to production; never silently use a new runtime.
2. Require the baseline integrated rehearsal to pass; also restore a fresh production-schema dump into isolated storage and rehearse the baseline's normal schema startup with its data. Fresh-fixture success does not prove real-data/schema compatibility. Current startup DDL is `create_all` plus two nullable match-result ID columns and two indexes (`IF NOT EXISTS`); compare every existing column/type/index and grants, measure lock duration, and test repeated startup. No destructive DDL is allowed. Unexpected drift blocks cutover.
3. Re-measure durable free disk, inode availability, memory and peak build/test allocation. Allow retained baseline + second-release artifacts + restored copies + backup/restore storage + 1 GiB test logs/DB and at least 2 GiB operating reserve. The harness checks its own copy budget only. Record `df -B1`, `df -i`, `du -sx --block-size=1`, `free -b`, PG database size and Redis `INFO memory/persistence`. Budget concurrent retained failed runs too. Do not count `/tmp` memory as durable disk or delete earlier evidence to force a pass.
4. Prepare fresh durable PostgreSQL and Redis recovery points and prove isolated restore. Earlier dump `/home/builder/vlr-gates-private/production-20260927.dump` SHA-256 `4c50d9f02a7a408e7816be4d439647ef5e3976dcac5ef4bec74f4da9e5ee8d4c` restored with matching counts; this is historical, not a new cutover point. No fresh production backup/cache snapshot was made here. Redis backup/restore remains an explicit gate.
5. Close ingress requirements below, retain applied-config attestations, and approve the maintenance window and failure decision owner. Validate configured DB/Redis targets, role permissions, UTF8, service user/EnvironmentFile paths without printing credentials. Record all writers and scheduler owners, unit/drop-in hashes and existing service identities immediately before cutover.

Backup commands below are **future operator steps**, using protected `.pgpass`/`PGSERVICE` and `REDISCLI_AUTH`, not credential-bearing command lines. `BACKUP` must be a new mode-0700 directory on durable storage. While all application writers are quiesced in maintenance, create paired final recovery points (earlier online copies permit advance restore testing):

```sh
pg_dump --format=custom --no-owner --no-acl --file="$BACKUP/postgres.dump"
pg_dump --schema-only --no-owner --no-acl --file="$BACKUP/schema.sql"
# Select the verified Redis host/port/db/auth via protected operator environment.
redis-cli --rdb "$BACKUP/redis.rdb"
redis-check-rdb "$BACKUP/redis.rdb"
sha256sum "$BACKUP/postgres.dump" "$BACKUP/schema.sql" "$BACKUP/redis.rdb" > "$BACKUP/SHA256SUMS"
pg_restore --list "$BACKUP/postgres.dump" > "$BACKUP/pg-contents.txt"
```

Retain protected role/grant and configuration backups separately, RDB snapshot start/end timestamps, Redis version/DB index/persistence mode and TTL expectations. Replication-based `--rdb` can fork/load the server: size memory/disk first. AOF users must preserve their actual persistence configuration and backup AOF manifest/segments consistently; do not infer that a random file copy is valid. Restore the RDB with the same Redis version to a **new isolated instance** (AOF disabled there for the RDB restore), check counts/values/absolute expiry semantics; expiry during elapsed downtime is expected, resurrection is not. Restore PostgreSQL with `pg_restore --exit-on-error --no-owner --no-acl` to private PG17, verify ordered row fingerprints/counts/constraints against the quiescent snapshot. Transfer encrypted backups off-host and verify checksums/restoration there. Backup age, loss window and restore duration require an explicit owner decision.

These are disaster recovery points, **not application rollback actions**. Never restore PostgreSQL/RDB, flush Redis or revert a container snapshot during an application rollback. Disaster restoration loses writes after the selected point and needs a separate incident/data-loss decision.

## First cutover: unknown process → known baseline

The first cutover has no attested old-backend rollback. It is a maintenance transition with a tested new-baseline recovery path. Reserve a 15-minute window provisionally; readiness checks are bounded to 120 seconds per service, shutdown up to 100 seconds, but unknown active requests, final backups and schema locks may extend the interruption. Measure actual duration in rehearsal; do not promise zero downtime. Existing requests and cron work may be interrupted. No production changes in this proposal.

1. Before the window, prepare verified fixed release directory, root-owned rendered overrides from [deploy/baseline](../deploy/baseline/), protected configuration and separate writable Next cache if needed. Keep PostgreSQL/Redis services and storage untouched. Record old unit files/drop-ins/config hashes privately as incident evidence, not proof of old application bytes. Approve a cached maintenance response at ingress and block new writes/scrapes.
2. Enter maintenance; stop `vlr-frontend`, then the API and any **actually active** standalone scheduler. Wait for worker exit and no in-flight DB writers, then take the final paired backup/fingerprints above. Do not start an in-process and standalone scheduler together. The proposed normal baseline is one API worker with `VLR_ENABLE_SCHEDULER=true`, standalone `vlr-scheduler` stopped/disabled (review persistent enablement separately). Leave storage running throughout.
3. Install the reviewed rendered fixed-path overrides, `systemctl daemon-reload`, inspect effective `systemctl cat/show` (including environment precedence), then start **API only**. Normal migrations/lifespan are enabled; never use `--lifespan off`. `Restart=no` prevents repeated failed startup/DDL loops in this window. Require `/health`, `/api/v1/status` with postgres/redis true, startup receipt, and one scheduler with eight expected jobs/max_instances=1. Verify exactly one API worker and no external duplicate scheduler/cron across hosts. Require one observed scheduled refresh without duplicate execution after reopening permitted egress.
4. Start frontend after API passes. Validate frontend receipt, exact BUILD_ID, known populated cached `/results` and representative cached detail/history/status routes, static asset hash and unavailable/loading behavior through the real ingress. Do not flush caches or use uncached detail paths as routine smoke tests. Production probes/scheduler egress are future authorized actions, not run here.
5. Compare data before resuming traffic: all pre-cutover history primary keys/row values must still exist; counts cannot decrease. New scheduler rows may legitimately append, so compare the preserved snapshot subset rather than demanding equal live table counts. Compare sampled cache value digests and absolute expiries, accounting for known refreshes and natural expiry. Confirm DB/Redis process identities/uptimes have not restarted. Record receipt verification, journal invocation, effective units, ingress hashes and operator decision.
6. Remove maintenance only after all checks. Observe at least one longest configured scheduler interval and a 24-hour baseline soak (error rates, dependency health, duplicates, data growth, memory/disk). Longer observation may be needed for weekly jobs; 24 hours does not test every schedule. Freeze the proven baseline manifest and startup receipt in immutable retention before any second release.

The [rendered API override](verification/baseline/2026-09-27/api.override.conf) and [rendered frontend override](verification/baseline/2026-09-27/frontend.override.conf) pin this package to `/opt/vlr-releases/6eb973ac839f5c8bbf87921eb15b946637854b136c8e19520aff62f16a7ea308`. Existing recorded units run as **root**, unlike the repository example's `User=vlr`; these overrides inherit the existing user and protected EnvironmentFiles. Do not assume a privilege migration has been tested. `ReadOnlyPaths` protects the release mount even for the inherited service identity; a release-specific systemd cache directory is bind-mounted only at frontend `.next/cache`. Create that empty mountpoint when staging the new release. Cache here means Next's disposable rendering cache, **not Redis**. Systemd namespace/cache mount and EnvironmentFile precedence must pass the disposable unit rehearsal before cutover.

Future staging commands (after immutable retention, under the authorized maintenance plan):

```sh
RELEASE_ROOT=/opt/vlr-releases/6eb973ac839f5c8bbf87921eb15b946637854b136c8e19520aff62f16a7ea308
# First verify archive digests and members with verify_archives.py at their retained source.
# Create RELEASE_ROOT exclusively; fail if it exists. Extract verified backend/frontend archives there.
# Copy release.json, dependencies.json, inputs.json and receipt.py; verify check_manifest(RELEASE_ROOT).
# Root-own release, remove write bits without removing execute bits, create empty frontend/.next/cache.
# Retain existing unit/drop-in files; install the rendered files as:
# /etc/systemd/system/vlr-api.service.d/50-baseline.conf
# /etc/systemd/system/vlr-frontend.service.d/50-baseline.conf
# Diff all effective overrides; an older/later conflicting override is an abort condition.
```

Future service commands, **only within the approved procedure**:

```sh
systemctl stop vlr-frontend.service
systemctl stop vlr-api.service vlr-scheduler.service
# Final backup/data fingerprints; install rendered overrides; validate targets.
systemctl daemon-reload
systemctl start vlr-api.service
# API/receipt/scheduler/data gates.
systemctl start vlr-frontend.service
# Frontend/ingress/data gates; exit maintenance only after acceptance.
```

Abort for hash/runtime/config drift, inadequate reserves, invalid backups, destructive/schema mismatch or lock timeout, startup >120s, missing/invalid receipt, failed health, duplicate schedulers, wrong BUILD_ID/import path, history loss, unexpected cache reset, storage restart or unresolved ingress. Stop new frontend/API/scheduler, keep maintenance and storage running, collect logs. Restore/re-extract the **same verified new baseline artifacts** to a fresh directory if local installation was damaged, correct only reviewed environmental defects, and retry once after cause review. If functional failure remains, stay in maintenance and prepare/test a corrected known release (roll forward) against isolated restored data. Returning to the old command or historical fallback is a separately reviewed emergency application choice with unknown compatibility; it is **not an attested application-only rollback**. Do not restore old database/cache data to make an application start.

## Startup receipt and live verification

[receipt.py](../scripts/baseline/receipt.py) wraps normal lifespan, checks every retained artifact/system-library hash, and records after successful startup: manifest/archive digests, invocation ID from systemd, PID, Linux process start ticks, boot ID, UTC observation time, interpreter hash, dependency inventory hash, imported module paths/hashes, frontend BUILD_ID and scheduler state. Each invocation has an exclusive file in `/var/lib/vlr-receipts`; old receipts cannot be overwritten. The monotonic start ticks plus boot ID avoid PID-reuse confusion. UTC observation time is not mislabeled as OS start time: the verifier adds systemd's actual `ExecMainStartTimestamp`.

```sh
INVOCATION=$(systemctl show vlr-api.service -p InvocationID --value)
python3 scripts/baseline/receipt.py verify "/var/lib/vlr-receipts/$INVOCATION.json" \
  > "$BACKUP/backend-live-attestation.json"
python3 scripts/baseline/frontend_receipt.py "$RELEASE_ROOT" \
  > "$BACKUP/frontend-live-attestation.json"
systemctl show vlr-api.service vlr-frontend.service \
  -p MainPID -p InvocationID -p ExecMainStartTimestamp -p ExecStart -p WorkingDirectory \
  > "$BACKUP/effective-services.txt"
sha256sum "$BACKUP/"*-attestation.json "$BACKUP/effective-services.txt"
```

Run with permission to read service receipts and `/proc`; never disable verifier checks with Python `-O`. Correlate frontend's systemd ExecStart with fixed Node/Next path (Next rewrites its process title). Re-run attestations after every restart; seal the output off-host with timestamps and unit/drop-in hashes. This is contemporaneous deployment evidence, not cryptographic remote attestation or proof against a compromised host. The verifier reads disk hashes and `/proc`; it cannot reconstruct arbitrary previous memory contents. Root ownership/read-only release mounts are necessary to preserve the startup-to-runtime link.

## Actual ingress and effective deadlines

The captured operator active-config observation establishes **Caddy v2.11.4 PID 87, `:80`, `val.jushosting.dev` → `10.0.0.21:3000`**. Yes, this is VLR's Next frontend path in the available evidence, corroborated by prior public/direct/disk asset equality and service destination. Path: Cloudflare edge → Tunnel `meowth` → Caddy localhost:80 → Next :3000 → FastAPI :8000. There is no evidence requiring a differently named VLR matcher. We accept the existing capture; no repeat historical provenance/config collection is proposed.

The summary reports no explicit proxy timeouts; it does not describe all server write limits, enclosing middleware or streaming. Backend detail budget is 80 seconds; Next initial detail read budget is 90 seconds. Every applicable active-response limit must be disabled or exceed 90 seconds with margin (proposed **120s**); buffering must permit the loading response and eventual result. TCP connection establishment and idle keep-alive settings are different limits.

The [configuration fragment](../deploy/baseline/Caddyfile.fragment) proposes VLR proxy header/read/write budgets of 120s and immediate flushing, with no response buffer. Server-level `write 120s` applies to the shared `:80` listener; review other sites or retain a proven disabled write deadline rather than blindly changing their policy. Inspect enclosing handlers/stream timeout and any custom modules. Caddy documents no default response-header/read/write transport timeouts; `flush_interval -1` disables buffering but also keeps upstream work alive after client disconnect, a resource tradeoff bounded by application deadlines. See [proxy documentation](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) and [server timeout documentation](https://caddyserver.com/docs/caddyfile/options). Validate against installed 2.11.4; current documentation alone is not runtime evidence.

Before any approved ingress change: retain the existing active export/config digest and Caddy service identity; merge the fragment into a complete copy; run `caddy adapt --pretty --config <candidate>` and `caddy validate --config <candidate>` on the matching binary offline. Review the diff across all sites. After an authorized reload, fetch **new** active JSON from `http://127.0.0.1:2019/config/` into a dated file, hash it, record Caddy version/PID/start/invocation and compare the matching route and enclosing server settings to the reviewed adapted JSON. This new post-change attestation is required, not another request for the old export. If reload/verification fails, reload the retained previous configuration under the same approved ingress-change procedure and verify it.

Also retain the running `meowth` connector version/process and applied configuration revision with merged originRequest overrides, hostname/service match, and effective hostname-specific Cloudflare response/streaming policy/override IDs (or explicit no-overrides attestation). General vendor defaults are insufficient. Use a separate controlled staging hostname/origin with synthetic 12/80/90-second responses to test delayed headers, streamed loading, final error delivery, no buffering and client disconnect behavior through equivalent applied policy; never induce slow VLR requests. A staging policy must be demonstrably equivalent to the production hostname. **Ingress gate remains OPEN; proposed settings do not pass it.**

## Second release and GO decision

The baseline is not permission to ship the next feature release. After baseline receipt/retention/soak approval, build a distinct second release, record its exact source delta and dependency/runtime/BUILD_ID/checksums, review schema compatibility in both directions, and populate a **new** input manifest with `purpose: second-release-rollback`, `stages: [candidate, baseline]`, the new candidate inventories, the retained baseline inventories and its reviewed startup receipt/hash. The baseline manifest must remain identical. No historical fallback is involved.

Run the private integrated harness with that input: candidate normal startup → newer DB/cache writes → graceful application shutdown → retained baseline normal startup → integrated Next/API/scheduler/data checks. Also rehearse on a freshly restored production-schema copy and exercise the deployment receipt launcher/systemd configuration. A self-switch baseline rehearsal is not a substitute for this distinct second-release test. A breaking schema/cache serialization change fails application-only rollback; redesign it as additive/backward-compatible or plan a separately approved migration release.

GO for first maintenance cutover requires every pre-cutover gate above plus explicit authorization. Baseline-proven requires successful live receipts/health/singleton/data/ingress and soak evidence. GO for second release requires baseline-proven, immutable retained baseline, fresh capacity/backup evidence, candidate acceptance, and **tested candidate→baseline rollback**. Second-release rollback: maintenance/drain → stop frontend then API/scheduler → select retained baseline fixed-path overrides → daemon-reload → start baseline API, verify receipt/health/singleton → start baseline frontend, verify BUILD_ID/routes/data → reopen. PostgreSQL and Redis stay running on their current data. Never roll back storage or run down migrations. All gates are machine-readable in the new assessment; older Gate 1 stays failed/superseded, never silently green.

Additional bounded operator checks (future authorized window):

```sh
# Dependency health only; /health alone is insufficient.
curl --fail --max-time 5 http://127.0.0.1:8000/health
curl --fail --max-time 5 http://127.0.0.1:8000/api/v1/status
systemctl is-active vlr-scheduler.service   # must report inactive for this model
systemctl show vlr-api.service -p MainPID -p TasksCurrent -p InvocationID
pgrep -af 'uvicorn|app.jobs.run'             # review argv/cgroups; one worker, no duplicate owner
journalctl -u vlr-api.service --since '<cutover UTC>' --no-pager
# Read and approve one scheduler owner with eight max_instances=1 jobs;
# verify one completed scheduled refresh, expected next-run timestamps, and no duplicate journal events.
```

Debian's packaged interpreter does not automatically add the retained `site-packages` directory under PYTHONHOME. Both the tested sandbox and proposed API override explicitly include `backend/runtime/lib/python3.13/site-packages` in PYTHONPATH. Do not omit it or substitute the mutable host virtualenv. Override/config environment precedence is part of the disposable systemd rehearsal gate.

After the first cutover passes, review restoring `Restart=on-failure` with a bounded delay; `Restart=no` is intentionally temporary during acceptance. Recapture effective unit hashes and verify a new receipt on the next authorized restart. Never leave the temporary policy undocumented as an availability assumption.
