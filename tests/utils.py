import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from dateutil.relativedelta import relativedelta

from ldi.app import runner
from ldi.engine.assumptions import Assumptions
from ldi.engine.allocator import GlidePath
from ldi.engine.portfolio import Liability, RequiredBucket, SurplusBucket


@dataclass
class ProjectionResult:
    model_output: dict[str, Any]
    liabilities: list[Liability]
    required_buckets: list[RequiredBucket]
    surplus_bucket: SurplusBucket
    contributions: pd.Series


def fixed_assumptions(*, inflation: float = 0.03, equity: float = 0.08, intl_equity: float = 0.07, treasury: float = 0.04) -> Assumptions:
    return Assumptions.from_dict(
        {
            "inflation_cpi": inflation,
            "assets": {
                "us_equity_total_market": equity,
                "intl_equity_developed": intl_equity,
                "us_nominal_treasury_long": treasury,
            },
        }
    )


def run_model_flow(scenario: dict[str, Any], assumptions: Assumptions, *, valuation_date: str = "2025-01-01") -> ProjectionResult:
    valuation_ts = pd.Timestamp(valuation_date)

    liabilities: list[Liability] = []
    for cfg in scenario.get("liabilities", []):
        start = datetime.strptime(cfg["start_date"], "%Y-%m-%d").date()
        years = cfg.get("duration_years", 1) if cfg["type"] == "recurring" else 1
        infl = float(cfg.get("inflation_rate", assumptions.inflation_cpi(valuation_ts)))
        disc = float(cfg.get("discount_rate", assumptions.asset_returns(valuation_ts)["us_nominal_treasury_long"]))

        for i in range(years):
            liabilities.append(
                Liability(
                    amount=float(cfg["amount_today"]),
                    valuation_date=valuation_ts,
                    maturity_date=pd.Timestamp(start + relativedelta(years=i)),
                    inflation_rate=infl,
                    discount_rate=disc,
                )
            )

    if liabilities:
        end_date = max(liability.maturity_date for liability in liabilities)
    else:
        end_date = pd.Timestamp(scenario["end_date"])

    contribution_index = pd.date_range(start=valuation_ts + pd.offsets.MonthBegin(1), end=end_date, freq="MS")
    contributions = pd.Series(0.0, index=contribution_index)

    for c in scenario.get("contributions", []):
        ctype = c["type"]
        if ctype == "recurring":
            amount = float(c["amount"])
            freq = c.get("frequency", "monthly")
            start = pd.to_datetime(c.get("start_date", contribution_index[0]))
            end = pd.to_datetime(c.get("end_date", contribution_index[-1]))
            if freq == "monthly":
                mask = (contributions.index >= start) & (contributions.index <= end)
                contributions.loc[mask] += amount
            elif freq == "annual":
                month = int(c.get("month", 1))
                mask = (contributions.index >= start) & (contributions.index <= end) & (contributions.index.month == month)
                contributions.loc[mask] += amount
            else:
                raise ValueError(f"Unsupported frequency: {freq}")
        elif ctype == "one_time":
            d = pd.to_datetime(c["date"])
            if d not in contributions.index:
                raise ValueError(f"One-time contribution date {d} not in timeline")
            contributions.loc[d] += float(c["amount"])
        else:
            raise ValueError(f"Unknown contribution type: {ctype}")

    current_balance = float(scenario.get("assets_today", 0.0))
    pv_total = sum(liability.get_pv_remaining_by_period(0) for liability in liabilities)
    required_capital = min(current_balance, pv_total)

    required_buckets: list[RequiredBucket] = []
    if liabilities:
        contributions_per_bucket = contributions / len(liabilities)
        for liability in liabilities:
            bucket_assets = required_capital * liability.get_pv_remaining_by_period(0) / pv_total
            required_buckets.append(
                RequiredBucket(
                    name=str(liability.maturity_date.date()),
                    amount=bucket_assets,
                    liability=liability,
                    assumptions=assumptions,
                    allocation_strategy=GlidePath,
                    contributions=contributions_per_bucket,
                )
            )

    surplus_contrib = 0.0 if not required_buckets else pd.concat([b.get_surplus_series() for b in required_buckets], axis=1).fillna(0).sum(axis=1)
    surplus_bucket = SurplusBucket(
        name="surplus",
        amount=max(0.0, current_balance - pv_total),
        valuation_date=valuation_ts,
        end_date=end_date,
        assumptions=assumptions,
        allocation_strategy=GlidePath,
        contributions=surplus_contrib,
    )

    surplus = surplus_bucket.get_asset_balance_by_period(-1)
    shortfall = sum(max(0.0, liability.get_pv_remaining_by_period(-1) - bucket.get_asset_balance_by_period(-1)) for liability, bucket in zip(liabilities, required_buckets))
    funded_status = surplus if surplus > 0 else -shortfall

    numerators: dict[str, float] = {}
    denominator = 0.0
    all_buckets = [*required_buckets, surplus_bucket]
    for bucket in all_buckets:
        weight = bucket.get_asset_balance_by_period(0) if current_balance != 0 else bucket.get_liability().get_pv_remaining_by_period(0)
        alloc = bucket.get_allocations_by_period(0)
        for asset, aw in alloc.items():
            numerators[asset] = numerators.get(asset, 0.0) + aw * weight
        denominator += weight
    allocations = {asset: val / denominator for asset, val in numerators.items()} if denominator else {}

    return ProjectionResult(
        model_output={
            "name": scenario.get("name", "scenario"),
            "assets_today": current_balance,
            "surplus_at_maturity": funded_status,
            "allocations": allocations,
            "bucket_balances": {
                **{str(i): b.get_asset_balance_by_period(-1) for i, b in enumerate(required_buckets)},
                "surplus": surplus_bucket.get_asset_balance_by_period(-1),
            },
            "funding_ratio": (current_balance / pv_total) if pv_total else None,
        },
        liabilities=liabilities,
        required_buckets=required_buckets,
        surplus_bucket=surplus_bucket,
        contributions=contributions,
    )


def assert_structural_invariants(output: dict[str, Any], *, allow_negative_required: bool = True) -> None:
    allocations = output["allocations"]
    assert sum(allocations.values()) == pytest.approx(1.0, abs=1e-9)
    assert all(np.isfinite(v) for v in allocations.values())
    assert all(v >= 0 for v in allocations.values())

    balances = output["bucket_balances"]
    assert all(np.isfinite(v) for v in balances.values())
    if not allow_negative_required:
        for k, v in balances.items():
            if k != "surplus":
                assert v >= -1e-8

    assert np.isfinite(output["surplus_at_maturity"])


def assert_json_like_close(actual: Any, expected: Any, *, atol: float = 1e-6, path: str = "root") -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"Type mismatch at {path}"
        assert set(actual.keys()) == set(expected.keys()), f"Key mismatch at {path}"
        for key in expected:
            assert_json_like_close(actual[key], expected[key], atol=atol, path=f"{path}.{key}")
        return

    if isinstance(expected, list):
        assert isinstance(actual, list), f"Type mismatch at {path}"
        assert len(actual) == len(expected), f"Length mismatch at {path}"
        for idx, (a, e) in enumerate(zip(actual, expected)):
            assert_json_like_close(a, e, atol=atol, path=f"{path}[{idx}]")
        return

    if isinstance(expected, (float, int)):
        assert actual == pytest.approx(float(expected), abs=atol), f"Float mismatch at {path}"
        return

    assert actual == expected, f"Value mismatch at {path}"


def write_snapshot(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def load_scenario_with_runner(scenario_file: Path) -> dict[str, Any]:
    return runner._load_scenario(scenario_file, Path("runs/constants.json"))
