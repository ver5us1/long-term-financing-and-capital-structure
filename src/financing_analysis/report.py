"""Build a readable Markdown report from the pipeline's computed outputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _num(value: float, decimals: int = 2) -> str:
    if pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def _pct(value: float, decimals: int = 2) -> str:
    return f"{_num(value * 100, decimals)}%" if pd.notna(value) else "—"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_report(
    frames: dict[str, pd.DataFrame], verification_summary: dict, output_dir: Path
) -> Path:
    """Write an evidence-based report; figures are relative to reports/figures."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    annual = frames["annual"].sort_values("year")
    first, last = annual.iloc[0], annual.iloc[-1]
    rates = frames["rates"]
    source = frames["source_scenarios"]
    model = frames["scenarios"]
    regular = model.loc[model["debt_share"].lt(1) & model["wacc"].notna()]
    minimum = regular.loc[regular["wacc"].idxmin()]
    invalid_weights = source.loc[~np.isclose(source["weight_sum"], 1)]

    historical_rows = [
        [
            str(int(row.year)),
            _num(row.revenue_k_rub / 1_000_000),
            _num(row.net_profit_k_rub / 1_000_000),
            _pct(row.net_margin),
            _num(row.book_equity_k_rub / 1_000_000),
            _num(row.interest_bearing_debt_k_rub / 1_000_000),
            _pct(row.canonical_debt_share),
        ]
        for row in annual.itertuples()
    ]
    cost_rows = [
        [
            str(int(row.year)),
            _pct(row.risk_free_rate),
            _pct(row.cost_of_equity),
            _pct(row.cost_of_debt_after_tax),
            _pct(row.wacc),
            _pct(row.workbook_wacc),
            _num((row.wacc - row.workbook_wacc) * 100),
        ]
        for row in annual.itertuples()
    ]
    source_min_rows = []
    for sheet, group in source.groupby("sheet", sort=False):
        valid = group.loc[
            np.isclose(group["weight_sum"], 1) & group["debt_share"].lt(1) & group["wacc"].notna()
        ]
        if not valid.empty:
            best = valid.loc[valid["wacc"].idxmin()]
            source_min_rows.append(
                [str(sheet), _pct(best.debt_share, 0), _pct(best.wacc), _pct(best.roe)]
            )
    source_min_rows.append(
        ["Согласованная модель", _pct(minimum.debt_share, 0), _pct(minimum.wacc), _pct(minimum.roe)]
    )

    rate_rows = [
        [
            str(int(year)),
            str(len(group)),
            _num(group["yield_pct"].mean()),
            _num(group["yield_pct"].min()),
            _num(group["yield_pct"].max()),
        ]
        for year, group in rates.groupby("year", sort=True)
    ]
    weight_rows = [
        [
            str(row.sheet),
            str(row.column),
            _pct(row.equity_share),
            _pct(row.debt_share),
            _num(row.weight_sum, 4),
        ]
        for row in invalid_weights.itertuples()
    ]

    total = verification_summary.get("total", verification_summary.get("formula_count", "—"))
    matched = verification_summary.get("matched", verification_summary.get("matches", "—"))
    expected_errors = verification_summary.get("expected_errors", "—")
    mismatches = verification_summary.get("mismatches", "—")
    verification_ok = isinstance(mismatches, (int, np.integer)) and mismatches == 0
    verification_verdict = (
        "Численных расхождений не обнаружено."
        if verification_ok
        else "Итог проверки нужно читать вместе с таблицей verification.csv."
    )
    revenue_growth = last["revenue_k_rub"] / first["revenue_k_rub"] - 1
    profit_growth = last["net_profit_k_rub"] / first["net_profit_k_rub"] - 1
    margin_change_pp = (last["net_margin"] - first["net_margin"]) * 100
    historical_wacc_change = (last["wacc"] - first["wacc"]) * 100
    sensitivity = frames["sensitivity"]
    high_debt = sensitivity.loc[
        np.isclose(sensitivity["debt_share"], regular["debt_share"].max())
    ].sort_values("debt_spread_pp")
    sensitivity_sentence = ""
    if len(high_debt) > 1:
        low_spread, high_spread = high_debt.iloc[0], high_debt.iloc[-1]
        sensitivity_sentence = (
            f"При доле долга {_pct(low_spread.debt_share, 0)} увеличение надбавки с "
            f"{_num(low_spread.debt_spread_pp, 1)} до {_num(high_spread.debt_spread_pp, 1)} п. п. "
            f"изменяет WACC с {_pct(low_spread.wacc)} до {_pct(high_spread.wacc)}. "
        )

    body = f"""# Источники финансирования ЛУКОЙЛ: воспроизводимый анализ

Этот отчёт автоматически создан из таблиц Python. Он отделяет точное воспроизведение
формул Excel от аналитической модели с согласованным определением капитала.
Исходный материал — предоставленный учебный проект за 2022–2024 годы.
Первичные внешние публикации отдельно не сверялись; выводы относятся к данным и
предпосылкам проекта, а не ко всей группе компаний или текущей рыночной ситуации.

## Что показывают данные

- За {int(first.year)}–{int(last.year)} выручка изменилась на {_pct(revenue_growth)}, чистая прибыль — на {_pct(profit_growth)}.
- Чистая рентабельность продаж изменилась с {_pct(first.net_margin)} до {_pct(last.net_margin)} ({_num(margin_change_pp)} п. п.).
- Доля процентного долга в выбранном периметре капитала изменилась с {_pct(first.canonical_debt_share)} до {_pct(last.canonical_debt_share)}.
- WACC в согласованной исторической модели изменился с {_pct(first.wacc)} до {_pct(last.wacc)} ({_num(historical_wacc_change)} п. п.).

Всего три годовых наблюдения описывают динамику, но не позволяют доказать причинные
связи, обучить убедительную прогнозную модель или оценить устойчивую долгосрочную тенденцию.

## 1. Исторические показатели

Денежные значения приведены в **млрд ₽**. Исходные числовые значения хранятся в
**тыс. ₽**; перевод в млрд ₽ выполняется делением на 1 000 000.

{_table(["Год", "Выручка", "Чистая прибыль", "Чистая маржа", "Собственный капитал", "Процентный долг", "Доля долга"], historical_rows)}

![Историческая финансовая база](figures/01_financial_history.png)

В согласованном историческом расчёте капитал = балансовый собственный капитал +
процентный долг. Процентный долг включает долгосрочные и краткосрочные займы.
Кредиторская задолженность и прочие непроцентные обязательства отдельно не становятся
стоимостью заёмного финансирования. Балансовые величины не заменяют рыночную оценку капитала.

## 2. Стоимость финансирования

{_table(["Год", "Безрисковая ставка", "CAPM", "Долг после налога", "WACC: согласованно", "WACC: Excel", "Разница, п. п."], cost_rows)}

Различия между двумя WACC отражают определения долга, собственного капитала и
весов в исходных формулах. Они не означают ошибку выполнения Python: соответствие
исходным формулам проверяется в отдельном слое реконструкции.

Годовая безрисковая ставка — простое среднее доступных дневных наблюдений, без
взвешивания по времени. Доступность строк по годам различается.

{_table(["Год", "Наблюдений", "Средняя, %", "Минимум, %", "Максимум, %"], rate_rows)}

![Дневные ставки и годовые средние](figures/02_risk_free_rates.png)

Историческая ставка налога — 20%; в сценарной модели — 25%, как в исходном
сценарном блоке. Стоимость долга после налога используется в WACC один раз:
повторное применение налогового щита не требуется.

## 3. Сценарии структуры капитала

Согласованная модель перебирает долю долга от 0% до 90% с постоянной суммой
капитала. CAPM использует фиксированную премию за рыночный риск, а бета пересчитывается
по формуле Хамады. Бета из исходного материала принята как сценарная входная
предпосылка: её интерпретация как бездолговой беты не подтверждена оценкой по рядам
доходностей. Поэтому результаты показывают действие формул при заданных предпосылках.

**100% долга исключено**: собственный капитал равен нулю, отношение D/E и ROE
не определены. NaN в этой строке — явный маркер недопустимой комбинации.

{_table(["Модель", "Доля долга при минимуме на сетке", "WACC", "ROE"], source_min_rows)}

![Сравнение сценарных моделей](figures/03_scenario_comparison.png)

Минимальный рассчитанный WACC в согласованной модели составляет {_pct(minimum.wacc)}
при доле долга {_pct(minimum.debt_share, 0)}. Это **минимум на заданной сетке**, а не
рекомендация по финансированию. Модель не оценивает вероятность дефолта, ковенанты,
доступность кредита, кредитный рейтинг, рыночную стоимость капитала и издержки финансовых
затруднений. При фиксированной низкой стоимости долга край сетки может механически
оказываться лучшим. Рост ROE при малом собственном капитале также может быть эффектом знаменателя.

## 4. Чувствительность к цене долга

{sensitivity_sentence}Сетка позволяет оценить зависимость результата от входной
ставки, сохраняя остальные предпосылки. Надбавка прибавляется к стоимости долга
**до налога**, затем применяется налоговый щит.

![Чувствительность WACC](figures/04_wacc_sensitivity.png)

Эта проверка не является стресс-тестом платёжеспособности: для него нужны прогноз
денежных потоков, график погашения и сценарии операционной деятельности.

## 5. Аудит исходной книги

- Проверено формул: **{total}**; совпадений численных результатов: **{matched}**.
- Ожидаемых ошибок исходника: **{expected_errors}**; неожиданных расхождений: **{mismatches}**.
- {verification_verdict} Проверка сравнивает результаты формул с сохранёнными значениями Excel; она подтверждает воспроизведение, но не корректность исходной методики.
- В сценарном базовом столбце встречаются веса капитала, сумма которых не равна 1. Такие точки не соединяются с корректными сценариями на графике.
- В исходных сценариях стоимость собственного капитала может снижаться с ростом долга. При положительной премии за риск и фиксированной бездолговой бете согласованная формула Хамады даёт противоположное направление.
- В сценарии 100% долга в Excel есть ошибки деления на ноль. Они сохранены как ожидаемые ошибки и не превращаются в численные результаты.
- Единицы в подписях учебного материала неоднородны. В Python масштаб каждого денежного поля указан в его имени и словаре данных.

{_table(["Лист", "Столбец", "Вес капитала", "Вес долга", "Сумма весов"], weight_rows) if weight_rows else "В переданных сценарных таблицах несогласованных весов не обнаружено."}

Подробные формулы, источник данных и ограничения описаны в `../docs/`.
Таблицы результата и проверки сохраняются рядом с этим отчётом в CSV.

## Как воспроизвести

Из корня проекта запустите команду анализа из README или выполните
`../notebooks/01_financing_analysis.ipynb` от начала до конца. Расчёты, графики и этот
отчёт создаются общим pipeline; ручных числовых массивов в notebook нет.
"""
    path = output_dir / "analysis_report.md"
    path.write_text(body, encoding="utf-8")
    return path
