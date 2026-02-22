from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions
from ldi.engine.model import LDIModel
from ldi.app import runner
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


def _run_model(scenario):
    with patch.object(model_module.pd.Timestamp, "today", classmethod(lambda cls: FIXED_TODAY)):
        return LDIModel(assumptions=ASSUMPTIONS, scenario=scenario, allocation_strategy=GlidePath)


def test_monthly_contributions_accumulate_without_infinite_values():
    scenario = {
        "name": "monthly-c",
        "assets_today": 0,
        "liabilities": [],
        "end_date": "2025-06-01",
        "contributions": [
            {"type": "recurring", "amount": 100, "frequency": "monthly", "start_date": "2025-02-01", "end_date": "2025-06-01"}
        ],
    }
    model = _run_model(scenario)
    result = model.result()

    assert result["surplus_at_maturity"] == pytest.approx(0.0)
    assert model.contributions.sum() == pytest.approx(500.0)
    assert np.isfinite(result["surplus_at_maturity"])


def test_annual_contributions_only_apply_in_target_month():
    scenario = {
        "name": "annual-c",
        "assets_today": 0,
        "liabilities": [],
        "end_date": "2026-12-01",
        "contributions": [
            {"type": "recurring", "amount": 1200, "frequency": "annual", "month": 6, "start_date": "2025-01-01", "end_date": "2026-12-01"}
        ],
    }
    model = _run_model(scenario)

    non_zero_months = model.contributions[model.contributions > 0].index.month.tolist()
    assert non_zero_months == [6, 6]


def test_one_time_contribution_is_applied_and_finite():
    scenario = {
        "name": "one-time-c",
        "assets_today": 0,
        "liabilities": [],
        "end_date": "2025-06-01",
        "contributions": [{"type": "one_time", "amount": 1000, "date": "2025-03-01"}],
    }
    model = _run_model(scenario)
    assert model.result()["surplus_at_maturity"] == pytest.approx(0.0)
    assert model.contributions.loc[pd.Timestamp("2025-03-01")] == pytest.approx(1000.0)


def test_calibration_converges_and_is_iteration_bounded(tmp_path):
    scenario = {
        "name": "calibrate",
        "assets_today": 1000,
        "liabilities": [{"type": "one_time", "amount_today": 5000, "start_date": "2027-01-01"}],
        "contributions": [],
    }

    with patch.object(runner.pd.Timestamp, "today", classmethod(lambda cls: FIXED_TODAY)), patch.object(model_module.pd.Timestamp, "today", classmethod(lambda cls: FIXED_TODAY)):
        monthly = runner._calculate_monthly_contribution_adjustment(ASSUMPTIONS, scenario, surplus_at_maturity=-3000)

    assert np.isfinite(monthly)
    assert abs(monthly) < 5000
    assert runner.MAX_ITERATIONS == 40
