"""Command line entry point: ``python -m scraper.cli run <spider>``."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import sys
from pathlib import Path

from . import __version__
from .config import Settings
from .engine import run_spider
from .exporters import existing_keys, open_exporter
from .records import Deduper
from .spiders import SPIDERS, build


def _output_path(spider_name: str, fmt: str, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    return Path("out") / f"{spider_name}.{fmt}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrape",
        description="Resumable, polite Playwright scraper.",
        epilog="examples:\n"
        "  python -m scraper.cli run quotes --pages 3\n"
        "  python -m scraper.cli run quotes --format jsonl --out data/quotes.jsonl --resume\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="run a spider")
    run.add_argument("spider", help="spider name, see `list`")
    run.add_argument("--pages", type=int, default=5, help="max pages to visit (default: 5)")
    run.add_argument("--max-items", type=int, default=0, help="stop after N records (0 = off)")
    run.add_argument("--format", dest="fmt", choices=("csv", "jsonl"), default="csv")
    run.add_argument("--out", default=None, help="output file (default: out/<spider>.<format>)")
    run.add_argument("--resume", action="store_true", help="skip records already in --out")
    run.add_argument("--delay", type=float, default=1.0, help="seconds between pages (default: 1.0)")
    run.add_argument("--jitter", type=float, default=0.5, help="random extra pause (default: 0.5)")
    run.add_argument("--timeout", type=int, default=30_000, help="page timeout in ms")
    run.add_argument("--retries", type=int, default=2, help="extra attempts per page")
    run.add_argument("--headed", action="store_true", help="show the browser window")
    run.add_argument("--proxy", default=None, help="proxy URL, e.g. http://host:8080")
    run.add_argument("--ignore-robots", action="store_true", help="only for sites you own")
    run.add_argument("--no-block-assets", action="store_true", help="load images/fonts")

    subparsers.add_parser("list", help="list available spiders")
    return parser


def _cmd_list() -> int:
    if not SPIDERS:
        print("no spiders registered")
        return 0
    width = max(len(name) for name in SPIDERS)
    for name, spider_class in sorted(SPIDERS.items()):
        urls = ", ".join(spider_class.start_urls) or "-"
        print(f"{name:<{width}}  {urls}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    spider = build(args.spider)
    settings = Settings.from_env()
    settings.headless = not args.headed
    settings.delay_s = max(0.0, args.delay)
    settings.jitter_s = max(0.0, args.jitter)
    settings.timeout_ms = args.timeout
    settings.retries = max(0, args.retries)
    settings.proxy = args.proxy
    settings.respect_robots = not args.ignore_robots
    settings.block_assets = not args.no_block_assets

    out = _output_path(spider.name, args.fmt, args.out)
    deduper = Deduper(spider.key_fields)
    if args.resume:
        for key in existing_keys(out, args.fmt, spider.key_fields):
            deduper.add(key)
        print(f"resume | {len(deduper)} keys already in {out}")

    def log(message: str) -> None:
        print(message, flush=True)

    exporter = open_exporter(args.fmt, out, spider.fields, resume=args.resume)
    try:
        stats = asyncio.run(
            run_spider(
                spider,
                settings,
                max_pages=max(1, args.pages),
                max_items=max(0, args.max_items),
                exporter=exporter,
                deduper=deduper,
                log=log,
            )
        )
    except KeyboardInterrupt:
        print("\ninterrupted - finished rows are already on disk", file=sys.stderr)
        return 130
    finally:
        exporter.close()

    print(
        "done: {items} items | {pages} pages | {duplicates} duplicates | "
        "{errors} errors | {elapsed_s}s -> {out}".format(out=out, **stats)
    )
    if stats["items"] == 0:
        return 1 if stats["errors"] else 0
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        # Windows consoles default to cp1251/cp866 and choke on non-ASCII output
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        return _cmd_list()
    return _cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
