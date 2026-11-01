"""Next-page resolution and loop protection."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

PAGE_TOKEN = "{page}"


def resolve(base_url: str, href: str | None) -> str | None:
    """Turn a relative ``next`` href into an absolute URL, or None."""
    href = (href or "").strip()
    if not href:
        return None
    if href in {"#", "javascript:void(0)", "javascript:;"}:
        return None
    return urljoin(base_url, href).split("#", 1)[0]


def page_template(template: str, page_number: int) -> str:
    """Fill ``{page}`` in a URL template, e.g. ``/catalog?page={page}``."""
    if PAGE_TOKEN not in template:
        return template
    return template.replace(PAGE_TOKEN, str(page_number))


def with_page_param(url: str, page_number: int, param: str = "page") -> str:
    """Set/replace a query parameter without touching the rest of the URL."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != param]
    query.append((param, str(page_number)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def canonical(url: str) -> str:
    """Comparable form used for loop detection (pagination paths only)."""
    parts = urlsplit(url)
    query = sorted(parse_qsl(parts.query, keep_blank_values=True))
    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


class LoopGuard:
    """Stops a spider when the site returns the same page over and over."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def contains(self, url: str) -> bool:
        """Check without marking: used when deciding whether to enqueue."""
        return canonical(url) in self._seen

    def is_new(self, url: str) -> bool:
        """Mark as visited. True when the URL had not been visited before."""
        key = canonical(url)
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def __len__(self) -> int:
        return len(self._seen)
