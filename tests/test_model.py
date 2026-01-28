import pytest
from ldi.engine.model import LDIModel
from ldi.engine.assumptions import Assumptions

assumptions_dict = {
    "market": {
        "discount_rate": 0.03,
        "cash_equivalent_expected_return": .03,
        "fixed_income_expected_return": .04,
        "equity_expected_return": .08,
        "cpi_inflation": .03
    }
}
assumptions = Assumptions.from_dict(assumptions_dict)

scenario = {
    "name": "Test Scenario",
    "assets_today": 100_000,
    "withdraw": {
        "start_date": "2045-08-01",
        "window": 4,
        "amount_today": 1000
    }
}

def init_happy_path():

    result = LDIModel(assumptions=assumptions, scenario=scenario).run()
    
    assert result.name == "Test Scenario"
    assert result.current_balance == 100_000

@pytest.mark.parametrize(
    "missing_key",
    ["name", "assets_today", "withdraw"]
)
def test_scenario_missing_key_raises(missing_key):

    scenario.pop(missing_key)
    
    with pytest.raises(ValueError):
        LDIModel(assumptions=assumptions, scenario=scenario).run()

@pytest.mark.parametrize(
    "missing_key",
    [
        "discount_rate",
        "cash_equivalent_expected_return",
        "fixed_income_expected_return",
        "equity_expected_return",
        "cpi_inflation"
    ]
)
def test_assumptions_missing_key_raises(missing_key):
    with pytest.raises(ValueError):
        assumptions_dict["market"].pop(missing_key)
        scenario = {"name": "Test", "assets_today": 100_000, "withdraw": 5_000}
        LDIModel(assumptions=Assumptions.from_dict(assumptions_dict), scenario=scenario).run()