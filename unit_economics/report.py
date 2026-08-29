"""Сборка отчёта: Markdown в консоль и один самодостаточный HTML-файл."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape
from pathlib import Path

from unit_economics.analysis import AbcRow, abc, break_even, totals
from unit_economics.charts import drr_comparison, waterfall
from unit_economics.money import ZERO, money, percent
from unit_economics.pnl import SkuPnL

CHART_ROWS = 12


def _rub(value: Decimal) -> str:
    return f"{int(round(float(value))):,}".replace(",", " ")


def _pct(value: Decimal | None) -> str:
    return "—" if value is None else f"{value}".replace(".", ",") + "%"


def waterfall_steps(summary: dict[str, Decimal]) -> list[tuple[str, Decimal, str]]:
    return [
        ("Выручка", summary["revenue"], "start"),
        ("Закупка", summary["cogs"], "cost"),
        ("Комиссия", summary["commission"], "cost"),
        ("Эквайринг", summary["acquiring"], "cost"),
        ("Логистика", summary["logistics"], "cost"),
        ("Возвраты", summary["logistics_on_returns"], "cost"),
        ("Хранение", summary["storage"], "cost"),
        ("Налог", summary["tax"], "cost"),
        ("Маржа", summary["contribution"], "total"),
        ("Реклама", summary["ad_spend"], "cost"),
        ("Прибыль", summary["net_profit"], "total"),
    ]


def to_markdown(rows: list[SkuPnL], fixed_costs: Decimal = ZERO) -> str:
    """Короткий отчёт для консоли и README."""
    summary = totals(rows)
    even = break_even(rows, fixed_costs)
    lines = [
        "# Юнит-экономика за период",
        "",
        f"Артикулов: {len(rows)}. Продано единиц: {int(summary['units_sold'])}.",
        "",
        "| Показатель | Сумма | Доля выручки |",
        "|---|---:|---:|",
    ]
    for label, key in (
        ("Выручка", "revenue"), ("Закупка", "cogs"), ("Комиссия", "commission"),
        ("Эквайринг", "acquiring"), ("Логистика", "logistics"),
        ("Логистика возвратов", "logistics_on_returns"), ("Хранение", "storage"),
        ("Налог", "tax"), ("Маржа до рекламы", "contribution"),
        ("Реклама", "ad_spend"), ("Чистая прибыль", "net_profit"),
    ):
        share = percent(summary[key], summary["revenue"])
        lines.append(f"| {label} | {_rub(summary[key])} ₽ | {_pct(share)} |")

    lines += ["", "## Что делать со ставками", "",
              "| Артикул | Выручка | ДРР | Безубыточный ДРР | Запас | Решение |",
              "|---|---:|---:|---:|---:|---|"]
    for row in sorted(rows, key=lambda r: r.revenue, reverse=True):
        lines.append(
            f"| {row.sku.article} | {_rub(row.revenue)} ₽ | {_pct(row.drr_pct)} "
            f"| {_pct(row.breakeven_drr_pct)} | {_rub(row.headroom())} ₽ | {row.decision()} |"
        )

    if even.units_needed is not None:
        lines += ["", "## Точка безубыточности", "",
                  f"Маржа на единицу: {_rub(even.unit_contribution)} ₽. "
                  f"Постоянные расходы: {_rub(even.fixed_costs)} ₽. "
                  f"Нужно продать {even.units_needed} единиц, продано {even.units_sold}."]
    return "\n".join(lines) + "\n"


def _table(headers: list[str], body: list[list[str]], numeric_from: int = 1) -> str:
    head = "".join(
        f'<th{" class=n" if index >= numeric_from else ""}>{escape(text)}</th>'
        for index, text in enumerate(headers)
    )
    rows = []
    for line in body:
        cells = "".join(
            f'<td{" class=n" if index >= numeric_from else ""}>{cell}</td>'
            for index, cell in enumerate(line)
        )
        rows.append(f"<tr>{cells}</tr>")
    body_html = "".join(rows)
    return (
        '<div class="scroll"><table>'
        f"<thead><tr>{head}</tr></thead><tbody>{body_html}</tbody></table></div>"
    )


def _verdict_chip(text: str) -> str:
    tone = {
        "поднимать ставку": "good",
        "держать": "neutral",
        "снижать ставку": "warn",
        "выключать рекламу": "bad",
        "нет продаж": "muted",
    }.get(text, "muted")
    return f'<span class="chip {tone}">{escape(text)}</span>'


# Стили вынесены из f-строки: внутри неё каждую фигурную скобку CSS
# пришлось бы удваивать, и правило превращается в шум.
_STYLES = """:root {
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --secondary:#52514e;
  --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  --series-1:#2a78d6; --series-2:#eb6834; --good:#0ca30c; --critical:#d03b3b;
  --warning:#fab219; --good-ink:#006300;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --secondary:#c3c2b7;
    --muted:#898781; --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
    --series-1:#3987e5; --series-2:#d95926; --good:#0ca30c; --critical:#d03b3b;
    --good-ink:#0ca30c;
  }
}
:root[data-theme="dark"] {
  --page:#0d0d0d; --surface:#1a1a19; --ink:#ffffff; --secondary:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
  --series-1:#3987e5; --series-2:#d95926; --good:#0ca30c; --critical:#d03b3b;
  --good-ink:#0ca30c;
}
* { box-sizing:border-box }
body { margin:0; background:var(--page); color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif; font-size:15px; line-height:1.6 }
.wrap { max-width:1000px; margin:0 auto; padding:40px 24px 80px }
h1 { font-size:30px; margin:0 0 6px; letter-spacing:-.01em }
h2 { font-size:20px; margin:0 0 14px; padding-bottom:8px; border-bottom:1px solid var(--border) }
h3 { font-size:16px; margin:0 0 6px }
p { margin:0 0 14px; max-width:74ch }
.sub { color:var(--secondary); margin-bottom:28px }
section { margin-bottom:44px }
.tiles { display:grid; gap:14px; margin-bottom:40px;
  grid-template-columns:repeat(auto-fit,minmax(190px,1fr)) }
.tile { background:var(--surface); border:1px solid var(--border);
  border-radius:6px; padding:16px 18px }
.tile-label { margin:0; font-size:12px; color:var(--muted);
  text-transform:uppercase; letter-spacing:.07em }
.tile-value { margin:6px 0 2px; font-size:25px; font-weight:600; letter-spacing:-.01em }
.tile-note { margin:0; font-size:12.5px; color:var(--secondary) }
.card { background:var(--surface); border:1px solid var(--border);
  border-radius:6px; padding:20px }
.scroll { overflow-x:auto; border:1px solid var(--border);
  border-radius:6px; background:var(--surface) }
table { border-collapse:collapse; width:100%; min-width:640px; font-size:13.5px }
th, td { padding:9px 13px; text-align:left; white-space:nowrap;
  border-bottom:1px solid var(--grid) }
th { font-size:11px; text-transform:uppercase; letter-spacing:.07em;
  color:var(--muted); font-weight:500 }
td.n, th.n { text-align:right; font-variant-numeric:tabular-nums }
tbody tr:last-child td { border-bottom:0 }
.neg { color:var(--critical); font-weight:600 }
.chip { font-size:12px; padding:3px 9px; border-radius:3px;
  border:1px solid var(--border); white-space:nowrap }
.chip.good { color:var(--good-ink) } .chip.bad { color:var(--critical) }
.chip.warn { color:var(--secondary) } .chip.neutral, .chip.muted { color:var(--secondary) }
.callout { background:var(--surface); border-left:3px solid var(--critical);
  border-radius:0 6px 6px 0; padding:16px 20px; margin-bottom:24px }
.callout p { margin:0; color:var(--secondary); font-size:14px }
footer { border-top:1px solid var(--border); padding-top:16px;
  color:var(--muted); font-size:12.5px }
"""


def to_html(rows: list[SkuPnL], fixed_costs: Decimal = ZERO, title: str = "Юнит-экономика") -> str:
    summary = totals(rows)
    even = break_even(rows, fixed_costs)
    by_revenue = sorted(rows, key=lambda r: r.revenue, reverse=True)
    abc_rows: list[AbcRow] = abc(rows, by="net_profit")
    losing = [row for row in rows if row.net_profit < 0]

    chart_rows = [
        (row.sku.article, row.drr_pct, row.breakeven_drr_pct, row.decision())
        for row in by_revenue[:CHART_ROWS]
    ]

    tiles = [
        ("Выручка", f"{_rub(summary['revenue'])} ₽", "за вычетом возвратов"),
        ("Маржа до рекламы", f"{_rub(summary['contribution'])} ₽",
         f"{_pct(percent(summary['contribution'], summary['revenue']))} выручки"),
        ("Реклама", f"{_rub(summary['ad_spend'])} ₽",
         f"ДРР {_pct(percent(summary['ad_spend'], summary['revenue']))}"),
        ("Чистая прибыль", f"{_rub(summary['net_profit'])} ₽",
         f"{_pct(percent(summary['net_profit'], summary['revenue']))} выручки"),
    ]
    tiles_html = "".join(
        f'<div class="tile"><p class="tile-label">{escape(label)}</p>'
        f'<p class="tile-value">{escape(value)}</p>'
        f'<p class="tile-note">{escape(note)}</p></div>'
        for label, value, note in tiles
    )

    pnl_table = _table(
        ["Артикул", "Категория", "Продано", "Выручка", "Закупка", "Площадка",
         "Реклама", "Прибыль", "Маржа", "Возвраты"],
        [[
            escape(row.sku.article), escape(row.sku.category), str(row.units_sold),
            f"{_rub(row.revenue)} ₽", f"{_rub(row.cogs)} ₽", f"{_rub(row.platform_costs)} ₽",
            f"{_rub(row.ad_spend)} ₽",
            f'<span class="{"neg" if row.net_profit < 0 else ""}">{_rub(row.net_profit)} ₽</span>',
            _pct(row.net_margin_pct), _pct(row.return_rate),
        ] for row in by_revenue],
        numeric_from=2,
    )

    decisions_table = _table(
        ["Артикул", "Выручка", "ДРР факт", "Безубыточный", "Запас на рекламу", "Решение"],
        [[
            escape(row.sku.article), f"{_rub(row.revenue)} ₽", _pct(row.drr_pct),
            _pct(row.breakeven_drr_pct), f"{_rub(row.headroom())} ₽", _verdict_chip(row.decision()),
        ] for row in by_revenue],
    )

    abc_table = _table(
        ["Место", "Артикул", "Прибыль", "Накопленная доля", "Класс"],
        [[
            str(item.position), escape(item.pnl.sku.article), f"{_rub(item.pnl.net_profit)} ₽",
            _pct(item.running_share_pct), item.abc_class,
        ] for item in abc_rows],
    )

    losing_block = ""
    if losing:
        lost = money(sum((row.net_profit for row in losing), start=Decimal(0)))
        names = ", ".join(row.sku.article for row in losing)
        losing_block = (
            f'<div class="callout"><h3>Убыточных артикулов: {len(losing)}</h3>'
            f"<p>Суммарно они забирают {_rub(abs(lost))} ₽ прибыли. Это {escape(names)}. "
            f"У каждого фактический ДРР выше безубыточного предела: реклама тратит "
            f"больше, чем артикул зарабатывает до неё.</p></div>"
        )

    break_even_block = ""
    if even.units_needed is not None and fixed_costs > 0:
        state = "закрыты" if even.covered else "не закрыты"
        break_even_block = (
            f'<section><h2>Точка безубыточности</h2>'
            f"<p>Маржа на единицу по портфелю {_rub(even.unit_contribution)} ₽. "
            f"Чтобы закрыть постоянные расходы в {_rub(even.fixed_costs)} ₽, нужно продать "
            f"<b>{even.units_needed}</b> единиц. "
            f"Продано {even.units_sold}, расходы {state}.</p></section>"
        )

    return f"""<title>{escape(title)}</title>
<style>{_STYLES}</style>
<div class="wrap">
<h1>{escape(title)}</h1>
<p class="sub">Отчёт собран {date.today().strftime('%d.%m.%Y')} по {len(rows)} артикулам.
Возвраты вычтены из выручки, но их логистика учтена в расходах.</p>

<div class="tiles">{tiles_html}</div>

{losing_block}

<section>
  <h2>Куда уходит рубль выручки</h2>
  <p>Столбцы идут в том порядке, в котором деньги реально уходят. Реклама стоит
  последней не для красоты: всё, что выше неё, задаёт потолок рекламного бюджета.</p>
  <div class="card">{waterfall(waterfall_steps(summary))}</div>
</section>

<section>
  <h2>Ставки: где есть запас, а где реклама съедает прибыль</h2>
  <p>Безубыточный ДРР считается от маржи конкретного артикула, а не от планового
  ориентира по магазину. Плановые 10% для товара с маржой 8% означают работу
  в минус, и отчёт по магазину этого не покажет: в среднем всё будет прилично.</p>
  <div class="card">{drr_comparison(chart_rows)}</div>
</section>

<section>
  <h2>Решение по каждому артикулу</h2>
  {decisions_table}
</section>

<section>
  <h2>Экономика по артикулам</h2>
  {pnl_table}
</section>

<section>
  <h2>ABC по прибыли</h2>
  <p>Разбиение идёт по прибыли, а не по выручке. Списки «80% выручки» и
  «80% прибыли» совпадают редко, и разница между ними обычно и есть самое
  интересное в ассортименте.</p>
  {abc_table}
</section>

{break_even_block}

<footer>Собрано движком unit-economics-engine. Все денежные величины считаются
в Decimal, копейки не теряются.</footer>
</div>
"""


def write_html(rows: list[SkuPnL], destination: str | Path,
               fixed_costs: Decimal = ZERO, title: str = "Юнит-экономика") -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(to_html(rows, fixed_costs, title), encoding="utf-8")
    return destination
