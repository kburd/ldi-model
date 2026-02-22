from unittest.mock import patch

import numpy as np
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


def _run(scenario):
    with patch.object(model_module.pd.Timestamp, "today", classmethod(lambda cls: FIXED_TODAY)):
        return LDIModel(assumptions=ASSUMPTIONS, scenario=scenario, allocation_strategy=GlidePath)


def test_one_time_liability_creates_single_bucket_with_maturity_alignment():
    scenario = {
        "name": "one-time",
        "assets_today": 20000,
        "liabilities": [{"type": "one_time", "amount_today": 10000, "start_date": "2027-06-01"}],
    }
    model = _run(scenario)

    assert len(model.required_buckets) == 1
    assert model.required_buckets[0].get_liability().maturity_date == pd.Timestamp("2027-06-01")


def test_recurring_liability_expands_to_annual_buckets_and_maturity_alignment():
    scenario = {
        "name": "recurring",
        "assets_today": 25000,
        "liabilities": [
            {
                "type": "recurring",
                "amount_today": 5000,
                "start_date": "2028-01-01",
                "duration_years": 4,
            }
        ],
    }
    model = _run(scenario)

    assert len(model.required_buckets) == 4
    maturities = [bucket.get_liability().maturity_date for bucket in model.required_buckets]
    assert maturities == [
        pd.Timestamp("2028-01-01"),
        pd.Timestamp("2029-01-01"),
        pd.Timestamp("2030-01-01"),
        pd.Timestamp("2031-01-01"),
    ]


def test_extreme_liability_inflation_reduces_funding_ratio_behavior():
    low_inflation = {
        "name": "low-infl",
        "assets_today": 15000,
        "liabilities": [
            {
                "type": "one_time",
                "amount_today": 12000,
                "start_date": "2030-01-01",
                "inflation_rate": 0.01,
                "discount_rate": 0.03,
            }
        ],
    }
    high_inflation = {
        "name": "high-infl",
        "assets_today": 15000,
        "liabilities": [
            {
                "type": "one_time",
                "amount_today": 12000,
                "start_date": "2030-01-01",
                "inflation_rate": 0.15,
                "discount_rate": 0.03,
            }
        ],
    }

    low = _run(low_inflation)
    high = _run(high_inflation)

    assert np.isfinite(low.current_funding_ratio)
    assert np.isfinite(high.current_funding_ratio)
    assert high.present_value > low.present_value
    assert high.current_funding_ratio < low.current_funding_ratio
