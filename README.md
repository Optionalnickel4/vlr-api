# vlr-api

Self-hosted VLR.gg REST API with historical storage. Scrapes vlr.gg HTML →
normalizes to JSON → caches in Redis → persists history in Postgres → serves via FastAPI.

vlr.gg has no official API; this parses the site. Be polite (throttled, real UA).

## Quick start (dev)
```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest -q                      # 10 tests, no network
```

## Endpoints
`/api/v1/` → matches/results, matches/upcoming, matches/live, rankings, events, news,
history/results, history/rankings/{team_id}. Docs at `/docs`.

## Deploy
See **DEPLOY.md** — targets LXC 289 (192.168.1.35) on Mewtwo. Postgres + Redis local.

## IMPORTANT: verify selectors
Selectors in `app/scrapers/selectors.py` were written without live vlr.gg access.
On the container, run `python -m app.scrapers.verify` and fix any 0-count entity.

## Conventions
See **CLAUDE.md**. API never scrapes inline; scheduler does. All CSS selectors in one file.
