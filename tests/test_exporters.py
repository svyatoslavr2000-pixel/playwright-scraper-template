import csv
import json

import pytest

from scraper.exporters import CsvExporter, JsonlExporter, existing_keys, open_exporter

FIELDS = ["url", "title", "tags"]


def test_csv_writes_header_once_and_appends(tmp_path):
    path = tmp_path / "out" / "rows.csv"
    with CsvExporter(path, FIELDS) as writer:
        writer.write({"url": "https://a.test/1", "title": "Первый", "tags": ["x", "y"]})
    with CsvExporter(path, FIELDS) as writer:
        writer.write({"url": "https://a.test/2", "title": "Second"})

    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["title"] for row in rows] == ["Первый", "Second"]
    assert rows[0]["tags"] == "x; y"
    assert path.read_text(encoding="utf-8-sig").count("url,title,tags") == 1


def test_jsonl_is_one_object_per_line(tmp_path):
    path = tmp_path / "rows.jsonl"
    with JsonlExporter(path, FIELDS) as writer:
        writer.write({"url": "https://a.test/1", "title": "T", "tags": ["a", "b"]})

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"url": "https://a.test/1", "title": "T", "tags": "a; b"}


def test_existing_keys_supports_resume_for_both_formats(tmp_path):
    csv_path = tmp_path / "r.csv"
    with CsvExporter(csv_path, FIELDS) as writer:
        writer.write({"url": "https://a.test/1", "title": "one"})
    assert existing_keys(csv_path, "csv", ("url",)) == {"https://a.test/1"}

    jsonl_path = tmp_path / "r.jsonl"
    with JsonlExporter(jsonl_path, FIELDS) as writer:
        writer.write({"url": "https://a.test/2", "title": "two"})
    assert existing_keys(jsonl_path, "jsonl", ("url",)) == {"https://a.test/2"}


def test_existing_keys_on_missing_file_is_empty(tmp_path):
    assert existing_keys(tmp_path / "nope.csv", "csv", ("url",)) == set()


def test_open_exporter_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        open_exporter("xlsx", tmp_path / "x.xlsx", FIELDS)
