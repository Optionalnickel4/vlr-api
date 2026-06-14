from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="VLR_", extra="ignore")

    # vlr.gg
    base_url: str = "https://www.vlr.gg"
    user_agent: str = (
        "vlr-api/0.1 (self-hosted; +https://jushosting.dev) httpx"
    )
    min_request_interval: float = 1.5  # seconds between requests to vlr
    request_timeout: float = 20.0
    max_retries: int = 3

    # redis
    redis_url: str = "redis://localhost:6379/0"

    # postgres
    database_url: str = "postgresql+asyncpg://vlr:vlr@localhost:5432/vlr"

    # cache TTLs (seconds)
    ttl_live: int = 30
    ttl_results: int = 600
    ttl_matches: int = 600
    ttl_events: int = 1800
    ttl_rankings: int = 3600
    ttl_players: int = 3600
    ttl_teams: int = 3600
    ttl_news: int = 900
    ttl_search: int = 600  # VLR-autocomplete fallback cache (short — players churn in)

    # api
    api_prefix: str = "/api/v1"
    enable_scheduler: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
