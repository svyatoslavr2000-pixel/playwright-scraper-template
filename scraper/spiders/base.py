"""Spider contract + selector helpers that fail soft instead of raising."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from playwright.async_api import ElementHandle, Page

Scoped = Page | ElementHandle


class Spider:
    """Subclass this, set ``start_urls`` + ``fields``, implement ``parse``."""

    name: str = "base"
    start_urls: Sequence[str] = ()
    fields: Sequence[str] = ()
    key_fields: Sequence[str] = ("url",)  # used for dedupe/resume

    def __init__(self) -> None:
        self.page_number: int = 1

    async def parse(self, page: Page, url: str) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Return one record, a list of records, or None."""
        raise NotImplementedError

    async def next_url(self, page: Page, url: str) -> str | None:
        """Return the next page URL (relative is fine) or None to stop."""
        return None


async def _first(scope: Scoped, selector: str) -> ElementHandle | None:
    try:
        return await scope.query_selector(selector)
    except Exception:  # noqa: BLE001 - a broken selector must not kill the run
        return None


async def text(scope: Scoped, selector: str) -> str:
    element = await _first(scope, selector)
    if element is None:
        return ""
    try:
        return (await element.inner_text()).strip()
    except Exception:  # noqa: BLE001
        return ""


async def texts(scope: Scoped, selector: str) -> list[str]:
    try:
        elements = await scope.query_selector_all(selector)
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    for element in elements:
        try:
            out.append((await element.inner_text()).strip())
        except Exception:  # noqa: BLE001
            continue
    return [value for value in out if value]


async def attr(scope: Scoped, selector: str, name: str) -> str:
    element = await _first(scope, selector)
    if element is None:
        return ""
    try:
        return (await element.get_attribute(name)) or ""
    except Exception:  # noqa: BLE001
        return ""
