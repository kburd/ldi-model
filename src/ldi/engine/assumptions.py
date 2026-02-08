
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple
from pathlib import Path
import json
import pandas as pd

Schedule = List[Tuple[pd.Timestamp, pd.Timestamp, float]]

@dataclass(frozen=True)
class Assumptions:

    _infl_default: float
    _infl_schedule: Schedule

    _disc_default: float
    _disc_schedule: Schedule

    _asset_defaults: Dict[str, float]
    _asset_schedules: Dict[str, Schedule]

    # ---------- loading ----------

    @classmethod
    def from_file(cls, file_name: str | Path = None) -> "Assumptions":
        config_dir = Path(__file__).parent.parent / "configs"
        file_path = config_dir / (Path(file_name) if file_name else "assumptions.json")

        if not file_path.exists():
            raise FileNotFoundError(file_path)

        with open(file_path) as f:
            data = json.load(f)

        return cls.from_dict(data)

    @classmethod
    def _parse_field(cls, x) -> tuple[float, Schedule]:
        """
        Accepts:
          number → constant default
          {default, schedule[]} → default + overrides
        """
        if isinstance(x, (int, float)):
            return float(x), []

        if isinstance(x, dict):
            default = float(x["default"])
            sched = []
            for row in x.get("schedule", []):
                sched.append((
                    pd.Timestamp(row["start"]),
                    pd.Timestamp(row["end"]),
                    float(row["value"])
                ))
            return default, sched

        raise TypeError("Invalid assumption field format")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Assumptions":

        infl_default, infl_sched = cls._parse_field(data["inflation_cpi"])
        disc_default, disc_sched = cls._parse_field(data["discount_rate"])

        asset_defaults = {}
        asset_schedules = {}

        for name, val in data["assets"].items():
            dflt, sched = cls._parse_field(val)
            asset_defaults[name] = dflt
            asset_schedules[name] = sched

        return cls(
            _infl_default=infl_default,
            _infl_schedule=infl_sched,
            _disc_default=disc_default,
            _disc_schedule=disc_sched,
            _asset_defaults=asset_defaults,
            _asset_schedules=asset_schedules,
        )

    # ---------- lookup ----------

    @staticmethod
    def _lookup(d: pd.Timestamp, default: float, sched: Schedule) -> float:
        for start, end, value in sched:
            if start <= d <= end:
                return value
        return default

    # ---------- public interface ----------

    def inflation_cpi(self, d: pd.Timestamp) -> float:
        return self._lookup(d, self._infl_default, self._infl_schedule)

    def discount_rate(self, d: pd.Timestamp) -> float:
        return self._lookup(d, self._disc_default, self._disc_schedule)

    def asset_returns(self, d: pd.Timestamp) -> Dict[str, float]:
        return {
            name: self._lookup(d, self._asset_defaults[name], self._asset_schedules[name])
            for name in self._asset_defaults
        }

