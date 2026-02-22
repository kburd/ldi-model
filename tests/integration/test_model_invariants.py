import pytest

from ldi.engine.allocator import GlidePath
from ldi.engine.assumptions import Assumptions
from ldi.engine.model import LDIModel


@pytest.mark.xfail(strict=True, reason="Current LDIModel orchestration is broken in production wiring.")
def test_no_liability_case_executes_real_model_entrypoint():
    assumptions = Assumptions.from_dict(
        {
            "inflation_cpi": 0.0,
            "assets": {
                "us_equity_total_market": 0.06,
                "intl_equity_developed": 0.06,
                "us_nominal_treasury_long": 0.06,
            },
        }
    )
    scenario = {
        "name": "no-liability",
        "assets_today": 1000.0,
        "liabilities": [],
        "contributions": [],
        "end_date": "2025-04-01",
    }

    result = LDIModel(name="no-liability", assumptions=assumptions, scenario=scenario, allocation_strategy=GlidePath).result()
    assert result["surplus_at_maturity"] >= 0


@pytest.mark.xfail(strict=True, reason="Current LDIModel orchestration is broken in production wiring.")
def test_zero_return_zero_cpi_world_executes_real_model_entrypoint():
    assumptions = Assumptions.from_dict(
        {
            "inflation_cpi": 0.0,
            "assets": {
                "us_equity_total_market": 0.0,
                "intl_equity_developed": 0.0,
                "us_nominal_treasury_long": 0.0,
            },
        }
    )
    scenario = {
        "name": "zero-world",
        "assets_today": 1000.0,
        "liabilities": [{"type": "one-time", "amount_today": 200.0, "start_date": "2025-04-01", "discount_rate": 0.0, "inflation_rate": 0.0}],
        "contributions": [],
    }

    result = LDIModel(name="zero-world", assumptions=assumptions, scenario=scenario, allocation_strategy=GlidePath).result()
    assert result["surplus_at_maturity"] == pytest.approx(800.0)
