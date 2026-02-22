import numpy as np
import pandas as pd
import pytest

from ldi.engine.portfolio import BaseBucket, Liability, RequiredBucket, SurplusBucket


class DummyAssumptions:
    def __init__(self, inflation_by_date, returns_by_date):
        self.inflation_by_date = inflation_by_date
        self.returns_by_date = returns_by_date
        self.inflation_calls = []
        self.return_calls = []

    def inflation_cpi(self, date):
        self.inflation_calls.append(date)
        return self.inflation_by_date[date]

    def asset_returns(self, date):
        self.return_calls.append(date)
        return self.returns_by_date[date]


class RecordingStrategy:
    def __init__(self, allocations):
        self.allocations = allocations
        self.inputs = []

    def get_allocation(self, inputs):
        self.inputs.append(inputs)
        key = "none" if inputs["funding_ratio"] is None else "ratio"
        return self.allocations[key]


@pytest.fixture
def monthly_index():
    return pd.date_range("2025-01-01", periods=3, freq="MS")


@pytest.mark.parametrize(
    "annual_rate",
    [0.0, 0.06, -0.03],
)
def test_liability_to_monthly_matches_formula(annual_rate):
    liability = Liability(
        amount=1000,
        valuation_date=pd.Timestamp("2025-01-01"),
        maturity_date=pd.Timestamp("2025-01-01"),
        inflation_rate=0.0,
        discount_rate=0.0,
    )

    got = liability._to_monthly(annual_rate)
    expected = (1 + annual_rate) ** (1 / 12) - 1
    assert got == pytest.approx(expected)


@pytest.mark.parametrize(
    "inflation_rate,discount_rate",
    [
        (0.0, 0.0),
        (0.02, 0.05),
        (-0.01, 0.03),
        (0.04, -0.02),
    ],
)
def test_liability_builds_expected_horizon_and_pv(inflation_rate, discount_rate):
    liability = Liability(
        amount=1200.0,
        valuation_date=pd.Timestamp("2025-01-15"),
        maturity_date=pd.Timestamp("2025-04-01"),
        inflation_rate=inflation_rate,
        discount_rate=discount_rate,
    )

    expected_dates = pd.date_range("2025-02-01", "2025-04-01", freq="MS")
    assert liability.df.index.equals(expected_dates)
    assert liability.df["horizon"].tolist() == [2, 1, 0]

    infl_m = (1 + inflation_rate) ** (1 / 12) - 1
    disc_m = (1 + discount_rate) ** (1 / 12) - 1
    real_disc_m = (1 + disc_m) / (1 + infl_m) - 1
    expected_pv = [1200.0 / (1 + real_disc_m) ** h for h in [2, 1, 0]]
    assert liability.df["pv_remaining"].tolist() == pytest.approx(expected_pv)


def test_liability_period_accessors():
    liability = Liability(
        amount=500,
        valuation_date=pd.Timestamp("2025-01-01"),
        maturity_date=pd.Timestamp("2025-03-01"),
        inflation_rate=0.0,
        discount_rate=0.0,
    )

    assert liability.get_pv_remaining_by_period(0) == pytest.approx(500)
    assert liability.get_pv_remaining_by_period(2) == pytest.approx(500)
    assert liability.horizon() == 2


def test_basebucket_normalize_contributions_from_scalar(monthly_index):
    df = pd.DataFrame({"horizon": [2, 1, 0], "pv_remaining": [100, 50, 0]}, index=monthly_index)
    assumptions = DummyAssumptions(
        inflation_by_date={d: 0.0 for d in monthly_index},
        returns_by_date={d: {"bond": 0.0} for d in monthly_index},
    )
    strategy = RecordingStrategy({"ratio": {"bond": 1.0}, "none": {"bond": 1.0}})

    bucket = BaseBucket(
        name="base",
        amount=100,
        df=df,
        assumptions=assumptions,
        allocation_strategy=strategy,
        contributions=5,
        allow_surplus=False,
    )

    assert bucket.contributions_ts.dtype == np.dtype("float64")
    assert bucket.contributions_ts.tolist() == [5.0, 5.0, 5.0]


def test_basebucket_normalize_contributions_series_aligns_by_month(monthly_index):
    df = pd.DataFrame({"horizon": [2, 1, 0], "pv_remaining": [100, 100, 100]}, index=monthly_index)
    source = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.to_datetime(["2025-01-20", "2025-02-14", "2025-03-31"]),
    )
    assumptions = DummyAssumptions(
        inflation_by_date={d: 0.0 for d in monthly_index},
        returns_by_date={d: {"bond": 0.0} for d in monthly_index},
    )
    strategy = RecordingStrategy({"ratio": {"bond": 1.0}, "none": {"bond": 1.0}})

    bucket = BaseBucket(
        name="aligned",
        amount=0,
        df=df,
        assumptions=assumptions,
        allocation_strategy=strategy,
        contributions=source,
        allow_surplus=False,
    )

    assert bucket.contributions_ts.index.equals(monthly_index)
    assert bucket.contributions_ts.tolist() == [1.0, 2.0, 3.0]


@pytest.mark.parametrize(
    "bad_contributions,expected_error,pattern",
    [
        # Non-datetime index should still fail
        (pd.Series([1.0, 2.0, 3.0], index=[0, 1, 2]), TypeError, "datetime-indexed"),

        # Non-Series / non-float should still fail
        ([1.0, 2.0], TypeError, "float or pandas Series"),
    ],
)
def test_basebucket_normalize_contributions_errors(
    monthly_index, bad_contributions, expected_error, pattern
):
    df = pd.DataFrame(
        {"horizon": [2, 1, 0], "pv_remaining": [100, 100, 100]},
        index=monthly_index,
    )

    assumptions = DummyAssumptions(
        inflation_by_date={d: 0.0 for d in monthly_index},
        returns_by_date={d: {"bond": 0.0} for d in monthly_index},
    )

    strategy = RecordingStrategy(
        {"ratio": {"bond": 1.0}, "none": {"bond": 1.0}}
    )

    with pytest.raises(expected_error, match=pattern):
        BaseBucket(
            name="bad",
            amount=0,
            df=df,
            assumptions=assumptions,
            allocation_strategy=strategy,
            contributions=bad_contributions,
            allow_surplus=False,
        )
        
def test_basebucket_allow_surplus_false_and_negative_cash_supply(monthly_index):
    df = pd.DataFrame(
        {
            "horizon": [2, 1, 0],
            "pv_remaining": [10.0, 10.0, 10.0],
        },
        index=monthly_index,
    )
    assumptions = DummyAssumptions(
        inflation_by_date={d: 0.0 for d in monthly_index},
        returns_by_date={d: {"bond": 0.0} for d in monthly_index},
    )
    strategy = RecordingStrategy({"ratio": {"bond": 1.0}, "none": {"bond": 1.0}})

    bucket = BaseBucket(
        name="nosurplus",
        amount=-50.0,
        df=df,
        assumptions=assumptions,
        allocation_strategy=strategy,
        contributions=-5.0,
        allow_surplus=False,
    )

    assert (bucket.df["surplus"] == 0.0).all()
    assert bucket.df.iloc[0]["asset_balance"] == pytest.approx(-50.0)
    assert bucket.df.iloc[1]["asset_balance"] == pytest.approx(-55.0)


def test_surplusbucket_constructs_infinite_horizon_without_surplus_and_accessors():
    strategy = RecordingStrategy({"ratio": {"bond": 1.0}, "none": {"bond": 1.0}})
    dates = pd.date_range("2025-02-01", "2025-04-01", freq="MS")
    assumptions = DummyAssumptions(
        inflation_by_date={d: 0.0 for d in dates},
        returns_by_date={d: {"bond": 0.0} for d in dates},
    )

    bucket = SurplusBucket(
        name="surplus",
        amount=200.0,
        valuation_date=pd.Timestamp("2025-01-15"),
        end_date=pd.Timestamp("2025-04-01"),
        assumptions=assumptions,
        allocation_strategy=strategy,
        contributions=0.0,
    )

    assert (bucket.df["horizon"] == np.inf).all()
    assert (bucket.df["pv_remaining"] == 0.0).all()
    assert (bucket.df["surplus"] == 0.0).all()
    assert all(call["funding_ratio"] is None for call in strategy.inputs)
    assert all(call["horizon_months"] == np.inf for call in strategy.inputs)

    series = bucket.get_surplus_series()
    assert series.name == "surplus"
    assert series.tolist() == [0.0, 0.0, 0.0]


def test_requiredbucket_links_liability_and_horizon_and_caps_surplus():
    liability = Liability(
        amount=90.0,
        valuation_date=pd.Timestamp("2025-01-01"),
        maturity_date=pd.Timestamp("2025-03-01"),
        inflation_rate=0.0,
        discount_rate=0.0,
    )

    idx = liability.df.index
    assumptions = DummyAssumptions(
        inflation_by_date={d: 0.0 for d in idx},
        returns_by_date={d: {"bond": 0.0} for d in idx},
    )
    strategy = RecordingStrategy({"ratio": {"bond": 1.0}, "none": {"bond": 1.0}})

    bucket = RequiredBucket(
        name="required",
        amount=120.0,
        liability=liability,
        assumptions=assumptions,
        allocation_strategy=strategy,
        contributions=0.0,
    )

    assert bucket.get_liability() is liability
    assert bucket.get_horizon() == 2
    assert bucket.get_asset_balance_by_period(0) == pytest.approx(90.0)
    assert bucket.get_surplus_series().iloc[0] == pytest.approx(30.0)
