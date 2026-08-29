"""Входные данные и настройки расчёта."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from unit_economics.money import money, rate


@dataclass(frozen=True, slots=True)
class Sku:
    """Товар: то, что не меняется от заказа к заказу."""

    sku_id: int
    article: str
    title: str
    category: str
    cost_price: Decimal        # закупка за единицу
    volume_l: Decimal          # литраж для логистики и хранения
    commission_rate: Decimal   # комиссия площадки, доля

    def __post_init__(self) -> None:
        if self.cost_price <= 0:
            raise ValueError(f"{self.article}: закупочная цена должна быть больше нуля")
        if not 0 <= self.commission_rate < 1:
            raise ValueError(f"{self.article}: комиссия {self.commission_rate} вне диапазона")
        if self.volume_l <= 0:
            raise ValueError(f"{self.article}: объём должен быть больше нуля")

    @classmethod
    def from_row(cls, row: dict[str, str]) -> Sku:
        return cls(
            sku_id=int(row["sku_id"]),
            article=row["article"].strip(),
            title=row["title"].strip(),
            category=row["category"].strip(),
            cost_price=money(row["cost_price"]),
            volume_l=rate(row["volume_l"]),
            commission_rate=rate(row["commission_rate"]),
        )


@dataclass(frozen=True, slots=True)
class Order:
    """Один заказ одного артикула."""

    order_date: date
    sku_id: int
    marketplace: str
    units: int
    price: Decimal             # цена продажи за единицу, уже со скидкой
    is_returned: bool

    def __post_init__(self) -> None:
        if self.units <= 0:
            raise ValueError("в заказе должна быть хотя бы одна единица")
        if self.price < 0:
            raise ValueError("цена не может быть отрицательной")

    @property
    def revenue(self) -> Decimal:
        """Выручка заказа. У возврата она нулевая: деньги вернулись покупателю.

        Расходы при этом остаются, и в этом весь смысл отдельного учёта
        возвратов. Заказ, который вернули, стоил логистики в обе стороны.
        """
        return money(0) if self.is_returned else money(self.price * self.units)

    @classmethod
    def from_row(cls, row: dict[str, str]) -> Order:
        return cls(
            order_date=date.fromisoformat(row["date"].strip()),
            sku_id=int(row["sku_id"]),
            marketplace=row["marketplace"].strip(),
            units=int(row["units"]),
            price=money(row["price"]),
            is_returned=row["is_returned"].strip().lower() in {"1", "true", "да", "yes"},
        )


@dataclass(frozen=True, slots=True)
class AdSpend:
    """Расход на рекламу за день по артикулу."""

    spend_date: date
    sku_id: int
    spend: Decimal

    @classmethod
    def from_row(cls, row: dict[str, str]) -> AdSpend:
        return cls(
            spend_date=date.fromisoformat(row["date"].strip()),
            sku_id=int(row["sku_id"]),
            spend=money(row["spend"]),
        )


@dataclass(frozen=True, slots=True)
class Tariffs:
    """Тарифы площадки и налоговый режим.

    Значения по умолчанию близки к тарифам WB и Ozon на середину 2026 года,
    но это именно параметры расчёта: у каждого продавца они свои, и вся
    суть в том, чтобы их можно было подставить, а не найти зашитыми в коде.
    """

    acquiring_rate: Decimal = rate("0.015")
    tax_rate: Decimal = rate("0.06")           # УСН «доходы»
    delivery_base: Decimal = money("38")       # доставка до покупателя, база
    delivery_per_liter: Decimal = money("9.5")
    return_share: Decimal = rate("1.0")        # какую долю логистики стоит возврат
    storage_per_liter_day: Decimal = money("0.12")
    storage_days: int = 30

    def delivery_cost(self, sku: Sku, units: int) -> Decimal:
        """Логистика до покупателя. Первый литр по базе, дальше по литражу."""
        extra_liters = max(sku.volume_l - 1, rate("0"))
        per_unit = self.delivery_base + money(self.delivery_per_liter * extra_liters)
        return money(per_unit * units)

    def storage_cost(self, sku: Sku, units: int) -> Decimal:
        return money(self.storage_per_liter_day * sku.volume_l * self.storage_days * units)


@dataclass(frozen=True, slots=True)
class BidPolicy:
    """Правило принятия решения по рекламной ставке.

    Пороги вынесены в объект намеренно. Это не константы в формуле, а
    политика продавца: осторожный держит запас в половину, агрессивный
    работает почти в ноль. Правило должно обсуждаться, а значит и жить
    отдельно от расчёта.
    """

    raise_below: Decimal = rate("0.60")   # ниже 60% от безубыточного ДРР есть запас
    hold_below: Decimal = rate("0.90")
    reduce_below: Decimal = rate("1.00")
    labels: dict[str, str] = field(default_factory=lambda: {
        "raise": "поднимать ставку",
        "hold": "держать",
        "reduce": "снижать ставку",
        "stop": "выключать рекламу",
        "unknown": "нет продаж",
    })
