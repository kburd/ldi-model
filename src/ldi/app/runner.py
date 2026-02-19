
import json, re, copy
from pathlib import Path
from typing import Any, Dict
import pandas as pd
from ldi.engine.allocator import GlidePath

from ldi.engine.model import LDIModel
from ldi.engine.assumptions import Assumptions

MAX_ITERATIONS = 40
TOLERANCE = 100

def run_scenario(scenario_file: Path, constants_file: Path = None, assumptions_file: Path = None):
    
    scenario = _load_scenario(scenario_file, constants_file)
    assumptions = Assumptions.from_file(assumptions_file)

    # Baseline
    result = LDIModel(
        assumptions=assumptions, 
        scenario=scenario,
        allocation_strategy=GlidePath,
    ).result()

    # Shortfall / Surplus and Contribution Calculations
    surplus_at_maturity = result["surplus_at_maturity"]
    if scenario.get("liabilities", []) != []:
        result["net_contribution_today"] = _calculate_current_balance_adjustment(assumptions, scenario, surplus_at_maturity)
        result["monthly_contribution"] = _calculate_monthly_contribution_adjustment(assumptions, scenario, surplus_at_maturity)


    return result

def _load_scenario(scenario_file: Path, constants_file: Path):

    with open(scenario_file, "r") as f:
        scenario = json.load(f)

    if constants_file is not None and constants_file.exists():
        with open(constants_file, "r") as f:
            constants = json.load(f)
    else:
        constants = {}

    scenario = _resolve_refs(scenario, constants)

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

def _calculate_current_balance_adjustment(assumptions, scenario, surplus_at_maturity):

    scenario_copy = copy.deepcopy(scenario)

    upper = scenario_copy["assets_today"] if surplus_at_maturity > 0 else -surplus_at_maturity
    lower = 0

    for idx in range(MAX_ITERATIONS):

        middle = (lower + upper) / 2

        scenario_copy["assets_today"] = middle
        scenario_copy["contributions"] = []

        result = LDIModel(
            assumptions=assumptions,
            scenario=scenario_copy,
            allocation_strategy=GlidePath
        ).result()

        if abs(result["surplus_at_maturity"]) <= TOLERANCE:
            break
        elif result["surplus_at_maturity"] > TOLERANCE:
            upper = middle
        else:
            lower = middle

    return middle - scenario["assets_today"]

def _calculate_monthly_contribution_adjustment(assumptions, scenario, surplus_at_maturity):

    end_date = scenario.get("end_date")
    if end_date == None:
        liability_config = scenario["liabilities"][0]  
        end_date = pd.Timestamp(liability_config["start_date"]) - pd.DateOffset(months=1)

    upper = max(-surplus_at_maturity, 0)
    lower = min(-surplus_at_maturity, 0)

    for idx in range(MAX_ITERATIONS):

        scenario_copy = copy.deepcopy(scenario)
        middle = (lower + upper) / 2
        
        if "contributions" not in scenario_copy:
            scenario_copy["contributions"] = []

        scenario_copy["contributions"].append({
            "type": "recurring",
            "amount": middle,
            "frequency": "monthly",
            "start_date": pd.Timestamp.today(),
            "end_date": end_date
        })
        
        result = LDIModel(
            assumptions=assumptions,
            scenario=scenario_copy,
            allocation_strategy=GlidePath
        ).result()
        
        if abs(result["surplus_at_maturity"]) <= TOLERANCE:
            break
        elif result["surplus_at_maturity"] > TOLERANCE:
            upper = middle
        else:
            lower = middle

    return middle
