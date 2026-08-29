"""Бизнес-правила расчёта. Каждый тест это одно утверждение о деньгах."""

from decimal import Decimal

import pytest

from unit_economics.models import BidPolicy, Tariffs
from unit_economics.money import money
from unit_economics.pnl import build_pnl


def build(skus, orders, ads=(), tariffs=None):
    return build_pnl({s.sku_id: s for s in skus}, list(orders), list(ads), tariffs)


def test_breakeven_drr_makes_profit_exactly_zero(sku, order):
    """Главный тест проекта.

    Если потратить на рекламу ровно безубыточный ДРР от выручки, прибыль
    обязана оказаться нулевой. Это не пример с придуманными числами, а
    проверка самой формулы: она либо согласована с расчётом P&L, либо нет.
    """
    from datetime import date

    from unit_economics.models import AdSpend

    rows = build([sku()], [order() for _ in range(20)])
    row = rows[0]
    spend_at_limit = money(row.revenue * row.breakeven_drr_pct / 100)

    with_ads = build(
        [sku()],
        [order() for _ in range(20)],
        [AdSpend(spend_date=date(2026, 3, 1), sku_id=1, spend=spend_at_limit)],
    )[0]
    # Допуск не произвольный: показатель публикуется с одним знаком после
    # запятой, значит расход, посчитанный из него, отличается от точного не
    # более чем на половину десятой доли процента выручки. Требовать здесь
    # ровного нуля значило бы требовать, чтобы в отчёте печатались все знаки.
    tolerance = money(row.revenue * Decimal("0.0006"))
    assert abs(with_ads.net_profit) <= tolerance

    # А от точной маржи прибыль обнуляется без всякого допуска.
    exact = build(
        [sku()],
        [order() for _ in range(20)],
        [AdSpend(spend_date=date(2026, 3, 1), sku_id=1, spend=row.contribution)],
    )[0]
    assert exact.net_profit == money(0)


def test_returned_order_brings_no_revenue_but_costs_logistics(sku, order):
    """Возврат это не «продажи не было». Это продажа, за которую заплатили дважды."""
    delivered = build([sku()], [order()])[0]
    returned = build([sku()], [order(returned=True)])[0]

    assert returned.revenue == money(0)
    assert returned.logistics_on_returns > delivered.logistics
    assert returned.net_profit < 0


def test_return_does_not_add_cost_of_goods(sku, order):
    """Вернувшийся товар остаётся на складе: закупку по нему списывать нельзя."""
    returned = build([sku()], [order(returned=True)])[0]
    assert returned.cogs == money(0)


def test_tax_is_charged_on_receipts_even_when_the_sku_loses_money(sku, order, ad):
    """На УСН «доходы» убыточный артикул всё равно платит налог с оборота."""
    rows = build([sku(cost="2900")], [order() for _ in range(5)], [ad(spend="5000")])
    row = rows[0]
    assert row.net_profit < 0
    assert row.tax == money(row.revenue * Tariffs().tax_rate)


def test_three_points_of_commission_flip_the_decision(sku, order, ad):
    """Комиссия выросла на три пункта, и решение по ставке поменялось.

    Это и есть причина считать безубыточный ДРР по каждому артикулу, а не
    брать плановую цифру по магазину: при одном и том же рекламном бюджете
    товар с комиссией 18% уже требует снижать ставку, а с 15% ещё держится.
    """
    orders = [order() for _ in range(30)]
    ads = [ad(spend="34000")]
    lenient = build([sku(commission="0.15")], orders, ads)[0]
    strict = build([sku(commission="0.18")], orders, ads)[0]
    assert lenient.decision() != strict.decision()
    assert strict.breakeven_drr_pct < lenient.breakeven_drr_pct


def test_sku_without_sales_does_not_crash_and_reports_no_data(sku):
    row = build([sku()], [])[0]
    assert row.revenue == money(0)
    assert row.net_margin_pct is None
    assert row.decision() == BidPolicy().labels["unknown"]


def test_policy_thresholds_are_configurable(sku, order, ad):
    """Пороги это политика продавца, а не константа внутри формулы."""
    rows = build([sku()], [order() for _ in range(20)], [ad(spend="8000")])
    row = rows[0]
    cautious = BidPolicy(raise_below=Decimal("0.1"), hold_below=Decimal("0.2"),
                         reduce_below=Decimal("0.3"))
    assert row.decision() != row.decision(cautious)


def test_costs_never_silently_disappear(sku, order, ad):
    """Сумма всех строк расхода обязана сойтись с выручкой и прибылью."""
    row = build([sku()], [order() for _ in range(7)], [ad(spend="3000")])[0]
    restored = money(
        row.cogs + row.platform_costs + row.ad_spend + row.net_profit
    )
    assert restored == row.revenue


def test_unknown_sku_in_orders_is_an_error_not_a_silent_skip(sku, order):
    """Заказ на артикул, которого нет в справочнике, это испорченная выгрузка.

    Молча пропустить его значит занизить выручку и никому об этом не сказать.
    """
    with pytest.raises(KeyError, match="нет в справочнике"):
        build([sku(sku_id=1)], [order(sku_id=99)])


def test_headroom_is_never_negative(sku, order, ad):
    row = build([sku()], [order() for _ in range(3)], [ad(spend="999999")])[0]
    assert row.headroom() == money(0)


@pytest.mark.parametrize("attribute", [
    "revenue", "cogs", "commission", "acquiring", "logistics",
    "logistics_on_returns", "storage", "tax", "ad_spend",
])
def test_every_money_field_is_decimal(sku, order, ad, attribute):
    row = build([sku()], [order()], [ad()])[0]
    assert isinstance(getattr(row, attribute), Decimal)
