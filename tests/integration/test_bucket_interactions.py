import pytest

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions
from ldi.engine.model import LDIModel


@pytest.mark.xfail(strict=True, reason="Current LDIModel liability wiring prevents real bucket interaction execution.")
def test_surplus_peeling_with_real_model():
    assumptions = Assumptions.from_file("base_assumptions.json")
    scenario = {
        "name": "peeling",
        "assets_today": 500.0,
        "liabilities": [{"type": "one-time", "amount_today": 100.0, "start_date": "2025-03-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [],
    }

    result = LDIModel(name="peeling", assumptions=assumptions, scenario=scenario, allocation_strategy=GlidePath).result()
    assert result["surplus_at_maturity"] > 0
