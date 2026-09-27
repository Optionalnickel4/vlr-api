# Release gate verification — 2026-09-27

## Superseding proposal: establish a new known baseline

**Current recommendation: NO-GO pending the new baseline gates.** The September 17 backend provenance is **unrecoverable from the available evidence**; no further provenance pursuit is required. Historical Gate 1 is **failed/superseded**, not passed. The retained historical fallback is not an exact copy of that process and is not an attested application-only rollback.

The [new baseline deployment proposal](BASELINE_DEPLOYMENT_PROPOSAL.md) is the governing plan. It separates (1) a maintenance transition from the unknown backend to a newly retained known backend/frontend and (2) a later, separately gated application release with tested rollback to that proven baseline. Read its [machine-readable assessment](verification/baseline/2026-09-27/assessment.json) and [artifact identities](verification/baseline/2026-09-27/artifacts.json). All earlier “recover the original backend” instructions and historical-only Gate 2 prerequisites below are retained as history and superseded for this strategy.

Before first cutover: sealed source/runtime/build review, immutable off-host retention, private baseline recovery rehearsal, real-schema restore/startup compatibility, deployment-launcher/systemd rehearsal, fresh DB/cache backups and restore proof, capacity, effective ingress attestation and maintenance/failure authorization must pass. After cutover: live startup receipts, health, singleton scheduler, data preservation and soak prove the baseline. Only then may a distinct second release seek GO after its own candidate→baseline rollback rehearsal. Proposed Caddy settings do not pass the ingress gate. No production action has been taken.

The active Caddy observation remains accepted: v2.11.4 PID 87 on :80, `val.jushosting.dev` to `10.0.0.21:3000`, no explicit proxy timeouts. This identifies VLR's frontend path, not effective end-to-end 80/90-second deadline compliance. The new plan requires a post-change active-config attestation if configuration is changed, without asking to recollect the old observation.

---

The following sections preserve earlier reviews; the proposal above controls current gate interpretation.

Application under test: **`9301682c4165d7507e49d6ad7678d14ca9df377e`**. No application or live configuration changes were necessary for the tested deadlines; no application fix commit was created. Evidence and reproducible review harnesses are in [verification/release-gates/2026-09-27](verification/release-gates/2026-09-27/). The recommendation remains **NO-GO**: full backend rollback and effective ingress deadline attestation remain unresolved. Cold-cache staging and durable application capacity pass. The latest closure section below supersedes the earlier measurements where noted.

| Gate | Result | Pass criteria | Outstanding requirement |
| --- | --- | --- | --- |
| Rollback provenance | **Unresolved; frontend restore and limited historical backend read checks pass** | Verified data-preserving full-service rollback with identified artifacts/runtime | Recover an attested old backend; isolated application switching preserves newer test data, but normal schema startup and integrated full-service recovery remain unverified |
| Ingress deadlines | **Active Caddy VLR route identified; end-to-end deadline gate open** | Compatible effective settings and finite application deadlines | Applied `meowth` connector/version and hostname-specific edge-policy receipts; confirmation of remaining server/middleware/streaming semantics from the already obtained Caddy export. No repeat configuration request or live mutation |
| Cold-cache staging | **Pass for three selected core details** | Empty isolated caches, sequential bounded real-source reads, populated cold/warm API responses, successful browser outcomes, no production writes | Broader sampling/load testing is not claimed; browser outcomes were measured after API warming |
| Build/backup capacity | **Pass for measured durable layout** | Measured build requirements, restored backups and sufficient headroom | 11.374 GB free after restores; 4.617 GB additional budget including 2 GiB reserve leaves 6.757 GB. Recheck recovered artifact size; off-host disaster recovery remains unverified |

## Active Caddy observation — VLR route identified

Starting review commit: **`366acc0e797116a3e4d39643c167debbf1b72687`**. Operator observation: **2026-09-27T15:39:41+00:00**, from read-only commands inside the Caddy LXC. This supersedes the earlier “no outputs supplied” assessment **for Caddy only**, and the earlier claims that the installed Caddy version and active route were unknown. The [structured receipt](verification/release-recovery/2026-09-27/caddy-ingress-assessment.json) preserves the supplied summary separately from our conclusions. No raw JSON export/hash or service start timestamp was supplied; none is fabricated. We accept the operator's active-config observation without asking for this LXC's configuration again.

Reported results: Caddy is active, **MainPID 87**, launched with `/usr/bin/caddy run --environ --config /etc/caddy/Caddyfile`; `caddy version` reports **v2.11.4**. `GET http://127.0.0.1:2019/config/` successfully returned active JSON. The server listens on **`:80`**, with host matches reported as vault, media, request, mcp, jamz, assets, val, openclaw, jarvis and jushosting.dev. Specifically, **`val.jushosting.dev` → `10.0.0.21:3000`**. No explicit reverse-proxy timeout settings or host match labelled VLR were reported.

**`val.jushosting.dev` is the VLR frontend ingress in the available deployment evidence.** This conclusion follows from the route destination and service identity, not the spelling of a matcher:

| Evidence | What it establishes |
| --- | --- |
| [Installed unit capture](verification/release/2026-09-27/configuration.json), `units.vlr-frontend` | VLR Next service uses `/opt/vlr-api/frontend` and `next start -H 0.0.0.0 -p 3000` |
| [Earlier provenance](verification/release-gates/2026-09-27/provenance-ingress.json), owner-supplied topology below | Public hostname is `val.jushosting.dev`; supplied tunnel `meowth` sends it to Caddy `localhost:80` on the separate LXC |
| New operator active-config observation | That hostname currently selects upstream `10.0.0.21:3000`, the recorded application host and production frontend port |
| [Prior static smoke](verification/release-closure/2026-09-27/public-smoke.json) | Public hostname, direct frontend and disk asset share SHA-256 `aee2d073d2a1157cfe5c98907f90b3967de4c3625f9ffb154bd1979ae2b917b0`; public curl returned 200 with Cloudflare/Caddy headers |

The supported chain remains **public `val.jushosting.dev` → Cloudflare / supplied Tunnel `meowth` → Caddy `:80` → VLR Next `10.0.0.21:3000` → server-side FastAPI `:8000`**. The frontend's server-side API wiring is recorded in [the release review](PRODUCTION_RELEASE_REVIEW.md#what-is-actually-running); port 3100 is the isolated preview. There is no repository/deployment evidence requiring another VLR ingress, although these observations cannot exclude additional unpublished routes. A host need not contain “vlr” to serve this application. The static match corroborates identity only; it does not attest tunnel identity or deadlines.

**What this closes:** the Caddy version/active-config availability and matching VLR route are now operator-observed, rather than inferred solely from a Caddyfile. No explicit reverse-proxy timeout override is reported in that active configuration. **What it does not close:** absence of explicit proxy timeouts is not a measured or configured 80/90-second deadline, nor proof of every server/middleware/edge limit or streamed delivery. The earlier Caddyfile and static curl cannot establish those properties. The isolated 12/80/90-second application tests retain their original scope.

Precise remaining ingress evidence:

1. **Applied tunnel receipt:** running `meowth` connector version/process and applied configuration version (or loaded local configuration identity), matching `val.jushosting.dev` → `http://localhost:80` including merged `originRequest` overrides. Earlier supplied YAML describes intent; the new Caddy observation does not attest what the connector loaded.
2. **Effective edge policy for this hostname:** dated applicable response/streaming limits and override/rule IDs, or an owner attestation that no overrides apply identifying the applicable Tunnel limits. General Cloudflare defaults and a fast asset response do not substitute for this.
3. **Narrow Caddy interpretation gap:** the supplied summary explicitly covers reverse-proxy timeouts, but does not state HTTP-server `write_timeout`, enclosing response-duration middleware, or buffering/flush behavior. A conclusion from the **already obtained** active JSON covering those fields and the matching handler chain would resolve this gap; do not request another Caddyfile, config export, version command or broad LXC collection. No contrary short timeout is evidenced. If the retained export has no such overrides, record that scope explicitly and assess the relevant version's defaults; do not invent values from their omission in the summary.

For applicable active-response limits across the chain, the existing acceptance criterion remains disabled limits or limits **greater than 90 seconds with delivery margin** (for example ≥100 seconds), with compatible streaming. Connect/request-read/idle keep-alive limits are distinct and are not automatically active-response deadlines. No long production request or live configuration change is needed or authorized by this review. The remaining tunnel/edge receipts are described below; the former Caddy collection instructions are superseded.

**NO-GO remains:** exact loaded backend provenance and integrated full-service recovery with normal schema startup and newer data preserved are still open, independently of ingress. Cold-cache and capacity passes are retained, not remeasured. This pass only reads repository evidence and updates documentation; no production access/change, application test rerun, migration, scrape or new public curl occurred.

## Operator-output assessment — no outputs supplied

Historical assessment; the active Caddy section above supersedes its missing-Caddy-output claims.

Review timestamp: **2026-09-27T15:36:43.210292+00:00** (review time, not an operator observation). Starting review commit: **`bea34d5df9cdb2fa635222d2092c129d2ed99cc3`**. The submitted operator-output block contains only the literal placeholder `[PASTE OUTPUTS HERE]`. **Zero command outputs, observation timestamps, process identities or artifact/configuration hashes were supplied.** There is no new operator evidence to compare or authenticate; do not treat the placeholder as a successful observation. The structured [assessment receipt](verification/release-recovery/2026-09-27/operator-output-assessment.json) records this absence explicitly.

| Open gate | Comparison with existing acceptance criteria | Result / precise missing evidence |
| --- | --- | --- |
| Exact loaded backend source and runtime | No deployment receipt, loaded identity or matching bundle supplied | **Open.** Need the contemporaneous service-start identity linked to immutable deployed source (including dirty changes), interpreter/dependency manifest and archive hash, with matching retained bytes. Historical bundle health/current disk hashes do not establish this link. |
| Integrated full-service recovery with normal schema startup | No integrated recovery transcript supplied; previous harness replaced `init_db` | **Open.** Need timestamped isolated candidate→attested-backend recovery evidence using unmodified normal schema startup, selected artifact/runtime and process identities, dependency readiness/one scheduler with fixture refresh, restored frontend BUILD_ID and populated backend-backed route, and graceful shutdown. Before/after complete history fingerprints and newer database/cache sentinels must demonstrate preservation while storage stays running without restore/flush. No new migration or recovery run is authorized or performed in this assessment. |
| Effective Caddy ingress deadlines | No active Caddy configuration or runtime receipt supplied | **Open.** Need timestamped active HTTP-server configuration export with hash, running Caddy version/process identity and proof its admin endpoint belongs to the serving instance; include matching route chain, server/transport response limits, buffering/flush settings and enclosing middleware. Applicable active-response limits must be disabled or exceed 90 seconds with delivery margin. Existing broader ingress criteria also retain the applied tunnel configuration/version and effective hostname-specific edge-policy receipts. |

**NO-GO remains.** Supplied source configuration stays **compatible**, not verified effective configuration; public static curl and isolated 12/80/90-second tests keep their original scopes. Existing narrowly scoped operator collection commands and acceptance procedures below remain available and were **not executed in this pass**. No access or repeated source configuration is requested.

Previously passed application-only rollback (with its startup substitution), selected cold-cache checks and measured capacity are retained without rerunning or expanding their claims. The last capacity observation remains 6,751,125,504 bytes beyond budget/reserve, not a fresh measurement. Prior process identities, hashes and timestamps elsewhere in this report are historical evidence, not refreshed attestations. This pass only reads repository evidence and edits documentation; no production operation, migration, VLR request or whole-container rollback occurred. Validation is limited to documentation links/fences, JSON parsing, protected-file preservation and `git diff --check`.

## Application-only recovery follow-up — 2026-09-27

This section supersedes earlier statements that Redis and scheduler startup were never exercised for the historical bundle. **NO-GO remains.** Evidence: [release-recovery](verification/release-recovery/2026-09-27/). No application changes, deployment, production restart, production storage changes, migrations or VLR requests were made. Prior cold-cache/deadline/final checks remain valid and were not repeated.

### Provenance: observations and confidence

| Claim | Source | Confidence / limit |
| --- | --- | --- |
| API PID 61821, September 17 11:10:09 UTC, one worker using mutable `/opt/vlr-api` and `.venv`; frontend PID 308 unchanged | Fresh `systemctl show` in `provenance.json` | High for systemd identity/launch metadata; no loaded-code attestation |
| Running API reports `commit: unknown` | Previously captured status; `app/status_meta.py` resolves Git once at import | High for that observation; even a Git value would need an immutable clean artifact link |
| `139378c` was committed 34 seconds after startup; prior commit `32e7e23` | Fresh Git history and earlier reflog | High for timestamps, insufficient to choose a loaded revision; dirty source could have been imported |
| Historical restored bundle is `139378cb7505c6257c7b69da3491e382c4ebf0bc`, with copied current Python/dependencies | Existing archive/source manifest, 5,752 hashes rechecked by new harness | High for bundle identity; **no evidence it equals the running process** |
| Current disk Python 3.13.5 / Uvicorn 0.52.4 | Previous inventory and isolated imported runtime | High for disk/test runtime; production's already imported versions remain unknown |
| No additional startup identity evidence available to this account | `/proc/61821/{exe,cwd,maps}` permission denied; narrow journal read reports no entries and restricted visibility | Access limitation, not proof the journal contains no evidence |

Inspected `deploy/vlr-api.service`, optional scheduler unit, `start-services.sh`, installed-unit evidence and history. They contain no immutable release slot, artifact digest or startup manifest tying PID to source/runtime. `start-services.sh restart` rebuilds in the serving frontend directory and restarts services; it is unsuitable as an artifact-preserving release/rollback mechanism. It was not executed. An executable path, healthy endpoint, Git timestamp, or current package list cannot recover overwritten Python module contents.

Exact evidence needed: a contemporaneous deployment/startup record tying this service start (and ideally boot ID/invocation ID) to a clean source tree digest, runtime/dependency manifest and retained archive hash, plus the matching bytes. A source commit alone omits then-uncommitted files and runtime. A present-day directory hash is not retroactive attestation. The following **operator-only, read-only** collection is narrowly scoped to the known API startup; it is not an access request:

```sh
sudo journalctl -u vlr-api.service --since '2026-09-17 11:09:00 UTC' \
  --until '2026-09-17 11:12:00 UTC' --no-pager -o short-iso
systemctl show vlr-api.service -p MainPID -p ExecMainStartTimestamp -p InvocationID
sudo readlink /proc/61821/exe /proc/61821/cwd
sudo sha256sum /proc/61821/exe
```

Review locally and share only release/runtime identity fields, with secrets removed. The executable hash identifies the interpreter inode, **not** imported Python code/dependencies. If the journal lacks a deployment manifest, the smallest missing artifact is the original immutable September 17 application bundle and its contemporaneous start/deployment receipt. For an already identified owner-held archive, collect its checksum without extracting over production:

```sh
# Replace the path with the actual retained deployment archive; no archive is assumed to exist.
BACKEND_ARCHIVE=/absolute/path/to/retained-backend-deployment.tar.gz
sha256sum -- "$BACKEND_ARCHIVE"
tar -tzf "$BACKEND_ARCHIVE" | rg '(^|/)(MANIFEST.json|SHA256SUMS.json|requirements.lock|vlr-api.service)$'
```

Read the listed manifest member with `tar -xOzf "$BACKEND_ARCHIVE" exact/member/path` once its name is known. A newly generated receipt for the fallback cannot satisfy the historical claim. If no original bundle/receipt exists, exact rollback to the running worker remains unprovable; an explicitly selected, separately qualified historical fallback would be a different release decision.

### Executed application switch and data preservation

Command: `python3 docs/verification/release-recovery/2026-09-27/recovery.py`. The harness reuses only the stopped private restored PostgreSQL cluster and creates a new Redis Unix socket with TCP/persistence disabled. It starts real single-worker Uvicorn twice over a private Unix socket: candidate source, then historical bundle source with the restored interpreter/dependencies. Only these API processes switch; database and Redis stay running throughout. Python audit hooks reject TCP and Unix connections outside the private recovery directory. No production environment file is copied into either source directory; storage environment overrides are explicit. The previous database dump is **not restored during the switch**.

**Startup substitution:** normal lifespan calls `init_db`, which executes migrations. To respect this pass's no-migrations boundary, the harness replaces that call with a successful database `SELECT` check. Scheduler construction/start/shutdown and job functions remain real; the existing `live_matches` job is advanced once against a seeded empty live list. This verifies a successful no-source-work scheduler tick and fresh Redis heartbeat, not scraping recovery or all eight job bodies. It does not qualify unmodified normal startup.

Before switching, the harness adds a new history row to the isolated database and a new persistent cache sentinel, plus retained/refresh keys. It compares ordered full-row fingerprints and counts of all four history tables across both API versions; it checks cache values and that the lease TTL remains positive. These additions are newer than the retained dump. Earlier failed attempts left two other sentinel rows only in the private database; they are retained and included in the final fingerprints.

See `recovery.json` for the final results and exact module/runtime paths. Both versions pass health, PostgreSQL/Redis checks, two-row history reads, eight jobs with next-run times, and a newly completed scheduler heartbeat. All four table fingerprints match before/after switching, and the new cache sentinel, retained copy and expiring lease survive. Both lifespans exit before process completion. The initial harness attempt used a nonexistent FastAPI helper; the second incorrectly required exit 0 although Uvicorn re-raises SIGTERM after graceful shutdown. Their partial results remain in `recovery-initial.json` and `recovery-second.json`; the final harness checks the completed-lifespan marker and exit 0 or SIGTERM. No application assertion was weakened.

**Proven:** switching only application processes to this identified historical bundle preserves newer **isolated** data for the exercised paths. This does not prove retention of future production writes, equality to current production code, normal migration startup, full scheduler refresh behavior, systemd switch/readiness, or integrated restored frontend→backend recovery. Previous frontend artifact/startup checks stand independently. **Full-service recovery gate stays open.** All private test processes are stopped; production service identities and protected environment/unit/ignore/plan bytes match before/after. `checks.json` also revalidates all **511 candidate source blobs** and measures **11,368,103,936 bytes free**, leaving **6,751,125,504 bytes** after the unchanged **4,616,978,432-byte** additional release budget/reserve; capacity still passes.

### Smallest concrete deployment change and remaining recovery test

An attested backend artifact must contain immutable source (including any deployed dirty patch), relocatable Python/dependencies with hashes, the required OS-library inventory, original unit/configuration-name manifest, archive checksum and startup receipt. Do not include PostgreSQL/Redis data in the application rollback artifact. The existing fallback already supplies much of the packaging; its missing original identity cannot be repaired by relabeling it.

For a future authorized deployment, retain two immutable backend directories and point `WorkingDirectory`, `PYTHONHOME`, `PYTHONPATH` and an **absolute** `runtime/bin/python3.13 -m uvicorn app.main:app --workers 1 ...` command to one selected slot. The copied interpreter requires its runtime home/site-packages; copying a virtualenv's script shebang alone is insufficient. Preserve the protected production environment file separately. Retain the old frontend artifact and point its unit to that completed artifact. A reviewed systemd override switching only these application paths is sufficient; no container image restore or database/cache replacement is needed. No such override was installed here.

Remaining isolated full-service acceptance: use the attested slot and normal startup in a separately authorized migration-capable sandbox (or first implement/test an explicit schema-preserving startup mode); use private database/Redis, fixtures and blocked external egress. Start candidate, append newer history and cache values, stop frontend then API, switch application slots only, start old API and verify dependency readiness/one scheduler, then old frontend and verify its BUILD_ID plus a populated backend-backed route. Exercise scheduler refresh with fixtures, compare complete history fingerprints and sentinel values, and verify graceful shutdown. Capture selected slot, imported module paths/runtime hashes and process identities at each stage. Keep storage running without restore/flush. The present test establishes the storage-preserving mechanism but leaves these acceptance observations open; whole-container rollback remains unacceptable.

### Integrated recovery harness implementation — not yet executed

The [Gate 2 runner and operator instructions](../scripts/recovery/README.md) now implement the remaining integrated sequence with normal schema startup, private storage, a real fixture-driven scheduler refresh, real Next/backend integration, newer-data preservation and graceful shutdown. Startup/deployment scripts were inspected; no application startup or deployment script changed. The new runner rejects the known fallback and requires independently reviewed startup-linked artifacts. It does not turn a self-declared manifest into Gate 1 proof.

**Gate 2 remains open.** Only safety unit tests and read-only preflight ran. Preflight reports missing `bwrap` and `/home/builder/vlr-recovery-check/gate2-input.json`; no isolated application/storage process or migration was started. The missing manifest must identify an attested original backend archive/receipt, verified complete candidate/historical backend/runtime and frontend inventories, and expected frontend BUILD_IDs. The existing results HTML fixture is available. Namespace support and integrated runtime behavior remain untested until those prerequisites exist; no unsafe fallback run is permitted.

**Gate 1 remains open.** New read-only systemd observation: PID 61821, `Thu 2026-09-17 11:10:09 UTC`, invocation `7b182addf99f4053bc8d665711feafe2`. Scoped filename inspection under `/home/builder/vlr-recovery-check`, `/home/builder/vlr-gates-private`, and `/var/backups` found known fallback/backend packaging and frontend backup artifacts, not an original startup-linked backend receipt. Unprivileged startup-window journal read returned no entries with a restricted-visibility warning; this does not prove that privileged logs or other backup locations lack evidence. Archive names do not prove running identity. See the [implementation receipt](verification/release-recovery/2026-09-27/integrated-harness-assessment.json).

NO-GO remains for the unresolved backend and ingress gates. No production restart, deployment, migration, storage/cache mutation or whole-container rollback occurred. Prior application-only preservation passes remain scoped as before.

### Effective ingress attestation: exact missing observations

The [latest active Caddy assessment](#active-caddy-observation--vlr-route-identified) is authoritative for current scope. Caddy's active route/version and absence of explicit reverse-proxy timeouts have been supplied. The earlier broad Caddy collection commands are removed because that configuration has already been obtained; no repeated LXC configuration request is required. Only the narrower server/middleware/streaming interpretation of that retained export remains unreported, alongside the tunnel/edge receipts below. The 80/90-second values are application deadlines, not deadlines demonstrated by Caddy configuration or the static curl.

For `meowth`, the missing observation is the **active connector's applied configuration/version receipt**, including matching hostname/service and merged originRequest overrides, tied to the running connector version/process. A disk YAML or a desired remote configuration alone is insufficient. A retained connector startup/configuration log may provide the applied version; if it does not, leave that evidence absent. Cloudflare edge policy additionally needs the hostname's effective response/streaming limits and applicable override/rule IDs from the authorized account owner; general published defaults are not tunnel-specific proof. A narrowly scoped read-only account collection, when account/tunnel IDs and a read token already exist, is:

```sh
# Credential remains in the environment, never a curl argument or printed header.
python3 - <<'PY'
import json, os, urllib.request
account = os.environ['CF_ACCOUNT_ID']
tunnel = os.environ['CF_TUNNEL_ID']  # UUID for meowth, not its display name
url = f'https://api.cloudflare.com/client/v4/accounts/{account}/cfd_tunnel/{tunnel}/configurations'
req = urllib.request.Request(url, headers={'Authorization': 'Bearer '+os.environ['CF_READ_TOKEN']})
with urllib.request.urlopen(req, timeout=10) as response:
    body = json.load(response)
assert body.get('success'), 'Configuration read did not succeed'
print(json.dumps(body['result'], indent=2))
PY
```

The endpoint is documented in the [Cloudflare Tunnel API](https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/subresources/cloudflared/). For a locally managed tunnel this remote configuration may not represent its loaded YAML; retain that distinction. Run into a private file and redact credentials/unrelated hostnames before sharing. Match its remote version with the running connector's applied-version receipt; this API result alone remains desired configuration. For edge overrides, the exact missing artifact is a dated effective-policy export for **only `val.jushosting.dev`**, including timeout values and matching rule IDs (or an owner statement that no overrides apply, identifying the applicable Tunnel limits). No account IDs, policy IDs or credential are present here, so inventing an executable rule-specific API URL would misstate available evidence. Do not generate a long production detail request to infer settings. The previous static curl and isolated 12/80/90-second tests remain valid within their original scopes.

## Previous closure review — supplied tunnel topology and enlarged disk

This section supersedes earlier unresolved-capacity and unknown-topology statements. New evidence is in [release-closure/2026-09-27](verification/release-closure/2026-09-27/). **NO-GO remains:** full backend rollback has not been verified, and effective public-ingress deadline settings remain unattested. Capacity now passes. No application code changed and completed cold-cache/final application tests were not repeated.

### Backend recovery: useful artifact, incomplete rollback

`baseline.json` records `systemctl show` identities/commands, unit hashes and the interpreter checksum. API PID **61821** still runs `/opt/vlr-api/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`, with working directory `/opt/vlr-api`, installed unit `/etc/systemd/system/vlr-api.service` and protected `.env`. Frontend PID **308** is unchanged. The configuration names and exact private copies recorded below remain valid. Python on disk is **3.13.5**; the complete installed dependency inventory is `installed-python-packages.json` (including Uvicorn **0.52.4**, httpx **0.28.1**, asyncpg **0.31.0**, Redis client **8.1.0**, SQLAlchemy **2.0.52**). These are current disk versions, not proof of versions already imported by the old process. The exact loaded source remains unknown; neither Git date nor current `.venv` closes that gap.

`python3 docs/verification/release-closure/2026-09-27/package_fallback.py` archived historical source **`139378cb7505c6257c7b69da3491e382c4ebf0bc`**, the copied interpreter/stdlib and current installed dependencies. It removes editable-install indirection only from the copy, so imports cannot resolve back into the changing production checkout. First extraction safely rejected an absolute stdlib symlink; the final archive dereferences copied links and restores with Python's `data` extraction filter. No production file was edited. Failed-attempt files remain private and are included in current disk use.

Verified archive: `/home/builder/vlr-recovery-check/backend-fallback-139378c-portable.tar.gz`, **66,175,718 bytes**, SHA-256 **`f0ab700c450bd9edc11775e9b7af38ef8fdfd040b6f28f25fccdb4685c53fdaa`**. All **5,752** regular-file hashes match after extraction. Expanded bundle is **192,485,242 logical bytes**; allocated restored size is **208,490,496 bytes**. Source tree and manifest are recorded in `backend-artifact.json`. This is a **known historical fallback candidate**, not the exact running backend artifact. It depends on the existing OS shared libraries (`ldd` captured in `final-preservation-capacity.json`), so it is not an independently bootable system image.

`restore_checks.py` used the restored Python/source against a fresh **disk-backed**, Unix-socket-only PostgreSQL cluster on logical port **55440**. It restored the retained database dump, verified all four snapshot counts, then called the historical ASGI app: `/health` returned HTTP **200**, object; `/api/v1/history/results?limit=2` returned HTTP **200**, two-element array. Before/after row counts matched. The harness rejects every TCP connection, preventing VLR and production storage access. The restored interpreter prefix and imported application path both point inside the recovery directory. Eight scheduler jobs could be constructed, but were **not started**. The private cluster was stopped afterward.

**Verification boundary:** these are read-only ASGI health/history checks, not a Uvicorn/systemd/full-scheduler recovery test. The historical normal lifespan executes schema initialization/migrations; it was not run. Emergency `--lifespan off` also disables the in-process scheduler, and Redis operation was not verified by this new backend probe. Consequently this bundle does **not** pass the full-service rollback gate. Existing frontend restoration/startup evidence remains valid; a second durable extraction verified all **25,776** hashes and the same BUILD_ID. No new backend service definition has been installed or declared ready.

**Snapshot alternative evaluated:** this guest is LXC, with root device `/dev/mapper/pve-vm--221--disk--0`; no `pct`, `qm`, `pvesm`, hypervisor backup inventory or usable snapshot is accessible here. A current disk-only LXC snapshot would capture today's on-disk candidate/dependencies/configuration, **not the old Python process memory/source**. Reverting the whole container could also revert `/var/lib/postgresql` and `/var/lib/redis` on that root filesystem, discarding later data. Such a revert is not an acceptable data-preserving application rollback. No snapshot restore has been verified. A historical backup must be mounted/extracted into an isolated location and its application artifacts tested; its database/cache files must never replace live storage.

**Required infrastructure/artifact action:** on application host **`vlr-api` / `10.0.0.21`**, recover an attested September 17 backend deployment bundle (source, Python/dependencies, original unit and configuration-name manifest) to a new private directory under `/home/builder/vlr-recovery-check`. Obtain it from the backup owner or the Proxmox host owning the above LXC volume; that hypervisor's hostname and historical-backup availability are unknown, so no executable hypervisor restore command can honestly be supplied. Reserve **1 GiB** for compressed plus expanded application recovery as budgeted below; remeasure if larger. If extracting an entire container backup is necessary, provision separate storage for its actual uncompressed image plus at least **2 GiB reserve**, rather than restoring over CT 221 or assuming this guest's free space covers a whole image. Expected effect: a testable historical application recovery slot without touching serving processes/data. Reversal: stop only isolated test processes and remove only the newly created recovery copy after review; retain the original backup. Pass requires attested provenance, hash verification and isolated API/Redis/history/scheduler verification with network fixtures and no production writes. The current limited bundle cannot substitute for that evidence.

### Public ingress: supplied configuration, observed request, remaining uncertainty

The following is **user-supplied configuration evidence**, not inspected effective runtime configuration:

```yaml
# cloudflared tunnel meowth, separate LXC shared with Caddy
ingress:
  - hostname: val.jushosting.dev
    service: http://localhost:80
  - service: http_status:404
```

```caddyfile
{
    auto_https off
}
:80 {
    @val host val.jushosting.dev
    handle @val {
        reverse_proxy 10.0.0.21:3000
    }
}
```

The supplied route establishes **Browser → Cloudflare edge/Tunnel `meowth` → Caddy localhost:80 → Next `10.0.0.21:3000` → server-side FastAPI `:8000` → Redis/Postgres** (VLR only on ordinary refresh paths). It does not publish FastAPI directly through this hostname. `auto_https off` fits HTTP inside the tunnel; public TLS is terminated at Cloudflare. No short response timeout or response-buffer override appears in these excerpts.

[Caddy's documented defaults](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy) have no response-header/read timeout, and immediately flush responses of unknown content length. That is compatible with Next's streaming and the application's **80-second backend / 90-second initial-page** budgets; explicit other configuration could change it. [Cloudflare's general connection-limit table](https://developers.cloudflare.com/fundamentals/reference/connection-limits/) gives a **125-second proxy read limit**, greater than those budgets, but explicitly redirects Tunnel users to origin parameters. It is not an independently verified effective limit for `meowth`. [Tunnel origin parameters](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-parameters/) distinguish the default **30-second TCP connect timeout** from the **90-second idle keep-alive timeout**; neither is an active-response 30/90-second cutoff. Do not increase these settings merely because their numbers resemble application deadlines.

`public-smoke.json` records only static-asset requests, bounded to 15 seconds/request and 2 MB/body (initial Python pair additionally wrapped by a 40-second process bound). Direct Next: **200**, **3,377 bytes**, **97.7 ms**. Python public request: **403**, **87.2 ms**, cause unknown. One diagnostic `curl --max-time 15 --max-filesize 2000000` to the same asset returned **200**, `server: cloudflare`, `via: 1.1 Caddy`, `CF-Cache-Status: MISS`, and exactly the same SHA-256 **`aee2d073d2a1157cfe5c98907f90b3967de4c3625f9ffb154bd1979ae2b917b0`** as disk/direct Next. This observes working static delivery through Cloudflare/Caddy for that client. It does not independently prove the tunnel identity, every upstream address, browser behavior, streaming or long-response survival. No dynamic detail request, scrape, production cache flush or load test occurred.

The existing isolated **12-second healthy**, **80-second backend 504**, and **90-second Next unavailable-state** tests below remain the deadline evidence. No code/configuration correction is justified by the supplied excerpts. **Configuration review passes for the supplied route; the stricter effective-ingress gate stays unresolved.** At that earlier review, Caddy/cloudflared versions and effective settings were unknown. The latest active Caddy section supersedes the Caddy-version/route gap and lists only the remaining evidence; do not repeat the Caddy configuration collection. If verifying remaining settings would require live infrastructure changes, leave that work unresolved until separately authorized. This task proposes no live proxy mutation, so there is no proxy rollback or added space requirement. Optional browser/content polish is unrelated to these blockers.

### Capacity: passed on the enlarged durable filesystem

`df -B1 /` now reports total **21,024,690,176 bytes** on ext4; initial available **13,156,806,656 bytes**. The disk increase was already present when this follow-up began; this task did not resize it. `/tmp` remains memory-backed and is not used for these restores. All existing backups, production artifacts/data/caches and failed/new recovery artifacts are retained.

Measured additional durable restore allocations: frontend **724,770,816 bytes**, complete isolated PostgreSQL cluster **119,771,136 bytes**, backend restored tree **208,490,496 bytes**, and backend packaging tree **208,121,856 bytes**. Existing compressed database/frontend artifacts remain **9,901,311 / 215,041,425 bytes**; the verified backend archive adds **66,175,718 bytes**. `restoration.json` records sampled available-space minimum **11,379,400,704 bytes** during restoration; final settled measurement was lower, **11,373,789,184 bytes**, so use the final measurement for budgeting rather than treating samples as an absolute peak bound. The complete new recovery directory occupies about **1.782 GB**, including failed packaging artifacts. Existing retained candidate build/source occupies **108,232,704 allocated bytes**.

The earlier exact-release build measurement is reused: sampled **702,152,704-byte RSS** peak; **94,716,374-byte logical `.next`** peak; **96,182,272-byte** total filesystem decrease during the build. Prior candidate `node_modules` measured **712,368,128 bytes**. No rebuild was justified by a documentation-only follow-up. Free disk at final preservation check: **11,373,678,592 bytes**, after durable restores and all retained archives.

Conservative **additional** budget, on top of everything already present:

| Item | Bytes |
| --- | ---: |
| Candidate pinned dependencies, prior measurement | 712,368,128 |
| Another build output, prior measured filesystem delta | 96,182,272 |
| Another source tree allowance | 33,554,432 |
| Candidate backend runtime allowance | 268,435,456 |
| New database dump allowance | 16,777,216 |
| Another compressed frontend archive allowance | 268,435,456 |
| Missing attested backend artifact plus expansion allowance | 1,073,741,824 |
| Operating reserve | 2,147,483,648 |
| **Total additional budget** | **4,616,978,432** |
| **Available beyond that entire budget/reserve** | **6,756,700,160** |

Use separate release/recovery directories on `/home/builder`'s ext4 filesystem; keep PostgreSQL/Redis at their existing paths. Build serially, then perform recovery checks, and recheck `df` before any later cutover. Capacity passes for this measured application layout with explicit allowances; the unknown historical artifact must fit the 1 GiB allowance or be remeasured. Memory remains 4 GiB with about 1.35 GiB available at preflight; swap is now 2 GiB with about 1 GiB used. Successful prior build peak is not permission for concurrent heavy builds/restores.

The existing database dump was hash-verified and restored again specifically to verify this new durable layout and the historical backend's history reads; all snapshot table counts matched. There was no new production dump or database connection in this follow-up. Backups are recoverable locally, but **not protected against loss of this host**; off-host retention remains a disaster-recovery risk, not a claim of verified off-host recovery. No additional capacity increase is currently necessary for this application layout. If off-host durability is required by policy, copy the retained artifacts/configuration privately to a named backup destination and verify hashes there; no destination was supplied and no transfer is claimed.

## 1. Earlier rollback verification (retained evidence)

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

## 2. Earlier isolated deadline verification

The latest closure section supplies the formerly missing route. The following application tests are retained without rerunning them.

**Configured application limits, read from pinned source:** `frontend/src/lib/vlr.ts` defines 90,000 ms for initial detail-page upstream reads, including headers/body, and 10,000 ms for ordinary loaders/proxies. `app/api/v1/routes.py` wraps detail cache/refresh in an 80-second deadline. History persistence after cache publication has a five-second budget. API Uvicorn uses one worker; no additional request-duration override is present in the installed ExecStart. These limits are application behavior, not proxy defaults.

**Actual isolated tests:** `staging_backend.py` in fixture mode used the real candidate FastAPI routes/parser and private Redis/Postgres, with saved HTML replacing VLR transport. Candidate compiled Next ran on loopback 3111 and the private API on 8111. No live upstream calls were made for deadline tests.

| Test | Observed result | Pass criterion |
| --- | --- | --- |
| Healthy 12-second fixture via FastAPI | 200 bare match object in **12,045.4 ms** | Valid response beyond the former 10-second limit, within 80 seconds |
| Healthy fixture through Next/browser | Loading at **203 ms**, populated match at **12,566 ms**, HTTP 200, zero page errors | Prompt loading and successful completion, no premature 10-second failure |
| Hung refresh through real FastAPI detail route | **504** in **80,002.6 ms**, `{"detail": string}` shape | Finite 80-second backend deadline, no indefinite request |
| HTTP service bypassing backend route deadline, through Next/browser | Loading at **150 ms**, unavailable state at **90,305 ms**, HTTP 200, zero page errors | Independent 90-second frontend deadline and honest failure UI |

The final case deliberately bypassed the backend route only in the private harness; it proves Next's own limit rather than remeasuring FastAPI's 80 seconds. The initial direct-API test accidentally inherited httpx's five-second idle timeout; those failed attempts are retained in `deadline-api-initial.json`. `deadline_probe.py` disables that client idle timeout while retaining the helper's 95-second whole-request deadline; the corrected results above are from that rerun. No application setting or assertion was weakened.

Effective-ingress uncertainty and the owner evidence needed are described in the latest closure section; no LXC access or live change is requested.

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

## 4. Earlier build and backup measurements (capacity shortage superseded)

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

**Historical assessment, superseded by the latest durable restores and budget above:** provision enough durable space for both releases, recovery work and reserve; obtain the missing backend artifact; verify backup retention outside this nearly full root volume. If a recoverable Redis disk backup is required for the deployment's disaster-recovery policy, have an authorized operator copy and verify the existing persistence artifact without changing the live cache. Do not use the passing temporary restores as a durable-capacity pass.

## Final checks, cleanup and recommendation

Fresh final checks on the pinned archive: **284 backend tests, 348 frontend tests (25 files), lint, TypeScript, and clean webpack production build all pass**. No application code changed, so no new production-code regression test was needed; the existing deadline/cache/history suites ran in full. All **511 tracked archive file blobs** still match the pinned Git commit after verification.

`final-preservation.json` confirms unchanged production PIDs/start times, unit-file hashes, environment-file bytes, `.gitignore`, and the untracked plan. All private HTTP servers, Redis and PostgreSQL are stopped. The three source GETs wrote only private staging storage. Production interaction consisted of configuration/artifact reads, a read-only database snapshot/dump, a read-only status GET and a public TLS handshake. No live proxy changes, production detail refreshes, schema changes, cache mutations or service restarts were performed by this task. Normal production scheduler activity was not stopped or rolled back.

**NO-GO remains for full backend rollback and effective-ingress attestation.** Capacity and selected cold-cache staging pass. The release review’s deployment/service order remains conditional; do not execute it. Latest production preservation checks pass in `release-closure/2026-09-27/final-preservation-capacity.json`. No deployment, service restart, production configuration/data/cache change, migration or VLR request occurred in this follow-up. Browser/content polish is optional and cannot close these gates.
