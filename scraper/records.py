"""Record shaping: text cleaning, URL normalisation, deduplication."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

_WS = re.compile(r"[\s\u00a0\u1680\u2000-\u200d\u202f\u205f\u3000\ufeff]+")
_TRACKING = re.compile(r"^(utm_|fbclid$|gclid$|yclid$|mc_cid$|mc_eid$|ref$|ref_src$)", re.I)


def clean(value: Any) -> str:
    """Flatten anything into a single deterministic CSV-safe string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, set)):
        parts = [clean(item) for item in value]
        return "; ".join(part for part in parts if part)
    if isinstance(value, dict):
        return "; ".join(f"{k}={clean(v)}" for k, v in value.items())
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _WS.sub(" ", str(value)).strip()


def absolute(url: str, base: str | None = None) -> str:
    if not url:
        return ""
    resolved = urljoin(base, url) if base else url
    return resolved.split("#", 1)[0]


def normalize_url(url: str, base: str | None = None) -> str:
    """Lower-case scheme/host, drop fragments, tracking params and default ports."""
    url = absolute(url, base)
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING.match(k)]
    netloc = parts.netloc.lower()
    if netloc.endswith(":80") and parts.scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and parts.scheme == "https":
        netloc = netloc[:-4]
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query, doseq=True), ""))


class Deduper:
    """Remembers record keys so re-runs and overlapping pages stay clean."""

    def __init__(self, key_fields: Iterable[str] = ("url",)) -> None:
        self.key_fields = tuple(key_fields) or ("url",)
        self._seen: set[str] = set()

    def __len__(self) -> int:
        return len(self._seen)

    def key_of(self, record: dict[str, Any]) -> str:
        parts = [clean(record.get(field)) for field in self.key_fields]
        if any(parts):
            return "␟".join(parts)
        payload = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
        return "hash:" + hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def add(self, key: str) -> None:
        self._seen.add(key)

    def is_new(self, record: dict[str, Any]) -> bool:
        """True when the record was not seen before; marks it as seen."""
        key = self.key_of(record)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True


def to_row(record: dict[str, Any], fields: Iterable[str]) -> dict[str, str]:
    return {field: clean(record.get(field)) for field in fields}
