
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
        discount_rate: float,
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
        real_disc = (1 + infl_m) / (1 + disc_m) - 1

        dates = pd.date_range(
            start=self.valuation_date + pd.offsets.MonthBegin(1), 
            end=self.maturity_date, 
            freq="MS"
        )
        horizon = 12 * (self.maturity_date.year - dates.year) + (self.maturity_date.month - dates.month)

        self.df = pd.DataFrame({
            "date": dates,
            "horizon": horizon,
            "pv_remaining": self.amount * (1 + real_disc) ** horizon,
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

            # collapse both sides to month starts
            bucket_months = self.df["date"].dt.to_period("M")
            contrib_months = ts.index.to_period("M")

            ts.index = contrib_months

            aligned = ts.reindex(bucket_months)

            if aligned.isna().any():
                missing = self.df.loc[aligned.isna(), "date"]
                raise ValueError(
                    f"Missing contributions for months: {missing.dt.strftime('%Y-%m').tolist()}"
                )

            aligned.index = self.df.index
            return aligned.astype("float64")

        raise TypeError("contributions must be float or pandas Series")

    def _build(self):

        infl_m = self._to_monthly(self.assumptions.inflation_cpi)

        assets_today = self.amount 

        rows = []

        for t in range(len(self.df)):

            liability = self.df.at[t, "pv_remaining"]
            horizon = self.df.at[t, "horizon"]
            funding_ratio = assets_today / liability if liability > 0 else None
            
            allocations = self.allocation_strategy.get_allocation({
                "horizon_months": horizon,
                "funding_ratio": funding_ratio
            })

            expected_return = 0.0
            for asset, weight in allocations.items():
                nominal_m = self._to_monthly(self.assumptions.assets[asset])
                real_m = (1 + nominal_m) / (1 + infl_m) - 1
                expected_return += weight * real_m

            if self.allow_surplus:
                surplus = max(0, assets_today - liability)
                assets_today -= surplus
            else:
                surplus = 0

            rows.append({
                "t": t,
                "asset_balance": assets_today,
                "funding_ratio": funding_ratio,
                "allocations": allocations,
                "expected_return": expected_return,
                "surplus": surplus,
            })

            assets_today *= (1 + expected_return)
            assets_today += self.contributions_ts.iloc[t]

        proj_df = pd.DataFrame(rows).set_index("t")
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
        s = self.df.set_index("date")["surplus"]
        return s.rename(self.name)

class SurplusBucket(BaseBucket):

    def __init__(
        self,
        name: str,
        amount: float,
        horizon_months: int,
        valuation_date: pd.Timestamp,
        assumptions: Assumptions,
        allocation_strategy: AllocationStrategy,
        contributions: Union[float, pd.Series] = 0.0,
    ):

        dates = pd.date_range(
            start=valuation_date + pd.offsets.MonthBegin(1),
            periods=horizon_months,
            freq="MS"
        )

        df = pd.DataFrame({
            "date": dates,
            "horizon": np.inf,
            "pv_remaining": 0.0,   
        })

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
