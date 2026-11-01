"""Minimal, testable robots.txt handling.

Only the parts a scraper actually needs: ``Disallow``/``Allow`` and
``Crawl-delay``. Group precedence follows RFC 9309: an exact user-agent group
wins over ``*``, rules from every matching group are combined, and the longest
matching rule wins (``Allow`` beats ``Disallow`` on a tie).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_ROBOTS_BYTES = 500_000


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern[str]:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.compile("^" + regex + ("$" if anchored else ""), re.DOTALL)


@dataclass(slots=True)
class RobotsPolicy:
    rules: list[tuple[bool, str]] = field(default_factory=list)  # (allow, raw pattern)
    crawl_delay: float | None = None

    def allowed(self, path: str) -> bool:
        if not path.startswith("/"):
            path = "/" + path
        best: tuple[int, bool] | None = None
        for allow, pattern in self.rules:
            if not _compile(pattern).match(path):
                continue
            candidate = (len(pattern), allow)
            if best is None or candidate > best:
                best = candidate
        return True if best is None else best[1]

    @property
    def is_empty(self) -> bool:
        return not self.rules


def parse_robots(text: str, agent: str = "*") -> RobotsPolicy:
    groups: list[tuple[list[str], list[tuple[bool, str]], float | None]] = []
    agents: list[str] = []
    rules: list[tuple[bool, str]] = []
    delay: float | None = None

    def flush() -> None:
        nonlocal agents, rules, delay
        if agents:
            groups.append((agents, rules, delay))
        agents, rules, delay = [], [], None

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if rules or delay is not None:
                flush()
            agents.append(value.lower())
        elif key in {"allow", "disallow"}:
            if value:  # an empty value means "allow everything"
                rules.append((key == "allow", value))
        elif key == "crawl-delay":
            try:
                delay = float(value)
            except ValueError:
                delay = None
    flush()

    wanted = agent.lower()
    exact = [g for g in groups if wanted in g[0] and wanted != "*"]
    matching = exact or [g for g in groups if "*" in g[0]]

    policy = RobotsPolicy()
    for _, group_rules, group_delay in matching:
        policy.rules.extend(group_rules)
        if group_delay is not None:
            policy.crawl_delay = (
                group_delay
                if policy.crawl_delay is None
                else min(policy.crawl_delay, group_delay)
            )
    return policy


def fetch_robots(url: str, timeout: float = 5.0) -> RobotsPolicy | None:
    """Best-effort fetch. ``None`` means "no robots.txt / unreachable"."""
    parts = urlparse(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    target = f"{parts.scheme}://{parts.netloc}/robots.txt"
    request = Request(target, headers={"User-Agent": "playwright-scraper-template/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - scheme checked above
            if response.status >= 400:
                return None
            raw = response.read(MAX_ROBOTS_BYTES)
    except Exception:  # noqa: BLE001 - robots.txt is advisory infrastructure
        return None
    return parse_robots(raw.decode("utf-8", errors="replace"))


def origin_of(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}"


def path_of(url: str) -> str:
    parts = urlparse(url)
    path = parts.path or "/"
    return f"{path}?{parts.query}" if parts.query else path
