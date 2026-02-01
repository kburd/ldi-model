import typer
from pathlib import Path
import pandas as pd
from ldi.app.runner import run_scenario

app = typer.Typer(help="LDI Monte Carlo runner CLI")

import pandas as pd


def _build_result_dfs(results):

    summary_rows = []
    allocation_rows = []

    for result in results:
        name = result["name"]

        summary = {
            k: v
            for k, v in result.items()
            if k not in {"allocations"}
        }
        summary_rows.append(summary)

        for asset, weight in result.get("allocations", {}).items():
            allocation_rows.append({
                "name": name,
                "asset": asset,
                "allocation": weight,
            })

    summary_df = pd.DataFrame(summary_rows)
    allocation_df = pd.DataFrame(allocation_rows)

    return summary_df, allocation_df

def _format_dollars(x):
    return f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}"

def _display_results(results):

    DOLLAR_COLUMNS = {
        "assets_today",
        "surplus_at_maturity",
        "net_contribution_today",
        "monthly_contribution",
    }

    summary_df, allocation_df = _build_result_dfs(results)

    for col in DOLLAR_COLUMNS & set(summary_df.columns):
        summary_df[col] = summary_df[col].map(_format_dollars)

    allocation_df["allocation"] = allocation_df["allocation"].map(
        lambda x: f"{x * 100:.1f}%"
    )
    allocation_df = allocation_df.pivot(
        index="name",
        columns="asset",
        values="allocation",
    ).fillna(0.0)
    allocation_df.columns.name = None
    allocation_df = allocation_df.reset_index()

    typer.echo()
    typer.echo("Summary")
    typer.echo("=======")
    typer.echo(summary_df)

    typer.echo()
    typer.echo("Allocations")
    typer.echo("===========")
    typer.echo(allocation_df)

@app.command()
def run(
    cmd: Path = typer.Argument(None),
    files: list[Path] = typer.Option(None, "--file", "-f", help="Scenario JSON file(s)"),
    all_runs: bool = typer.Option(False, "--all", "-a", help="Run all JSONs in folder"),
    constants_file: Path = typer.Option(Path("runs/constants.json"), "--constants", "-c")
):
    """Run one or more LDI scenarios."""

    folder = Path("runs")
    
    if all_runs:
        scenario_files = [f for f in folder.glob("*.json") if f.name != "constants.json"]
        if not scenario_files:
            typer.echo(f"No JSON files found in {folder}")
            raise typer.Exit(1)
    elif files:
        scenario_files = files
    else:
        typer.echo("Specify --file or --all")
        raise typer.Exit(1)

    results = []
    for fpath in scenario_files:
        typer.echo(f"Running scenario: {fpath}")
        result = run_scenario(fpath, constants_file=constants_file)
        results.append(result)
    
    _display_results(results)

if __name__ == "__main__":
    app()
