import math

import pytest

from financing_analysis.finance import capital_weights, capm, debt_cost, hamada_beta, scenario, wacc


def test_capital_weights_and_single_tax_shield():
    assert capital_weights(80, 20) == (0.8, 0.2)
    assert debt_cost(2, 20, 0.25) == pytest.approx(0.075)
    assert wacc(80, 20, 0.15, 0.10, 0.25) == pytest.approx(0.135)


def test_hamada_capm_independent_example():
    beta = hamada_beta(0.8, 50, 100, 0.2)
    assert beta == pytest.approx(1.12)
    assert capm(0.10, beta, 0.06) == pytest.approx(0.1672)


@pytest.mark.parametrize("equity,debt", [(0, 0), (-1, 2), (1, -2), (math.nan, 2)])
def test_invalid_capital(equity, debt):
    with pytest.raises(ValueError):
        capital_weights(equity, debt)


def test_zero_debt_and_invalid_tax():
    assert debt_cost(0, 0) == 0
    with pytest.raises(ValueError):
        debt_cost(1, 0)
    with pytest.raises(ValueError):
        debt_cost(1, 100, 25)


def test_scenario_boundaries_and_relevering():
    common = dict(
        total_capital=100,
        unlevered_beta=0.8,
        risk_free_rate=0.1,
        market_risk_premium=0.06,
        tax_rate=0.25,
        base_debt_cost=0.05,
        base_debt_share=0.3,
        relative_debt_step=0.015,
        net_profit=10,
    )
    zero = scenario(debt_share=0, **common)
    medium = scenario(debt_share=0.5, **common)
    full = scenario(debt_share=1, **common)
    assert zero["wacc"] == pytest.approx(0.148)
    assert medium["levered_beta"] > zero["levered_beta"]
    assert full["status"] == "undefined_zero_equity"
    assert math.isnan(full["wacc"]) and math.isnan(full["roe"])
    assert medium["debt_k_rub"] + medium["equity_k_rub"] == 100
