import pandas as pd
import pytest

from ldi.engine.assumptions import Assumptions
from ldi.engine.portfolio import Liability, RequiredBucket, SurplusBucket


class FixedAllocation:
    @staticmethod
    def get_allocation(_inputs):
        return {
            "us_equity_total_market": 0.0,
            "intl_equity_developed": 0.0,
            "us_nominal_treasury_long": 1.0,
        }


def _assumptions():
    return Assumptions.from_dict(
        {
            "inflation_cpi": 0.0,
            "assets": {
                "us_equity_total_market": 0.0,
                "intl_equity_developed": 0.0,
                "us_nominal_treasury_long": 0.0,
            },
        }
    )


def test_liability_builds_monthly_projection():
    liability = Liability(
        amount=1200,
        valuation_date=pd.Timestamp("2025-01-01"),
        maturity_date=pd.Timestamp("2025-04-01"),
        inflation_rate=0.0,
        discount_rate=0.0,
    )

    assert len(liability.df) == 4
    assert liability.df.index[0] == pd.Timestamp("2025-01-01")
    assert liability.df.index[-1] == pd.Timestamp("2025-04-01")
    assert liability.get_pv_remaining_by_period(0) == pytest.approx(1200.0)
    assert liability.horizon() == 3


def test_required_bucket_normalizes_scalar_contributions():
    liability = Liability(
        amount=1000,
        valuation_date=pd.Timestamp("2025-01-01"),
        maturity_date=pd.Timestamp("2025-03-01"),
        inflation_rate=0.0,
        discount_rate=0.0,
    )

    bucket = RequiredBucket(
        name="required",
        amount=1000,
        liability=liability,
        assumptions=_assumptions(),
        allocation_strategy=FixedAllocation,
        contributions=25,
    )

    assert (bucket.contributions_ts == 25.0).all()
    assert bucket.get_asset_balance_by_period(0) == pytest.approx(1000.0)


def test_surplus_bucket_requires_full_contribution_series_coverage():
    contributions = pd.Series(
        [10.0],
        index=pd.to_datetime(["2025-02-01"]),
    )

    with pytest.raises(ValueError, match="Missing contributions"):
        SurplusBucket(
            name="surplus",
            amount=0.0,
            valuation_date=pd.Timestamp("2025-01-01"),
            end_date=pd.Timestamp("2025-03-01"),
            assumptions=_assumptions(),
            allocation_strategy=FixedAllocation,
            contributions=contributions,
        )
