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
    redis_url: str = "redis://localhost:***@localhost:5432/vlr"

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
    ttl_stats: int = 21600  # stats leaderboard — season-aggregate; matches the 6h scrape cadence

    # api
    api_prefix: str = "/api/v1"
    enable_scheduler: bool = True


class HltvSettings(BaseSettings):
    """CS2 (HLTV) settings — separate env prefix so the hltv-scheduler service
    can have its own env file (/etc/vlr-api/hltv.env) without inheriting VLR_* vars.

    Why a separate class: the hltv-scheduler systemd unit loads hltv.env, NOT .env,
    so VLR_* vars from the API process don't leak into the CS2 scheduler (and vice
    versa). Both Settings() and HltvSettings() can be instantiated independently.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="HLTV_", extra="ignore"
    )

    # hltv.org
    base_url: str = "https://www.hltv.org"
    # Real Chrome UA (current stable). HLTV's basic Cloudflare challenge fingerprints
    # the UA against the TLS handshake — a custom/curl UA will be challenged even if
    # cloudscraper bypasses the JS check.
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    )
    # Matches M3MONs/hltv-scraper-api's DOWNLOAD_DELAY = 3 — polite but realistic.
    # HLTV's basic challenge is per-request; spacing requests out by 3s is enough to
    # stay under the radar for the v1 surface (results/upcoming/live/events/rankings/news).
    min_request_interval: float = 3.0
    request_timeout: float = 30.0
    max_retries: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_hltv_settings() -> HltvSettings:
    return HltvSettings()