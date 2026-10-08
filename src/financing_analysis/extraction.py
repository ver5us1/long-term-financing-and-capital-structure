"""Extract typed observations with source coordinates from the workbook snapshot."""

from __future__ import annotations

import pandas as pd

BALANCE_SHEET = 'ПАО "ЛУКОЙЛ"'
YEARS = (2022, 2023, 2024)


def _number(engine, sheet: str, cell: str, *, allow_blank: bool = False) -> float:
    value = engine.value(sheet, cell)
    if value is None and allow_blank:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Required numeric input {sheet}!{cell}: {value!r}")
    return float(value)


def extract_inputs(engine) -> dict[str, pd.DataFrame]:
    """Subtotal calculations use raw line items and exclude 'of which' rows."""
    annual, provenance, balance_items, operating_metrics, rates = [], [], [], [], []
    finance_rows = {
        "revenue_k_rub": 4,
        "cost_of_sales_k_rub": 5,
        "net_profit_k_rub": 6,
        "gross_profit_k_rub": 19,
        "income_tax_k_rub": 20,
        "operating_profit_k_rub": 21,
        "pretax_profit_k_rub": 22,
        "interest_expense_k_rub": 23,
    }
    balance_groups = {
        "noncurrent_assets_k_rub": [5, 7, 8, 9, 10, 13, 14, 15, 16],
        "current_assets_k_rub": [19, 20, 21, 24, 25, 26],
        "book_equity_k_rub": list(range(35, 41)),
        "long_term_liabilities_k_rub": list(range(43, 47)),
        "short_term_liabilities_k_rub": [49, 50, 52, 53, 54],
    }
    balance_single = {
        "long_term_loans_k_rub": 43,
        "short_term_loans_k_rub": 49,
        "trade_payables_k_rub": 50,
        "dividends_payable_k_rub": 51,
        "current_provisions_k_rub": 53,
        "deferred_income_k_rub": 52,
        "long_term_receivables_k_rub": 22,
        "inventory_k_rub": 19,
        "vat_k_rub": 20,
        "short_term_receivables_k_rub": 23,
        "other_current_assets_k_rub": 26,
        "short_term_investments_k_rub": 24,
        "cash_k_rub": 25,
        "other_short_term_liabilities_k_rub": 54,
    }
    for year, balance_column, tep_column, beta_column in zip(
        YEARS, "DEF", "CDE", "CDE", strict=True
    ):
        row = {"year": year}
        for field, source_row in finance_rows.items():
            address = f"{tep_column}{source_row}"
            row[field] = _number(engine, "ТЭП", address)
            provenance.append(
                {
                    "year": year,
                    "field": field,
                    "source_sheet": "ТЭП",
                    "source_cells": address,
                    "input_unit": "thousand_rub",
                }
            )
        for field, source_rows in balance_groups.items():
            addresses = [f"{balance_column}{r}" for r in source_rows]
            row[field] = sum(_number(engine, BALANCE_SHEET, c, allow_blank=True) for c in addresses)
            provenance.append(
                {
                    "year": year,
                    "field": field,
                    "source_sheet": BALANCE_SHEET,
                    "source_cells": ",".join(addresses),
                    "input_unit": "thousand_rub",
                }
            )
        for field, source_row in balance_single.items():
            address = f"{balance_column}{source_row}"
            row[field] = _number(engine, BALANCE_SHEET, address, allow_blank=True)
            provenance.append(
                {
                    "year": year,
                    "field": field,
                    "source_sheet": BALANCE_SHEET,
                    "source_cells": address,
                    "input_unit": "thousand_rub",
                }
            )
        row["source_beta"] = _number(engine, "СК", f"{beta_column}7")
        row["total_assets_k_rub"] = row["noncurrent_assets_k_rub"] + row["current_assets_k_rub"]
        annual.append(row)
        for r in range(5, 56):
            label = engine.value(BALANCE_SHEET, f"B{r}")
            if not label or r in (18, 33, 34, 42, 48):
                continue
            address = f"{balance_column}{r}"
            value = engine.value(BALANCE_SHEET, address)
            if value is not None:
                balance_items.append(
                    {
                        "year": year,
                        "line_code": engine.value(BALANCE_SHEET, f"C{r}"),
                        "label": label,
                        "value_k_rub": value,
                        "source_sheet": BALANCE_SHEET,
                        "source_cell": address,
                    }
                )
        for r in range(4, 24):
            address = f"{tep_column}{r}"
            operating_metrics.append(
                {
                    "year": year,
                    "metric": f"tep_{r}",
                    "label": engine.value("ТЭП", f"B{r}"),
                    "value": _number(engine, "ТЭП", address),
                    "source_sheet": "ТЭП",
                    "source_cell": address,
                }
            )
    for year, date_col, value_col, last_row in (
        (2022, "B", "D", 257),
        (2023, "F", "H", 274),
        (2024, "J", "L", 276),
    ):
        for r in range(21, last_row + 1):
            address = f"{value_col}{r}"
            rates.append(
                {
                    "date": str(engine.value("СК", f"{date_col}{r}"))[:10],
                    "year": year,
                    "yield_pct": _number(engine, "СК", address),
                    "source_sheet": "СК",
                    "source_cell": address,
                }
            )
    rate_frame = pd.DataFrame(rates)
    rate_frame["date"] = pd.to_datetime(rate_frame["date"], errors="raise")
    if rate_frame.duplicated(["date"]).any():
        raise ValueError("Duplicate dates in the risk-free rate sample")
    if not (rate_frame["date"].dt.year == rate_frame["year"]).all():
        raise ValueError("Risk-free dates do not match their source year")
    return {
        "annual_inputs": pd.DataFrame(annual),
        "input_provenance": pd.DataFrame(provenance),
        "balance_items": pd.DataFrame(balance_items),
        "operating_metrics": pd.DataFrame(operating_metrics),
        "rates": rate_frame,
    }


def extract_source_scenarios(engine) -> pd.DataFrame:
    """Recomputed source outputs. Error strings become missing values plus a status."""
    rows = []
    for sheet in ("Расчет базовый", "Расчет изменный"):
        for col in "LMNOPQRSTUVW":

            def get(r):
                value = engine.value(sheet, f"{col}{r}")
                return float(value) if isinstance(value, (int, float)) else float("nan")

            equity_share, debt_share = get(20), get(21)
            rows.append(
                {
                    "sheet": sheet,
                    "column": col,
                    "debt_share": debt_share,
                    "equity_share": equity_share,
                    "weight_sum": equity_share + debt_share,
                    "cost_of_equity": get(32) / 100,
                    "cost_of_debt_after_tax": get(26) / 100,
                    "wacc": get(33) / 100,
                    "roe": get(25) / 100,
                    "leverage_effect": get(31) / 100,
                    "interest_expense_k_rub": get(14),
                    "status": "undefined_zero_equity" if equity_share == 0 else "source_reproduced",
                }
            )
    return pd.DataFrame(rows)
