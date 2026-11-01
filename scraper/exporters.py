"""CSV / JSONL writers that append, flush, and never lose a finished row."""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from .records import clean, to_row


class Exporter(Protocol):
    fields: list[str]

    def write(self, record: dict[str, Any]) -> None: ...

    def close(self) -> None: ...


class _Base:
    fields: list[str]

    def __init__(self, path: str | os.PathLike[str], fields: Iterable[str], resume: bool = False) -> None:
        self.path = Path(path)
        self.fields = list(fields)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._resume = resume and self.path.exists()
        self._handle = None

    @property
    def is_empty(self) -> bool:
        return not self.path.exists() or self.path.stat().st_size == 0

    def __enter__(self) -> _Base:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class CsvExporter(_Base):
    """Appends rows. Writes the header once, and only if the file is new."""

    def __init__(self, path: str | os.PathLike[str], fields: Iterable[str], resume: bool = False) -> None:
        super().__init__(path, fields, resume)
        new_file = self.is_empty
        # utf-8-sig keeps Cyrillic readable when the client opens the file in Excel
        self._handle = self.path.open("a", encoding="utf-8-sig", newline="")
        self._writer = csv.DictWriter(self._handle, fieldnames=self.fields, extrasaction="ignore")
        if new_file:
            self._writer.writeheader()
            self._handle.flush()

    def write(self, record: dict[str, Any]) -> None:
        self._writer.writerow(to_row(record, self.fields))
        self._handle.flush()

    def close(self) -> None:
        if self._handle and not self._handle.closed:
            self._handle.close()


class JsonlExporter(_Base):
    """One JSON object per line: crash-safe, streamable, easy to inspect."""

    def __init__(self, path: str | os.PathLike[str], fields: Iterable[str], resume: bool = False) -> None:
        super().__init__(path, fields, resume)
        self._handle = self.path.open("a", encoding="utf-8", newline="\n")

    def write(self, record: dict[str, Any]) -> None:
        row = to_row(record, self.fields) if self.fields else {k: clean(v) for k, v in record.items()}
        self._handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._handle.flush()

    def close(self) -> None:
        if self._handle and not self._handle.closed:
            self._handle.close()


def open_exporter(fmt: str, path: str | os.PathLike[str], fields: Iterable[str], resume: bool = False) -> Exporter:
    fmt = fmt.lower()
    if fmt == "csv":
        return CsvExporter(path, fields, resume)
    if fmt == "jsonl":
        return JsonlExporter(path, fields, resume)
    raise ValueError(f"unsupported format: {fmt!r} (use 'csv' or 'jsonl')")


def existing_keys(path: str | os.PathLike[str], fmt: str, key_fields: Iterable[str]) -> set[str]:
    """Read keys already on disk so ``--resume`` neither duplicates nor refetches."""
    file = Path(path)
    if not file.exists() or file.stat().st_size == 0:
        return set()
    keys: set[str] = set()
    if fmt.lower() == "csv":
        with file.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                keys.add("␟".join(clean(row.get(field)) for field in key_fields))
    elif fmt.lower() == "jsonl":
        with file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                keys.add("␟".join(clean(row.get(field)) for field in key_fields))
    return keys
