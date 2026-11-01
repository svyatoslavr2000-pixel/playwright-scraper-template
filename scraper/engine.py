"""Browser lifecycle, retries, politeness and the crawl loop."""

from __future__ import annotations

import asyncio
import random
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Route, async_playwright

from .config import Settings
from .exporters import Exporter
from .pagination import LoopGuard, resolve
from .politeness import RobotsPolicy, fetch_robots, origin_of, path_of
from .records import Deduper, absolute, clean
from .spiders.base import Spider

BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}

# Chromium exposes navigator.webdriver=true in automated browsers. Some sites
# reject the request on that flag alone, before any content is served, so it is
# cleared here. This is *not* a stealth suite: no fingerprint spoofing, no
# CAPTCHA workaround. Disclosed on purpose, see README "Limitations".
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
"""

Logger = Callable[[str], None]


async def _block_assets(route: Route) -> None:
    if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
        await route.abort()
    else:
        await route.continue_()


async def _goto(page: Page, url: str, settings: Settings, log: Logger):
    """Navigate with bounded exponential backoff. Returns the response or None."""
    attempts = max(0, settings.retries) + 1
    for attempt in range(1, attempts + 1):
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=settings.timeout_ms)
            if response is None or response.status < 400:
                return response
            log(f"http {response.status} | attempt {attempt}/{attempts} | {url}")
        except PlaywrightError as exc:
            log(f"nav error | attempt {attempt}/{attempts} | {clean(str(exc))[:140]}")
        if attempt < attempts:
            await asyncio.sleep(min(2.0 ** attempt * 0.8, 8.0))
    return None


def _as_records(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, (list, tuple)):
        return [item for item in data if isinstance(item, dict)]
    return []


async def run_spider(
    spider: Spider,
    settings: Settings,
    *,
    max_pages: int = 5,
    max_items: int = 0,
    exporter: Exporter | None = None,
    deduper: Deduper | None = None,
    log: Logger = print,
) -> dict[str, Any]:
    started = time.monotonic()
    stats: dict[str, Any] = {
        "pages": 0,
        "items": 0,
        "duplicates": 0,
        "skipped": 0,
        "errors": 0,
        "blocked_by_robots": 0,
    }
    queue: deque[str] = deque(spider.start_urls)
    guard = LoopGuard()
    robots_cache: dict[str, RobotsPolicy | None] = {}

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=settings.headless,
            slow_mo=settings.slow_mo_ms or 0,
            proxy={"server": settings.proxy} if settings.proxy else None,
        )
        context = await browser.new_context(
            user_agent=settings.user_agent,
            locale=settings.locale,
            timezone_id=settings.timezone,
            viewport={"width": 1366, "height": 768},
        )
        await context.add_init_script(STEALTH_JS)
        if settings.block_assets:
            await context.route("**/*", _block_assets)
        page = await context.new_page()
        page.set_default_timeout(settings.timeout_ms)

        try:
            while queue and stats["pages"] < max_pages:
                url = queue.popleft()
                if not guard.is_new(url):
                    stats["skipped"] += 1
                    continue

                policy = None
                if settings.respect_robots:
                    origin = origin_of(url)
                    if origin not in robots_cache:
                        robots_cache[origin] = await asyncio.to_thread(fetch_robots, url)
                    policy = robots_cache[origin]
                    if policy is not None and not policy.allowed(path_of(url)):
                        stats["blocked_by_robots"] += 1
                        log(f"skip (robots.txt) | {url}")
                        continue

                response = await _goto(page, url, settings, log)
                if response is None:
                    stats["errors"] += 1
                    continue

                stats["pages"] += 1
                spider.page_number = stats["pages"]
                current = page.url

                try:
                    data = await spider.parse(page, current)
                except Exception as exc:  # noqa: BLE001 - one bad page must not end the run
                    stats["errors"] += 1
                    log(f"parse error | {current} | {clean(str(exc))[:140]}")
                    data = None

                for record in _as_records(data):
                    record.setdefault("url", current)
                    record["url"] = absolute(clean(record.get("url")), current)
                    if deduper is not None and not deduper.is_new(record):
                        stats["duplicates"] += 1
                        continue
                    if exporter is not None:
                        exporter.write(record)
                    stats["items"] += 1
                    if max_items and stats["items"] >= max_items:
                        break

                if max_items and stats["items"] >= max_items:
                    break

                log(
                    f"page {stats['pages']}/{max_pages} | {len(_as_records(data))} records | "
                    f"{stats['items']} total | {current}"
                )

                try:
                    following = await spider.next_url(page, current)
                except Exception as exc:  # noqa: BLE001
                    log(f"next_url error | {clean(str(exc))[:120]}")
                    following = None

                next_page = resolve(current, following)
                if next_page:
                    # contains() instead of is_new(): enqueuing must not mark the URL visited
                    if not guard.contains(next_page):
                        queue.append(next_page)
                    else:
                        log(f"stop | pagination loop at {next_page}")
                else:
                    log("stop | no next page link")

                base_delay = settings.delay_s
                if policy is not None and policy.crawl_delay:
                    base_delay = max(base_delay, policy.crawl_delay)
                await asyncio.sleep(base_delay + random.uniform(0, settings.jitter_s))
        finally:
            await context.close()
            await browser.close()

    stats["elapsed_s"] = round(time.monotonic() - started, 2)
    return stats
