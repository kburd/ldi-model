
import json, re, copy
from pathlib import Path
from typing import Any, Dict
import pandas as pd
from ldi.engine.allocator import GlidePath

from ldi.engine.model import LDIModel
from ldi.engine.assumptions import load_assumptions_from_path

MAX_ITERATIONS = 40
TOLERANCE = 100

def run_scenario(scenario_file: Path, constants_file: Path = None):
    
    scenario = _load_scenario(scenario_file, constants_file)
    assumptions = load_assumptions_from_path()

    # Base Line
    result = LDIModel(
        assumptions=assumptions, 
        scenario=scenario,
        allocation_strategy=GlidePath,
    ).result()

    # Shortfall / Surplus and Contribution Calculations
    result["net_contribution_today"] = _calculate_current_balance_adjustment(assumptions, scenario)
    result["monthly_contribution"] = 0 if result["surplus_at_maturity"] > 0 else _calculate_monthly_contribution_adjustment(assumptions, scenario)

    return result

def _load_scenario(scenario_file: Path, constants_file: Path):

    # Load scenario JSON
    with open(scenario_file, "r") as f:
        scenario = json.load(f)

    # Load constants if provided
    if constants_file is not None and constants_file.exists():
        with open(constants_file, "r") as f:
            constants = json.load(f)
    else:
        constants = {}

    # Recursively resolve constants in the scenario
    scenario = _resolve_refs(scenario, constants)

    # Now scenario is fully populated and ready to pass to the model
    return scenario

def _resolve_refs(obj: Any, constants: Dict[str, Any]) -> Any:
    """Recursively replace ${constant.path} in the scenario dict, preserving types."""
    if isinstance(obj, dict):
        return {k: _resolve_refs(v, constants) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_refs(v, constants) for v in obj]
    if isinstance(obj, str):
        pattern = re.compile(r"\$\{([\w\.]+)\}")

        # If the entire string is a placeholder, return the actual type
        match_entire = pattern.fullmatch(obj)
        if match_entire:
            return constants.get(match_entire.group(1), obj)

        # Otherwise, replace placeholders inside a string
        def replacer(m):
            return str(constants.get(m.group(1), m.group(0)))

        return pattern.sub(replacer, obj)

    return obj

def _calculate_current_balance_adjustment(assumptions, scenario):

    scenario_copy = copy.deepcopy(scenario)

    liability_config = scenario["liabilities"][0]

    start = pd.Timestamp(liability_config["start_date"])
    duration_years = liability_config.get("duration_years", 1)
    amount_today = liability_config["amount_today"]
    inflation = liability_config.get("inflation", assumptions.inflation_cpi)

    maturity = start + pd.DateOffset(years=duration_years)
    first_cashflow = pd.Timestamp.today() + pd.offsets.MonthBegin(1)

    horizon = (
        (maturity.year - first_cashflow.year)
        + (maturity.month - first_cashflow.month) / 12
    )

    upper = len(scenario["liabilities"]) * amount_today * duration_years * (1 + inflation) ** horizon
    lower = 0

    for idx in range(MAX_ITERATIONS):

        middle = (lower + upper) / 2
        scenario_copy["assets_today"] = middle


        result = LDIModel(
            assumptions=assumptions,
            scenario=scenario_copy,
            allocation_strategy=GlidePath
        ).result()
        
        if result["surplus_at_maturity"] <= 0:
            lower = middle
        elif result["surplus_at_maturity"] > TOLERANCE:
            upper = middle
        else:
            break

    return middle - scenario["assets_today"]  

def _calculate_monthly_contribution_adjustment(assumptions, scenario):

    if "deposit" not in scenario:
        scenario["deposit"] = {
            "monthly": 0
        }

    scenario_copy = copy.deepcopy(scenario)

    liability_config = scenario["liabilities"][0]

    start = pd.Timestamp(liability_config["start_date"])
    window = liability_config.get("duration_years", 1)
    amount_today = liability_config["amount_today"]
    inflation = liability_config.get("inflation", assumptions.inflation_cpi)

    maturity = start + pd.DateOffset(years=window)
    first_cashflow = pd.Timestamp.today() + pd.offsets.MonthBegin(1)

    horizon = (
        (maturity.year - first_cashflow.year)
        + (maturity.month - first_cashflow.month) / 12
    )

    upper = (len(scenario["liabilities"]) * amount_today * window * (1 + inflation) ** horizon) / horizon
    lower = 0

    for idx in range(MAX_ITERATIONS):

        middle = (lower + upper) / 2
        scenario_copy["deposit"]["monthly"] = middle

        result = LDIModel(
            assumptions=assumptions,
            scenario=scenario_copy,
            allocation_strategy=GlidePath
        ).result()
        
        if result["surplus_at_maturity"] <= 0:
            lower = middle
        elif result["surplus_at_maturity"] > TOLERANCE:
            upper = middle
        else:
            break

    return middle - scenario["deposit"]["monthly"] 
