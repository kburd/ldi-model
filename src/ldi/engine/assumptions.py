
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path
import json


from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path
import json


@dataclass(frozen=True)
class Assumptions:
    inflation_cpi: float
    discount_rate: float
    assets: Dict[str, float]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Assumptions":
        return cls(
            inflation_cpi=float(data["inflation_cpi"]),
            discount_rate=float(data["discount_rate"]),
            assets={k: float(v) for k, v in data["assets"].items()},
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