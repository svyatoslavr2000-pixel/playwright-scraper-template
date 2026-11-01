from scraper.pagination import LoopGuard, canonical, page_template, resolve, with_page_param


def test_resolve_handles_relative_absolute_and_dead_links():
    assert resolve("https://s.test/page/2/", "page/3/") == "https://s.test/page/2/page/3/"
    assert resolve("https://s.test/a", "/b") == "https://s.test/b"
    assert resolve("https://s.test/a", "https://other.test/x#frag") == "https://other.test/x"
    assert resolve("https://s.test/a", None) is None
    assert resolve("https://s.test/a", "#") is None
    assert resolve("https://s.test/a", "  ") is None


def test_page_template_and_query_helper():
    assert page_template("https://s.test/list?p={page}", 4) == "https://s.test/list?p=4"
    assert page_template("https://s.test/list", 4) == "https://s.test/list"
    assert with_page_param("https://s.test/list?sort=asc", 3) == "https://s.test/list?sort=asc&page=3"
    assert with_page_param("https://s.test/list?page=1", 9) == "https://s.test/list?page=9"


def test_canonical_ignores_trailing_slash_order_and_case():
    assert canonical("https://S.test/a/?b=1&a=2") == canonical("https://s.test/a?a=2&b=1")


def test_loop_guard_stops_repeats():
    guard = LoopGuard()
    assert guard.is_new("https://s.test/page/1") is True
    assert guard.is_new("https://s.test/page/1/") is False
    assert guard.is_new("https://s.test/page/2") is True
    assert len(guard) == 2


def test_loop_guard_contains_does_not_mark():
    guard = LoopGuard()
    assert guard.contains("https://s.test/a") is False
    assert len(guard) == 0
    assert guard.is_new("https://s.test/a") is True
    assert guard.contains("https://s.test/a/") is True
