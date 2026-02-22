from unittest.mock import patch

import pandas as pd
import pytest

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


def test_surplus_peeling_releases_from_required_bucket_into_surplus_bucket():
    scenario = {
        "name": "peel",
        "assets_today": 30000,
        "liabilities": [{"type": "one_time", "amount_today": 10000, "start_date": "2027-01-01"}],
    }
    model = _run(scenario)

    first_required_surplus = model.required_buckets[0].get_surplus_series().iloc[0]
    assert first_required_surplus == pytest.approx(0.0)
    assert model.surplus_bucket.get_asset_balance_by_period(0) == pytest.approx(model.current_balance - model.present_value)


def test_required_bucket_depletion_creates_shortfall_when_assets_low():
    scenario = {
        "name": "depletion",
        "assets_today": 100,
        "liabilities": [{"type": "one_time", "amount_today": 10000, "start_date": "2026-01-01"}],
    }
    model = _run(scenario)

    shortfall = model.required_buckets[0].get_shortfall_by_period(-1)
    assert shortfall > 0
    assert model.result()["surplus_at_maturity"] < 0


def test_surplus_only_case_has_no_required_buckets_and_tracks_surplus_bucket():
    scenario = {
        "name": "surplus-only",
        "assets_today": 5000,
        "liabilities": [],
        "end_date": "2025-08-01",
    }
    model = _run(scenario)

    assert len(model.required_buckets) == 0
    assert model.surplus_bucket.get_asset_balance_by_period(0) == pytest.approx(5000)
