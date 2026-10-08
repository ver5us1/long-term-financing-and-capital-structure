"""Domain calculations. All rates are fractions; all monetary inputs use the same unit.

The workbook's literal formulas live in excel_engine.py. These functions implement
a separately documented model with consistent capital definitions and units.
"""

from __future__ import annotations

import math


def _finite(**values: float) -> None:
    for name, value in values.items():
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")


def validate_rate(rate: float, name: str = "tax_rate") -> None:
    _finite(**{name: rate})
    if not 0 <= rate <= 1:
        raise ValueError(f"{name} must be between 0 and 1")


def capital_weights(equity: float, debt: float) -> tuple[float, float]:
    """Return E/(E+D), D/(E+D) for non-negative capital amounts."""
    _finite(equity=equity, debt=debt)
    if equity < 0 or debt < 0 or equity + debt <= 0:
        raise ValueError("Capital must be non-negative with a positive total")
    total = equity + debt
    return equity / total, debt / total


def debt_cost(interest_expense: float, debt: float, tax_rate: float = 0.0) -> float:
    """Interest/debt with a tax shield. Zero debt with zero interest costs zero."""
    _finite(interest_expense=interest_expense, debt=debt)
    validate_rate(tax_rate)
    if interest_expense < 0 or debt < 0:
        raise ValueError("Interest and debt must be non-negative")
    if debt == 0:
        if interest_expense != 0:
            raise ValueError("Interest expense cannot be positive when debt is zero")
        return 0.0
    return interest_expense / debt * (1 - tax_rate)


def hamada_beta(unlevered_beta: float, debt: float, equity: float, tax_rate: float) -> float:
    """βL = βU × [1 + (1 − T) × D/E]. Requires positive equity."""
    _finite(unlevered_beta=unlevered_beta, debt=debt, equity=equity)
    validate_rate(tax_rate)
    if unlevered_beta < 0 or debt < 0 or equity <= 0:
        raise ValueError("Hamada requires non-negative beta/debt and positive equity")
    return unlevered_beta * (1 + (1 - tax_rate) * debt / equity)


def capm(risk_free_rate: float, beta: float, market_risk_premium: float) -> float:
    """Ke = Rf + β × ERP. ERP is a premium, not total market return."""
    _finite(risk_free_rate=risk_free_rate, beta=beta, market_risk_premium=market_risk_premium)
    if beta < 0 or market_risk_premium < 0:
        raise ValueError("Beta and market risk premium must be non-negative")
    return risk_free_rate + beta * market_risk_premium


def wacc(
    equity: float, debt: float, cost_of_equity: float, cost_of_debt: float, tax_rate: float
) -> float:
    """E/V × Ke + D/V × Kd × (1 − T); Kd is BEFORE tax."""
    _finite(cost_of_equity=cost_of_equity, cost_of_debt=cost_of_debt)
    validate_rate(tax_rate)
    if cost_of_equity < 0 or cost_of_debt < 0:
        raise ValueError("Capital costs must be non-negative")
    equity_weight, debt_weight = capital_weights(equity, debt)
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)


def ratio(numerator: float, denominator: float) -> float:
    """Preserve an undefined denominator as NaN, never as a healthy zero."""
    _finite(numerator=numerator, denominator=denominator)
    return numerator / denominator if denominator != 0 else math.nan


def growth_rate(previous: float, current: float) -> float:
    return ratio(current - previous, previous)


def scenario(
    *,
    debt_share: float,
    total_capital: float,
    unlevered_beta: float,
    risk_free_rate: float,
    market_risk_premium: float,
    tax_rate: float,
    base_debt_cost: float,
    base_debt_share: float,
    relative_debt_step: float,
    net_profit: float,
) -> dict[str, float | str]:
    """Sensitivity at fixed capital/profit; not a forecast or an optimal debt policy.

    Debt cost rises geometrically by relative_debt_step per 10 percentage points
    of leverage. This is a transparent educational assumption, not an estimate.
    At 100% debt, Hamada and ROE are undefined, so the scenario is excluded.
    """
    validate_rate(debt_share, "debt_share")
    validate_rate(base_debt_share, "base_debt_share")
    validate_rate(tax_rate)
    _finite(
        total_capital=total_capital,
        relative_debt_step=relative_debt_step,
        base_debt_cost=base_debt_cost,
        net_profit=net_profit,
    )
    if total_capital <= 0 or relative_debt_step < 0 or base_debt_cost < 0:
        raise ValueError("Invalid scenario capital or debt-cost assumptions")
    equity_share = 1 - debt_share
    debt = total_capital * debt_share
    equity = total_capital * equity_share
    kd = base_debt_cost * (1 + relative_debt_step) ** ((debt_share - base_debt_share) / 0.1)
    result = {
        "debt_share": debt_share,
        "equity_share": equity_share,
        "debt_k_rub": debt,
        "equity_k_rub": equity,
        "cost_of_debt": kd,
        "cost_of_debt_after_tax": kd * (1 - tax_rate),
        "interest_expense_k_rub": debt * kd,
        "debt_equity_ratio": ratio(debt, equity),
        "roe": ratio(net_profit, equity),
    }
    if equity == 0:
        return {
            **result,
            "levered_beta": math.nan,
            "cost_of_equity": math.nan,
            "wacc": math.nan,
            "status": "undefined_zero_equity",
        }
    beta = hamada_beta(unlevered_beta, debt, equity, tax_rate)
    ke = capm(risk_free_rate, beta, market_risk_premium)
    return {
        **result,
        "levered_beta": beta,
        "cost_of_equity": ke,
        "wacc": wacc(equity, debt, ke, kd, tax_rate),
        "status": "ok",
    }
