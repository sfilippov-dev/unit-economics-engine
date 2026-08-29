"""ABC-анализ и точка безубыточности."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from unit_economics.money import ZERO, money, percent
from unit_economics.pnl import SkuPnL

A_THRESHOLD = Decimal("0.80")
B_THRESHOLD = Decimal("0.95")


@dataclass(frozen=True, slots=True)
class AbcRow:
    pnl: SkuPnL
    position: int
    running_share_pct: Decimal
    abc_class: str


def abc(rows: list[SkuPnL], by: str = "revenue") -> list[AbcRow]:
    """Разложить ассортимент на A, B и C.

    По умолчанию по выручке, но правильнее смотреть и по прибыли: набор
    артикулов, дающих 80% выручки, и набор, дающих 80% прибыли, совпадают
    далеко не всегда, и разница между этими двумя списками и есть самое
    интересное в ассортименте.
    """
    if by not in {"revenue", "net_profit", "contribution"}:
        raise ValueError("группировать можно по revenue, contribution или net_profit")

    def value(row: SkuPnL) -> Decimal:
        return getattr(row, by)

    ordered = sorted(rows, key=value, reverse=True)
    total = sum((value(row) for row in ordered), start=ZERO)
    if total <= 0:
        return [AbcRow(row, index, ZERO, "C") for index, row in enumerate(ordered, start=1)]

    running = ZERO
    result: list[AbcRow] = []
    for index, row in enumerate(ordered, start=1):
        # Класс определяется долей, накопленной ДО этого товара, а не после.
        # Иначе товар, который в одиночку перешагивает 80%, попадает в B, и
        # класса A в ассортименте не оказывается вовсе. Правило звучит как
        # «товары, которые вместе набирают первые 80%», а значит тот, кто
        # пересекает черту, входит в A, а не выпадает из него.
        share_before = running / total
        running += value(row)
        result.append(
            AbcRow(
                pnl=row,
                position=index,
                running_share_pct=percent(running, total) or ZERO,
                abc_class=(
                    "A" if share_before < A_THRESHOLD
                    else "B" if share_before < B_THRESHOLD
                    else "C"
                ),
            )
        )
    return result


@dataclass(frozen=True, slots=True)
class BreakEven:
    """Точка безубыточности в штуках при заданных постоянных расходах."""

    unit_contribution: Decimal
    fixed_costs: Decimal
    units_needed: int | None
    units_sold: int

    @property
    def covered(self) -> bool:
        return self.units_needed is not None and self.units_sold >= self.units_needed


def break_even(rows: list[SkuPnL], fixed_costs: Decimal) -> BreakEven:
    """Сколько единиц нужно продать, чтобы закрыть постоянные расходы.

    Берётся средняя маржинальность на единицу по всему портфелю: считать
    точку безубыточности по каждому артикулу отдельно бессмысленно, потому
    что постоянные расходы общие и делить их между артикулами можно
    десятком способов, и все они спорные.
    """
    units = sum(row.units_sold for row in rows)
    contribution = sum((row.contribution for row in rows), start=ZERO)
    if units == 0 or contribution <= 0:
        return BreakEven(ZERO, fixed_costs, None, units)
    per_unit = money(contribution / units)
    needed = int((fixed_costs / per_unit).to_integral_value(rounding="ROUND_CEILING"))
    return BreakEven(per_unit, fixed_costs, needed, units)


def totals(rows: list[SkuPnL]) -> dict[str, Decimal]:
    """Свод по всему портфелю."""
    fields = (
        "revenue", "cogs", "commission", "acquiring", "logistics",
        "logistics_on_returns", "storage", "tax", "ad_spend",
    )
    result = {name: money(sum((getattr(r, name) for r in rows), start=ZERO)) for name in fields}
    result["contribution"] = money(sum((r.contribution for r in rows), start=ZERO))
    result["net_profit"] = money(sum((r.net_profit for r in rows), start=ZERO))
    result["units_sold"] = Decimal(sum(r.units_sold for r in rows))
    return result
