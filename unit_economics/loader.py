"""Чтение входных CSV с внятными ошибками.

Файл с данными почти всегда приходит от человека, а не от системы: его
выгрузили руками, поправили в Excel и прислали. Поэтому загрузчик должен
называть номер строки и колонку, а не падать с ValueError где-то в глубине.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from unit_economics.models import AdSpend, Order, Sku

T = TypeVar("T")

REQUIRED = {
    "skus": {"sku_id", "article", "title", "category", "cost_price", "volume_l", "commission_rate"},
    "orders": {"date", "sku_id", "marketplace", "units", "price", "is_returned"},
    "ads": {"date", "sku_id", "spend"},
}


class DataError(Exception):
    """Во входном файле что-то не так, и сообщение объясняет что именно."""


def _read(path: Path, kind: str, factory: Callable[[dict[str, str]], T]) -> list[T]:
    if not path.exists():
        raise DataError(f"Файл не найден: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DataError(f"{path.name}: файл пустой")
        missing = REQUIRED[kind] - {name.strip() for name in reader.fieldnames}
        if missing:
            raise DataError(f"{path.name}: не хватает колонок {', '.join(sorted(missing))}")
        rows: list[T] = []
        for line_number, row in enumerate(reader, start=2):
            clean = {key.strip(): (value or "") for key, value in row.items() if key}
            try:
                rows.append(factory(clean))
            except (ValueError, KeyError, TypeError) as error:
                raise DataError(f"{path.name}, строка {line_number}: {error}") from error
    if not rows:
        raise DataError(f"{path.name}: нет ни одной строки данных")
    return rows


def load_skus(path: str | Path) -> dict[int, Sku]:
    items = _read(Path(path), "skus", Sku.from_row)
    catalogue: dict[int, Sku] = {}
    for sku in items:
        if sku.sku_id in catalogue:
            raise DataError(f"Артикул {sku.sku_id} встречается в справочнике дважды")
        catalogue[sku.sku_id] = sku
    return catalogue


def load_orders(path: str | Path) -> list[Order]:
    return _read(Path(path), "orders", Order.from_row)


def load_ads(path: str | Path) -> list[AdSpend]:
    return _read(Path(path), "ads", AdSpend.from_row)
