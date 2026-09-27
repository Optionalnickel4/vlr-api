# Audit evidence

See [the audit report](../../../BROADCAST_PREDEPLOYMENT_AUDIT.md) for conclusions and limitations. Final implementation commit: `cac586af15db04c0edd61fc7f120f832706bcda1`; the documentation commit adds this evidence only.

- `check-results.json` and `logs/{backend,tests,lint,typescript,build}.log`: final full checks with UTC command boundaries and exit codes.
- `logs/*fix.log`: focused tests run before each small implementation commit. `backend-freshness.log`: verbose retained-cache/cold-failure regression run on isolated Redis.
- `browser-results.json`: 72 final-build route/viewport observations, including focus, reduced motion, ticker, overflow and page errors. `zoom-results.json`: 18 native Chromium 200% cases.
- `flows.json`, `interactions.json`, `filters.json`: real links/back-forward/search and controlled map, table, ticker, filter and search interactions. Accessible snapshot is a DOM/ARIA inspection, not a screen-reader test.
- `states.json`: controlled empty/error/partial/stale/live/slow checks. The requested `stale` scenario only injects actual staleness into Rankings (header) and Stats (envelope); other listing/news rows in that scenario are populated fixture controls, not evidence of retained stale responses.
- `deadline.json`: wall-clock request check against a simulated 12-second backend. `states.json` separately measures whole-browser network-idle, which includes later ticker requests.
- `api-coverage.json`: read-only observations of all 14 frontend API route patterns; these are time-specific, not assertions that keys remain cached. `cache-inventory.json` removes raw sample text while preserving key/count/header observations.
- `operations.json`: final preview source hashes, basic production health and PID/start-time continuity, unrelated-file byte comparisons. Preview uses the read-only adapter, not the production API.
- Browser `.cjs` files and `fixture-fetch.cjs`: exact temporary harnesses. They require the local Playwright/Chromium installation and read-only preview described in the report. Fixture wrappers imported from `/tmp/vlr-{match,team,player,listings,ladders,news}-delivery/fixture-fetch.cjs` are copied under `fixture-inputs/<name>/`; restore those paths and writable `scenario` files to reproduce. They read committed frontend JSON fixtures. Never preload these into production or 3100.
- `zoom-capture.cjs` replaces the header-only zoom capture with a useful focused-table viewport. Selected final captures are in `docs/screenshots/audit`; earlier captures were excluded.

The controlled server ran on loopback 3101 using the same isolated build and was stopped. No cache mutation, scraper invocation, deployment, or production restart was required. Real-cache pictures are QA evidence, not cleared promotional assets. Controlled fixtures can still contain source-derived names and statistics.

Terminal trailing blank lines were removed from focused-test log copies; test output content is unchanged.
