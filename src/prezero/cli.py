"""Command-line interface."""

from __future__ import annotations

from pathlib import Path

import click

from prezero import ingest


@click.group()
def cli() -> None:
    """PreZero Route CLI."""
    pass


@cli.command()
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


if __name__ == "__main__":
    cli()
