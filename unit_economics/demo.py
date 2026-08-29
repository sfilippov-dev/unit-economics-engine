"""Генератор демонстрационных данных.

Нужен, чтобы проект запускался у любого человека одной командой, без
чужих коммерческих данных. Числа синтетические, но структура настоящая:
разная маржинальность по категориям, возвраты, сезонность и несколько
артикулов, сознательно уведённых в минус рекламой. Без последних отчёт
показывал бы ровный ряд прибыльных строк и был бы бесполезен.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

CATEGORIES = {
    # категория: (цена от, цена до, наценка к закупке, комиссия, литраж)
    "Планшеты":       (11900, 21900, 2.1, 0.155, 3.2),
    "Электробритвы":  (2490, 6990, 3.4, 0.185, 0.9),
    "Фотоэпиляторы":  (3990, 9900, 3.8, 0.190, 1.4),
    "Наушники":       (1290, 5900, 3.1, 0.170, 0.4),
    "Аксессуары":     (390, 1490, 4.2, 0.210, 0.2),
}
BRANDS = ["Lumina", "NeoShave", "Lingbo", "W&O", "Karta"]
MARKETPLACES = ["WB", "Ozon"]

START = date(2026, 2, 1)
DAYS = 180


def generate(destination: str | Path, sku_count: int = 24, seed: int = 20260829) -> dict[str, int]:
    """Записать skus.csv, orders.csv и ads.csv. Данные зависят только от зерна."""
    rng = random.Random(seed)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)

    skus, profile = [], {}
    names = list(CATEGORIES)
    for sku_id in range(1, sku_count + 1):
        category = names[sku_id % len(names)]
        low, high, markup, commission, volume = CATEGORIES[category]
        price = round(rng.uniform(low, high), -1)
        cost = round(price / rng.uniform(markup * 0.8, markup * 1.2), 2)
        popularity = rng.choice([0.4, 0.7, 1.0, 1.6, 2.4, 4.0])
        # Каждый четвёртый артикул получает завышенную рекламу: в реальном
        # кабинете такие есть всегда, и находить их и есть работа отчёта.
        overspending = sku_id % 4 == 0
        skus.append({
            "sku_id": sku_id,
            "article": f"ART-{sku_id:04d}",
            "title": f"{BRANDS[sku_id % len(BRANDS)]} {category[:-1].lower()} {sku_id}",
            "category": category,
            "cost_price": f"{cost:.2f}",
            "volume_l": f"{volume:.2f}",
            "commission_rate": f"{commission:.3f}",
        })
        profile[sku_id] = {
            "price": price,
            "popularity": popularity,
            "return_rate": rng.uniform(0.08, 0.28),
            "target_drr": rng.uniform(0.28, 0.55) if overspending else rng.uniform(0.03, 0.14),
        }

    orders, ads = [], []
    for offset in range(DAYS):
        day = START + timedelta(days=offset)
        season = 1.35 if day.month in (11, 12) else 0.8 if day.month in (1, 7) else 1.0
        weekday = 0.85 if day.isoweekday() > 5 else 1.0
        for sku_id, meta in profile.items():
            count = int(rng.gauss(meta["popularity"] * season * weekday, 0.8))
            revenue_today = 0.0
            for _ in range(max(count, 0)):
                units = 1 if rng.random() < 0.9 else 2
                discount = rng.choice([0, 0, 0.05, 0.1])
                price = round(meta["price"] * (1 - discount), 2)
                returned = rng.random() < meta["return_rate"]
                orders.append({
                    "date": day.isoformat(),
                    "sku_id": sku_id,
                    "marketplace": rng.choice(MARKETPLACES),
                    "units": units,
                    "price": f"{price:.2f}",
                    "is_returned": "true" if returned else "false",
                })
                if not returned:
                    revenue_today += price * units
            if revenue_today > 0:
                spend = revenue_today * meta["target_drr"] * rng.uniform(0.7, 1.3)
                ads.append({"date": day.isoformat(), "sku_id": sku_id, "spend": f"{spend:.2f}"})

    _write(destination / "skus.csv", skus)
    _write(destination / "orders.csv", orders)
    _write(destination / "ads.csv", ads)
    return {"skus": len(skus), "orders": len(orders), "ads": len(ads)}


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
