from pathlib import Path

import pytest

from ldi.app.runner import run_scenario


@pytest.mark.xfail(strict=True, reason="Runner currently cannot instantiate LDIModel with production signature.")
def test_one_time_liability_real_runner_flow(tmp_path):
    scenario = {
        "name": "single-liability",
        "assets_today": 100.0,
        "liabilities": [{"type": "one-time", "amount_today": 1000.0, "start_date": "2025-04-01", "discount_rate": 0.05, "inflation_rate": 0.02}],
        "contributions": [],
    }
    scenario_file = tmp_path / "single.json"
    scenario_file.write_text(__import__("json").dumps(scenario))

    result = run_scenario(scenario_file=Path(scenario_file), constants_file=None, assumptions_file="base_assumptions.json")
    assert "surplus_at_maturity" in result
