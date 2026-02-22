import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions
from ldi.engine.model import LDIModel
import ldi.engine.model as model_module

FIXED_TODAY = pd.Timestamp("2025-01-01")
SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

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

SCENARIOS = {
    "baseline_one_time": {
        "name": "baseline_one_time",
        "assets_today": 20000,
        "liabilities": [{"type": "one_time", "amount_today": 10000, "start_date": "2028-01-01"}],
    },
    "recurring_with_contributions": {
        "name": "recurring_with_contributions",
        "assets_today": 5000,
        "liabilities": [{"type": "recurring", "amount_today": 4000, "start_date": "2027-01-01", "duration_years": 3}],
        "contributions": [{"type": "recurring", "amount": 150, "frequency": "monthly", "start_date": "2025-01-01", "end_date": "2029-01-01"}],
    },
}


def _structured_output(model):
    result = model.result()
    required_balances = [bucket.get_asset_balance_by_period(-1) for bucket in model.required_buckets]
    return {
        "name": result["name"],
        "assets_today": float(result["assets_today"]),
        "surplus_at_maturity": float(result["surplus_at_maturity"]),
        "allocations": {k: float(v) for k, v in result["allocations"].items()},
        "bucket_balances": {
            "required_count": len(model.required_buckets),
            "required_end_balances": [float(x) for x in required_balances],
            "surplus_start_balance": float(model.surplus_bucket.get_asset_balance_by_period(0)),
            "surplus_end_balance": float(model.surplus_bucket.get_asset_balance_by_period(-1)),
        },
    }


def _assert_close(actual, expected):
    assert actual.keys() == expected.keys()
    for key in actual:
        a = actual[key]
        e = expected[key]
        if isinstance(a, dict):
            _assert_close(a, e)
        elif isinstance(a, list):
            assert len(a) == len(e)
            for ai, ei in zip(a, e):
                assert ai == pytest.approx(ei, rel=1e-6, abs=1e-6)
        elif isinstance(a, float):
            assert a == pytest.approx(e, rel=1e-6, abs=1e-6)
        else:
            assert a == e


@pytest.mark.parametrize("scenario_name", sorted(SCENARIOS))
def test_regression_snapshots(scenario_name):
    scenario = SCENARIOS[scenario_name]
    with patch.object(model_module.pd.Timestamp, "today", classmethod(lambda cls: FIXED_TODAY)):
        model = LDIModel(assumptions=ASSUMPTIONS, scenario=scenario, allocation_strategy=GlidePath)

    actual = _structured_output(model)
    snap_file = SNAPSHOT_DIR / f"{scenario_name}.json"
    expected = json.loads(snap_file.read_text())

    _assert_close(actual, expected)
