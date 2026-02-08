
import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import datetime
from typing import List

from ldi.engine.assumptions import Assumptions
from ldi.engine.portfolio import SurplusBucket, RequiredBucket, Liability
from ldi.engine.allocator import AllocationStrategy

class LDIModel:

    def __init__(self, *, name: str, assumptions: Assumptions, scenario: dict, allocation_strategy: AllocationStrategy):

        self.name = name or scenario["name"]
        self.current_balance = scenario.get("assets_today", 0)
        self.liabilities_config = scenario.get("liabilities", [])
        self.contributions_config = scenario.get("contributions", [])
        self.end_date = scenario.get("end_date")

        self.assumptions = assumptions
        self.allocation_strategy = allocation_strategy
        self.valuation_date = pd.Timestamp.today().normalize()

        self.liabilities: List[Liability] = []
        self.required_buckets:List[RequiredBucket] = []
        self.surplus_bucket:SurplusBucket = None

        self._run()

    def _validate_parameters(self, name: str, assumptions: Assumptions, scenario: dict, allocation_strategy: AllocationStrategy):

        for key in ["assets_today"]:
            if key not in scenario:
                raise ValueError(F"Missing '{key}' in scenario")
            
        if "liabilities" not in scenario and "end_date" not in scenario:
            raise ValueError(F"End Date must be present in scenario if no Liabilities are provided")

    def _run(self):

        self._generate_liabilities()
        self._calculate_end_date()
        self._generate_contributions()

        self._generate_required_buckets()
        self._rebalance_surplus()

        self._calculate_funded_status()
        self._calculate_current_asset_allocations()

    def _generate_liabilities(self):

        for liability_config in self.liabilities_config:

            first_withdrawal = datetime.strptime(liability_config["start_date"], "%Y-%m-%d").date()
            withdrawal_amount = liability_config["amount_today"]

            if liability_config["type"] == "recurring":
                duration_years = liability_config["duration_years"]
            
            else:
                duration_years = 1

            for i in range(duration_years):

                liability = Liability(
                    amount=withdrawal_amount,
                    valuation_date=self.valuation_date,
                    maturity_date=pd.Timestamp(first_withdrawal + relativedelta(years=i)),
                    assumptions=self.assumptions
                )
                self.liabilities.append(liability)

        self.present_value = sum([liability.present_value() for liability in self.liabilities])
        self.current_funding_ratio = self.current_balance / self.present_value if self.present_value != 0 else None
    
    def _calculate_end_date(self):

        if self.end_date is None and len(self.liabilities) > 0:
            self.end_date = max([liability.maturity_date for liability in self.liabilities])

    def _generate_contributions(self) -> pd.Series:

        date_index = pd.date_range(
            start=self.valuation_date + pd.offsets.MonthBegin(1),         
            end=self.end_date,
            freq="MS"
        )
        ts = pd.Series(0.0, index=date_index)

        for c in self.contributions_config:
            ctype = c["type"]

            if ctype == "recurring":

                amount = float(c["amount"])
                freq = c.get("frequency", "monthly")

                start = pd.to_datetime(c.get("start_date", date_index[0]))
                end = pd.to_datetime(c.get("end_date", date_index[-1]))

                if freq == "monthly":
                    mask = (ts.index >= start) & (ts.index <= end)
                    ts.loc[mask] += amount

                elif freq == "annual":
                    month = int(c.get("month", 1))
                    mask = (
                        (ts.index >= start)
                        & (ts.index <= end)
                        & (ts.index.month == month)
                    )
                    ts.loc[mask] += amount

                else:
                    raise ValueError(f"Unsupported frequency: {freq}")

            elif ctype == "one_time":
                date = pd.to_datetime(c["date"])
                if date not in ts.index:
                    raise ValueError(f"One-time contribution date {date} not in timeline")
                ts.loc[date] += float(c["amount"])

            else:
                raise ValueError(f"Unknown contribution type: {ctype}")

        self.contributions = ts

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

        if len(self.required_buckets) == 0:
            contributions = 0
        else:
            contributions = pd.concat(
                [bucket.get_surplus_series() for bucket in self.required_buckets],
                axis=1
            ).fillna(0).sum(axis=1)

        self.surplus_bucket = SurplusBucket(
            name="surplus",
            amount=surplus_capital,
            valuation_date=self.valuation_date,
            end_date=self.end_date,
            assumptions=self.assumptions,
            allocation_strategy=self.allocation_strategy,
            contributions=contributions
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

    def result(self):

        return {
            "name": self.name,
            "assets_today": self.current_balance,
            "surplus_at_maturity": self.funded_status,
            "allocations": self.current_allocations
        }