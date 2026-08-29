"""Командный интерфейс."""

from __future__ import annotations

from pathlib import Path

import click

from unit_economics.analysis import abc, totals
from unit_economics.demo import generate
from unit_economics.loader import DataError, load_ads, load_orders, load_skus
from unit_economics.models import Tariffs
from unit_economics.money import money, percent
from unit_economics.pnl import build_pnl
from unit_economics.report import to_markdown, write_html


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="unit-economics-engine", prog_name="unit-econ")
def cli() -> None:
    """Юнит-экономика маркетплейса: P&L по артикулам и решения по ставкам."""


data_options = [
    click.option("--data", type=click.Path(exists=True, file_okay=False, path_type=Path),
                 default=Path("data/demo"), show_default=True,
                 help="Папка с skus.csv, orders.csv и ads.csv."),
    click.option("--fixed-costs", default="0", show_default=True,
                 help="Постоянные расходы за период для точки безубыточности."),
    click.option("--tax-rate", default=None, help="Ставка налога, доля. По умолчанию 0.06."),
    click.option("--acquiring-rate", default=None, help="Эквайринг, доля. По умолчанию 0.015."),
]


def with_data_options(function):
    for option in reversed(data_options):
        function = option(function)
    return function


def _load(data: Path, tax_rate, acquiring_rate):
    defaults = Tariffs()
    tariffs = Tariffs(
        tax_rate=money(tax_rate) if tax_rate else defaults.tax_rate,
        acquiring_rate=money(acquiring_rate) if acquiring_rate else defaults.acquiring_rate,
    )
    skus = load_skus(data / "skus.csv")
    orders = load_orders(data / "orders.csv")
    ads = load_ads(data / "ads.csv")
    return build_pnl(skus, orders, ads, tariffs)


@cli.command("report")
@with_data_options
@click.option("--html", type=click.Path(path_type=Path), default=None,
              help="Куда положить HTML-отчёт.")
@click.option("--title", default="Юнит-экономика", show_default=True)
def report_command(data: Path, fixed_costs: str, tax_rate, acquiring_rate,
                   html: Path | None, title: str) -> None:
    """Посчитать экономику и вывести отчёт."""
    try:
        rows = _load(data, tax_rate, acquiring_rate)
    except DataError as error:
        raise click.ClickException(str(error)) from error
    click.echo(to_markdown(rows, money(fixed_costs)))
    if html:
        path = write_html(rows, html, money(fixed_costs), title)
        click.echo(f"HTML-отчёт: {path}")


@cli.command("check")
@with_data_options
def check_command(data: Path, fixed_costs: str, tax_rate, acquiring_rate) -> None:
    """Показать только то, что требует решения: убыточные и перегретые артикулы."""
    try:
        rows = _load(data, tax_rate, acquiring_rate)
    except DataError as error:
        raise click.ClickException(str(error)) from error

    problems = [row for row in rows if row.net_profit < 0 or "выключать" in row.decision()]
    if not problems:
        click.echo("Убыточных артикулов нет, рекламные ставки в пределах безубыточного ДРР.")
        return
    click.echo(f"Требуют решения: {len(problems)} из {len(rows)}\n")
    for row in sorted(problems, key=lambda r: r.net_profit):
        click.echo(
            f"  {row.sku.article}  {row.sku.category:<15} "
            f"прибыль {int(row.net_profit):>10} ₽   "
            f"ДРР {row.drr_pct}% при пределе {row.breakeven_drr_pct}%   {row.decision()}"
        )
    lost = sum(row.net_profit for row in problems if row.net_profit < 0)
    if lost:
        click.echo(f"\nСуммарный убыток по ним: {int(abs(lost))} ₽")


@cli.command("abc")
@with_data_options
@click.option("--by", type=click.Choice(["revenue", "contribution", "net_profit"]),
              default="net_profit", show_default=True)
def abc_command(data: Path, fixed_costs: str, tax_rate, acquiring_rate, by: str) -> None:
    """ABC-анализ ассортимента."""
    rows = _load(data, tax_rate, acquiring_rate)
    for item in abc(rows, by=by):
        click.echo(
            f"{item.position:>3}. {item.pnl.sku.article}  {item.abc_class}  "
            f"{int(getattr(item.pnl, by)):>12} ₽   накоплено {item.running_share_pct}%"
        )


@cli.command("summary")
@with_data_options
def summary_command(data: Path, fixed_costs: str, tax_rate, acquiring_rate) -> None:
    """Свод по всему портфелю одной таблицей."""
    rows = _load(data, tax_rate, acquiring_rate)
    summary = totals(rows)
    revenue = summary["revenue"]
    for label, key in (
        ("Выручка", "revenue"), ("Закупка", "cogs"), ("Комиссия", "commission"),
        ("Эквайринг", "acquiring"), ("Логистика", "logistics"),
        ("Логистика возвратов", "logistics_on_returns"), ("Хранение", "storage"),
        ("Налог", "tax"), ("Маржа до рекламы", "contribution"),
        ("Реклама", "ad_spend"), ("Чистая прибыль", "net_profit"),
    ):
        share = percent(summary[key], revenue)
        click.echo(f"{label:<22} {int(summary[key]):>14} ₽   {share}%")


@cli.command("demo")
@click.option("--out", type=click.Path(path_type=Path), default=Path("data/demo"),
              show_default=True)
@click.option("--skus", type=int, default=24, show_default=True)
def demo_command(out: Path, skus: int) -> None:
    """Сгенерировать демонстрационные данные."""
    counts = generate(out, sku_count=skus)
    click.echo(f"Записано в {out}: {counts['skus']} артикулов, "
               f"{counts['orders']} заказов, {counts['ads']} строк рекламы")


if __name__ == "__main__":
    cli()
