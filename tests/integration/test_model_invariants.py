import math
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions
from ldi.engine.model import LDIModel
import ldi.engine.model as model_module

FIXED_TODAY = pd.Timestamp("2025-01-01")


def _run_model(scenario, assumptions_dict):
    assumptions = Assumptions.from_dict(assumptions_dict)
    with patch.object(model_module.pd.Timestamp, "today", classmethod(lambda cls: FIXED_TODAY)):
        model = LDIModel(assumptions=assumptions, scenario=scenario, allocation_strategy=GlidePath)
    return model


def _assert_finite_model_outputs(model):
    result = model.result()
    assert np.isfinite(result["surplus_at_maturity"])
    for weight in result["allocations"].values():
        assert np.isfinite(weight)
    assert sum(result["allocations"].values()) == pytest.approx(1.0)


def test_no_liability_case_has_finite_outputs_and_weights_sum_to_one():
    scenario = {
        "name": "no-liability",
        "assets_today": 1000,
        "liabilities": [],
        "end_date": "2025-06-01",
    }
    assumptions_dict = {
        "inflation_cpi": 0.02,
        "assets": {
            "us_equity_total_market": 0.06,
            "intl_equity_developed": 0.05,
            "us_nominal_treasury_long": 0.03,
        },
    }

    model = _run_model(scenario, assumptions_dict)
    _assert_finite_model_outputs(model)
    assert len(model.required_buckets) == 0


def test_zero_return_world_preserves_real_value_for_no_liability_case():
    scenario = {
        "name": "zero-return",
        "assets_today": 5000,
        "liabilities": [],
        "end_date": "2025-04-01",
    }
    assumptions_dict = {
        "inflation_cpi": 0.0,
        "assets": {
            "us_equity_total_market": 0.0,
            "intl_equity_developed": 0.0,
            "us_nominal_treasury_long": 0.0,
        },
    }

    model = _run_model(scenario, assumptions_dict)
    _assert_finite_model_outputs(model)
    assert model.result()["surplus_at_maturity"] == pytest.approx(5000.0)


def test_perfect_funding_case_matches_analytical_surplus_near_zero():
    assumptions_dict = {
        "inflation_cpi": 0.02,
        "assets": {
            "us_equity_total_market": 0.02,
            "intl_equity_developed": 0.02,
            "us_nominal_treasury_long": 0.02,
        },
    }
    liability_amount = 12000.0
    scenario_underfunded = {
        "name": "liability-pv",
        "assets_today": 0,
        "liabilities": [
            {
                "type": "one_time",
                "amount_today": liability_amount,
                "start_date": "2026-01-01",
                "inflation_rate": 0.02,
                "discount_rate": 0.02,
            }
        ],
    }
    underfunded = _run_model(scenario_underfunded, assumptions_dict)
    pv = underfunded.liabilities[0].present_value()

    scenario_perfect = {
        "name": "perfect-funded",
        "assets_today": pv,
        "liabilities": scenario_underfunded["liabilities"],
    }

    model = _run_model(scenario_perfect, assumptions_dict)
    _assert_finite_model_outputs(model)
    assert model.result()["surplus_at_maturity"] == pytest.approx(0.0, abs=1e-6)
