
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
        assumptions: Assumptions,
    ):
        self.amount = amount
        self.valuation_date = valuation_date
        self.maturity_date = maturity_date
        self.assumptions = assumptions

        self._build()

    def _build(self):

        dates = pd.date_range(
            start=self.valuation_date + pd.offsets.MonthBegin(1), 
            end=self.maturity_date, 
            freq="MS"
        )
        horizon = 12 * (self.maturity_date.year - dates.year) + (self.maturity_date.month - dates.month)

        rd = pd.Series([
            (1 + self._to_monthly(self.assumptions.inflation_cpi(d))) /
            (1 + self._to_monthly(self.assumptions.discount_rate(d))) - 1
            for d in dates
        ], index=dates)

        discount_factors = rd[::-1].add(1).cumprod()[::-1]
        discount_factors = discount_factors.shift(-1, fill_value=1.0)

        self.df = pd.DataFrame({
            "horizon": horizon,
            "pv_remaining": self.amount * discount_factors
        })

    def _to_monthly(self, annual_rate):
        return (1 + annual_rate) ** (1/12) - 1

    def present_value(self) -> float:
        return self.df["pv_remaining"].iloc[0]
    
    def horizon(self):
        return self.df["horizon"].iloc[0]

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
                    f"Missing contributions for months: {missing.dt.strftime('%Y-%m').tolist()}"
                )

            aligned.index = self.df.index
            return aligned.astype("float64")

        raise TypeError("contributions must be float or pandas Series")

    def _build(self):

        assets_today = self.amount 

        rows = []

        for d in self.df.index:

            liability = self.df.at[d, "pv_remaining"]
            horizon = self.df.at[d, "horizon"]
            infl_m = self._to_monthly(self.assumptions.inflation_cpi(d))
            funding_ratio = assets_today / liability if liability > 0 else None
            
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
                surplus = max(0, assets_today - liability)
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

        self.df["shortfall"] = (self.df["pv_remaining"] - self.df["asset_balance"]).clip(lower=0)

    def get_liability(self):
        return self.liability

    def get_shortfall_by_period(self, period):
        return self.df["shortfall"].iloc[period]
    
    def get_horizon(self):
        return self.df["horizon"].iloc[0]
