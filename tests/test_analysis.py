"""ABC, точка безубыточности и сводные суммы."""

from decimal import Decimal

import pytest

from unit_economics.analysis import abc, break_even, totals
from unit_economics.money import money
from unit_economics.pnl import build_pnl


def build(skus, orders, ads=()):
    return build_pnl({s.sku_id: s for s in skus}, list(orders), list(ads))


@pytest.fixture
def portfolio(sku, order):
    """Три товара с разным вкладом: один везёт почти всё, третий почти ничего."""
    skus = [sku(1), sku(2), sku(3)]
    orders = (
        [order(sku_id=1) for _ in range(60)]
        + [order(sku_id=2) for _ in range(12)]
        + [order(sku_id=3) for _ in range(2)]
    )
    return build(skus, orders)


def test_running_share_reaches_exactly_one_hundred(portfolio):
    rows = abc(portfolio)
    assert rows[-1].running_share_pct == Decimal("100.0")


def test_abc_orders_from_largest_to_smallest(portfolio):
    rows = abc(portfolio)
    values = [row.pnl.revenue for row in rows]
    assert values == sorted(values, reverse=True)


def test_leader_lands_in_class_a(portfolio):
    assert abc(portfolio)[0].abc_class == "A"


def test_a_single_dominant_sku_still_belongs_to_class_a(sku, order):
    """Товар, который в одиночку перешагивает 80%, обязан остаться в A.

    Наивное правило «класс по накопленной доле после товара» отправляет его
    в B, и в ассортименте не оказывается ни одного товара класса A. На этом
    и споткнулась первая версия расчёта.
    """
    rows = build(
        [sku(1), sku(2)],
        [order(sku_id=1) for _ in range(90)] + [order(sku_id=2) for _ in range(5)],
    )
    classified = abc(rows, by="revenue")
    assert classified[0].running_share_pct > Decimal("80")
    assert classified[0].abc_class == "A"


def test_abc_by_profit_and_by_revenue_can_disagree(sku, order, ad):
    """Разница между этими двумя списками и есть самое интересное в ассортименте.

    Товар с большой выручкой и выжженной рекламой маржой стоит в A по
    обороту и в C по прибыли, и увидеть это можно только сравнив списки.
    """
    rows = build(
        [sku(1), sku(2)],
        [order(sku_id=1) for _ in range(40)] + [order(sku_id=2) for _ in range(20)],
        [ad(sku_id=1, spend="45000")],
    )
    by_revenue = [row.pnl.sku.sku_id for row in abc(rows, by="revenue")]
    by_profit = [row.pnl.sku.sku_id for row in abc(rows, by="net_profit")]
    assert by_revenue != by_profit


def test_empty_portfolio_has_no_break_even_point(sku):
    result = break_even(build([sku()], []), money("100000"))
    assert result.units_needed is None
    assert not result.covered


def test_break_even_units_cover_fixed_costs(portfolio):
    result = break_even(portfolio, money("50000"))
    assert result.units_needed is not None
    assert result.unit_contribution * result.units_needed >= money("50000")


def test_totals_match_the_sum_of_rows(portfolio):
    summary = totals(portfolio)
    assert summary["revenue"] == sum((row.revenue for row in portfolio), start=money(0))
    assert summary["net_profit"] == sum((row.net_profit for row in portfolio), start=money(0))


def test_unknown_grouping_is_rejected(portfolio):
    with pytest.raises(ValueError, match="группировать"):
        abc(portfolio, by="units")
