import pytest

from ldi.engine.allocator import GlidePath, clamp


def test_clamp_bounds_values():
    assert clamp(-0.2) == 0
    assert clamp(0.25) == 0.25
    assert clamp(1.8) == 1


def test_glide_path_allocation_sums_to_one():
    allocation = GlidePath.get_allocation({"horizon_months": 60, "funding_ratio": 0.9})

    assert set(allocation) == {
        "us_equity_total_market",
        "intl_equity_developed",
        "us_nominal_treasury_long",
    }
    assert sum(allocation.values()) == pytest.approx(1.0)


def test_glide_path_uses_more_hedge_for_shorter_horizon_and_higher_funding_ratio():
    low_hedge = GlidePath.get_allocation({"horizon_months": 240, "funding_ratio": 0.7})
    high_hedge = GlidePath.get_allocation({"horizon_months": 12, "funding_ratio": 1.0})

    assert high_hedge["us_nominal_treasury_long"] > low_hedge["us_nominal_treasury_long"]


def test_glide_path_handles_missing_funding_ratio():
    allocation = GlidePath.get_allocation({"horizon_months": 120, "funding_ratio": None})

    assert allocation["us_nominal_treasury_long"] >= 0
    assert sum(allocation.values()) == pytest.approx(1.0)
