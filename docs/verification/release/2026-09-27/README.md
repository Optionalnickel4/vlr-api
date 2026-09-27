# Release review evidence

See [the release review](../../../PRODUCTION_RELEASE_REVIEW.md). Application SHA:
`9301682c4165d7507e49d6ad7678d14ca9df377e`. The documentation commit does not
change application source, deployment configuration, `.gitignore` or the saved plan.

- `checks-final.json` and `*-final.log`: accepted final results, all five checks
  passing. Backend 284; frontend 348 across 25 files. Build uses webpack.
- `checks.json` and unsuffixed logs: initial resource-constrained attempts.
  Backend timing failure and build/TypeScript timeouts are retained. Initial
  frontend exit zero lacked a complete summary and was repeated successfully.
- `run_checks.py`: final serial reproduction harness. Extract the pinned archive
  to the directory it names, install the frontend lockfile with `npm ci`, then run
  this harness. It uses the existing Python virtualenv but imports archived source;
  all configured test/build origins are isolated placeholders, not production
  environment values. It overwrites final logs. Allow enough disk/RAM; do not
  execute on a busy production host or build in its served `.next` directory.
- `npm-ci.log`, `python-packages.json`: install receipt and Python package inventory.
  No dependency update is part of this release. Python manifests are not locked.
- `api-smoke.json`: standard `scripts/probe_api.py`, 14 sequential requests.
- `smoke.py`, `preview-analytics-smoke.json`: twelve-request follow-up. HTML rows
  validate successful HTML transport only, not rendered content. The match proxy's
  HTTP 200 is an unavailable stale/error envelope. No retries or forced cache misses.
- `runtime-before.json`, `runtime-after.json`: two initial and two final health/status
  reads, storage health/read-only encoding/persistence inspection, unchanged
  production process identity and protected-file hashes. Total HTTP requests in
  this review: 30 (2 initial + 14 primary + 12 follow-up + 2 final). Normal API GETs
  may cause cache/history writes on misses. No mutation/flush API was called.
- `configuration.json`: installed unit configuration with inline environment
  assignments reduced to names; environment files contribute names only. External
  proxy and effective root-process environment remain unverified.
- `parity.json`: 134 candidate frontend files match serving staging build sources;
  original production BUILD_ID/timestamp. `runtime-after.json` independently verifies
  all 511 archived tracked files still match release Git blobs after tests/build.
- `commits.txt`: full post-September-17 commit range; the review distinguishes runtime
  commits, tooling, documentation and uncertainty about the older production SHA.

No new browser session or live-source load test ran. Earlier browser/isolated-failure
checks are explicitly linked as historical evidence. No production/staging service
was restarted, and no schema or cache reset occurred. Runtime backups and a deployment
were not taken/performed; they remain future operator steps after the NO-GO gates.

Log copies normalize terminal color escapes and trailing whitespace only.
