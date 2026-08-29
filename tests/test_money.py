"""Проверки денежного типа. Ради них весь проект и написан на Decimal."""

from decimal import Decimal

import pytest

from unit_economics.money import money, percent, rate


def test_float_arithmetic_is_the_reason_for_decimal():
    """Наглядно: на float три десятых не получаются, на Decimal получаются."""
    assert 0.1 + 0.2 != 0.3
    assert money("0.1") + money("0.2") == money("0.3")


def test_thousand_kopecks_add_up_exactly():
    """Тысяча операций по копейке дают ровно десять рублей, без хвоста."""
    total = sum((money("0.01") for _ in range(1000)), start=money(0))
    assert total == money("10.00")


def test_float_input_goes_through_its_text_form():
    """Decimal(0.1) даёт длинный хвост, money(0.1) не даёт."""
    assert money(0.1) == Decimal("0.10")


@pytest.mark.parametrize("value", ["1 200,50", "1200.50", 1200.5, Decimal("1200.50")])
def test_accepts_the_shapes_people_actually_paste(value):
    assert money(value) == Decimal("1200.50")


def test_rate_is_not_rounded_to_kopecks():
    """Комиссия 15,5% обязана остаться 0.155, а не превратиться в 0.16."""
    assert rate("0.155") == Decimal("0.155")


def test_percent_of_nothing_is_none_not_zero():
    """У артикула без выручки маржа не нулевая, она не определена."""
    assert percent(money("100"), money("0")) is None


def test_bad_input_says_what_is_wrong():
    with pytest.raises(ValueError, match="денежную величину"):
        money("три рубля")
