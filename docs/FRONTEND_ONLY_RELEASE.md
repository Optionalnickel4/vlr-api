# Verified frontend-only release

The baseline proposal is stopped. This release replaces only `/opt/vlr-api/frontend/.next`, using the existing tested build. **Ready for frontend-only cutover authorization; production cutover has not run. No frontend-specific blocker was found.** Recheck the supplied preflight immediately before execution; drift or a failed smoke is a stop/rollback condition.

## Exact identity and retained artifacts

Reviewed release commit: **`9301682c4165d7507e49d6ad7678d14ca9df377e`**. Last frontend-changing commit: **`a251c99ade3e8d426e2782ab5d140815db1f33d4`**. Both and current HEAD have frontend tree **`2a5c474942a81a58ceda8cf49ad2398a65e763ae`**. The latter commit also contains backend changes: **do not deploy the whole commit or restart the backend**. Only its verified frontend output is selected.

Existing build: `/home/builder/vlr-release-review-9301682/frontend/.next`, BUILD_ID **`86jVlbyKpPMhJnvsgczQ5`**, from the successful 14:57 UTC webpack build in [checks.json](verification/release-gates/2026-09-27/checks.json). No rebuild occurred. Every retained frontend source file matches the reviewed commit. Existing 348 frontend tests, TypeScript, lint, production build and route-specific visual/browser evidence are reused; source has not changed.

| Artifact | Exact location | SHA-256 |
| --- | --- | --- |
| Candidate `.next` archive (17,527,940 bytes) | `/home/builder/vlr-frontend-only-9301682/frontend-next-9301682.tar.gz` | `67816ae50c7ce9b05e50d40957cea82d69542e08449f7a6f1e641c2c7e4030b2` |
| Existing complete frontend rollback (215,041,425 bytes) | `/home/builder/vlr-gates-private/frontend-rollback.tar.gz` | `cfabf6b2d94faf3d253bcdbb5191c10b0fe725d00ba3a992891de53ad992a5b6` |
| File/runtime manifest | `/home/builder/vlr-frontend-only-9301682/manifest.json` | `a04eba4df875cabeac017de0da4251aa81caec3aa4affb3493c35c008451a502` |

Candidate archive member hashes exactly match the retained build. The rollback archive was freshly extracted to `/home/builder/vlr-frontend-only-9301682/rollback/frontend` on durable disk: **25,776 archive regular files plus one hard-linked file verified**, no mismatch, BUILD_ID **`5RXlwj7jwc2eDLWI_-439`**. Its original Git revision is not asserted; these exact retained bytes are the tested frontend rollback target.

Both restored rollback and candidate served HTML 200 and byte-matching build-specific static assets in private network namespaces using the unchanged Node/Next runtime. Both exited cleanly. No backend/database/cache was started or contacted. See [artifact identities](verification/frontend-only/2026-09-27/artifacts.json), [candidate smoke](verification/frontend-only/2026-09-27/candidate-smoke.json), [rollback smoke](verification/frontend-only/2026-09-27/rollback-smoke.json), [source/runtime parity](verification/frontend-only/2026-09-27/parity.json) and [assessment](verification/frontend-only/2026-09-27/assessment.json).

## Why the cutover is only a directory swap

The deployed `node_modules`, public assets, package files and Next configuration match the rollback inventory. Candidate source package/config/public files match the verified commit. No dependency install, public-file replacement, config change, unit override, daemon-reload or build is needed. Node is `/usr/bin/node` with SHA-256 `fde6a4bf8d0562f7751d1a2d6cb9b417c4cfe107bbcb0aa3e9a24e125e348f48`.

The inspected frontend unit has only `After=vlr-api.service` (ordering), **no backend activation/stop propagation and no pre-start/post-stop hooks**. It continues to use the existing `.env`, port 3000 and command. Only `vlr-frontend.service` is stopped/started. Do not use `start-services.sh`, the full-release/baseline overrides, `git checkout` in production, or a container snapshot restore.

No backend service/configuration/code, PostgreSQL, Redis, Caddy/Cloudflare configuration or migrations are changed. No backup, restore, cache flush or warm-up is part of this release. Existing backend/scheduler activity and normal user traffic continue independently; this is not a promise that those processes stop writing. Mandatory smoke checks request **static frontend assets only**, avoiding API cache-miss side effects. The frontend does not deliver backend-only analytics fixes; existing backend behavior remains as-is, outside this visual release.

## Cutover commands — review only, not executed

Run on the application host as the operator with sudo. Both prepared trees are already restored and hash-checked. The moves are on the same filesystem. About 5 GB remained after preparation; the preflight requires at least 1 GiB reserve. The file check must pass again immediately before stopping the frontend. Any changed runtime, unit/drop-in, build, archive or failed check blocks this minimal swap until reviewed.

```bash
set -euo pipefail
cd /opt/vlr-api
R=/home/builder/vlr-frontend-only-9301682
F=/opt/vlr-api/frontend
python3 scripts/frontend_release/verify.py "$R" \
  --manifest-sha256 a04eba4df875cabeac017de0da4251aa81caec3aa4affb3493c35c008451a502
test ! -e "$R/precutover-next"
test ! -e "$R/failed-next"
systemctl show vlr-api.service -p MainPID -p InvocationID > "$R/api-before.txt"
systemctl show vlr-frontend.service -p MainPID -p InvocationID > "$R/frontend-before.txt"

sudo systemctl stop vlr-frontend.service
sudo mv -- "$F/.next" "$R/precutover-next"
sudo mv -- "$R/candidate/.next" "$F/.next"
sudo systemctl start vlr-frontend.service
```

Stop/start affects frontend requests. Expect roughly **5–15 seconds** interruption normally; reserve **two minutes**. Existing `TimeoutStopSec` is 90 seconds, so an active request may extend the stop; allow at most 30 seconds after start for readiness. Caddy may return transient 502 while port 3000 is down. Existing browser tabs may request old chunk URLs after the swap and need one refresh. Do not force-stop unrelated services or extend a failed window indefinitely.

If any command after the frontend stop fails, keep the frontend stopped and run the rollback sequence below. No runtime/dependency/config files have moved.

## Smoke and rollback trigger

Require the candidate BUILD_ID, active frontend service/new invocation, localhost and public build-specific asset 200 with the expected hash, and unchanged backend PID/invocation. Do not poll dynamic pages or uncached API/detail routes for this smoke. Visual behavior is covered by the unchanged-source browser evidence. The public URL uses the existing route; no Caddy change or deadline exercise is required.

```bash
test "$(cat "$F/.next/BUILD_ID")" = 86jVlbyKpPMhJnvsgczQ5
# Each attempt <=2s, at most 10 attempts and 9 one-second sleeps: <=29s total.
ready=false
for attempt in $(seq 1 10); do
  if curl --fail --silent --show-error --max-time 2 --max-filesize 2000000 \
    http://127.0.0.1:3000/_next/static/86jVlbyKpPMhJnvsgczQ5/_ssgManifest.js \
    -o "$R/local-smoke.js"; then ready=true; break; fi
  if test "$attempt" -lt 10; then sleep 1; fi
done
test "$ready" = true
systemctl is-active --quiet vlr-frontend.service
printf '%s  %s\n' 678f6ce2cb80b1fe72fc67e7412be6e2ab6ada083111b64f7c40d35e3cba5e00 \
  "$R/local-smoke.js" | sha256sum -c -
curl --fail --silent --show-error --max-time 10 --max-filesize 2000000 \
  https://val.jushosting.dev/_next/static/86jVlbyKpPMhJnvsgczQ5/_ssgManifest.js \
  -o "$R/public-smoke.js"
printf '%s  %s\n' 678f6ce2cb80b1fe72fc67e7412be6e2ab6ada083111b64f7c40d35e3cba5e00 \
  "$R/public-smoke.js" | sha256sum -c -
systemctl show vlr-api.service -p MainPID -p InvocationID > "$R/api-after.txt"
cmp "$R/api-before.txt" "$R/api-after.txt"
systemctl show vlr-frontend.service -p MainPID -p InvocationID > "$R/frontend-after.txt"
! cmp -s "$R/frontend-before.txt" "$R/frontend-after.txt"
```

Rollback immediately for failure to start/become ready in 30 seconds, wrong BUILD_ID/hash, sustained static 5xx or failed public smoke, or a user-visible regression observed after reopening. A backend identity change is unexpected external activity: stop acceptance and investigate; do not restart/repair the backend as part of this release. Do not claim success from the disk BUILD_ID alone. Observe frontend logs briefly after smoke for asset/load errors; use `journalctl -u vlr-frontend.service --since '<cutover UTC>' --no-pager`.

## Frontend-only rollback commands

Use the **freshly restored old `.next`** from the verified existing rollback archive. The unchanged runtime/public/config files make this sufficient; do not restore backend configuration or any data. This works even if the candidate move failed and `$F/.next` is absent. It is a one-use prepared directory; retain the archive and `precutover-next` afterward.

```bash
set -euo pipefail
R=/home/builder/vlr-frontend-only-9301682
F=/opt/vlr-api/frontend
python3 /opt/vlr-api/scripts/frontend_release/verify.py "$R" --rollback-only \
  --manifest-sha256 a04eba4df875cabeac017de0da4251aa81caec3aa4affb3493c35c008451a502
test "$(cat "$R/rollback/frontend/.next/BUILD_ID")" = 5RXlwj7jwc2eDLWI_-439
test ! -e "$R/failed-next"
sudo systemctl stop vlr-frontend.service
if test -e "$F/.next"; then
  sudo mv -- "$F/.next" "$R/failed-next"
fi
sudo mv -- "$R/rollback/frontend/.next" "$F/.next"
sudo systemctl start vlr-frontend.service
test "$(cat "$F/.next/BUILD_ID")" = 5RXlwj7jwc2eDLWI_-439
```

Repeat the bounded local/public static smoke above with **`5RXlwj7jwc2eDLWI_-439`** in both URLs; the expected `_ssgManifest.js` hash is the same. Require active frontend, a new frontend invocation and the unchanged backend identity. Rollback has the same interruption profile. If the restored frontend fails too, leave other services/configuration/data untouched and investigate the frontend failure; do not invoke the stopped baseline proposal.

The only pending action is authorization/execution of this frontend cutover and its production smoke. The fresh preflight protects against intervening drift; no backend provenance, new baseline, migration, backup or ingress-reconfiguration gate is imposed on this release.
