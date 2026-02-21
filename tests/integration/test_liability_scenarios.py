import pytest

from utils import fixed_assumptions, run_model_flow, assert_structural_invariants


def test_one_time_liability_creates_single_bucket_and_matches_pv():
    assumptions = fixed_assumptions(inflation=0.02, treasury=0.05)
    scenario = {
        "name": "single-liability",
        "assets_today": 100.0,
        "liabilities": [{"type": "one-time", "amount_today": 1000.0, "start_date": "2025-04-01", "discount_rate": 0.05, "inflation_rate": 0.02}],
    }
    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")

    assert len(result.required_buckets) == 1
    assert result.liabilities[0].maturity_date == result.required_buckets[0].get_liability().maturity_date
    analytical = 1000.0 / (((1 + 0.05) ** (1 / 12) / ((1 + 0.02) ** (1 / 12))) ** 3)
    assert result.liabilities[0].get_pv_remaining_by_period(0) == pytest.approx(analytical)
    assert_structural_invariants(result.model_output)


def test_recurring_liability_expands_annually_and_discounts_each_bucket():
    assumptions = fixed_assumptions(inflation=0.0, treasury=0.04)
    scenario = {
        "name": "recurring",
        "assets_today": 1000.0,
        "liabilities": [{"type": "recurring", "amount_today": 500.0, "start_date": "2026-01-01", "duration_years": 3, "discount_rate": 0.04, "inflation_rate": 0.0}],
    }
    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")

    assert len(result.required_buckets) == 3
    maturities = [l.maturity_date for l in result.liabilities]
    assert (maturities[1] - maturities[0]).days in (365, 366)
    assert (maturities[2] - maturities[1]).days in (365, 366)
    assert result.liabilities[0].get_pv_remaining_by_period(0) > result.liabilities[1].get_pv_remaining_by_period(0) > result.liabilities[2].get_pv_remaining_by_period(0)
    assert_structural_invariants(result.model_output)


def test_extreme_liability_inflation_deteriorates_funding_and_goes_negative():
    assumptions = fixed_assumptions(inflation=0.01, equity=0.02, intl_equity=0.02, treasury=0.02)
    scenario = {
        "name": "extreme-inflation",
        "assets_today": 200.0,
        "liabilities": [{"type": "one-time", "amount_today": 5000.0, "start_date": "2027-01-01", "discount_rate": 0.01, "inflation_rate": 0.20}],
    }
    result = run_model_flow(scenario, assumptions, valuation_date="2025-01-01")

    assert result.model_output["funding_ratio"] < 1.0
    assert result.model_output["surplus_at_maturity"] < 0
    assert_structural_invariants(result.model_output)
