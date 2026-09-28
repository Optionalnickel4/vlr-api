"""Process-wide settings, from environment or .env, all prefixed VLR_.

Every value has a working default so the app boots with no configuration at all
(that is what lets tests import the whole app without a .env). Override in
production by env var: the field `min_request_interval` is `VLR_MIN_REQUEST_INTERVAL`.

The TTLs below govern freshness; the scheduler in app/jobs sets refresh cadence.
Rankings/events retain a separate last-successful copy without expiry. Other
datasets still expire outright and can refresh inline on a cache miss.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VLR_", extra="ignore")

    # vlr.gg
    base_url: str = "https://www.vlr.gg"
    user_agent: str = (
        "vlr-api/0.1 (self-hosted; +https://jushosting.dev) httpx"
    )
    # Politeness floor: seconds between ANY two requests to vlr, enforced
    # globally across the whole process (VlrClient._throttle). vlr.gg is a
    # volunteer-run site with no API and no rate-limit contract — this number is
    # the main thing keeping us a good citizen. Lower it and you are gambling
    # with the project's access.
    min_request_interval: float = 1.5
    request_timeout: float = 20.0
    max_retries: int = 3

    # redis
    redis_url: str = "redis://localhost:6379/0"

    # postgres
    database_url: str = "postgresql+asyncpg://vlr:vlr@localhost:5432/vlr"

    # Cache TTLs (seconds). Each is set from how fast the underlying data can
    # actually change, not from how often anyone asks for it: a live scoreboard
    # moves every round, a season-aggregate leaderboard moves once a day.
    ttl_live: int = 30
    ttl_results: int = 600
    ttl_matches: int = 600
    ttl_events: int = 1800  # freshness only; separate retained copy has no expiry
    ttl_rankings: int = 3600  # freshness only; separate retained copy has no expiry
    ttl_players: int = 3600
    ttl_teams: int = 3600
    ttl_news: int = 900
    ttl_search: int = 600  # VLR-autocomplete fallback cache (short — players churn in)
    ttl_stats: int = 21600  # stats leaderboard — season-aggregate; matches the 6h scrape cadence

    # api
    api_prefix: str = "/api/v1"
    # Dedicated credential grants only Jarvis team-match reads; contents never logged.
    jarvis_token_file: str = "/home/builder/.config/vlr-api/jarvis.token"
    # True (default) runs the scraping scheduler inside the API process — fine
    # for the single-worker deployment this ships with. Set False and run
    # `python -m app.jobs.run` separately (deploy/vlr-scheduler.service) if you
    # ever scale the API past one worker: otherwise every worker starts its own
    # copy of every cron job and multiplies the load on vlr.gg.
    enable_scheduler: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
