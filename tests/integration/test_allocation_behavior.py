import pandas as pd
import pytest

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions
from utils import fixed_assumptions, run_model_flow, assert_structural_invariants


def test_static_assumptions_produce_constant_series():
    assumptions = fixed_assumptions(inflation=0.03, equity=0.08, intl_equity=0.07, treasury=0.04)
    dates = pd.date_range("2025-01-01", periods=6, freq="MS")

    assert len({assumptions.inflation_cpi(d) for d in dates}) == 1
    assert len({assumptions.asset_returns(d)["us_equity_total_market"] for d in dates}) == 1


def test_dynamic_schedule_override_honors_boundary_dates():
    assumptions = Assumptions.from_dict(
        {
            "inflation_cpi": {"default": 0.02, "schedule": [{"start": "2025-03-01", "end": "2025-04-01", "value": 0.10}]},
            "assets": {"us_equity_total_market": {"default": 0.08, "schedule": [{"start": "2025-04-01", "end": "2025-04-01", "value": 0.01}]}, "intl_equity_developed": 0.07, "us_nominal_treasury_long": 0.04},
        }
    )

    assert assumptions.inflation_cpi(pd.Timestamp("2025-02-01")) == pytest.approx(0.02)
    assert assumptions.inflation_cpi(pd.Timestamp("2025-03-01")) == pytest.approx(0.10)
    assert assumptions.inflation_cpi(pd.Timestamp("2025-05-01")) == pytest.approx(0.02)
    assert assumptions.asset_returns(pd.Timestamp("2025-04-01"))["us_equity_total_market"] == pytest.approx(0.01)


def test_glide_path_responds_to_time_to_need_and_funding_ratio():
    long_horizon = GlidePath.get_allocation({"horizon_months": 360, "funding_ratio": 0.8})
    short_horizon = GlidePath.get_allocation({"horizon_months": 12, "funding_ratio": 0.8})
    underfunded = GlidePath.get_allocation({"horizon_months": 120, "funding_ratio": 0.7})
    overfunded = GlidePath.get_allocation({"horizon_months": 120, "funding_ratio": 1.2})

    assert short_horizon["us_nominal_treasury_long"] > long_horizon["us_nominal_treasury_long"]
    assert overfunded["us_nominal_treasury_long"] > underfunded["us_nominal_treasury_long"]

    for allocation in [long_horizon, short_horizon, underfunded, overfunded]:
        assert sum(allocation.values()) == pytest.approx(1.0)
        assert all(v >= 0 for v in allocation.values())


def test_pipeline_level_allocation_invariants_hold_in_under_and_over_funded_cases():
    assumptions = fixed_assumptions()
    base = {
        "name": "alloc-pipeline",
        "liabilities": [{"type": "one-time", "amount_today": 1000.0, "start_date": "2026-01-01", "discount_rate": 0.04, "inflation_rate": 0.02}],
        "contributions": [],
    }

    under = run_model_flow({**base, "assets_today": 500.0}, assumptions, valuation_date="2025-01-01")
    over = run_model_flow({**base, "assets_today": 2000.0}, assumptions, valuation_date="2025-01-01")

    assert_structural_invariants(under.model_output)
    assert_structural_invariants(over.model_output)
    assert over.model_output["allocations"]["us_nominal_treasury_long"] >= under.model_output["allocations"]["us_nominal_treasury_long"]
