
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path
import json


@dataclass(frozen=True)
class Assumptions:
    # Market regime
    cpi_inflation: float

    equity_expected_return: float
    fixed_income_expected_return: float
    cash_equivalent_expected_return: float

    discount_rate: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Assumptions":

        if "market" not in data:
            raise ValueError("Missing 'market' section in assumptions data")

        market = data["market"]

        required = {
            "cpi_inflation",
            "equity_expected_return",
            "fixed_income_expected_return",
            "cash_equivalent_expected_return",
            "discount_rate",
        }

        missing = required - market .keys()
        if missing:
            raise ValueError(f"Missing assumption fields: {missing}")

        return cls(
            cpi_inflation=float(market ["cpi_inflation"]),

            equity_expected_return=float(market ["equity_expected_return"]),
            fixed_income_expected_return=float(market ["fixed_income_expected_return"]),
            cash_equivalent_expected_return=float(market ["cash_equivalent_expected_return"]),

            discount_rate=float(market ["discount_rate"]),
        )

def load_assumptions_from_path(file_path: str | Path = None) -> Assumptions:
    """
    Load Assumptions from a JSON file. Defaults to 'assumptions.json'.
    """
    config_dir = Path(__file__).parent.parent / "configs"
    file_path = Path(file_path) if file_path else config_dir / "assumptions.json"

    if not file_path.exists():
        raise FileNotFoundError(f"Assumptions file not found: {file_path}")

    with open(file_path, "r") as f:
        data = json.load(f)

    return Assumptions.from_dict(data)