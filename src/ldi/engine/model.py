
import pandas as pd
from dataclasses import dataclass
from dateutil.relativedelta import relativedelta
from datetime import datetime
from typing import List

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions
from ldi.engine.portfolio import SurplusBucket, RequiredBucket, Liability

class LDIModel:

    TOLERANCE = 100
    MAX_ITERATIONS = 20

    def __init__(self, *, assumptions: Assumptions, scenario: dict):

        self.assumptions = assumptions

        for key in ["name", "assets_today", "liabilities"]:
            if key not in scenario:
                raise ValueError(F"Missing '{key}' in scenario")

        self.name = scenario["name"]
        self.current_balance = scenario["assets_today"]
        self.liabilities_config = scenario["liabilities"]
        self.depost = scenario.get("deposit", {})
        self.contributions = self.depost.get("monthly", 0)

        self.valuation_date = pd.Timestamp.today()

        self.liabilities: List[Liability] = []
        self.required_buckets:List[RequiredBucket] = []
        self.surplus_bucket:SurplusBucket = None

        self._run()

    def _run(self):

        self._generate_liabilities()

        self._generate_required_buckets()
        self._rebalance_surplus()

        self._calculate_funded_status()
        self._calculate_current_asset_allocations()

    def _generate_liabilities(self):

        for liability_config in self.liabilities_config:

            first_withdrawal = datetime.strptime(liability_config["start_date"], "%Y-%m-%d").date()
            withdrawal_amount = liability_config["amount_today"]
            inflation_rate = liability_config.get("inflation_rate", self.assumptions.cpi_inflation)

            if liability_config["type"] == "recurring":
                duration_years = liability_config["duration_years"]
            
            else:
                duration_years = 1

            for i in range(duration_years):

                liability = Liability(
                    amount=withdrawal_amount,
                    valuation_date=self.valuation_date,
                    maturity_date=pd.Timestamp(first_withdrawal + relativedelta(years=i)),
                    inflation_rate=inflation_rate,
                    discount_rate=self.assumptions.discount_rate
                )
                self.liabilities.append(liability)

        self.present_value = sum([liability.present_value() for liability in self.liabilities])
        self.current_funding_ratio = self.current_balance / self.present_value   
    
    def _generate_required_buckets(self):

        contributions_per_bucket = self.contributions / len(self.liabilities)
        required_capital = min(self.current_balance, self.present_value)

        for liability in self.liabilities:

            asset_balance = required_capital * liability.present_value() / self.present_value
            bucket = RequiredBucket(
                name=liability.maturity_date,
                amount=asset_balance,
                liability=liability,
                inflation_rate=self.assumptions.cpi_inflation,
                equity_return_rate=self.assumptions.equity_expected_return,
                fixed_income_return_rate=self.assumptions.fixed_income_expected_return,
                allocation_strategy= GlidePath,
                contributions=contributions_per_bucket
            )

            self.required_buckets.append(bucket)

    def _rebalance_surplus(self):

        surplus_capital  = max(0, self.current_balance - self.present_value)
        surplus_series = pd.concat(
            [bucket.get_surplus_series() for bucket in self.required_buckets],
            axis=1
        ).fillna(0)

        self.surplus_bucket = SurplusBucket(
            name="surplus",
            amount=surplus_capital,
            horizon_months=max([liability.horizon() for liability in self.liabilities]),
            valuation_date=self.valuation_date,
            inflation_rate=self.assumptions.cpi_inflation,
            equity_return_rate=self.assumptions.equity_expected_return,
            fixed_income_return_rate=self.assumptions.fixed_income_expected_return,
            contributions=surplus_series.sum(axis=1)
        )

    def _calculate_funded_status(self):

        surplus = self.surplus_bucket.get_asset_balance_by_period(-1)
        shortfall = sum([bucket.get_shortfall_by_period(-1) for bucket in self.required_buckets])

        if surplus > 0:
            self.funded_status = self.surplus_bucket.get_asset_balance_by_period(-1)
        else:
            self.funded_status = -shortfall        

    def _calculate_current_asset_allocations(self):

        equity_numerator = 0
        fixed_income_numerator = 0
        denominator = 0 

        if self.current_balance == 0:

            for bucket in self.required_buckets:
                equity_numerator += bucket.get_equity_allocation_by_period(0) * bucket.get_liability().present_value()
                fixed_income_numerator += bucket.get_fixed_income_allocation_by_period(0) * bucket.get_liability().present_value()
            denominator = self.present_value

        else:
            for bucket in [*self.required_buckets, self.surplus_bucket]:
                equity_numerator += bucket.get_equity_allocation_by_period(0) * bucket.get_asset_balance_by_period(0)
                fixed_income_numerator += bucket.get_fixed_income_allocation_by_period(0) * bucket.get_asset_balance_by_period(0)
            denominator = self.current_balance

        self.current_equity_allocation = equity_numerator / denominator
        self.current_fixed_income_allocation = fixed_income_numerator / denominator

    # def result(self):

    #     return {
    #         "Name": self.name,
    #         "Portfolio Value (Today)": self.current_balance,
    #         "Projected Surplus / Shortfall (At Maturity)": self.funded_status,
    #         "Equity Allocation (%)": self.current_equity_allocation,
    #         "Fixed Income Allocation (%)": self.current_fixed_income_allocation,
    #     }

    def result(self):
        return {
            "name": self.name,
            "assets_today": self.current_balance,
            "surplus_at_maturity": self.funded_status,
            "equity_allocation": self.current_equity_allocation,
            "fixed_income_allocation": self.current_fixed_income_allocation,
            # "net_contribution_today": self.required_net_contribution,
            # "monthly_contribution": self.required_monthly_contribution,
        }