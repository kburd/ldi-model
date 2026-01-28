
import pandas as pd
import numpy as np
from typing import Union

from ldi.engine.allocator import AllocationStrategy, EquityOnly

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
            inflation_rate: float,
            equity_return_rate: float,
            fixed_income_return_rate: float,
            allocation_strategy: AllocationStrategy,
            contributions: Union[float, pd.Series] = 0.0,
            allow_surplus: bool = True
        ):

        self.name = name
        self.amount = amount
        self.allocation_strategy = allocation_strategy
        self.contributions = contributions
        self.allow_surplus = allow_surplus

        self.df = df.copy(deep=True)

        self.inflation_rate = inflation_rate
        self.equity_return_rate = equity_return_rate
        self.fixed_income_return_rate = fixed_income_return_rate

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

        infl_m = self._to_monthly(self.inflation_rate)
        equity_m = self._to_monthly(self.equity_return_rate)
        bond_m = self._to_monthly(self.fixed_income_return_rate)
        real_equity_m = (1 + equity_m) / (1 + infl_m) - 1
        real_bond_m = (1 + bond_m) / (1 + infl_m) - 1

        self.df["equity_allocation"] = self.df["horizon"].apply(self.allocation_strategy.equity_allocation)
        self.df["fixed_income_allocation"] = self.df["horizon"].apply(self.allocation_strategy.fixed_income_allocation)
        self.df["expected_return"] = self.df["equity_allocation"] * real_equity_m + self.df["fixed_income_allocation"] * real_bond_m
        self.df["growth_factor"] = (1 + self.df["expected_return"]).shift(1, fill_value=1).cumprod()

        balances, surpluses = self._project_balances_and_surpluses()

        self.df["asset_balance"] = balances
        self.df["surplus"] = surpluses

    def _project_balances_and_surpluses(self):

        balances = []
        surpluses = []

        assets_today = self.amount  # initial assets_today

        for t in range(len(self.df)):
            liability = self.df.at[t, "pv_remaining"]

            # record assets_today at start of period t
            if self.allow_surplus:
                surplus = max(0, assets_today - liability)
                assets_today -= surplus
            else:
                surplus = 0

            balances.append(assets_today)
            surpluses.append(surplus)

            # now roll forward to next period
            r = self.df.at[t, "expected_return"]
            assets_today *= (1 + r)
            assets_today += self.contributions_ts.iloc[t]

        return balances, surpluses
        
    def _to_monthly(self, annual_rate):
        return (1 + annual_rate) ** (1/12) - 1

    def _get_column_by_period(self, column, period):
        return self.df[column].iloc[period]

    def get_asset_balance_by_period(self, period):
        return self._get_column_by_period("asset_balance", period)
    
    def get_equity_allocation_by_period(self, period):
        return self._get_column_by_period("equity_allocation", period)

    def get_fixed_income_allocation_by_period(self, period):
        return self._get_column_by_period("fixed_income_allocation", period)
    
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
        inflation_rate: float,
        equity_return_rate: float,
        fixed_income_return_rate: float,
        contributions: Union[float, pd.Series] = 0.0,
    ):

        dates = pd.date_range(
            start=valuation_date + pd.offsets.MonthBegin(1),
            periods=horizon_months,
            freq="MS"
        )

        horizon = np.arange(horizon_months)[::-1]

        df = pd.DataFrame({
            "date": dates,
            "horizon": horizon,
            "pv_remaining": 0.0,   
        })

        super().__init__(
            name=name,
            amount=amount,
            df=df,
            inflation_rate=inflation_rate,
            equity_return_rate=equity_return_rate,
            fixed_income_return_rate=fixed_income_return_rate,
            allocation_strategy=EquityOnly,
            contributions=contributions,
            allow_surplus=False
        )

        self.df["funding_ratio"] = np.inf

class RequiredBucket(BaseBucket):

    def __init__(
        self,
        name: str,
        amount: float,
        liability: Liability,
        inflation_rate: float,
        equity_return_rate: float,
        fixed_income_return_rate: float,
        allocation_strategy: AllocationStrategy,
        contributions: float = 0,
    ):

        super().__init__(
            name=name,
            amount=amount,
            df=liability.df,
            inflation_rate=inflation_rate,
            equity_return_rate=equity_return_rate,
            fixed_income_return_rate=fixed_income_return_rate,
            allocation_strategy=allocation_strategy,
            contributions=contributions,
            allow_surplus=True
        )

        self.liability = liability

        self.df["funding_ratio"] = self.df["asset_balance"] / self.df["pv_remaining"]
        self.df["shortfall"] = (self.df["pv_remaining"] - self.df["asset_balance"]).clip(lower=0)

    def get_liability(self):
        return self.liability

    def get_shortfall_by_period(self, period):
        return self.df["shortfall"].iloc[period]
    
    def get_horizon(self):
        return self.df["horizon"].iloc[0]
