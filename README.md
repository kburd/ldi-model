# LDI Model

## Overview
LDI Model is a deterministic liability-driven investing engine for projecting whether a portfolio can meet future cash obligations. The model is designed around a liability-first workflow: define liabilities, define contribution policy, apply capital market assumptions, and evaluate funded status and required funding actions.

The projection framework runs in monthly steps and tracks values in real terms. Inflation assumptions (CPI) are explicitly modeled and used to convert nominal expected returns into real expected returns during bucket-level projection. This keeps funding analysis focused on purchasing power rather than nominal balances.

Liabilities can be modeled as one-time obligations or recurring annual payouts. Recurring liabilities are expanded into individual annual maturity buckets, each with its own horizon and present value path. This enables the engine to evaluate funding adequacy against a schedule of dated obligations rather than a single terminal value.

Allocation is policy-driven via a strategy interface. The default glide path uses both funding ratio and time-to-liability to set hedge intensity, blending growth and hedging assets as funded status improves and liability horizons shorten.

The capital structure is bucketed into required capital (mapped to liabilities) and surplus capital (managed separately). Required buckets can release surplus over time; released surplus is aggregated into a dedicated surplus bucket. Final output reports projected surplus/shortfall at maturity, current allocation mix, and calibrated contribution adjustments.

## Core Design Principles
- **Liability-first modeling**: liabilities are expanded and valued before asset projection.
- **Real-term valuation**: inflation-adjusted discounting and real return projection are used throughout buckets.
- **Monthly projection resolution**: all asset and contribution mechanics are aligned to month-start periods.
- **Deterministic scenario modeling**: the engine applies explicit assumptions/schedules rather than Monte Carlo simulation.
- **Funding-ratio feedback into allocation**: allocation responds to both funded status and liability horizon.
- **Required vs surplus separation**: required buckets fund liabilities; surplus capital is tracked and compounded independently.

## Architecture

### 1. Liability Engine
- Supports two liability types in scenarios:
  - `one-time`: single maturity bucket.
  - `recurring`: expanded into one annual bucket per `duration_years`.
- Each liability bucket carries a monthly horizon and present-value-remaining series.
- Present values are tracked through time for funding-ratio and shortfall calculations.

### 2. Contribution Engine
- Supports contributions as:
  - Recurring monthly (`frequency: monthly`)
  - Recurring annual (`frequency: annual`, with contribution `month`)
  - One-time (`type: one_time`, specific `date`)
- Contributions are normalized to the monthly projection index.
- Calibration helpers run iterative search to estimate:
  - Net one-time contribution needed today (`net_contribution_today`)
  - Level recurring monthly contribution (`monthly_contribution`)
- One-time contribution dates must align to the projection timeline month index.

### 3. Assumptions Framework
- Assumptions can be static constants or date-scheduled values (`default` + `schedule`).
- CPI inflation supports date schedules.
- Asset expected returns support per-asset date schedules.
- Repository includes baseline and stress-style presets (for example high inflation, stagflation, rate spike, equity lost decade variants).

### 4. Allocation Strategy Framework
- Allocation is abstracted behind an `AllocationStrategy` interface.
- Default implementation is `GlidePath`.
- Glide path inputs:
  - `funding_ratio`
  - `horizon_months`
- Output is a deterministic set of asset weights used in bucket projection.

### 5. Bucketed Funding Mechanics
- Current assets are partitioned into:
  - **Required capital**: distributed across liability buckets by PV weight.
  - **Surplus capital**: excess above aggregate liability PV.
- Required buckets can release surplus when assets exceed PV-remaining.
- Released surplus is aggregated into a surplus bucket and projected separately.
- Final funded status combines surplus bucket ending balance and required-bucket shortfalls.

### 6. Scenario Runner & CLI
- Scenarios are JSON files in `runs/` (with optional constants file).
- Constants templating supports `${...}` placeholders resolved recursively.
- CLI can run one or multiple files, or all files in `runs/`.
- Results are rendered as:
  - Summary table (assets, surplus/shortfall, contribution calibration fields)
  - Allocation table (pivoted by scenario)

## Example Output

```text
Running scenario: runs/sample.json

Summary
=======
      name assets_today surplus_at_maturity net_contribution_today monthly_contribution
0   Sample  $100,000.00         -$42,850.00            $38,400.00             $315.00

Allocations
===========
      name intl_equity_developed us_equity_total_market us_nominal_treasury_long
0   Sample                 12.4%                  49.8%                     37.8%
```

## Example Scenario File

```yaml
name: Sample
assets_today: 100000
liabilities:
  - type: recurring
    amount_today: "${retirement.income}"
    start_date: "${retirement.date}"
    discount_rate: "${discount.rate}"
    duration_years: 30
  - type: one-time
    amount_today: 177700
    discount_rate: "${discount.rate}"
    start_date: "${retirement.date}"
contributions:
  - type: recurring
    amount: 100
    frequency: monthly
    start_date: "2025-01-01"
    end_date: "${retirement.date}"
  - type: recurring
    amount: 5000
    frequency: annual
    month: 1
    end_date: "${retirement.date}"
  - type: one_time
    amount: 20000
    date: "2030-06-01"
```

## Usage

### Installation

```bash
pip install .
```

For development:

```bash
pip install -e .
```

### CLI Commands

Show CLI help:

```bash
python -m ldi.cli --help
```

Run a single scenario file:

```bash
python -m ldi.cli run --file runs/sample.json --constants runs/constants.json
```

Run all scenarios in `runs/`:

```bash
python -m ldi.cli run --all --constants runs/constants.json
```

## Feature Summary
- Deterministic monthly LDI projection engine.
- Liability expansion for recurring annual payout streams.
- Bucket-level required/surplus capital mechanics.
- Funding-ratio/time-horizon glide path allocation policy.
- Static and scheduled macro/asset assumptions.
- Contribution schedule handling (monthly, annual, one-time).
- Contribution calibration utilities for funding-gap closure.
- Scenario templating with constants substitution and CLI batch execution.

## Non-Goals
- Monte Carlo or stochastic path simulation.
- Tax-aware household cash-flow optimization.
- Intramonth cash-flow timing or execution microstructure.
- Brokerage order routing or implementation tooling.
