"""Spider registry. Add your spider here and it becomes a CLI command."""

from __future__ import annotations

from .base import Spider
from .quotes import QuotesSpider

SPIDERS: dict[str, type[Spider]] = {
    QuotesSpider.name: QuotesSpider,
}


def build(name: str) -> Spider:
    try:
        spider_class = SPIDERS[name]
    except KeyError:
        available = ", ".join(sorted(SPIDERS)) or "none"
        raise SystemExit(f"unknown spider {name!r} (available: {available})") from None
    return spider_class()
