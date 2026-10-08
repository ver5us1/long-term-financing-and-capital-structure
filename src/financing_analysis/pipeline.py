"""One reproducible entry point: snapshot → calculation → checks → CSV → report."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .excel_engine import WorkbookEngine, summarize_verification
from .extraction import extract_inputs, extract_source_scenarios
from .finance import capital_weights, capm, debt_cost, hamada_beta, ratio, scenario, wacc
from .workbook_io import load_snapshot


def analyze_annual(inputs: pd.DataFrame, rates: pd.DataFrame, assumptions: dict) -> pd.DataFrame:
    rf = rates.groupby("year")["yield_pct"].mean() / 100
    rows = []
    tax = assumptions["historical_tax_rate"]
    premium = assumptions["market_risk_premium"]
    for source in inputs.to_dict("records"):
        row = dict(source)
        row["interest_bearing_debt_k_rub"] = (
            row["long_term_loans_k_rub"] + row["short_term_loans_k_rub"]
        )
        row["adjusted_equity_k_rub"] = (
            row["book_equity_k_rub"]
            + row["dividends_payable_k_rub"]
            + row["deferred_income_k_rub"]
            + row["current_provisions_k_rub"]
        )
        row["workbook_financing_debt_k_rub"] = (
            row["long_term_liabilities_k_rub"] + row["short_term_loans_k_rub"]
        )
        row["workbook_total_borrowed_k_rub"] = (
            row["total_assets_k_rub"] - row["adjusted_equity_k_rub"]
        )
        row["workbook_asset_denominator_k_rub"] = (
            row["total_assets_k_rub"] - row["trade_payables_k_rub"]
        )
        row["risk_free_rate"] = float(rf.loc[row["year"]])
        row["balance_residual_k_rub"] = (
            row["total_assets_k_rub"]
            - row["book_equity_k_rub"]
            - row["long_term_liabilities_k_rub"]
            - row["short_term_liabilities_k_rub"]
        )
        equity, debt = row["book_equity_k_rub"], row["interest_bearing_debt_k_rub"]
        row["canonical_equity_share"], row["canonical_debt_share"] = capital_weights(equity, debt)
        row["levered_beta"] = hamada_beta(row["source_beta"], debt, equity, tax)
        row["cost_of_equity"] = capm(row["risk_free_rate"], row["levered_beta"], premium)
        row["cost_of_debt"] = debt_cost(row["interest_expense_k_rub"], debt)
        row["cost_of_debt_after_tax"] = debt_cost(row["interest_expense_k_rub"], debt, tax)
        row["wacc"] = wacc(equity, debt, row["cost_of_equity"], row["cost_of_debt"], tax)
        row["net_margin"] = ratio(row["net_profit_k_rub"], row["revenue_k_rub"])
        row["roe"] = ratio(row["net_profit_k_rub"], equity)
        row["return_on_assets"] = ratio(row["pretax_profit_k_rub"], row["total_assets_k_rub"])
        row["long_term_capital_debt_share"] = ratio(
            row["long_term_liabilities_k_rub"],
            row["long_term_liabilities_k_rub"] + row["adjusted_equity_k_rub"],
        )
        workbook_beta = hamada_beta(
            row["source_beta"],
            row["workbook_total_borrowed_k_rub"],
            row["adjusted_equity_k_rub"],
            tax,
        )
        row["workbook_cost_of_equity"] = capm(row["risk_free_rate"], workbook_beta, premium)
        row["workbook_cost_of_debt_after_tax"] = debt_cost(
            row["interest_expense_k_rub"], row["workbook_financing_debt_k_rub"], tax
        )
        denominator = row["workbook_asset_denominator_k_rub"]
        we = row["adjusted_equity_k_rub"] / denominator
        wd = row["workbook_financing_debt_k_rub"] / denominator
        row["workbook_equity_share"], row["workbook_debt_share"] = we, wd
        row["workbook_weight_sum"] = we + wd
        row["workbook_wacc"] = (
            we * row["workbook_cost_of_equity"] + wd * row["workbook_cost_of_debt_after_tax"]
        )
        rows.append(row)
    result = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    for metric in (
        "revenue_k_rub",
        "net_profit_k_rub",
        "book_equity_k_rub",
        "interest_bearing_debt_k_rub",
    ):
        result[metric.replace("_k_rub", "_growth")] = result[metric].pct_change(fill_method=None)
    if not np.allclose(result["balance_residual_k_rub"], 0, atol=1e-6, rtol=0):
        raise ValueError("Extracted balance does not reconcile")
    if not np.allclose(result["canonical_equity_share"] + result["canonical_debt_share"], 1):
        raise ValueError("Canonical capital weights do not sum to 1")
    return result


def build_scenarios(annual: pd.DataFrame, assumptions: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = annual.loc[annual["year"] == assumptions["scenario_year"]].iloc[0]
    kwargs = dict(
        total_capital=float(base["book_equity_k_rub"] + base["interest_bearing_debt_k_rub"]),
        unlevered_beta=float(base["source_beta"]),
        risk_free_rate=float(base["risk_free_rate"]),
        market_risk_premium=assumptions["market_risk_premium"],
        tax_rate=assumptions["scenario_tax_rate"],
        base_debt_cost=float(base["cost_of_debt"]),
        base_debt_share=float(base["canonical_debt_share"]),
        relative_debt_step=assumptions["relative_debt_cost_step_per_10pp"],
        net_profit=float(base["net_profit_k_rub"]),
    )
    shares = sorted({i / 10 for i in range(11)} | {kwargs["base_debt_share"]})
    scenarios = pd.DataFrame([scenario(debt_share=share, **kwargs) for share in shares])
    scenarios["is_historical_share"] = np.isclose(
        scenarios["debt_share"], kwargs["base_debt_share"]
    )
    sensitivity = []
    for share in (i / 10 for i in range(10)):
        result = scenario(debt_share=share, **kwargs)
        for spread in np.linspace(0, 0.10, 11):
            sensitivity.append(
                {
                    "debt_share": share,
                    "debt_spread_pp": float(spread * 100),
                    "wacc": wacc(
                        result["equity_k_rub"],
                        result["debt_k_rub"],
                        result["cost_of_equity"],
                        result["cost_of_debt"] + float(spread),
                        assumptions["scenario_tax_rate"],
                    ),
                }
            )
    return scenarios, pd.DataFrame(sensitivity)


def run_analysis(project_root: Path, output_dir: Path | None = None) -> dict:
    project_root = Path(project_root).resolve()
    output_dir = Path(output_dir) if output_dir is not None else project_root / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot = load_snapshot(project_root / "data/source/workbook_snapshot.json")
    assumptions = json.loads(
        (project_root / "data/source/assumptions.json").read_text(encoding="utf-8")
    )
    engine = WorkbookEngine(snapshot)
    engine.recalculate()
    verification = engine.verify()
    summary = summarize_verification(verification)
    if summary["mismatches"]:
        raise ValueError(f"Workbook reconciliation failed: {summary}")
    frames = extract_inputs(engine)
    frames["annual"] = analyze_annual(frames["annual_inputs"], frames["rates"], assumptions)
    frames["source_scenarios"] = extract_source_scenarios(engine)
    frames["scenarios"], frames["sensitivity"] = build_scenarios(frames["annual"], assumptions)
    processed_dir = (
        project_root / "data/processed"
        if output_dir == project_root / "reports"
        else output_dir / "tables"
    )
    processed_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_csv(
            processed_dir / f"{name}.csv", index=False, encoding="utf-8", float_format="%.12g"
        )
    pd.DataFrame(verification).to_csv(
        output_dir / "excel_reconciliation.csv", index=False, encoding="utf-8"
    )
    (output_dir / "verification_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    from .report import write_report
    from .visualization import generate_figures

    figures = generate_figures(frames, output_dir / "figures")
    report_path = write_report(frames, summary, output_dir)
    return {
        "frames": frames,
        "verification": verification,
        "verification_summary": summary,
        "report": report_path,
        "figures": figures,
        "assumptions": assumptions,
    }
