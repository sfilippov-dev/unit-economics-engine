"""Графики для отчёта: SVG собирается своим кодом, без внешних библиотек.

Причина не в самодостаточности ради принципа. Отчёт открывают в письме, в
мессенджере и на компьютере без интернета, поэтому он обязан быть одним
файлом без единой внешней загрузки. Двух графиков для этого хватает, и
тянуть ради них библиотеку на полмегабайта незачем.

Палитра и правила разметки взяты из проверенного набора: категориальные
цвета в фиксированном порядке, тонкие штрихи, подпись у каждого столбца,
приглушённая сетка. Цветом ничего не кодируется в одиночку: рядом с любым
цветным элементом стоит подпись.
"""

from __future__ import annotations

from decimal import Decimal
from html import escape

SERIES_1 = "var(--series-1)"
SERIES_2 = "var(--series-2)"
POSITIVE = "var(--good)"
NEGATIVE = "var(--series-2)"


def _fmt_money(value: Decimal) -> str:
    """Рубли без копеек и с неразрывными пробелами: в подписи копейки шумят."""
    return f"{int(round(float(value))):,}".replace(",", " ")


def _fmt_pct(value: Decimal | None) -> str:
    return "нет данных" if value is None else f"{value}%".replace(".", ",")


def waterfall(steps: list[tuple[str, Decimal, str]], width: int = 940, height: int = 380) -> str:
    """Каскад: из чего складывается прибыль.

    steps: список (подпись, величина, вид), где вид это start, cost или total.
    Столбцы вида total рисуются от нуля, остальные продолжают предыдущий.
    """
    left, right, top, bottom = 12, 12, 34, 62
    plot_w = width - left - right
    plot_h = height - top - bottom
    column = plot_w / len(steps)
    bar_w = column * 0.62

    running = Decimal(0)
    geometry = []
    for label, value, kind in steps:
        if kind == "total":
            start, end = Decimal(0), value
            running = value
        elif kind == "start":
            start, end = Decimal(0), value
            running = value
        else:
            start, end = running, running - value
            running = end
        geometry.append((label, value, kind, start, end))

    peak = max(max(abs(s), abs(e)) for _, _, _, s, e in geometry) or Decimal(1)
    scale = plot_h / float(peak)

    def y_of(value: Decimal) -> float:
        return top + plot_h - float(value) * scale

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" width="100%" '
        f'aria-label="Каскад: из чего складывается прибыль" '
        f'style="max-width:{width}px;font-family:inherit">'
    ]
    for fraction in (0, 0.25, 0.5, 0.75, 1):
        y = top + plot_h * fraction
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" '
            f'stroke="var(--grid)" stroke-width="1"/>'
        )

    for index, (label, value, kind, start, end) in enumerate(geometry):
        x = left + column * index + (column - bar_w) / 2
        y_top, y_bottom = min(y_of(start), y_of(end)), max(y_of(start), y_of(end))
        bar_h = max(y_bottom - y_top, 2)
        colour = POSITIVE if kind in {"start", "total"} else NEGATIVE
        if kind == "total" and value < 0:
            colour = "var(--critical)"
        parts.append(
            f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'rx="4" fill="{colour}"/>'
        )
        if index < len(geometry) - 1 and kind != "total":
            connector_y = y_of(end)
            parts.append(
                f'<line x1="{x + bar_w:.1f}" y1="{connector_y:.1f}" '
                f'x2="{left + column * (index + 1) + (column - bar_w) / 2:.1f}" '
                f'y2="{connector_y:.1f}" stroke="var(--axis)" stroke-width="1" '
                f'stroke-dasharray="2 3"/>'
            )
        sign = "" if kind in {"start", "total"} else "−"
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{y_top - 7:.1f}" text-anchor="middle" '
            f'font-size="11" font-weight="600" fill="var(--ink)" '
            f'style="font-variant-numeric:tabular-nums">{sign}{_fmt_money(abs(value))}</text>'
        )
        for line_index, word in enumerate(label.split(" ")):
            parts.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h + 18 + line_index * 13:.1f}" '
                f'text-anchor="middle" font-size="11" fill="var(--muted)">{escape(word)}</text>'
            )
    parts.append(
        f'<line x1="{left}" y1="{top + plot_h:.1f}" x2="{width - right}" '
        f'y2="{top + plot_h:.1f}" stroke="var(--axis)" stroke-width="1"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def drr_comparison(rows: list[tuple[str, Decimal | None, Decimal | None, str]],
                   width: int = 940) -> str:
    """Факт ДРР против безубыточного, по строке на артикул.

    Две величины одной природы и одной шкалы, поэтому это один график с
    одной осью, а не два наложенных друг на друга с разными шкалами.
    """
    row_h, gap, left, top = 34, 8, 132, 30
    height = top + len(rows) * (row_h + gap) + 34
    plot_w = width - left - 96
    peak = max(
        [float(value) for _, fact, be, _ in rows for value in (fact, be) if value is not None]
        or [1.0]
    )
    scale = plot_w / (peak * 1.15)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" width="100%" '
        f'aria-label="Фактический ДРР против безубыточного по артикулам" '
        f'style="max-width:{width}px;font-family:inherit">'
    ]
    parts.append(
        f'<rect x="{left}" y="6" width="10" height="10" rx="2" fill="{SERIES_1}"/>'
        f'<text x="{left + 16}" y="15" font-size="11" fill="var(--secondary)">факт</text>'
        f'<rect x="{left + 62}" y="6" width="10" height="10" rx="2" fill="{SERIES_2}"/>'
        f'<text x="{left + 78}" y="15" font-size="11" fill="var(--secondary)">'
        f'безубыточный предел</text>'
    )
    for index, (article, fact, breakeven, verdict) in enumerate(rows):
        y = top + index * (row_h + gap)
        parts.append(
            f'<text x="{left - 10}" y="{y + 13}" text-anchor="end" font-size="11.5" '
            f'fill="var(--ink)">{escape(article)}</text>'
            f'<text x="{left - 10}" y="{y + 27}" text-anchor="end" font-size="10" '
            f'fill="var(--muted)">{escape(verdict)}</text>'
        )
        for offset, (value, colour) in enumerate(((fact, SERIES_1), (breakeven, SERIES_2))):
            if value is None:
                continue
            bar_w = max(float(value) * scale, 2)
            bar_y = y + offset * 15
            parts.append(
                f'<rect x="{left}" y="{bar_y}" width="{bar_w:.1f}" height="13" rx="4" '
                f'fill="{colour}"/>'
                f'<text x="{left + bar_w + 7:.1f}" y="{bar_y + 10.5}" font-size="10.5" '
                f'fill="var(--secondary)" style="font-variant-numeric:tabular-nums">'
                f'{_fmt_pct(value)}</text>'
            )
    parts.append("</svg>")
    return "".join(parts)
