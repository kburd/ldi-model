import pandas as pd
import pytest

from utils import fixed_assumptions, run_model_flow, assert_structural_invariants


def test_monthly_contributions_have_exact_injection_count_and_additivity_at_zero_return():
    assumptions = fixed_assumptions(inflation=0.0, equity=0.0, intl_equity=0.0, treasury=0.0)
    scenario = {
        "name": "monthly-contrib",
        "assets_today": 0.0,
        "liabilities": [{"type": "one-time", "amount_today": 600.0, "start_date": "2025-07-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [{"type": "recurring", "amount": 100.0, "frequency": "monthly", "start_date": "2025-02-01", "end_date": "2025-07-01"}],
    }
    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")

    assert (result.contributions > 0).sum() == 6
    assert result.contributions.sum() == pytest.approx(600.0)
    assert result.model_output["surplus_at_maturity"] == pytest.approx(0.0)
    assert_structural_invariants(result.model_output)


def test_annual_contributions_inject_only_selected_month():
    assumptions = fixed_assumptions(inflation=0.0, equity=0.0, intl_equity=0.0, treasury=0.0)
    scenario = {
        "name": "annual-contrib",
        "assets_today": 0.0,
        "liabilities": [{"type": "one-time", "amount_today": 300.0, "start_date": "2027-01-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [{"type": "recurring", "amount": 100.0, "frequency": "annual", "month": 1, "start_date": "2025-01-01", "end_date": "2027-01-01"}],
    }
    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")

    assert (result.contributions > 0).sum() == 3
    assert set(result.contributions[result.contributions > 0].index.month) == {1}
    assert_structural_invariants(result.model_output)


def test_one_time_contribution_alignment_valid_and_misaligned_errors():
    assumptions = fixed_assumptions(inflation=0.0, equity=0.0, intl_equity=0.0, treasury=0.0)
    good = {
        "name": "good-one-time",
        "assets_today": 0.0,
        "liabilities": [{"type": "one-time", "amount_today": 100.0, "start_date": "2025-04-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [{"type": "one_time", "amount": 100.0, "date": "2025-03-01"}],
    }
    bad = {
        "name": "bad-one-time",
        "assets_today": 0.0,
        "liabilities": [{"type": "one-time", "amount_today": 100.0, "start_date": "2025-04-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [{"type": "one_time", "amount": 100.0, "date": "2025-03-15"}],
    }

    good_result = run_model_flow(good, assumptions, valuation_date="2025-01-01")
    assert good_result.model_output["surplus_at_maturity"] == pytest.approx(0.0)

    with pytest.raises(ValueError, match="not in timeline"):
        run_model_flow(bad, assumptions, valuation_date="2025-01-01")


def test_calibration_helpers_are_bounded_and_handle_impossible_case_gracefully():
    assumptions = fixed_assumptions(inflation=0.0, equity=0.0, intl_equity=0.0, treasury=0.0)

    scenario = {
        "name": "calibration-target",
        "assets_today": 0.0,
        "liabilities": [{"type": "one-time", "amount_today": 120.0, "start_date": "2025-03-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [],
    }

    def solve_monthly(max_iter=30):
        lo, hi = 0.0, 200.0
        for i in range(max_iter):
            mid = (lo + hi) / 2
            test = dict(scenario)
            test["contributions"] = [{"type": "recurring", "amount": mid, "frequency": "monthly", "start_date": "2025-02-01", "end_date": "2025-03-01"}]
            res = run_model_flow(test, assumptions, valuation_date="2025-01-01")
            if abs(res.model_output["surplus_at_maturity"]) <= 1e-6:
                return mid, i + 1
            if res.model_output["surplus_at_maturity"] > 0:
                hi = mid
            else:
                lo = mid
        return mid, max_iter

    monthly, iterations = solve_monthly()
    assert iterations <= 30
    assert monthly == pytest.approx(60.0, abs=1e-3)

    impossible = dict(scenario)
    impossible["contributions"] = [{"type": "recurring", "amount": -1000.0, "frequency": "monthly", "start_date": "2025-02-01", "end_date": "2025-03-01"}]
    res = run_model_flow(impossible, assumptions, valuation_date="2025-01-01")
    assert pd.notna(res.model_output["surplus_at_maturity"])
    assert_structural_invariants(res.model_output)
