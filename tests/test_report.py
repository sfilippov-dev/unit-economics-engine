"""Отчёт: один файл, без внешних загрузок, с настоящими числами."""

import re

import pytest

from unit_economics.money import money
from unit_economics.pnl import build_pnl
from unit_economics.report import to_html, to_markdown


@pytest.fixture
def rows(sku, order, ad):
    return build_pnl(
        {1: sku(1), 2: sku(2)},
        [order(sku_id=1) for _ in range(30)] + [order(sku_id=2, returned=True) for _ in range(4)],
        [ad(sku_id=1, spend="9000")],
    )


def test_html_has_no_external_requests(rows):
    """Отчёт открывают в письме и без интернета: ни одной внешней загрузки."""
    html = to_html(rows)
    assert not re.search(r'(src|href)="https?://', html)
    assert "<script" not in html


def test_html_defines_both_themes(rows):
    html = to_html(rows)
    assert "prefers-color-scheme: dark" in html
    assert '[data-theme="dark"]' in html


def test_html_contains_the_actual_numbers(rows):
    html = to_html(rows)
    assert "Чистая прибыль" in html and "Безубыточный" in html
    assert "ART-0001" in html


def test_markdown_totals_line_up_with_the_rows(rows):
    text = to_markdown(rows, money("10000"))
    assert "Точка безубыточности" in text
    assert text.count("| ART-") == len(rows)


def test_report_survives_an_empty_period(sku):
    rows = build_pnl({1: sku(1)}, [], [])
    html = to_html(rows)
    assert "ART-0001" in html
