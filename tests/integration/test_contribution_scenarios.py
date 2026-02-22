from pathlib import Path
import json

import pytest

from ldi.app.runner import run_scenario


@pytest.mark.xfail(strict=True, reason="Runner currently cannot instantiate LDIModel with production signature.")
def test_monthly_contributions_through_real_runner(tmp_path):
    scenario = {
        "name": "monthly-contrib",
        "assets_today": 0.0,
        "liabilities": [{"type": "one-time", "amount_today": 600.0, "start_date": "2025-07-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [{"type": "recurring", "amount": 100.0, "frequency": "monthly", "start_date": "2025-02-01", "end_date": "2025-07-01"}],
    }
    path = tmp_path / "monthly.json"
    path.write_text(json.dumps(scenario))
    result = run_scenario(path, constants_file=None, assumptions_file="base_assumptions.json")
    assert "monthly_contribution" in result
