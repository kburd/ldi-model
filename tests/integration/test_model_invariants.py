import pandas as pd
import pytest

from utils import fixed_assumptions, run_model_flow, assert_structural_invariants


def test_no_liability_case_all_assets_compound_in_surplus_and_calibration_zero_like():
    assumptions = fixed_assumptions(inflation=0.0, equity=0.06, intl_equity=0.06, treasury=0.06)
    scenario = {"name": "no-liability", "assets_today": 1000.0, "liabilities": [], "contributions": [], "end_date": "2025-04-01"}

    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")

    assert len(result.required_buckets) == 0
    expected = 1000.0 * (1 + (1.06 ** (1 / 12) - 1)) ** 3
    assert result.surplus_bucket.get_asset_balance_by_period(-1) == pytest.approx(expected)
    assert result.model_output["surplus_at_maturity"] == pytest.approx(expected)
    assert_structural_invariants(result.model_output)


def test_zero_return_zero_cpi_world_matches_additive_balance_math():
    assumptions = fixed_assumptions(inflation=0.0, equity=0.0, intl_equity=0.0, treasury=0.0)
    scenario = {
        "name": "zero-world",
        "assets_today": 1000.0,
        "liabilities": [{"type": "one-time", "amount_today": 200.0, "start_date": "2025-04-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [],
    }

    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")
    assert result.model_output["surplus_at_maturity"] == pytest.approx(800.0)
    assert result.liabilities[0].get_pv_remaining_by_period(0) == pytest.approx(200.0)
    assert_structural_invariants(result.model_output)


def test_perfect_funding_with_matching_return_and_discount_near_zero_surplus():
    rate = 0.05
    assumptions = fixed_assumptions(inflation=0.0, equity=rate, intl_equity=rate, treasury=rate)
    maturity = pd.Timestamp("2026-01-01")
    valuation = pd.Timestamp("2025-01-01")
    months = (maturity.year - valuation.year) * 12 + (maturity.month - valuation.month)
    monthly = (1 + rate) ** (1 / 12) - 1
    pv = 1000.0 / ((1 + monthly) ** months)

    scenario = {
        "name": "perfect",
        "assets_today": pv,
        "liabilities": [{"type": "one-time", "amount_today": 1000.0, "start_date": "2026-01-01", "discount_rate": rate, "inflation_rate": 0.0}],
        "contributions": [],
    }

    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")
    assert result.model_output["surplus_at_maturity"] == pytest.approx(0.0, abs=1e-4)
    assert_structural_invariants(result.model_output)
