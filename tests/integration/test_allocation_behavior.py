from unittest.mock import patch

import pandas as pd

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions
from ldi.engine.model import LDIModel
import ldi.engine.model as model_module

FIXED_TODAY = pd.Timestamp("2025-01-01")
ASSUMPTIONS = Assumptions.from_dict(
    {
        "inflation_cpi": 0.02,
        "assets": {
            "us_equity_total_market": 0.06,
            "intl_equity_developed": 0.05,
            "us_nominal_treasury_long": 0.03,
        },
    }
)


def _model_for(start_date, assets_today, amount=10000):
    scenario = {
        "name": f"alloc-{start_date}-{assets_today}",
        "assets_today": assets_today,
        "liabilities": [{"type": "one_time", "amount_today": amount, "start_date": start_date}],
    }
    with patch.object(model_module.pd.Timestamp, "today", classmethod(lambda cls: FIXED_TODAY)):
        return LDIModel(assumptions=ASSUMPTIONS, scenario=scenario, allocation_strategy=GlidePath)


def test_longer_horizon_has_lower_hedge_weight_directionally():
    short = _model_for("2026-01-01", 10000)
    long = _model_for("2035-01-01", 10000)

    short_hedge = short.result()["allocations"]["us_nominal_treasury_long"]
    long_hedge = long.result()["allocations"]["us_nominal_treasury_long"]
    assert short_hedge > long_hedge


def test_higher_funding_ratio_has_higher_hedge_weight_directionally():
    under = _model_for("2030-01-01", 5000)
    over = _model_for("2030-01-01", 20000)

    assert over.required_buckets[0].get_allocations_by_period(0)["us_nominal_treasury_long"] > under.required_buckets[0].get_allocations_by_period(0)["us_nominal_treasury_long"]


def test_underfunded_vs_overfunded_shifts_to_bonds_when_overfunded():
    under = _model_for("2028-01-01", 4000, amount=10000)
    over = _model_for("2028-01-01", 20000, amount=10000)

    assert over.required_buckets[0].get_allocations_by_period(0)["us_nominal_treasury_long"] > under.required_buckets[0].get_allocations_by_period(0)["us_nominal_treasury_long"]
