# Live v2 backend deployment — 2026-09-28

Deployed revision: **0c4bd6dff0a65c86ef500f6ff924fded4e88d7ba**. Includes
6725057, earlier player-trend label aliases and freshness changes, plus status
artifact identity and runtime-path reporting. Jarvis remains a proposal, not an
implemented endpoint. No main, frontend or Caddy changes were made.

## What the restart evidence actually establishes

The unit is /etc/systemd/system/vlr-api.service, running as root with working
directory /opt/vlr-api, EnvironmentFile /opt/vlr-api/.env, and executable
/opt/vlr-api/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1.
No unit drop-ins, RootDirectory or RootImage were configured. The launcher uses
/opt/vlr-api/.venv/bin/python3, resolving to /usr/bin/python3.13. The virtualenv
has an editable install mapping app to /opt/vlr-api/app, with no separate installed
app package. Builder-side imports resolve there.

The stored final.json from the prior probe ran at 14:28–14:29 UTC, before commit
6725057 at 14:31 and before the 14:41 restart observed in this investigation.
That stored final check already has 27 trend points; the empty trend belongs to
earlier evidence. Fresh pre-cutover checks here returned 27 trend points and
rankings X-VLR-Cache: fresh / Cache-Control: no-store. Redis already contained
match scores [0,2]. Thus the claim that the 14:41 restart failed to load trend and
freshness fixes is not supported by current behavior. The retained detail
payloads and comparisons against older probe results obscured the code state.

Pre-cutover status commit was unknown. The previous implementation shells out
to Git and suppresses errors; unknown is not proof of an old deployed revision.
Root reading a builder-owned checkout can encounter Git ownership protection,
but its exact Git error was not captured and is not asserted as proven.

Sudo policy allows only specified service status/restart commands, not arbitrary
root commands. Direct pre-cutover /proc/PID/{cwd,exe,environ,root} reads and a full
privileged journal inspection were unavailable. We do not claim to have inspected
those. The effective unit, launcher, editable metadata, Python import resolution,
and fresh behavior were inspected. Post-cutover runtime paths are now directly
reported by the running service, eliminating this ambiguity for this deployment.

## Artifact and cutover

Exact Git export of app and pyproject.toml, plus a REVISION file containing the
full SHA, lives at:

/home/builder/vlr-releases/0c4bd6dff0a65c86ef500f6ff924fded4e88d7ba/source

All 40 artifact files (including marker) are inventoried in manifest.json;
committed file hashes were compared against git show. All app imports use this
source/app package: main.py, api/v1/routes.py, services/trends.py,
scrapers/match_detail.py and scrapers/players.py were also checked in the artifact
import smoke test. Dependencies stay in /opt/vlr-api/.venv/lib/python3.13/site-packages.

The builder-owned /opt/vlr-api/.venv/bin/uvicorn launcher now appends an explicit
--app-dir pointing at the artifact. This preserves the unit, working directory,
.env, database and Redis configuration. Its replacement was staged and renamed
atomically, then only `sudo -n systemctl restart vlr-api` was run. Unit content
was compared byte-for-byte with the backup afterward. No cache flush or forced
refresh was performed. Normal service startup and scheduler behavior continued.

Restart: 14:51:32 UTC, PID 177452. Status reports the full pinned SHA, artifact
source_root, /opt/vlr-api/.venv/bin/python3 and the actual Python search path,
with the artifact first. The process is active/running with NRestarts=0. Visible
service log excerpts show successful HTTP requests and scheduler jobs, no errors.
The limited sudo policy allows service-status log excerpts, not a full journal
export. See service-status.txt, unit-state.txt and live.json.

## Tests and six sequential live checks

- Full backend suite: 308 passed (tests.log).
- Exported artifact: 128 focused status, trends, freshness, scraper, match and
  detail-reliability tests passed (artifact-tests.log).
- pip check: no broken requirements. Artifact dependency imports succeeded.
- Existing Starlette/httpx deprecation warning remains; no test failures.

Live target http://10.0.0.21:8000, 14:51:53–14:51:58 UTC, one request per endpoint,
sequential with one-second spacing and no retries:

| Check | Result |
| --- | --- |
| /health | 200, ok |
| /api/v1/status | 200, full deployed SHA; PostgreSQL and Redis true |
| /api/v1/trends/player/36245 | 200, 27 points, current rating 1.11 |
| /api/v1/rankings?region=all | 200, 128 rows; X-VLR-Cache fresh; Cache-Control no-store |
| /api/v1/match/753445 | 200, scores [0,2], won flags [false,true] |
| /api/v1/player/36245 | 200, five cached results still lack date fields |

Date fields remain pending normal cache expiry/refetch, not deployment failure.
At 14:52:27 UTC player cache TTL was 1882 seconds: expected expiry approximately
15:23:49 UTC, followed by refresh when normally requested. Expiry does not itself
promise an immediate scrape. Match scores had already refreshed normally before
the cutover. Cache TTL evidence is read-only (cache-ttl.json).

## Backup and rollback

Private backup directory: /home/builder/vlr-backups/20260928-backend (mode 700).
backend.tar.gz contains app, complete .venv, pyproject.toml and .env; configuration
copies include vlr-api.service and effective-unit.txt. Archive listing and sample
restoration of launcher, main.py and .env were verified without displaying secrets.
Archive SHA256: 3593530b15037aa747a755cd79ba4ba7d836722610684f4ec8ef066215050b18.

Before launcher replacement, the original launcher was separately copied and a
rollback script prepared. The script now restores the complete archived app and
virtualenv, retaining replaced files for diagnosis, verifies that unit/env have
not changed, restarts only vlr-api, and checks health/status. This avoids a rollback
silently depending on later edits in the v2 checkout. No database/Redis/cache data
is restored or removed. The archive predates runtime-path additions and cutover;
it includes the already-tested, then-unactivated status REVISION fallback change.

Straightforward rollback command (as builder):

    bash /home/builder/vlr-backups/20260928-backend/rollback.sh

Rollback script syntax was checked; destructive restoration was not exercised on
the healthy live service. **Rollback was not needed.** The backup's original
launcher returns imports to /opt/vlr-api/app; status revision may again be unknown
because that checkout has no artifact REVISION marker.

Future deployments must deliberately update this launcher or service app-dir;
restarting the service alone now keeps the pinned artifact, independent of repo
HEAD. A reinstall of uvicorn can overwrite its entry-point script, so verify
status revision and source_root after any runtime maintenance.
