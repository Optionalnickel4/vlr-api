# Gate follow-up evidence

Application SHA: `9301682c4165d7507e49d6ad7678d14ca9df377e`.
See [gate analysis](../../../RELEASE_GATE_VERIFICATION.md) and the revised
[release review](../../../PRODUCTION_RELEASE_REVIEW.md). No application fix commit.

- `baseline.json`, `provenance-ingress.json`: installed service identity/hashes,
  denied process access, environment names only, read-only status, DNS/TLS observations,
  owner-confirmed remote Caddy topology and explicitly unknown effective config.
- `archive_frontend.py`, `rollback-artifact.json`: exact disk frontend/runtime archive
  and hashes. Protected archive, manifest and exact config copies stay outside Git.
- `restore_frontend.py`, `rollback-restore.json`, `rollback-smoke.json`: extraction,
  every-file validation, preserved BUILD_ID and HTTP/asset smoke on isolated 3112.
  Archive/current disk contents are not proof of an unavailable historical source SHA.
- `backup.py`, `backup-restore.json`: consistent read-only snapshot export/dump,
  new private backup, isolated Postgres restore and matching counts. The private dump
  is deliberately omitted from Git; existing production backups were not overwritten.
- `staging_backend.py`: private Redis/Postgres overrides before app import, no
  scheduler, candidate source on PYTHONPATH. Cold mode permits a bounded real-source
  transport; fixture mode uses saved HTML and private deadline scenarios only.
  No source failure injection, reset route or production storage is involved.
- `cold_probe.py`, `cold-probe.json`, `origin.jsonl`: documented probe helper,
  six sequential cold/warm reads and exactly three upstream GETs. API response shapes,
  not payload values, are saved. The source transport closes before browser testing.
- `browser.cjs`, `browser.json`: three warmed real-data pages at 390px on isolated
  Next 3110; no mocks in the browser. Screenshots stay in the private temporary test
  directory and are QA observations, not cleared promotional assets.
- `deadline_probe.py`, `deadline-api.json`, `deadline_browser.cjs`,
  `deadline-browser.json`: fixture-only 12-second healthy response, real 80-second
  FastAPI deadline and independent 90-second Next deadline on 8111/3111.
  `deadline-api-initial.json` retains the first harness attempt with an unintended
  five-second httpx idle limit; the corrected probe disables that idle limit while
  retaining a 95-second outer deadline. No application change was required.
- `final_checks.py`, `checks.json`, `logs/`: fresh full suites/lint/TypeScript and
  clean webpack production build, serially, with sampled RSS/disk/build size peaks.
  Logs normalize color escapes and trailing whitespace only.
- `capacity-inventory.json`, `temporary-cleanup.json`: measured sizes, explicit
  release/restore budget, unresolved durable shortfall and safe reclamation of
  only the review's redundant dependency directory. Reinstall that archive's
  pinned dependencies before rerunning checks; production dependencies are untouched.
- `final-preservation.json`: all 511 candidate source blobs unchanged, production
  PIDs/start times/unit hashes/config bytes unchanged, protected user files unchanged,
  private services stopped. Expanded temporary frontend/database restores removed
  after verification; compressed protected backups retained outside Git.

Reproduction is destructive only to the named *new private* paths. Do not point
harnesses at production, overwrite prior evidence/backups or run concurrently on a
memory-constrained host. Choose new private directories for another run, update the
harness paths consistently, and install the pinned archive/lockfile there. These are
operator evidence scripts, not production entry points. No Caddy config is guessed.

Private services were created with:

```sh
/usr/lib/postgresql/17/bin/initdb -D /tmp/vlr-gates-9301682/pg/data -A trust --no-locale -E UTF8
/usr/lib/postgresql/17/bin/pg_ctl -D /tmp/vlr-gates-9301682/pg/data \
  -l /tmp/vlr-gates-9301682/pg.log \
  -o "-k /tmp/vlr-gates-9301682/pg/socket -p 55439 -c listen_addresses='' -c shared_buffers=16MB" start
redis-server --port 0 --unixsocket /tmp/vlr-gates-9301682/redis/redis.sock \
  --unixsocketperm 700 --save '' --appendonly no --daemonize yes \
  --pidfile /tmp/vlr-gates-9301682/redis.pid --logfile /tmp/vlr-gates-9301682/redis.log
```

Parent directories were mode 0700. `backup.py` creates the private `cold` and
`restored` databases. Candidate Next commands used separate loopback ports with
private API origins and disabled Twitch; no production environment was loaded into
those frontend processes. Browser commands use the existing Playwright installation
and `PLAYWRIGHT_BROWSERS_PATH`, `LD_LIBRARY_PATH`, `FONTCONFIG_FILE` from the preceding
analytics verification. All task-created services were stopped by verified PID or
private socket/data-directory only; no systemd production stop/restart was issued.
