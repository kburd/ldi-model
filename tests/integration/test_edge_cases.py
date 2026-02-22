from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions
from ldi.engine.model import LDIModel
import ldi.engine.model as model_module

FIXED_TODAY = pd.Timestamp("2025-01-01")


def _run(scenario, inflation=0.02, returns=0.04):
    assumptions = Assumptions.from_dict(
        {
            "inflation_cpi": inflation,
            "assets": {
                "us_equity_total_market": returns,
                "intl_equity_developed": returns,
                "us_nominal_treasury_long": returns,
            },
        }
    )
    with patch.object(model_module.pd.Timestamp, "today", classmethod(lambda cls: FIXED_TODAY)):
        return LDIModel(assumptions=assumptions, scenario=scenario, allocation_strategy=GlidePath)


@pytest.mark.parametrize(
    "scenario,inflation,returns",
    [
        ({"name": "negative-cpi", "assets_today": 10000, "liabilities": [{"type": "one_time", "amount_today": 5000, "start_date": "2030-01-01", "inflation_rate": -0.02, "discount_rate": 0.02}]}, -0.02, 0.03),
        ({"name": "high-infl", "assets_today": 10000, "liabilities": [{"type": "one_time", "amount_today": 5000, "start_date": "2035-01-01", "inflation_rate": 0.25, "discount_rate": 0.03}]}, 0.15, 0.03),
        ({"name": "long-horizon", "assets_today": 5000, "liabilities": [{"type": "one_time", "amount_today": 3000, "start_date": "2050-01-01"}]}, 0.02, 0.04),
        ({"name": "one-month", "assets_today": 1000, "liabilities": [], "end_date": "2025-02-01"}, 0.02, 0.04),
        ({"name": "no-liabilities", "assets_today": 500, "liabilities": [], "end_date": "2025-04-01"}, 0.02, 0.04),
        ({"name": "post-maturity-contrib", "assets_today": 5000, "liabilities": [{"type": "one_time", "amount_today": 4000, "start_date": "2026-01-01"}], "contributions": [{"type": "recurring", "amount": 200, "frequency": "monthly", "start_date": "2026-02-01", "end_date": "2026-12-01"}]}, 0.02, 0.04),
    ],
)
def test_edge_case_stability_no_nan_no_inf_no_crash(scenario, inflation, returns):
    model = _run(scenario, inflation=inflation, returns=returns)
    result = model.result()

    assert np.isfinite(result["surplus_at_maturity"])
    assert all(np.isfinite(w) for w in result["allocations"].values())
