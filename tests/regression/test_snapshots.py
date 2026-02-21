import json
from pathlib import Path

import pytest

from ldi.app import runner
from ldi.engine.assumptions import Assumptions
from utils import assert_json_like_close, assert_structural_invariants, run_model_flow

SNAP_DIR = Path(__file__).parent / "snapshots"
TOLERANCE = 1e-6


def _scenario_from_file(data: dict, tmp_path: Path):
    scenario_file = tmp_path / f"{data['name']}.json"
    scenario_file.write_text(json.dumps(data))
    return runner._load_scenario(scenario_file, None)


@pytest.mark.parametrize(
    "snapshot_name,assumptions_file,builder",
    [
        (
            "base_scenario.json",
            "base_assumptions.json",
            lambda tmp_path: runner._load_scenario(Path("runs/sample.json"), Path("runs/constants.json")),
        ),
        (
            "high_inflation.json",
            "high_inflation_assumptions.json",
            lambda tmp_path: _scenario_from_file(
                {
                    "name": "high-inflation",
                    "assets_today": 100000.0,
                    "liabilities": [{"type": "recurring", "amount_today": 25000.0, "start_date": "2030-01-01", "duration_years": 5, "discount_rate": 0.04, "inflation_rate": 0.08}],
                    "contributions": [{"type": "recurring", "amount": 500.0, "frequency": "monthly", "start_date": "2025-02-01", "end_date": "2029-12-01"}],
                },
                tmp_path,
            ),
        ),
        (
            "overfunded.json",
            "base_assumptions.json",
            lambda tmp_path: _scenario_from_file(
                {
                    "name": "overfunded",
                    "assets_today": 500000.0,
                    "liabilities": [{"type": "one-time", "amount_today": 100000.0, "start_date": "2032-01-01", "discount_rate": 0.04, "inflation_rate": 0.02}],
                    "contributions": [],
                },
                tmp_path,
            ),
        ),
        (
            "lost_decade.json",
            "equity_lost_decade_assumptions.json",
            lambda tmp_path: _scenario_from_file(
                {
                    "name": "lost-decade",
                    "assets_today": 150000.0,
                    "liabilities": [{"type": "recurring", "amount_today": 40000.0, "start_date": "2030-01-01", "duration_years": 8, "discount_rate": 0.04, "inflation_rate": 0.03}],
                    "contributions": [{"type": "recurring", "amount": 3000.0, "frequency": "annual", "month": 1, "start_date": "2026-01-01", "end_date": "2029-01-01"}],
                },
                tmp_path,
            ),
        ),
    ],
)
def test_regression_snapshots(snapshot_name, assumptions_file, builder, tmp_path):
    assumptions = Assumptions.from_file(assumptions_file)
    scenario = builder(tmp_path)
    actual = run_model_flow(scenario, assumptions, valuation_date="2025-01-01").model_output
    assert_structural_invariants(actual)

    expected = json.loads((SNAP_DIR / snapshot_name).read_text())
    assert_json_like_close(actual, expected, atol=TOLERANCE)
