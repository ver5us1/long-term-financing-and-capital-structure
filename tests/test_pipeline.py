from pathlib import Path

import numpy as np
import pytest

from financing_analysis.excel_engine import WorkbookEngine, summarize_verification
from financing_analysis.extraction import extract_inputs
from financing_analysis.pipeline import analyze_annual, build_scenarios, run_analysis
from financing_analysis.workbook_io import load_snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_all_original_formulas_reconcile():
    summary = summarize_verification(WorkbookEngine(load_snapshot()).verify())
    assert summary["total"] == 1104
    assert summary["matched"] == 1096
    assert summary["expected_errors"] == 8
    assert summary["mismatches"] == 0


def test_source_extraction_and_capital_definitions():
    import json

    engine = WorkbookEngine(load_snapshot())
    inputs = extract_inputs(engine)
    assert inputs["rates"].groupby("year").size().to_dict() == {2022: 237, 2023: 254, 2024: 256}
    assumptions = json.loads((ROOT / "data/source/assumptions.json").read_text())
    annual = analyze_annual(inputs["annual_inputs"], inputs["rates"], assumptions)
    last = annual.iloc[-1]
    assert last["book_equity_k_rub"] == 1339944216
    assert last["interest_bearing_debt_k_rub"] == 687296708
    assert last["workbook_financing_debt_k_rub"] == 707912688
    assert last["workbook_weight_sum"] == pytest.approx(1.13120554452446)
    assert np.allclose(annual["balance_residual_k_rub"], 0)
    assert last["workbook_cost_of_equity"] == pytest.approx(engine.value("СК", "E11") / 100)
    assert last["workbook_wacc"] == pytest.approx(engine.value("Расчет базовый", "P33") / 100)
    scenarios, sensitivity = build_scenarios(annual, assumptions)
    assert scenarios.loc[scenarios["debt_share"] == 1, "wacc"].isna().all()
    assert len(sensitivity) == 110


def test_end_to_end_without_original_excel(tmp_path):
    result = run_analysis(ROOT, tmp_path)
    assert result["verification_summary"]["mismatches"] == 0
    assert (tmp_path / "analysis_report.md").is_file()
    assert (tmp_path / "excel_reconciliation.csv").is_file()
    assert len(result["figures"]) == 4
    assert all(p.is_file() for p in result["figures"])
