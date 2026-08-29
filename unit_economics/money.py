"""Деньги.

Одно правило на весь проект: денежная величина это Decimal, а не float.
Причина не в педантизме. Копейки на float не представимы точно, ошибка
накапливается на каждой операции, и сумма за год перестаёт сходиться с
выгрузкой площадки. Расхождение в тысячу рублей на пятимиллионном обороте
выглядит мелочью ровно до того момента, когда его приходится искать.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTS = Decimal("0.01")
PERCENT = Decimal("0.1")
ZERO = Decimal("0")


def money(value: object) -> Decimal:
    """Привести значение к рублям и копейкам.

    Из строки, а не из float: Decimal(0.1) даёт 0.1000000000000000055511151231,
    Decimal("0.1") даёт ровно одну десятую. Поэтому float сначала печатается
    строкой, и только потом становится Decimal.
    """
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, float):
        result = Decimal(repr(value))
    else:
        try:
            result = Decimal(str(value).replace(",", ".").replace(" ", ""))
        except InvalidOperation as error:
            raise ValueError(f"{value!r} не похоже на денежную величину") from error
    return result.quantize(CENTS, rounding=ROUND_HALF_UP)


def rate(value: object) -> Decimal:
    """Доля: комиссия, налог, эквайринг. Хранится как есть, без округления.

    Округлять ставку до копеек нельзя: 15,5% это 0.155, а квантование до
    двух знаков превратило бы её в 0.16 и завысило комиссию на треть.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(repr(value))
    return Decimal(str(value).replace(",", ".").replace(" ", ""))


def percent(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    """Доля в процентах с одним знаком. None, если делить не на что.

    Возвращается именно None, а не ноль: у артикула без продаж маржа не
    равна нулю, она не определена, и в отчёте это разные вещи.
    """
    if denominator == 0:
        return None
    return (numerator / denominator * 100).quantize(PERCENT, rounding=ROUND_HALF_UP)
