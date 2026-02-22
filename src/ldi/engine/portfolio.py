
import pandas as pd
import numpy as np
from typing import Union

from ldi.engine.allocator import AllocationStrategy
from ldi.engine.assumptions import Assumptions

class Liability:

    def __init__(
        self,
        amount: float,
        valuation_date: pd.Timestamp,
        maturity_date: pd.Timestamp,
        inflation_rate: float,
        discount_rate: float
    ):
        self.amount = amount
        self.valuation_date = valuation_date
        self.maturity_date = maturity_date
        self.inflation_rate = inflation_rate
        self.discount_rate = discount_rate

        self._build()

    def _build(self):

        infl_m = self._to_monthly(self.inflation_rate)
        disc_m = self._to_monthly(self.discount_rate)
        real_disc_m = (1 + disc_m) / (1 + infl_m) - 1

        dates = pd.date_range(
            start=pd.offsets.MonthBegin().rollforward(self.valuation_date), 
            end=self.maturity_date, 
            freq="MS"
        )
        horizon = 12 * (self.maturity_date.year - dates.year) + (self.maturity_date.month - dates.month)

        self.df = pd.DataFrame({
            "horizon": horizon,
            "pv_remaining": self.amount / (1 + real_disc_m) ** horizon,
        }, index=dates)

    def _to_monthly(self, annual_rate):
        return (1 + annual_rate) ** (1/12) - 1

    def get_pv_remaining_by_period(self, i) -> float:
        return self.df["pv_remaining"].iloc[i]
    
    def horizon(self):
        return self.df["horizon"].iloc[0]

    def present_value(self):
        return self.get_pv_remaining_by_period(0)

class BaseBucket:

    def __init__(
            self, 
            name: str,
            amount: float, 
            df: pd.DataFrame,
            assumptions: Assumptions,
            allocation_strategy: AllocationStrategy,
            contributions: Union[float, pd.Series] = 0.0,
            allow_surplus: bool = True
        ):

        self.name = name
        self.amount = amount
        self.assumptions = assumptions
        self.allocation_strategy = allocation_strategy
        self.contributions = contributions
        self.allow_surplus = allow_surplus

        self.df = df.copy(deep=True)
        self.contributions_ts = self._normalize_contributions(contributions)
        
        self._build()

    def _normalize_contributions(self, contributions):

        if isinstance(contributions, (int, float)):
            return pd.Series(
                contributions,
                index=self.df.index,
                dtype="float64",
            )

        if isinstance(contributions, pd.Series):
            ts = contributions.copy()

            if not isinstance(ts.index, pd.DatetimeIndex):
                raise TypeError("Contribution series must be datetime-indexed")

            bucket_months = self.df.index.to_period("M")
            ts.index = ts.index.to_period("M")
            aligned = ts.reindex(bucket_months)

            if aligned.isna().any():
                missing = self.df.index[aligned.isna()]
                raise ValueError(
                    f"Missing contributions for months: {missing.strftime('%Y-%m').tolist()}"
                )

            aligned.index = self.df.index
            return aligned.astype("float64")

        raise TypeError("contributions must be float or pandas Series")

    def _build(self):

        assets_today = self.amount 

        rows = []

        for d in self.df.index:

            pv_remaining = self.df.at[d, "pv_remaining"]
            horizon = self.df.at[d, "horizon"]
            infl_m = self._to_monthly(self.assumptions.inflation_cpi(d))
            funding_ratio = assets_today / pv_remaining if pv_remaining > 0 else None
            
            allocations = self.allocation_strategy.get_allocation({
                "horizon_months": horizon,
                "funding_ratio": funding_ratio
            })

            expected_return = 0.0
            for asset, weight in allocations.items():
                nominal_m = self._to_monthly(self.assumptions.asset_returns(d)[asset])
                real_m = (1 + nominal_m) / (1 + infl_m) - 1
                expected_return += weight * real_m

            if self.allow_surplus:
                surplus = max(0, assets_today - pv_remaining)
                assets_today -= surplus
            else:
                surplus = 0

            rows.append({
                "date": d,
                "asset_balance": assets_today,
                "funding_ratio": funding_ratio,
                "allocations": allocations,
                "expected_return": expected_return,
                "surplus": surplus,
            })

            assets_today *= (1 + expected_return)
            assets_today += self.contributions_ts.at[d]

        proj_df = pd.DataFrame(rows).set_index("date")
        self.df = self.df.join(proj_df)
        
    def _to_monthly(self, annual_rate):
        return (1 + annual_rate) ** (1/12) - 1

    def _get_column_by_period(self, column, period):
        return self.df[column].iloc[period]

    def get_asset_balance_by_period(self, period):
        return self._get_column_by_period("asset_balance", period)
    
    def get_allocations_by_period(self, period):
        return self._get_column_by_period("allocations", period)
    
    def get_surplus_series(self):
        return self.df["surplus"].rename(self.name)

class SurplusBucket(BaseBucket):

    def __init__(
        self,
        name: str,
        amount: float,
        valuation_date: pd.Timestamp,
        end_date: pd.Timestamp,
        assumptions: Assumptions,
        allocation_strategy: AllocationStrategy,
        contributions: Union[float, pd.Series] = 0.0,
    ):

        dates = pd.date_range(
            start=valuation_date + pd.offsets.MonthBegin(1),
            end=end_date,
            freq="MS"
        )

        df = pd.DataFrame({
            "horizon": np.inf,
            "pv_remaining": 0.0,
        }, index=pd.Index(dates, name="date"))

        super().__init__(
            name=name,
            amount=amount,
            df=df,
            assumptions=assumptions,
            allocation_strategy=allocation_strategy,
            contributions=contributions,
            allow_surplus=False
        )

class RequiredBucket(BaseBucket):

    def __init__(
        self,
        name: str,
        amount: float,
        liability: Liability,
        assumptions: Assumptions,
        allocation_strategy: AllocationStrategy,
        contributions: float = 0,
    ):

        super().__init__(
            name=name,
            amount=amount,
            df=liability.df,
            assumptions=assumptions,
            allocation_strategy=allocation_strategy,
            contributions=contributions,
            allow_surplus=True
        )

        self.liability = liability

    def get_liability(self):
        return self.liability

    def get_horizon(self):
        return self.df["horizon"].iloc[0]

    def get_shortfall_by_period(self, period):
        pv_remaining = self.df["pv_remaining"].iloc[period]
        asset_balance = self.df["asset_balance"].iloc[period]
        return max(0.0, pv_remaining - asset_balance)
