# Integrated application recovery — Gate 2

> **New governing strategy:** [known baseline proposal](../../docs/BASELINE_DEPLOYMENT_PROPOSAL.md). September 17 provenance is unrecoverable from available evidence; stop pursuing it. Historical mode below is preserved for audit, not the current deployment path. New mode uses `strategy: new-known-baseline`, `stages: [candidate, baseline]`, purpose `baseline-rehearsal` (identical known artifacts) or `second-release-rollback` (distinct candidate plus proven baseline). It validates the baseline release manifest and full inventories, without claiming a historical startup identity. The latter additionally requires a reviewed baseline startup receipt and hash. Human review still must establish the receipt/artifact link. `seal.py` emits the baseline rehearsal input. Use the private Bubblewrap PATH and commands in the proposal; no production identity query occurs in new mode. Historical fallback rejection remains intact. A successful self-switch does not pass the second-release rollback gate.


This harness implements [the release acceptance sequence](../../docs/RELEASE_GATE_VERIFICATION.md#smallest-concrete-deployment-change-and-remaining-recovery-test). It is an isolated test, not a deployment tool. A successful run is conditional on an independently reviewed Gate 1 artifact/receipt. A boolean or archive filename is not proof of that historical identity.

Inspected startup: `app/main.py` awaits the real `init_db` before starting one scheduler; `app/core/db.py` runs `create_all` and additive `run_migrations`. `backend_worker.py` wraps the real lifespan solely to observe startup/shutdown and advance one real scheduler job. It never replaces `init_db` or migration functions and never uses `--lifespan off`. The deployed service uses one Uvicorn worker. `start-services.sh restart` rebuilds in the serving frontend directory and restarts production services; **do not use it for this test**. The separate scheduler unit is optional and must not run alongside the in-process scheduler.

## Application host prerequisites and invocation

Run as unprivileged `builder` on application host `vlr-api` / `10.0.0.21`. No root launch, production environment, systemd mutation, production storage, archive restoration over production, or whole-container rollback is involved. Only the current service identity is read from systemd before the test starts.

Required tools: Python 3.11+, Bubblewrap (`bwrap`) with permitted unprivileged user/mount/PID/network namespaces, `/usr/bin/node`, Redis server/CLI, and PostgreSQL 17 `initdb`, `postgres`, `psql`, `createdb`. No packages are installed by the runner. Missing tools or unavailable namespaces are blockers, not reasons to weaken isolation.

Required artifacts: **four completed, secret-free, dereferenced application trees** staged under `/home/builder/vlr-recovery-check`, with independently verified complete file inventories: candidate backend, attested historical backend, candidate frontend, historical frontend. Backend trees contain source plus a portable Python runtime and installed dependencies. Frontend trees contain `.next`, runtime dependencies and assets. No build/install step runs in the harness. Every file is hashed; symlinks, special files, and all `.env*` files are rejected. Any sanitization/relocation must be documented in the reviewed inventory and preserve the attested application/runtime identity. Do not copy production credentials into these trees or receipts. Ensure sufficient disk for two copies of each frontend (verified artifact and writable runtime copy), one copy of each backend, a 1 GiB new PostgreSQL data/log budget and at least 2 GiB reserve. The runner checks this minimum before copying; filesystem allocation overhead or unexpected growth can still cause a failed run. A prior capacity pass does not size these new inputs.

Supply the reviewed JSON manifest at `/home/builder/vlr-recovery-check/gate2-input.json`. It is intentionally not generated or populated with the fallback by this change. Its schema is:

| Field | Required value |
| --- | --- |
| `candidate_revision` | `9301682c4165d7507e49d6ad7678d14ca9df377e`; verify the candidate source/build inventory against this release independently |
| `secret_free_artifacts_reviewed` | Boolean true after reviewing all four artifacts for secrets, including compiled frontend output |
| `candidate_backend`, `historical_backend` | Objects with `root` (absolute staged directory), `files` (every relative file path → SHA-256), `source`, `runtime_home`, `python` (the latter three are relative paths within that tree) |
| `candidate_frontend`, `historical_frontend` | Objects with `root`, complete `files` inventory, and expected `build_id`; `.next` and `node_modules/next/dist/bin/next` must exist directly under `root` |
| `provenance.reviewed_startup_link` | Boolean true only after reviewing a contemporaneous receipt linking retained backend bytes/runtime to the running service start; this is a human evidence decision, not automated historical authentication |
| `provenance.pid`, `startup_timestamp`, `invocation_id` | Current service identity; timestamp must exactly match systemd's `ExecMainStartTimestamp` string. Last observed: `61821`, `Thu 2026-09-17 11:10:09 UTC`, `7b182addf99f4053bc8d665711feafe2` |
| `provenance.source_identity` | Attested immutable source identity including deployed dirty changes, if any |
| `provenance.archive_path`, `archive_sha256` | Original backend archive path and verified checksum; known fallback digest `f0ab700c450bd9edc11775e9b7af38ef8fdfd040b6f28f25fccdb4685c53fdaa` is explicitly rejected |
| `provenance.receipt_path`, `receipt_sha256` | Locally retained, redacted contemporaneous receipt and checksum |
| `provenance.backend_files_sha256` | SHA-256 of UTF-8 `json.dumps(historical_backend.files, sort_keys=True, separators=(',', ':'))`, independently linked to the receipt |

The inventory digest verifies internal consistency, not that someone truthfully linked it to the original archive. The reviewer must verify that source/runtime bytes actually derive from the attested archive, and that frontend artifact identities and candidate revision are correct. Do not manufacture a new receipt for the fallback. Known restored frontend BUILD_ID is `5RXlwj7jwc2eDLWI_-439`; its retained identity must still be checked when preparing the input.

Copy-ready commands from the application host:

```sh
cd /opt/vlr-api
python3 scripts/recovery/integrated.py --preflight
```

Preflight reads inputs and hashes only; it does not create or start a test. It exits 2 with exact missing inputs. After all prerequisites pass and the Gate 1 review is complete:

```sh
cd /opt/vlr-api
python3 scripts/recovery/integrated.py
```

This second invocation creates a **new mode-0700 `gate2-` directory** under `/home/builder/vlr-recovery-check`, copies only the reviewed application artifacts, rechecks their hashes, then starts the disposable sandbox. It prints its exact evidence location. It never uses the older private database or production backups/data. Bubblewrap enables only its own loopback; the runner verifies it is up without CAP_NET_ADMIN; no host network interface, host Unix socket, production directory, host environment or host `/etc` is available. `/usr`, `/bin`, `/lib` and `/lib64` supply read-only system binaries/libraries; no `/home`, `/opt`, `/run` or `/var` is mounted. Package-level Python audit hooks are not the network isolation boundary.

## Test sequence and failure conditions

1. Create fresh UTF8 PostgreSQL and Unix-socket-only Redis in `/work` (the new private state directory). PostgreSQL logs DDL. A fixture HTTP server exposes only `/matches/results`, backed by repository `tests/fixtures/results.html` with a unique per-run team marker. Unknown fixture requests fail acceptance.
2. Start candidate backend with the packaged interpreter and normal application lifespan. A call profiler observes both `init_db` and `run_migrations`; missing calls fail. Check dependency health and migration columns. Require the application's single scheduler, eight jobs with `max_instances=1`, and a real scheduled results refresh through HTTP fixture → parser → Redis → PostgreSQL. Other job times are suspended to make the bounded scenario deterministic; full coverage of all eight job bodies is not claimed.
3. Start the real candidate Next production server. Require `/results` to render the unique runtime marker, not merely return HTTP 200. This verifies populated frontend/backend integration over local HTTP; it is not a browser hydration or visual test.
4. Insert newer rows into **all four history tables**, plus persistent and expiring cache sentinels. Capture complete ordered row fingerprints/counts. Stop frontend then API, requiring successful lifespan/scheduler shutdown. Storage remains running.
5. Switch to the attested historical backend and historical frontend artifacts only. Repeat **normal schema startup**, real scheduled fixture refresh, dependency checks and integrated populated `/results` check. Verify the restored frontend BUILD_ID, imported application paths, selected artifacts, API/frontend process identities, packaged interpreter hash and Node executable hash.
6. Require complete history fingerprints/counts to remain identical and newer cache values/lease to survive. Results refresh is intentionally idempotent; unexpected data changes fail rather than being silently excluded. Require the same continuously running storage processes. Gracefully stop test applications and storage.

Any missing/changed input, wrong service identity, namespace failure, startup/migration error, scheduler error, missing marker, wrong BUILD_ID/module/runtime, changed fingerprint, lost sentinel/lease, storage exit, unknown fixture path, timeout, missing shutdown receipt or forced cleanup is a failure. Readiness is bounded at 40 seconds, individual HTTP reads at 5 seconds/2 MB, command calls at 30 seconds, and the complete sandbox at 600 seconds. Do not convert failures into passes by disabling migrations, scheduler, isolation or artifact checks.

## Evidence and cleanup

`state/result.json` records acceptance, per-stage identities/hashes, schema-call observations, scheduler outcomes, frontend BUILD_ID, history fingerprints and cleanup status. Stage logs and PostgreSQL DDL logs remain private beside it; `launcher.log` captures namespace failures. Inputs and original artifacts remain intact. The parent revalidates copied artifacts before execution. The test never rewrites repository evidence files.

Normal and error paths terminate all owned test processes. A graceful-shutdown failure remains a failure even if forced cleanup succeeds. Bubblewrap's private PID namespace and `--die-with-parent` bound descendants if the runner dies or times out. No host service stop command is needed. Retain the reported `gate2-` directory for review; after the launcher has exited and its evidence is reviewed, remove **only that exact newly created directory** to reclaim disk. Never remove the recovery root, original artifacts, prior evidence or production directories. On interruption inspect `launcher.log`/`launcher-failure.txt`; absence of `state/result.json` is not a pass.

## Gate 1: read-only collection on the application host

```sh
systemctl show vlr-api.service -p MainPID -p ExecMainStartTimestamp -p InvocationID
sudo journalctl -u vlr-api.service --since '2026-09-17 11:09:00 UTC' \
  --until '2026-09-17 11:12:00 UTC' --no-pager -o short-iso
rg --files --hidden /home/builder/vlr-recovery-check /home/builder/vlr-gates-private /var/backups \
  -g '!**/node_modules/**' -g '!**/.next/**' \
  -g '*.tar*' -g '*.zip' -g '*receipt*' -g '*deployment*' -g '*MANIFEST*' -g '*SHA256*'
```

This is a scoped filename inventory, not a whole-host or secret-content search. Permission errors/inaccessible journals are missing visibility, not evidence that no archive exists. If the running start differs, the September 17 log window is historical only. A matching filename or a newly created manifest is not running provenance. Needed next inputs remain the actual original archive path and contemporaneous receipt, then an independently reviewed link to the service identity and runtime.

Before sharing output, redact credentials, passwords, tokens, private keys, and credential-bearing PostgreSQL/Redis URLs. Share relevant identity fields/hashes and test assertions, not `.env` files, full raw receipts, or unrelated logs.

The baseline rehearsal exposed and fixed four launcher assumptions: resolve private Bubblewrap before clearing PATH; verify already-up namespace loopback without SIOCSIFFLAGS; explicitly include the packaged Python 3.13 site-packages; and recognize Next 16.2.7's awaited SIGTERM cleanup exit code 143 only for the frontend. Timeouts, API lifespan/scheduler shutdown receipts and forced-cleanup failure rules remain enforced. The retained Next source `node_modules/next/dist/server/lib/start-server.js` documents that signal exit behavior. Failed-run logs and result manifests remain private; only this task's redundant failed-run artifact/runtime copies were reclaimed, as recorded in the cleanup evidence.
