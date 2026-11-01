from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(slots=True)
class Settings:
    """Runtime knobs. Every value can be overridden with a ``SCRAPER_*`` env var."""

    headless: bool = True
    slow_mo_ms: int = 0
    timeout_ms: int = 30_000
    retries: int = 2
    delay_s: float = 1.0
    jitter_s: float = 0.5
    user_agent: str = DEFAULT_UA
    locale: str = "en-US"
    timezone: str = "UTC"
    proxy: str | None = None
    respect_robots: bool = True
    block_assets: bool = True

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            headless=_env_bool("SCRAPER_HEADLESS", True),
            slow_mo_ms=_env_int("SCRAPER_SLOW_MO", 0),
            timeout_ms=_env_int("SCRAPER_TIMEOUT_MS", 30_000),
            retries=_env_int("SCRAPER_RETRIES", 2),
            delay_s=_env_float("SCRAPER_DELAY", 1.0),
            jitter_s=_env_float("SCRAPER_JITTER", 0.5),
            user_agent=os.getenv("SCRAPER_USER_AGENT", DEFAULT_UA),
            locale=os.getenv("SCRAPER_LOCALE", "en-US"),
            timezone=os.getenv("SCRAPER_TIMEZONE", "UTC"),
            proxy=os.getenv("SCRAPER_PROXY") or None,
            respect_robots=_env_bool("SCRAPER_RESPECT_ROBOTS", True),
            block_assets=_env_bool("SCRAPER_BLOCK_ASSETS", True),
        )
