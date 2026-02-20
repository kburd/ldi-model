import pandas as pd
import pytest

from ldi.engine.assumptions import Assumptions


def test_from_dict_parses_defaults_and_schedules():
    assumptions = Assumptions.from_dict(
        {
            "inflation_cpi": {
                "default": 0.03,
                "schedule": [
                    {"start": "2030-01-01", "end": "2030-12-01", "value": 0.05}
                ],
            },
            "assets": {
                "us_equity_total_market": 0.08,
                "us_nominal_treasury_long": {
                    "default": 0.04,
                    "schedule": [
                        {"start": "2030-01-01", "end": "2030-06-01", "value": 0.02}
                    ],
                },
            },
        }
    )

    in_schedule = pd.Timestamp("2030-03-01")
    out_schedule = pd.Timestamp("2031-03-01")

    assert assumptions.inflation_cpi(in_schedule) == pytest.approx(0.05)
    assert assumptions.inflation_cpi(out_schedule) == pytest.approx(0.03)

    assert assumptions.asset_returns(in_schedule)["us_nominal_treasury_long"] == pytest.approx(0.02)
    assert assumptions.asset_returns(out_schedule)["us_nominal_treasury_long"] == pytest.approx(0.04)


def test_parse_field_rejects_invalid_type():
    with pytest.raises(TypeError):
        Assumptions._parse_field("0.03")


def test_from_file_loads_base_assumptions():
    assumptions = Assumptions.from_file("base_assumptions.json")
    returns = assumptions.asset_returns(pd.Timestamp("2028-01-01"))

    assert assumptions.inflation_cpi(pd.Timestamp("2028-01-01")) == pytest.approx(0.03)
    assert returns["us_equity_total_market"] == pytest.approx(0.08)


def test_parse_field_accepts_numeric_values():
    default, schedule = Assumptions._parse_field(3)

    assert default == pytest.approx(3.0)
    assert schedule == []


def test_lookup_returns_default_when_date_not_in_schedule():
    schedule = [
        (pd.Timestamp("2030-01-01"), pd.Timestamp("2030-01-31"), 0.07),
    ]

    assert Assumptions._lookup(pd.Timestamp("2029-12-01"), 0.03, schedule) == pytest.approx(0.03)


def test_from_file_raises_for_missing_file():
    with pytest.raises(FileNotFoundError):
        Assumptions.from_file("does_not_exist.json")
