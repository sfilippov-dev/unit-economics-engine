"""Загрузчик обязан объяснять, что именно не так во входном файле."""

import pytest

from unit_economics.demo import generate
from unit_economics.loader import DataError, load_ads, load_orders, load_skus
from unit_economics.pnl import build_pnl

HEADER = "sku_id,article,title,category,cost_price,volume_l,commission_rate\n"
GOOD = HEADER + "1,ART-0001,Товар,Тесты,1000,1.0,0.15\n"


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_says_which_one(tmp_path):
    with pytest.raises(DataError, match="не найден"):
        load_skus(tmp_path / "нет.csv")


def test_missing_column_is_named(tmp_path):
    path = write(tmp_path, "skus.csv", "sku_id,article\n1,ART-0001\n")
    with pytest.raises(DataError, match="commission_rate"):
        load_skus(path)


def test_broken_row_reports_its_line_number(tmp_path):
    path = write(tmp_path, "skus.csv", GOOD + "2,ART-0002,Товар,Тесты,не число,1.0,0.15\n")
    with pytest.raises(DataError, match="строка 3"):
        load_skus(path)


def test_negative_cost_price_is_rejected_with_the_article(tmp_path):
    path = write(tmp_path, "skus.csv", HEADER + "1,ART-0001,Товар,Тесты,-500,1.0,0.15\n")
    with pytest.raises(DataError, match="ART-0001"):
        load_skus(path)


def test_duplicate_sku_is_rejected(tmp_path):
    path = write(tmp_path, "skus.csv", GOOD + "1,ART-0001,Товар,Тесты,1200,1.0,0.15\n")
    with pytest.raises(DataError, match="дважды"):
        load_skus(path)


def test_empty_file_is_rejected(tmp_path):
    with pytest.raises(DataError, match="нет ни одной строки"):
        load_skus(write(tmp_path, "skus.csv", HEADER))


def test_byte_order_mark_from_excel_does_not_break_the_header(tmp_path):
    """Excel сохраняет CSV с меткой BOM, и без utf-8-sig первая колонка
    приезжает с невидимым префиксом, а файл выглядит как испорченный."""
    path = tmp_path / "skus.csv"
    path.write_text(GOOD, encoding="utf-8-sig")
    assert 1 in load_skus(path)


@pytest.mark.parametrize("value,expected", [("true", True), ("1", True), ("да", True),
                                            ("false", False), ("0", False), ("", False)])
def test_returned_flag_accepts_what_people_actually_write(tmp_path, value, expected):
    path = write(
        tmp_path, "orders.csv",
        "date,sku_id,marketplace,units,price,is_returned\n"
        f"2026-03-01,1,WB,1,3000,{value}\n",
    )
    assert load_orders(path)[0].is_returned is expected


def test_demo_data_is_reproducible_and_loads(tmp_path):
    generate(tmp_path / "a")
    generate(tmp_path / "b")
    first = (tmp_path / "a" / "orders.csv").read_bytes()
    second = (tmp_path / "b" / "orders.csv").read_bytes()
    assert first == second

    rows = build_pnl(
        load_skus(tmp_path / "a" / "skus.csv"),
        load_orders(tmp_path / "a" / "orders.csv"),
        load_ads(tmp_path / "a" / "ads.csv"),
    )
    assert len(rows) == 24
    assert any(row.net_profit < 0 for row in rows), "в наборе должны быть убыточные артикулы"
