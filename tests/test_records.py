from scraper.records import Deduper, absolute, clean, normalize_url, to_row


def test_clean_flattens_lists_and_collapses_whitespace():
    assert clean([" a ", "b", ""]) == "a; b"
    assert clean("a\u00a0\u00a0 b \n c") == "a b c"
    assert clean(None) == ""
    assert clean(10.0) == "10"
    assert clean({"k": "v"}) == "k=v"
    assert clean(True) == "true"


def test_absolute_resolves_against_base_and_drops_fragment():
    assert absolute("/item/1", "https://shop.test/catalog") == "https://shop.test/item/1"
    assert absolute("https://a.test/x#reviews") == "https://a.test/x"
    assert absolute("") == ""


def test_normalize_url_removes_tracking_and_default_port():
    url = "HTTPS://Shop.TEST:443/item/42/?utm_source=x&id=7&ref=abc#top"
    assert normalize_url(url) == "https://shop.test/item/42?id=7"


def test_deduper_uses_key_fields_and_survives_missing_values():
    deduper = Deduper(("text", "author"))
    first = {"text": "A", "author": "B"}
    assert deduper.is_new(first) is True
    assert deduper.is_new(dict(first)) is False
    assert deduper.is_new({"text": "A", "author": "C"}) is True
    # records without any key field still dedupe by content hash
    assert deduper.is_new({"x": 1}) is True
    assert deduper.is_new({"x": 1}) is False


def test_to_row_keeps_declared_field_order():
    row = to_row({"b": 2, "a": [1, 2], "c": None}, ["a", "b", "c", "missing"])
    assert row == {"a": "1; 2", "b": "2", "c": "", "missing": ""}
