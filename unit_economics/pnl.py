"""Отчёт о прибыли по каждому артикулу.

Порядок вычитания важен и повторяет порядок, в котором деньги реально
уходят: сначала площадка забирает своё с оборота, потом остаётся то, из
чего платится закупка, и только в конце вычитается реклама. Реклама стоит
последней не для красоты: именно она управляемая, и всё, что выше неё,
задаёт потолок, выше которого рекламный бюджет уводит артикул в минус.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from unit_economics.models import AdSpend, BidPolicy, Order, Sku, Tariffs
from unit_economics.money import money, percent


@dataclass(frozen=True, slots=True)
class SkuPnL:
    """Экономика одного артикула за период."""

    sku: Sku
    orders: int
    returned_orders: int
    units_sold: int
    revenue: Decimal
    cogs: Decimal
    commission: Decimal
    acquiring: Decimal
    logistics: Decimal
    logistics_on_returns: Decimal
    storage: Decimal
    tax: Decimal
    ad_spend: Decimal

    @property
    def platform_costs(self) -> Decimal:
        return money(
            self.commission + self.acquiring + self.logistics
            + self.logistics_on_returns + self.storage + self.tax
        )

    @property
    def contribution(self) -> Decimal:
        """Маржинальная прибыль: всё, что остаётся до рекламы.

        Это и есть весь бюджет, который можно потратить на рекламу, ничего
        при этом не заработав. Отсюда берётся безубыточный ДРР.
        """
        return money(self.revenue - self.cogs - self.platform_costs)

    @property
    def net_profit(self) -> Decimal:
        return money(self.contribution - self.ad_spend)

    @property
    def return_rate(self) -> Decimal | None:
        total = self.orders + self.returned_orders
        return percent(Decimal(self.returned_orders), Decimal(total)) if total else None

    @property
    def contribution_margin_pct(self) -> Decimal | None:
        return percent(self.contribution, self.revenue)

    @property
    def net_margin_pct(self) -> Decimal | None:
        return percent(self.net_profit, self.revenue)

    @property
    def drr_pct(self) -> Decimal | None:
        """Доля рекламных расходов в выручке, факт."""
        return percent(self.ad_spend, self.revenue)

    @property
    def breakeven_drr_pct(self) -> Decimal | None:
        """Доля рекламы, при которой артикул выходит ровно в ноль.

        Считается от маржи конкретного артикула, а не от планового
        ориентира по магазину. Плановый ДРР в 10% для товара с маржой 8%
        означает работу в минус, и никакой отчёт по магазину этого не
        покажет: в среднем всё будет прилично.
        """
        return percent(self.contribution, self.revenue)

    def decision(self, policy: BidPolicy | None = None) -> str:
        """Что делать со ставкой."""
        policy = policy or BidPolicy()
        if self.revenue == 0 or self.contribution <= 0:
            return policy.labels["stop"] if self.revenue else policy.labels["unknown"]
        ratio = self.ad_spend / self.contribution
        if ratio < policy.raise_below:
            return policy.labels["raise"]
        if ratio < policy.hold_below:
            return policy.labels["hold"]
        if ratio < policy.reduce_below:
            return policy.labels["reduce"]
        return policy.labels["stop"]

    def headroom(self) -> Decimal:
        """Сколько ещё можно потратить на рекламу, оставаясь в нуле."""
        return money(max(self.contribution - self.ad_spend, Decimal(0)))


def build_pnl(
    skus: dict[int, Sku],
    orders: list[Order],
    ads: list[AdSpend],
    tariffs: Tariffs | None = None,
) -> list[SkuPnL]:
    """Собрать экономику по каждому артикулу за весь период данных."""
    tariffs = tariffs or Tariffs()
    unknown = {order.sku_id for order in orders} - set(skus)
    if unknown:
        raise KeyError(f"В заказах есть артикулы, которых нет в справочнике: {sorted(unknown)}")

    ad_by_sku: dict[int, Decimal] = {}
    for entry in ads:
        ad_by_sku[entry.sku_id] = ad_by_sku.get(entry.sku_id, money(0)) + entry.spend

    result: list[SkuPnL] = []
    for sku_id, sku in sorted(skus.items()):
        own = [order for order in orders if order.sku_id == sku_id]
        delivered = [order for order in own if not order.is_returned]
        returned = [order for order in own if order.is_returned]

        units_sold = sum(order.units for order in delivered)
        revenue = money(sum((order.revenue for order in own), start=money(0)))
        cogs = money(sku.cost_price * units_sold)
        commission = money(revenue * sku.commission_rate)
        acquiring = money(revenue * tariffs.acquiring_rate)

        logistics = money(sum(
            (tariffs.delivery_cost(sku, order.units) for order in delivered), start=money(0)
        ))
        # Возврат оплачивается дважды: товар доехал до покупателя и вернулся.
        # Доля второй поездки настраивается: у части площадок обратная
        # логистика дешевле прямой.
        logistics_on_returns = money(sum(
            (
                tariffs.delivery_cost(sku, order.units) * (1 + tariffs.return_share)
                for order in returned
            ),
            start=money(0),
        ))
        storage = money(tariffs.storage_cost(sku, max(units_sold, 1)))
        # Налог считается с поступлений, а не с прибыли: на УСН «доходы»
        # убыточный артикул всё равно платит налог.
        tax = money(revenue * tariffs.tax_rate)

        result.append(
            SkuPnL(
                sku=sku,
                orders=len(delivered),
                returned_orders=len(returned),
                units_sold=units_sold,
                revenue=revenue,
                cogs=cogs,
                commission=commission,
                acquiring=acquiring,
                logistics=logistics,
                logistics_on_returns=logistics_on_returns,
                storage=storage,
                tax=tax,
                ad_spend=ad_by_sku.get(sku_id, money(0)),
            )
        )
    return result
