# vlr-api — self-hosted VLR.gg REST API

Own version of vlr.gg data as a clean REST API + historical store, for valstats dashboards.

## What this is
VLR.gg has **no official API**. This project scrapes vlr.gg HTML, normalizes it to JSON,
caches it in Redis, persists history in Postgres, and serves it via FastAPI. The public API
**never scrapes inline** — it reads cache first, then DB. A background scheduler does all scraping.

## Stack
- Python 3.13 (3.11+ ok), FastAPI, uvicorn
- httpx (async) + selectolax (fast HTML parsing)
- Redis (cache + read source for live data)
- Postgres via SQLAlchemy 2.x async + asyncpg (history)
- APScheduler (cron cadences)
- pytest (parses saved HTML fixtures — no live network in tests)

## Architecture (layers, do not cross)
- `app/api/v1/`      routers — READ from cache/db ONLY, never scrape
- `app/services/`    orchestrate scrape -> cache -> db
- `app/scrapers/`    one module per entity; ALL css selectors in `selectors.py`
- `app/schemas/`     pydantic response models
- `app/models/`      sqlalchemy ORM (history tables)
- `app/core/`        config, db, cache, shared http client
- `app/jobs/`        scheduler

## Rules
- Selectors live ONLY in `app/scrapers/selectors.py`. When vlr markup changes, fix one file.
- Be polite to vlr.gg: real User-Agent, MIN_REQUEST_INTERVAL throttle, retry w/ backoff.
- Cache TTLs: live matches 30s, results/matches 10m, events 30m, rankings 1h, players/teams 1h, news 15m.
- Tests must not hit the network. Save real pages into tests/fixtures/ and assert against them.
- Workflow: spec -> failing test -> implement -> pass. TDD.

## Cadences (scheduler)
- live/upcoming matches: every 60s
- results: every 10m
- rankings: every 6h
- events: every 6h
- news: every 15m

## Deploy
LXC 289 on Mewtwo (prox), 192.168.1.35, Debian 13. systemd units: vlr-api (uvicorn), vlr-scheduler.
Postgres + Redis local to the container. See DEPLOY.md.

## Selector verification
Sandbox cannot reach vlr.gg. Selectors are based on known vlr markup and MUST be verified on
the container: run `python -m app.scrapers.verify` which fetches live pages and reports
which selectors matched. Adjust selectors.py until all green.
