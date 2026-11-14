"""Command-line interface."""

from __future__ import annotations

from pathlib import Path

import click
import pandas as pd

from prezero import ingest, locations
from prezero.features import build_features
from prezero.routing import build_route
from prezero.scoring import score_containers
from prezero.viz import plot_route, plot_trends


@click.group()
def cli() -> None:
    """PreZero Route CLI."""
    pass


@cli.command("ingest")
@click.option(
    "--input",
    "-i",
    default="data/raw/glass_fill_levels_anonymized_f.csv",
    help="Path to raw CSV.",
)
@click.option(
    "--output",
    "-o",
    default="data/processed/cleaned_readings.csv",
    help="Path to cleaned output CSV.",
)
def ingest_cmd(input: str, output: str) -> None:
    """Ingest and clean raw fill-level data."""
    df = ingest.ingest(input, output)
    click.echo(f"Cleaned data written to {output}")
    ingest.print_stats(df)


@cli.command()
@click.option("--date", required=True, help="Target date in YYYY-MM-DD format.")
@click.option("--input", "input_path", default="data/raw/glass_fill_levels_anonymized_f.csv")
@click.option("--output-dir", default="data/processed")
def score(date: str, input_path: str, output_dir: str) -> None:
    """Score containers for a target date."""
    cleaned = _read_cleaned(input_path)
    scored = _score(cleaned, date)
    destination = Path(output_dir) / f"scored_{date}.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(destination, index=False)
    click.echo(f"{int(scored['critical'].sum())} critical containers; written to {destination}")


@cli.command()
@click.option("--date", required=True, help="Target date in YYYY-MM-DD format.")
@click.option("--input", "input_path", default="data/raw/glass_fill_levels_anonymized_f.csv")
@click.option("--locations", "locations_path", default="data/external/locations.csv")
@click.option("--output-dir", default=".")
@click.option("--max-stops", default=25, show_default=True, type=click.IntRange(min=1))
def route(
    date: str,
    input_path: str,
    locations_path: str,
    output_dir: str,
    max_stops: int,
) -> None:
    """Build and write a route for a target date."""
    cleaned = _read_cleaned(input_path)
    scored = _score(cleaned, date)
    route_df = build_route(
        scored,
        locations.load_locations(locations_path),
        depot=(49.1427, 9.2108),
        max_stops=max_stops,
        date=date,
        output_dir=output_dir,
    )
    click.echo(f"{len(route_df)} stops; written to {Path(output_dir) / f'route_{date}.json'}")


@cli.command()
@click.option("--date", required=True, help="Target date in YYYY-MM-DD format.")
@click.option("--input", "input_path", default="data/raw/glass_fill_levels_anonymized_f.csv")
@click.option("--locations", "locations_path", default="data/external/locations.csv")
@click.option("--output-dir", default=".")
@click.option("--max-stops", default=25, show_default=True, type=click.IntRange(min=1))
def visualize(
    date: str,
    input_path: str,
    locations_path: str,
    output_dir: str,
    max_stops: int,
) -> None:
    """Write trend and route visualizations for a target date."""
    cleaned = _read_cleaned(input_path)
    scored = _score(cleaned, date)
    route_df = build_route(
        scored,
        locations.load_locations(locations_path),
        depot=(49.1427, 9.2108),
        max_stops=max_stops,
        date=date,
        output_dir=output_dir,
    )
    destination = Path(output_dir)
    plot_trends(cleaned, destination / "trends.png")
    plot_route(route_df, destination / f"map_{date}.html")
    click.echo(f"Visualizations written to {destination}")


@cli.command()
@click.option("--date", required=True, help="Target date in YYYY-MM-DD format.")
@click.option("--input", "input_path", default="data/raw/glass_fill_levels_anonymized_f.csv")
@click.option("--locations", "locations_path", default="data/external/locations.csv")
@click.option("--output-dir", default=".")
@click.option("--max-stops", default=25, show_default=True, type=click.IntRange(min=1))
def run(
    date: str,
    input_path: str,
    locations_path: str,
    output_dir: str,
    max_stops: int,
) -> None:
    """Run scoring, routing and visualizations end to end."""
    cleaned = _read_cleaned(input_path)
    scored = _score(cleaned, date)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    scored.to_csv(destination / f"scored_{date}.csv", index=False)
    route_df = build_route(
        scored,
        locations.load_locations(locations_path),
        depot=(49.1427, 9.2108),
        max_stops=max_stops,
        date=date,
        output_dir=destination,
    )
    plot_trends(cleaned, destination / "trends.png")
    plot_route(route_df, destination / f"map_{date}.html")
    click.echo(f"Run complete: {int(scored['critical'].sum())} critical, {len(route_df)} stops")


def _read_cleaned(input_path: str) -> pd.DataFrame:
    return ingest.clean(ingest.load_raw(input_path))


def _score(cleaned: pd.DataFrame, date: str) -> pd.DataFrame:
    return score_containers(build_features(cleaned, date))


if __name__ == "__main__":
    cli()
