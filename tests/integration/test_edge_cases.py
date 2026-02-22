from pathlib import Path
import json

import pytest

from ldi.app.runner import run_scenario


@pytest.mark.xfail(strict=True, reason="Runner currently cannot instantiate LDIModel with production signature.")
def test_negative_cpi_runner_flow(tmp_path):
    scenario = {
        "name": "negative-cpi",
        "assets_today": 100.0,
        "liabilities": [{"type": "one-time", "amount_today": 120.0, "start_date": "2026-01-01", "discount_rate": 0.02, "inflation_rate": -0.02}],
        "contributions": [],
    }
    path = tmp_path / "negative.json"
    path.write_text(json.dumps(scenario))
    result = run_scenario(path, constants_file=None, assumptions_file="base_assumptions.json")
    assert "allocations" in result
