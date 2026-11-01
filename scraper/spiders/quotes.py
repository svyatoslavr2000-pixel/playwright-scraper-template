"""Reference spider: https://quotes.toscrape.com — a site published for scraping practice."""

from __future__ import annotations

from urllib.parse import urljoin

from playwright.async_api import Page

from .base import Spider, attr, text, texts


class QuotesSpider(Spider):
    name = "quotes"
    start_urls = ("https://quotes.toscrape.com/",)
    fields = ("url", "text", "author", "tags", "page")
    # one quote per row, so the page URL cannot be the key
    key_fields = ("text", "author")

    async def parse(self, page: Page, url: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for card in await page.query_selector_all("div.quote"):
            rows.append(
                {
                    "url": url,
                    "text": await text(card, "span.text"),
                    "author": await text(card, "small.author"),
                    "tags": await texts(card, "a.tag"),
                    "page": self.page_number,
                }
            )
        return rows

    async def next_url(self, page: Page, url: str) -> str | None:
        href = await attr(page, "li.next a", "href")
        return urljoin(url, href) if href else None
