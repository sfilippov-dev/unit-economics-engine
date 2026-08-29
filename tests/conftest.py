import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unit_economics.models import AdSpend, Order, Sku  # noqa: E402
from unit_economics.money import money, rate  # noqa: E402


@pytest.fixture
def sku():
    """Типичный товар: закупка 1000, продажа 3000, комиссия 15%."""
    def make(sku_id: int = 1, cost: str = "1000", commission: str = "0.15",
             volume: str = "1.0") -> Sku:
        return Sku(
            sku_id=sku_id,
            article=f"ART-{sku_id:04d}",
            title="Тестовый товар",
            category="Тесты",
            cost_price=money(cost),
            volume_l=rate(volume),
            commission_rate=rate(commission),
        )
    return make


@pytest.fixture
def order():
    def make(sku_id: int = 1, price: str = "3000", units: int = 1,
             returned: bool = False, day: int = 1) -> Order:
        return Order(
            order_date=date(2026, 3, day),
            sku_id=sku_id,
            marketplace="WB",
            units=units,
            price=money(price),
            is_returned=returned,
        )
    return make


@pytest.fixture
def ad():
    def make(sku_id: int = 1, spend: str = "1000", day: int = 1) -> AdSpend:
        return AdSpend(spend_date=date(2026, 3, day), sku_id=sku_id, spend=money(spend))
    return make
