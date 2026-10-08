"""Presentation-ready figures generated only from calculated analysis tables."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Headless runs and CI must not depend on a writable user home or display server.
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "financing-analysis-mpl"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, PercentFormatter

INK = "#172C3C"
MUTED = "#657783"
TEAL = "#087F8C"
ORANGE = "#D8893E"
PURPLE = "#7360AB"
GRID = "#E2E9EC"
PAPER = "#F7FAFB"

STYLE = {
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.edgecolor": GRID,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.facecolor": "white",
    "figure.facecolor": PAPER,
    "grid.color": GRID,
    "grid.linewidth": 0.7,
    "axes.axisbelow": True,
    "legend.frameon": False,
    "savefig.facecolor": PAPER,
}


def _title(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.text(0.055, 0.955, title, fontsize=19, fontweight="bold", va="top")
    fig.text(0.055, 0.893, subtitle, fontsize=10, color=MUTED, va="top")


def _footnote(fig: plt.Figure, text: str) -> None:
    fig.text(0.055, 0.023, text, fontsize=8, color=MUTED, va="bottom")


def _save(fig: plt.Figure, directory: Path, name: str) -> Path:
    path = directory / name
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return path


def _number(value: float, decimals: int = 0) -> str:
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def _history(annual: pd.DataFrame, directory: Path) -> Path:
    annual = annual.sort_values("year")
    x = np.arange(len(annual))
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    fig.subplots_adjust(left=0.075, right=0.965, top=0.77, bottom=0.20, wspace=0.29)
    _title(
        fig,
        "ЛУКОЙЛ: финансовая база анализа",
        "Исторические данные 2022–2024 · суммы в млрд ₽, исходный масштаб — тыс. ₽",
    )

    ax = axes[0]
    revenue = annual["revenue_k_rub"].to_numpy() / 1_000_000
    profit = annual["net_profit_k_rub"].to_numpy() / 1_000_000
    bars_revenue = ax.bar(x - 0.18, revenue, 0.35, color=TEAL, label="Выручка")
    bars_profit = ax.bar(x + 0.18, profit, 0.35, color=ORANGE, label="Чистая прибыль")
    for bar in [*bars_revenue, *bars_profit]:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(revenue) * 0.016,
            _number(bar.get_height()),
            ha="center",
            fontsize=9,
        )
    ax.set_title("Доходы и прибыль", loc="left", pad=16, fontweight="bold")
    ax.set_ylim(0, max(revenue) * 1.19)
    ax.set_ylabel("Млрд ₽")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _number(value)))
    ax.grid(axis="y")
    ax.legend(loc="upper left", bbox_to_anchor=(-0.01, -0.12), ncol=2, fontsize=9)

    ax = axes[1]
    equity = annual["book_equity_k_rub"].to_numpy() / 1_000_000
    debt = annual["interest_bearing_debt_k_rub"].to_numpy() / 1_000_000
    ax.bar(x, equity, 0.53, color=TEAL, label="Собственный капитал")
    ax.bar(x, debt, 0.53, bottom=equity, color=PURPLE, label="Процентный долг")
    for i, (equity_value, debt_value) in enumerate(zip(equity, debt)):
        ax.text(
            i,
            equity_value / 2,
            _number(equity_value),
            color="white",
            ha="center",
            fontweight="bold",
        )
        ax.text(
            i,
            equity_value + debt_value / 2,
            _number(debt_value),
            color="white",
            ha="center",
            fontweight="bold",
        )
        share = annual.iloc[i]["canonical_debt_share"]
        ax.text(
            i,
            equity_value + debt_value + max(equity + debt) * 0.025,
            f"Долг {_number(share * 100, 1)}%",
            ha="center",
            fontsize=9,
        )
    ax.set_title("Капитал по согласованному периметру", loc="left", pad=16, fontweight="bold")
    ax.set_ylim(0, max(equity + debt) * 1.21)
    ax.set_ylabel("Млрд ₽")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: _number(value)))
    ax.grid(axis="y")
    ax.legend(loc="upper left", bbox_to_anchor=(-0.01, -0.12), ncol=1, fontsize=9)
    for ax in axes:
        ax.set_xticks(x, annual["year"].astype(int).astype(str))
    _footnote(
        fig,
        "Процентный долг включает долгосрочные и краткосрочные займы; кредиторская задолженность не включена.",
    )
    return _save(fig, directory, "01_financial_history.png")


def _risk_free(rates: pd.DataFrame, directory: Path) -> Path:
    rates = rates.copy()
    rates["date"] = pd.to_datetime(rates["date"])
    rates = rates.sort_values("date")
    fig, ax = plt.subplots(figsize=(12, 5.7))
    fig.subplots_adjust(left=0.075, right=0.97, top=0.77, bottom=0.16)
    _title(
        fig,
        "Ставка в модели меняется вместе с рынком",
        f"Дневные наблюдения из Excel · {len(rates):,} строк".replace(",", " ")
        + " · годовое среднее используется в CAPM",
    )
    colours = [TEAL, PURPLE, ORANGE]
    for i, (year, group) in enumerate(rates.groupby("year", sort=True)):
        colour = colours[i % len(colours)]
        average = group["yield_pct"].mean()
        ax.plot(
            group["date"],
            group["yield_pct"],
            color=colour,
            linewidth=1.45,
            label=f"{int(year)} · средняя {_number(average, 2)}%",
        )
        ax.hlines(
            average,
            group["date"].min(),
            group["date"].max(),
            color=colour,
            linewidth=1.3,
            linestyle="--",
            alpha=0.65,
        )
    ax.set_ylabel("Доходность, % годовых")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
    ax.grid(axis="y")
    ax.legend(loc="upper left", fontsize=10)
    ax.margins(x=0.015, y=0.14)
    _footnote(
        fig,
        "Источник — предоставленная таблица; первичная публикация и сопоставимость срока инструментов отдельно не проверялись.",
    )
    return _save(fig, directory, "02_risk_free_rates.png")


def _scenarios(frames: dict[str, pd.DataFrame], directory: Path) -> Path:
    source = frames["source_scenarios"]
    scenarios = frames["scenarios"].sort_values("debt_share")
    model = scenarios.loc[scenarios["debt_share"].lt(1) & scenarios["wacc"].notna()]
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.2))
    fig.subplots_adjust(left=0.075, right=0.97, top=0.77, bottom=0.26, wspace=0.26)
    _title(
        fig,
        "Реконструкция Excel и согласованная модель",
        "Одинаковая доля долга — разные предпосылки и формулы · сравнение помогает обнаружить ошибки исходника",
    )

    for i, (sheet, group) in enumerate(source.groupby("sheet", sort=False)):
        valid = group.loc[
            np.isclose(group["weight_sum"], 1) & group["debt_share"].lt(1)
        ].sort_values("debt_share")
        colour = [ORANGE, PURPLE][i % 2]
        label = "Excel: базовый" if "баз" in str(sheet).lower() else "Excel: изменённый"
        for ax, metric in zip(axes, ["wacc", "cost_of_equity"]):
            clean = valid.loc[valid[metric].notna()]
            ax.plot(
                clean["debt_share"],
                clean[metric],
                color=colour,
                linestyle="--",
                linewidth=1.8,
                marker="o",
                markersize=4,
                label=label,
            )
    for ax, metric in zip(axes, ["wacc", "cost_of_equity"]):
        ax.plot(
            model["debt_share"],
            model[metric],
            color=TEAL,
            linewidth=2.7,
            marker="o",
            markersize=4.5,
            label="Согласованная модель",
        )
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.set_xticks(np.arange(0, 1, 0.1))
        ax.tick_params(axis="x", labelsize=9)
        ax.set_xlabel("Доля долга в капитале")
        ax.grid(axis="y")
        ax.margins(y=0.15)
    axes[0].set_title("Средневзвешенная стоимость капитала", loc="left", fontweight="bold", pad=15)
    axes[0].set_ylabel("WACC, % годовых")
    axes[1].set_title("Стоимость собственного капитала", loc="left", fontweight="bold", pad=15)
    axes[1].set_ylabel("CAPM, % годовых")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower left", bbox_to_anchor=(0.057, 0.085), ncol=3, fontsize=9)
    _footnote(
        fig,
        "Из линий Excel исключены несогласованные веса и 100% долга. Минимум на сетке не доказывает оптимальную структуру капитала.",
    )
    return _save(fig, directory, "03_scenario_comparison.png")


def _sensitivity(sensitivity: pd.DataFrame, directory: Path) -> Path:
    grid = (
        sensitivity.pivot(index="debt_spread_pp", columns="debt_share", values="wacc")
        .sort_index()
        .sort_index(axis=1)
    )
    x = grid.columns.to_numpy(dtype=float)
    y = grid.index.to_numpy(dtype=float)
    values = grid.to_numpy(dtype=float) * 100
    fig, ax = plt.subplots(figsize=(12, 6.5))
    fig.subplots_adjust(left=0.08, right=0.91, top=0.77, bottom=0.17)
    _title(
        fig,
        "Результат зависит от стоимости долга",
        "Анализ чувствительности · WACC при изменении доли долга и надбавки к его годовой стоимости",
    )
    im = ax.imshow(values, origin="lower", aspect="auto", cmap="YlGnBu", interpolation="nearest")
    ax.set_xticks(np.arange(len(x)), [f"{value:.0%}" for value in x])
    step = max(1, len(y) // 10)
    indices = np.arange(0, len(y), step)
    if indices[-1] != len(y) - 1:
        indices = np.append(indices, len(y) - 1)
    ax.set_yticks(indices, [_number(y[i], 1) for i in indices])
    ax.set_xlabel("Доля долга в капитале")
    ax.set_ylabel("Надбавка к стоимости долга до налога, п. п.")
    ax.grid(False)
    if len(y) <= 15 and len(x) <= 12:
        normalised = im.norm(values)
        for row in range(len(y)):
            for col in range(len(x)):
                ax.text(
                    col,
                    row,
                    _number(values[row, col], 1),
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if normalised[row, col] > 0.52 else INK,
                )
    colourbar = fig.colorbar(im, ax=ax, fraction=0.047, pad=0.035)
    colourbar.set_label("WACC, % годовых", labelpad=12)
    _footnote(
        fig,
        "Детерминированные сценарии с фиксированными прочими предпосылками; риск дефолта и издержки финансовых затруднений не оценены.",
    )
    return _save(fig, directory, "04_wacc_sensitivity.png")


def generate_figures(frames: dict[str, pd.DataFrame], output_dir: Path) -> list[Path]:
    """Save four figures and return their paths, independent of working directory."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with plt.rc_context(STYLE):
        return [
            _history(frames["annual"], output_dir),
            _risk_free(frames["rates"], output_dir),
            _scenarios(frames, output_dir),
            _sensitivity(frames["sensitivity"], output_dir),
        ]
