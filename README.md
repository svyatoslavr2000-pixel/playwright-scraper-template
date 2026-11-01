# Playwright Scraper Template

[![CI](https://github.com/svyatoslavr2000-pixel/playwright-scraper-template/actions/workflows/ci.yml/badge.svg)](https://github.com/svyatoslavr2000-pixel/playwright-scraper-template/actions/workflows/ci.yml)

A small, production-shaped **web scraping template** in Python + Playwright that you can copy, point at a site, and run. Built for the boring parts people usually forget: retries, resume after a crash, polite delays, robots.txt, deduplication, and clean CSV/JSONL output.

```bash
pip install -r requirements.txt && playwright install chromium
python -m scraper.cli run quotes --pages 3 --format csv
```

Real output of that command:

```
page 1/3 | 10 records | 10 total | https://quotes.toscrape.com/
page 2/3 | 10 records | 20 total | https://quotes.toscrape.com/page/2/
page 3/3 | 10 records | 30 total | https://quotes.toscrape.com/page/3/
done: 30 items | 3 pages | 0 duplicates | 0 errors | 5.03s -> out/quotes.csv
```

Run it again with `--resume` and it refetches nothing:

```
resume | 30 keys already in out/quotes.jsonl
done: 0 items | 3 pages | 30 duplicates | 0 errors | 4.92s -> out/quotes.jsonl
```

`examples/sample-output.csv` in this repo is the real 40-row result of `--pages 4`, committed so you can inspect the output format before installing anything.

## Why this exists

Most "scraper" repos are 40 lines of `page.goto` + `page.query_selector` in a loop. They die on the first timeout, refetch pages after a crash, hammer the target with zero delay, and export data with duplicated rows and broken quotes.

This template is the version I actually deliver to clients when the job is "collect N thousand rows from a site, weekly, without babysitting it":

| Problem | What the template does |
|---|---|
| Site is slow / returns 503 | configurable retries with exponential backoff, per-page, keeps the other pages running |
| Process crashed at row 4 000 | JSONL/CSV append + `--resume`, keys persisted, nothing refetched twice |
| Scraper got the site rate-limiting you | per-request delay with jitter, `robots.txt` enforced by default |
| Same product appears twice | dedupe by any key field (`url` by default) |
| Output cannot be opened in Excel | CSV written as `utf-8-sig`, lists flattened to `a; b; c` |
| Real browsers are heavy | images, fonts and media blocked; single context reused |
| Selectors break silently | `text()/texts()/attr()` helpers return empty strings instead of throwing, and each record keeps the source URL |
| "Can you also do it weekly?" | everything is one CLI call, so cron / Task Scheduler / GitHub Actions is a one-liner |

## Install

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Python 3.10+.

## Run

```bash
# 3 pages of https://quotes.toscrape.com (a public site built for scraping practice)
python -m scraper.cli run quotes --pages 3

# JSONL instead of CSV, custom destination, slower and with a visible browser
python -m scraper.cli run quotes --pages 5 --format jsonl --out data/quotes.jsonl --delay 2 --headed

# Continue an interrupted run (skips rows already on disk)
python -m scraper.cli run quotes --pages 50 --resume

# Scaffold info: which spiders ship with the template
python -m scraper.cli list
```

| Flag | Default | Meaning |
|---|---|---|
| `--pages N` | `5` | hard page cap, so a bad "next" selector cannot loop forever |
| `--max-items N` | `0` (off) | stop after N records |
| `--format` | `csv` | `csv` or `jsonl` |
| `--out PATH` | `out/<spider>.csv` | output file, appended to |
| `--resume` | off | reuse keys already present in `--out` |
| `--delay SEC` | `1.0` | base pause between pages |
| `--jitter SEC` | `0.5` | random extra pause, `0` to disable |
| `--timeout MS` | `30000` | navigation/selector timeout |
| `--retries N` | `2` | attempts per page |
| `--headed` | off | show the browser |
| `--proxy URL` | off | e.g. `http://user:pass@host:8080` |
| `--ignore-robots` | off | only for sites you own or have written permission for |
| `--no-block-assets` | off | load images/fonts when the page needs them to render |

## Output

`out/quotes.csv`, first lines of a real run:

```csv
url,text,author,tags,page
https://quotes.toscrape.com/page/1/,"“The world as we have created it is a process of our thinking...”,Albert Einstein,"change;deep-thoughts;thinking;world",1
https://quotes.toscrape.com/page/1/,"“It is our choices, Harry, that show what we truly are...”,J.K. Rowling,"abilities;choices",1
```

Every record carries its `url`, so any row can be traced back and re-checked — the first thing a client asks when one value looks wrong.

## Adapting it to a new site (~15 lines)

Create `scraper/spiders/mysite.py`:

```python
from .base import Spider, attr, text, texts


class MySite(Spider):
    name = "mysite"
    start_urls = ["https://example.com/catalog"]
    fields = ["url", "title", "price", "tags", "page"]

    async def parse(self, page, url):
        rows = []
        for card in await page.query_selector_all(".product-card"):
            rows.append({
                "url": await attr(card, "a.product-link", "href"),
                "title": await text(card, "h2"),
                "price": await text(card, ".price"),
                "tags": await texts(card, ".tag"),
                "page": self.page_number,
            })
        return rows

    async def next_url(self, page, url):
        return await attr(page, "a[rel=next]", "href")
```

Then register it in `scraper/spiders/__init__.py` and run `python -m scraper.cli run mysite`.

- `parse()` returns a `dict` or a `list[dict]`; missing fields are filled with `""`.
- Relative links in `next_url` are resolved against the current URL automatically.
- `page_number` is tracked for you.
- For sites behind a login, save a session once with
  `playwright codegen --save-storage=auth.json` and pass `storage_state` in `engine.py` — credentials never enter the code.

## Layout

```
scraper/
  cli.py            argparse entry point, stats, resume wiring
  engine.py         browser lifecycle, retries, delay, asset blocking
  config.py         env-driven settings (SCRAPER_* variables)
  politeness.py     robots.txt parser + longest-match allow/deny, crawl-delay
  pagination.py     next-link resolution, page templates, loop guards
  records.py        text cleaning, URL normalisation, dedupe keys
  exporters.py      CSV (utf-8-sig, atomic header) and JSONL writers
  spiders/
    base.py         Spider contract + text/texts/attr helpers
    quotes.py       reference spider (quotes.toscrape.com)
examples/
  sample-output.csv  real run, 40 rows, committed for inspection
tests/              21 unit tests, no network required
```

## Tests

```bash
python -m pytest -q      # pure logic: robots rules, dedupe, CSV/JSONL, pagination
ruff check .             # lint
```

The test suite is network-free on purpose: scraper tests that hit live sites are flaky, and flaky tests get deleted.

## Limitations (read before hiring me to do something impossible)

- **No CAPTCHA solving** and no anti-bot "bypass" magic. If a site actively fights automation, the honest answer is a different approach (official API, partner feed, browser session you own), not a bigger hammer.
- One concession to headless detection is disclosed in `engine.py`: the `navigator.webdriver` flag is cleared (3 lines), because some sites reject automated browsers before serving any content. There is no fingerprint spoofing beyond that, and no attempt to defeat a login or a challenge.
- `robots.txt` is respected by default. I will not scrape sites whose terms forbid it; I will tell you that before taking money.
- No login automation with stored plaintext passwords — use a saved browser session.
- JavaScript-heavy infinite scroll needs a small `page.mouse.wheel` loop in `parse()`; it is a 5-line change, not a rewrite.

## License

MIT — see `LICENSE`.

---

Built by **Svyatoslav** — Python automation, data extraction, integrations (Playwright, FastAPI, n8n).
Available for small, well-defined jobs: `svyatoslav.r2000@gmail.com` · [portfolio](https://svyatoslavr2000-pixel.github.io/en.html)
