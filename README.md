<div align="center">

# Выбор источников долгосрочного финансирования

### Воспроизводимый Python-анализ структуры капитала ПАО «ЛУКОЙЛ»

<p>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Pandas-data%20analysis-150458?logo=pandas&logoColor=white" alt="Pandas">
  <img src="https://img.shields.io/badge/Tests-11%20passed-2EA44F" alt="Tests passed">
  <img src="https://img.shields.io/badge/Excel%20formulas-1104-217346?logo=microsoftexcel&logoColor=white" alt="Excel formulas">
</p>

<p>
  <a href="reports/analysis_report.md">Итоговый отчёт</a> ·
  <a href="notebooks/01_financing_analysis.ipynb">Jupyter Notebook</a> ·
  <a href="docs/methodology.md">Методология</a> ·
  <a href="docs/source-audit.md">Аудит источника</a>
</p>

</div>

## О проекте

Проект переводит расчёты учебной работы из Excel в воспроизводимый Python pipeline. На данных ПАО «ЛУКОЙЛ» за 2022–2024 годы рассчитываются финансовые показатели, стоимость собственного и заёмного капитала, CAPM, модель Хамады, WACC и сценарии структуры капитала.

Главная особенность проекта — разделение двух задач. Первый слой точно воспроизводит исходные Excel-формулы и проверяет их значения. Второй слой использует единое определение капитала и показывает финансовый результат без скрытого смешения единиц и видов долга.

## Что внутри

| Блок | Результат |
|---|---|
| Перенос Excel → Python | Безопасный парсер арифметики, ссылок, диапазонов, `SUM` и `AVERAGE` |
| Контроль качества | Сверка всех 1 104 формул с сохранёнными результатами Excel |
| Финансовый анализ | Выручка, прибыль, маржа, ROE, структура капитала и динамика долга |
| Стоимость капитала | CAPM, Hamada beta, стоимость долга после налога и WACC |
| Сценарии | Доля долга от 0% до 90% и чувствительность WACC к цене долга |
| Визуализация | Четыре графика и автоматически сформированный аналитический отчёт |

## Результаты

| Показатель | 2022 | 2023 | 2024 |
|---|---:|---:|---:|
| Выручка, млрд ₽ | 2 874,04 | 2 753,48 | 3 046,94 |
| Чистая прибыль, млрд ₽ | 790,12 | 655,29 | 732,52 |
| Собственный капитал, млрд ₽ | 1 265,17 | 1 308,07 | 1 339,94 |
| Процентный долг, млрд ₽ | 649,58 | 671,71 | 687,30 |
| Доля долга в капитале | 33,93% | 33,93% | 33,90% |
| WACC согласованной модели | 11,20% | 11,86% | 15,04% |

## Визуальный отчёт

<table>
  <tr>
    <td width="50%"><img src="reports/figures/01_financial_history.png" alt="Финансовая база анализа"></td>
    <td width="50%"><img src="reports/figures/02_risk_free_rates.png" alt="Безрисковая ставка"></td>
  </tr>
  <tr>
    <td width="50%"><img src="reports/figures/03_scenario_comparison.png" alt="Сравнение сценарных моделей"></td>
    <td width="50%"><img src="reports/figures/04_wacc_sensitivity.png" alt="Чувствительность WACC"></td>
  </tr>
</table>

## Быстрый запуск

```bash
git clone https://github.com/ver5us1/long-term-financing-and-capital-structure.git
cd long-term-financing-and-capital-structure

python -m venv .venv
source .venv/bin/activate       # macOS / Linux

python -m pip install -e ".[dev]"
financing-analysis run
```

После запуска обновляются:

- `data/processed/` — таблицы анализа в CSV;
- `reports/analysis_report.md` — итоговый отчёт;
- `reports/figures/` — графики;
- `reports/excel_reconciliation.csv` — построчная сверка формул;
- `reports/verification_summary.json` — итог проверки.

Проверка только Excel-слоя:

```bash
financing-analysis verify
```

Ожидаемый результат: **1 096 совпадений, 8 ожидаемых ошибок деления на ноль, 0 неожиданных расхождений**.

## Запуск notebook

Открой `notebooks/01_financing_analysis.ipynb` в Jupyter или VS Code и выполни ячейки по порядку. Notebook использует тот же pipeline, что и команда `financing-analysis run`, поэтому результаты не дублируются вручную.

## Структура проекта

```text
.
├── data/
│   ├── source/              # обезличенный снимок Excel и допущения
│   └── processed/           # готовые таблицы анализа
├── docs/                    # методология и аудит исходных расчётов
├── notebooks/               # пошаговый анализ
├── reports/                 # отчёт, сверка и графики
├── src/financing_analysis/
│   ├── excel_engine.py      # безопасный пересчёт Excel-подмножества
│   ├── workbook_io.py       # импорт исходной книги в JSON-снимок
│   ├── extraction.py        # извлечение входов с координатами источника
│   ├── finance.py           # финансовые формулы
│   ├── pipeline.py          # единая точка запуска анализа
│   └── visualization.py     # построение графиков
├── tests/                   # тесты расчётов и сверки
└── pyproject.toml
```

## Методология

В согласованной модели используются:

```text
wD = D / (E + D)
wE = E / (E + D)
kd_after_tax = (interest / D) × (1 − tax)
beta_levered = beta_unlevered × (1 + (1 − tax) × D / E)
ke = risk_free + beta_levered × market_risk_premium
WACC = wE × ke + wD × kd_after_tax
```

Денежные значения исходника хранятся в тысячах рублей. В отчёте они показываются в млрд ₽. Веса капитала используют бухгалтерский собственный капитал и процентные займы, чтобы единообразно рассчитать `D / E`, стоимость долга и WACC.

## Ограничения

- В источнике только три годовых наблюдения, поэтому проект демонстрирует финансовую аналитику и воспроизводимость, а не прогнозную ML-модель.
- Исходная beta не имеет подтверждённого статуса `levered` или `unlevered`. В согласованной модели она используется как `unlevered beta` только как учебное допущение.
- Минимум WACC на сценарной сетке не является рекомендацией по долговой нагрузке. Модель не включает кредитные ковенанты, вероятность дефолта и стоимость финансовых затруднений.
- В документации сохранены расхождения исходного Excel, чтобы результат можно было проверить и воспроизвести.

## Проверки качества

```bash
ruff check .
ruff format --check .
pytest -q
```

Проект также запускает эти проверки через GitHub Actions для Python 3.11 и 3.12.

## Источник данных

В репозитории хранится обезличенный JSON-снимок исходной книги с формулами и сохранёнными значениями. Титульные страницы DOCX/PPTX, авторские метаданные и исходные файлы в репозиторий не включены.

## Лицензия

Учебный проект для портфолио и демонстрации воспроизводимого финансового анализа.
