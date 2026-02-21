import numpy as np
import pytest

from utils import fixed_assumptions, run_model_flow, assert_structural_invariants


@pytest.mark.parametrize(
    "scenario,assumptions",
    [
        (
            {"name": "negative-cpi", "assets_today": 100.0, "liabilities": [{"type": "one-time", "amount_today": 120.0, "start_date": "2026-01-01", "discount_rate": 0.02, "inflation_rate": -0.02}], "contributions": []},
            fixed_assumptions(inflation=-0.01, equity=0.02, intl_equity=0.02, treasury=0.01),
        ),
        (
            {"name": "large-inflation", "assets_today": 100.0, "liabilities": [{"type": "one-time", "amount_today": 200.0, "start_date": "2026-01-01", "discount_rate": 0.01, "inflation_rate": 0.25}], "contributions": []},
            fixed_assumptions(inflation=0.08, equity=0.09, intl_equity=0.09, treasury=0.03),
        ),
        (
            {"name": "long-horizon", "assets_today": 1000.0, "liabilities": [{"type": "one-time", "amount_today": 500.0, "start_date": "2055-01-01", "discount_rate": 0.03, "inflation_rate": 0.02}], "contributions": []},
            fixed_assumptions(),
        ),
        (
            {"name": "one-month", "assets_today": 100.0, "liabilities": [{"type": "one-time", "amount_today": 90.0, "start_date": "2025-02-01", "discount_rate": 0.0, "inflation_rate": 0.0}], "contributions": []},
            fixed_assumptions(inflation=0.0, equity=0.0, intl_equity=0.0, treasury=0.0),
        ),
        (
            {"name": "no-liability-no-contrib", "assets_today": 100.0, "liabilities": [], "contributions": [], "end_date": "2025-06-01"},
            fixed_assumptions(),
        ),
        (
            {"name": "contrib-after-maturity", "assets_today": 100.0, "liabilities": [{"type": "one-time", "amount_today": 100.0, "start_date": "2025-03-01", "discount_rate": 0.0, "inflation_rate": 0.0}], "contributions": [{"type": "recurring", "amount": 50.0, "frequency": "monthly", "start_date": "2025-04-01", "end_date": "2025-12-01"}]},
            fixed_assumptions(inflation=0.0, equity=0.0, intl_equity=0.0, treasury=0.0),
        ),
    ],
)
def test_pathological_scenarios_remain_finite_and_do_not_crash(scenario, assumptions):
    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")
    assert np.isfinite(result.model_output["surplus_at_maturity"])
    assert_structural_invariants(result.model_output)
