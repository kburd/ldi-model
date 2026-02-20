# LDI Model — Discovered Project Features

This document summarizes the capabilities currently implemented in the codebase after scanning the repository.

## 1) Liability Modeling Features

- Supports **recurring liabilities** (yearly withdrawals for `duration_years`) and **one-time liabilities**.  
- Recurring liabilities are expanded into individual annual liability buckets at build time.  
- Liability values are modeled in **real terms** (inflation-adjusted discounting) over a monthly timeline.  
- End date is derived automatically from the latest liability maturity when not explicitly provided.

## 2) Contribution Modeling Features

- Supports **recurring contributions** with:
  - `monthly` frequency
  - `annual` frequency with configurable contribution month
- Supports **one-time contributions** on a specific date.
- Contributions are represented as a monthly time series and applied during the projection.
- Contribution calibration helpers can estimate:
  - **Required one-time contribution today** (`net_contribution_today`)
  - **Required recurring monthly contribution** (`monthly_contribution`)
  using iterative search to target ~fully-funded maturity outcome.

## 3) Assumptions Engine (Static + Dynamic)

- Assumptions can be configured as either:
  - **Static constants** (single numeric value), or
  - **Dynamic schedules** (`default` + dated `schedule` overrides)
- Dynamic scheduling is available for:
  - CPI inflation
  - Per-asset expected returns
- Multiple predefined macro/market stress configs are included (e.g., high inflation, lost decade, rate spike, stagflation variants).

## 4) Allocation / Portfolio Construction Features

- Uses an allocation strategy interface with a built-in **GlidePath** implementation.
- Glide path allocation is driven by:
  - Liability horizon (time-to-need)
  - Funding ratio (assets vs. present value of liabilities)
- Blends risky vs. hedging assets based on those inputs.
- Produces current aggregate portfolio allocation weights across all modeled buckets.

## 5) Bucketed Funding Mechanics

- Splits plan into:
  - **Required buckets** (mapped to liabilities)
  - **Surplus bucket** (capital above present value of liabilities)
- Required buckets can peel off surplus during projection.
- Surplus bucket aggregates surplus released from required buckets and compounds separately.
- Final funded status is expressed as projected **surplus/shortfall at maturity**.

## 6) Scenario and Config Features

- Scenario files can include constants placeholders like `${retirement.date}`.
- Runner resolves placeholders recursively using a constants file.
- CLI supports:
  - Running one or many scenario files
  - Running all files in `runs/`
  - Displaying summary and allocation tables

## 7) Output Features

Model outputs include:

- Goal/scenario name
- Assets today
- Surplus (or shortfall) at maturity
- Current asset allocation weights
- (Runner-enhanced) one-time and monthly contribution adjustments when liabilities exist

## 8) Notable Behavior Characteristics (Useful for Users)

- Projection runs on **monthly periods**.
- Liability expansion for recurring liability type is **annual payouts** (not monthly payouts).
- Annual contributions are injected only in the specified month.
- One-time contribution dates must align with the projection timeline month index.

## 9) Practical “Feature Keywords” for This Project

- Recurring liabilities
- One-time liabilities
- Monthly contributions
- Annual contributions
- One-time contributions
- Dynamic assumption schedules
- Static assumptions
- Glide path allocation
- Surplus bucket / surplus-only tracking
- Funding status / shortfall targeting
- Scenario constants templating
