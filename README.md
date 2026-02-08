# LDI Model

A Python library for **liability‑driven investing (LDI) modeling**.  
This project lets you define financial goals as structured configs, simulate assets vs. liabilities over time, and compute key outputs like funding status and required contributions.

This repository contains:
- A core Python package implementing the LDI logic (`src/ldi`)  
- Example and test cases (`runs/`, `tests/`)  
- Utilities and configuration for running scenarios

## Features

- Define **assets, liabilities, and contribution schedules** in a flexible JSON/YAML config  
- Compute:
  - Portfolio value today
  - Projected surplus/shortfall at maturity
  - Required one‑time net contributions
  - Required recurring contributions
- Clear separation between model logic and formatted outputs

## Installation

Install with `pip`:

```bash
pip install .
```

or in editable mode during development:

```bash
pip install -e .
```

## Configuration

Goals are defined in JSON (or Python dict equivalent). An example goal:

```json
{
    "name": "College Savings",
    "assets_today": 0,
    "liabilities": [
        {
            "type": "recurring",
            "amount_today": 50000,
            "start_date": "2045-08-01",
            "duration_years": 4,
            "inflation_rate": 0.05
        }
    ],
    "contributions": [
        {
            "type": "recurring",
            "amount": 184.61,
            "frequency": "monthly",
            "start_date": "today"
        }
    ]
}
```

## Basic Usage

```python
from ldi.model import LDIModel

result = LDIModel(
    assumptions=assumptions,
    scenario=scenario,
    allocation_strategy=GlidePath
).result()

print(result)
```

## Output Summary

The model returns a structured result that includes:
- `name` — goal identifier
- `assets_today` — current assets
- `surplus_at_maturity` — projected surplus/shortfall
- Allocation metrics (e.g., equity, fixed income)
- Required contributions (one‑time and recurring)

Mapping from result keys to display labels is handled in your reporting/presenter layer.

## Tests

Run tests with `pytest`:

```bash
pytest
```

## Running via CLI

This project includes a command‑line interface for running LDI scenarios from config files.

After installing the package, you can invoke the CLI directly:

```bash
python -m ldi.cli run \
  --file path/to/goal/json \
  --all run/all/goals \
  --constants path/to/constants/json

## Future Work
- add unit tests
- fix liability specific inflation
- fix contributions should only go to underfunded accounts
- tax considerations
- allow configurable allocation


## License

This project is licensed under the **MIT License**.

