import pandas as pd
import pytest

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions


def test_static_assumptions_constant_series():
    assumptions = Assumptions.from_dict(
        {
            "inflation_cpi": 0.03,
            "assets": {
                "us_equity_total_market": 0.08,
                "intl_equity_developed": 0.07,
                "us_nominal_treasury_long": 0.04,
            },
        }
    )
    dates = pd.date_range("2025-01-01", periods=6, freq="MS")
    assert len({assumptions.inflation_cpi(d) for d in dates}) == 1
    assert len({assumptions.asset_returns(d)["us_equity_total_market"] for d in dates}) == 1


def test_glide_path_invariants():
    alloc = GlidePath.get_allocation({"horizon_months": 120, "funding_ratio": 0.9})
    assert sum(alloc.values()) == pytest.approx(1.0)
    assert all(v >= 0 for v in alloc.values())
