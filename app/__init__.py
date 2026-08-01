"""vlr-api — a self-hosted REST API and history store for vlr.gg data.

vlr.gg has no official API, so this service scrapes its HTML, normalizes it to
JSON, caches it in Redis, banks history in Postgres, and serves it over FastAPI.

THE ONE ARCHITECTURAL RULE: the public API never scrapes during a request.

    scheduler (app/jobs)  ->  services/refresh  ->  scrapers  ->  vlr.gg
                                     |
                                     +-> Redis (fresh JSON, TTL'd)
                                     +-> Postgres (append-only history)

    HTTP request  ->  app/api/v1  ->  Redis, then Postgres.  Never vlr.gg.

Everything else follows from that split. A request is fast and bounded because
it only reads local state; vlr.gg sees one polite, throttled client on a fixed
cadence rather than traffic proportional to our users; and an outage upstream
degrades to stale data instead of failing requests. The exceptions are narrow
and deliberate — a cache miss on a detail page (player/team/match) may refresh
inline, because there is nothing to serve otherwise.

Layers, in dependency order (never import upward):

    core/       config, Redis, Postgres, the shared throttled httpx client
    scrapers/   vlr.gg HTML -> dicts. All CSS selectors live in selectors.py
    services/   orchestration: scrape -> cache -> DB, plus search and trends
    ratings/    derived percentile/cohort math over the stats leaderboard
    models/     SQLAlchemy history tables
    api/        FastAPI routers — read-only, cache/DB only
    jobs/       APScheduler cadences that drive services/refresh

Tests never touch the network: scrapers are pure functions over saved HTML in
tests/fixtures/. Selector accuracy against live vlr.gg is checked separately by
`python -m app.scrapers.verify`, which must run somewhere with internet access.
"""
