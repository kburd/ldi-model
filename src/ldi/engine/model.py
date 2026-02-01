
import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import datetime
from typing import List

from ldi.engine.assumptions import Assumptions
from ldi.engine.portfolio import SurplusBucket, RequiredBucket, Liability
from ldi.engine.allocator import AllocationStrategy

class LDIModel:

    def __init__(self, *, assumptions: Assumptions, scenario: dict, allocation_strategy: AllocationStrategy):

        self.assumptions = assumptions

        for key in ["name", "assets_today", "liabilities"]:
            if key not in scenario:
                raise ValueError(F"Missing '{key}' in scenario")

        self.name = scenario["name"]
        self.current_balance = scenario["assets_today"]
        self.liabilities_config = scenario["liabilities"]
        self.depost = scenario.get("deposit", {})
        self.contributions = self.depost.get("monthly", 0)

        self.allocation_strategy = allocation_strategy

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
            inflation_rate = liability_config.get("inflation_rate", self.assumptions.inflation_cpi)

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
                assumptions=self.assumptions,
                allocation_strategy=self.allocation_strategy,
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
            assumptions=self.assumptions,
            allocation_strategy=self.allocation_strategy,
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

        numerators = {}
        denominator = 0.0

        if self.current_balance == 0:
            for bucket in self.required_buckets:
                weight = bucket.get_liability().present_value()
                alloc = bucket.get_allocations_by_period(0)

                for asset, asset_weight in alloc.items():
                    numerators[asset] = numerators.get(asset, 0.0) + asset_weight * weight

                denominator += weight

        else:
            for bucket in [*self.required_buckets, self.surplus_bucket]:
                weight = bucket.get_asset_balance_by_period(0)
                alloc = bucket.get_allocations_by_period(0)

                for asset, asset_weight in alloc.items():
                    numerators[asset] = numerators.get(asset, 0.0) + asset_weight * weight

                denominator += weight

        self.current_allocations = {
            asset: value / denominator
            for asset, value in numerators.items()
        }


    # def _calculate_current_asset_allocations(self):

    #     equity_numerator = 0
    #     fixed_income_numerator = 0
    #     denominator = 0 

    #     if self.current_balance == 0:

    #         for bucket in self.required_buckets:
    #             equity_numerator += bucket.get_equity_allocation_by_period(0) * bucket.get_liability().present_value()
    #             fixed_income_numerator += bucket.get_fixed_income_allocation_by_period(0) * bucket.get_liability().present_value()
    #         denominator = self.present_value

    #     else:
    #         for bucket in [*self.required_buckets, self.surplus_bucket]:
    #             equity_numerator += bucket.get_equity_allocation_by_period(0) * bucket.get_asset_balance_by_period(0)
    #             fixed_income_numerator += bucket.get_fixed_income_allocation_by_period(0) * bucket.get_asset_balance_by_period(0)
    #         denominator = self.current_balance

    #     self.current_equity_allocation = equity_numerator / denominator
    #     self.current_fixed_income_allocation = fixed_income_numerator / denominator

    def result(self):

        return {
            "name": self.name,
            "assets_today": self.current_balance,
            "surplus_at_maturity": self.funded_status,
            "allocations": self.current_allocations
        }