import typer
from pathlib import Path
import pandas as pd
from ldi.app.runner import run_scenario

app = typer.Typer(help="LDI Monte Carlo runner CLI")

def _display_results(results):

    df = pd.DataFrame(data = results)

    dollar_columns = ["Portfolio Value (Today)", "Projected Surplus / Shortfall (At Maturity)", "Required Net Contribution (Today)", "Required Monthly Contribution"]
    for column in dollar_columns:
        df[column] = df[column].map(lambda x: f"-${abs(x):,.2f}" if x < 0 else f"${x:,.2f}")

    percent_columns = ["Equity Allocation (%)", "Fixed Income Allocation (%)"]
    for column in percent_columns:
        df[column] = (df[column] * 100).map("{:.2f}%".format)

    typer.echo()
    typer.echo(df)


@app.command()
def run(
    cmd: Path = typer.Argument(None),
    files: list[Path] = typer.Option(None, "--file", "-f", help="Scenario JSON file(s)"),
    all_runs: bool = typer.Option(False, "--all", "-a", help="Run all JSONs in folder"),
    folder: Path = typer.Option(Path("runs"), "--dir", "-d", help="Folder containing scenario JSONs"),
    constants_file: Path = typer.Option(Path("runs/constants.json"), "--constants", "-c")
):
    """Run one or more LDI scenarios."""
    
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
