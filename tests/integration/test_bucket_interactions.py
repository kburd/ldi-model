import numpy as np

from utils import fixed_assumptions, run_model_flow, assert_structural_invariants


def test_surplus_peeling_moves_excess_to_surplus_bucket():
    assumptions = fixed_assumptions(inflation=0.0, equity=0.0, intl_equity=0.0, treasury=0.0)
    scenario = {
        "name": "peeling",
        "assets_today": 500.0,
        "liabilities": [{"type": "one-time", "amount_today": 100.0, "start_date": "2025-03-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [],
    }

    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")
    required = result.required_buckets[0]

    assert required.get_surplus_series().iloc[0] > 0
    assert result.surplus_bucket.get_asset_balance_by_period(-1) > 0
    assert_structural_invariants(result.model_output)


def test_required_bucket_depletion_underfunded_case_stays_finite_and_stable():
    assumptions = fixed_assumptions(inflation=0.05, equity=-0.02, intl_equity=-0.02, treasury=-0.01)
    scenario = {
        "name": "depletion",
        "assets_today": 10.0,
        "liabilities": [{"type": "one-time", "amount_today": 1000.0, "start_date": "2027-01-01", "discount_rate": 0.01, "inflation_rate": 0.07}],
        "contributions": [],
    }

    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")

    req_final = result.required_buckets[0].get_asset_balance_by_period(-1)
    assert np.isfinite(req_final)
    assert np.isfinite(result.model_output["surplus_at_maturity"])
    assert result.model_output["surplus_at_maturity"] < 0
    assert_structural_invariants(result.model_output)
