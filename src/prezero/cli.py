"""Command-line interface for GlasRoute / PreZero Route."""

from __future__ import annotations

from pathlib import Path

import click
import pandas as pd

from prezero import features, ingest, locations, routing, scoring, viz


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


@cli.command("score")
@click.option("--date", "-d", required=True, help="Target date (YYYY-MM-DD).")
@click.option(
    "--input",
    "-i",
    default="data/processed/cleaned_readings.csv",
    help="Path to cleaned readings CSV.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Path to scored CSV (default: data/processed/scored_<date>.csv).",
)
def score_cmd(date: str, input: str, output: str | None) -> None:
    """Build features and compute criticality scores up to --date."""
    df = pd.read_csv(input, parse_dates=["date"], dtype={"Location_id": str, "material_type": str})
    feat = features.build_features(df, date)
    scored = scoring.score_containers(feat)

    out_path = Path(output) if output is not None else Path("data/processed") / f"scored_{date}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    scored.to_csv(out_path, index=False)

    crit = scored[scored["critical"]]
    click.echo(
        f"Scored {len(scored)} container-material pairs ({crit['Location_id'].nunique()} "
        f"critical locations, {len(crit)} critical pairs) -> {out_path}"
    )


@cli.command("route")
@click.option("--date", "-d", required=True, help="Target date (YYYY-MM-DD).")
@click.option(
    "--scored",
    default=None,
    help="Path to scored CSV (default: data/processed/scored_<date>.csv).",
)
@click.option(
    "--locations",
    "locations_path",
    default="data/external/locations.csv",
    help="Path to canonical locations CSV.",
)
@click.option("--max-stops", default=25, show_default=True, type=int, help="Maximum stops.")
@click.option("--output-dir", default=".", show_default=True, help="Directory for route_<date>.json.")
def route_cmd(
    date: str,
    scored: str | None,
    locations_path: str,
    max_stops: int,
    output_dir: str,
) -> None:
    """Build nearest-neighbor collection route and write route_<date>.json."""
    scored_path = Path(scored) if scored is not None else Path("data/processed") / f"scored_{date}.csv"
    scored_df = pd.read_csv(scored_path, dtype={"Location_id": str, "material_type": str})
    locs_df = locations.load_locations(locations_path)
    route_data = routing.build_route(
        scored_df,
        locs_df,
        depot=routing.DEFAULT_DEPOT,
        max_stops=max_stops,
        date=date,
        output_dir=output_dir,
    )
    click.echo(f"Route written to {Path(output_dir) / f'route_{date}.json'}")
    click.echo(route_data["comparison"])


@cli.command("visualize")
@click.option("--date", "-d", default="2026-04-15", show_default=True, help="Target date (YYYY-MM-DD).")
@click.option(
    "--readings",
    default="data/processed/cleaned_readings.csv",
    show_default=True,
    help="Path to cleaned readings CSV.",
)
@click.option("--route", default=None, help="Path to route_<date>.json.")
@click.option("--scored", default=None, help="Optional scored CSV for background markers.")
@click.option(
    "--locations",
    "locations_path",
    default="data/external/locations.csv",
    show_default=True,
    help="Path to canonical locations CSV.",
)
@click.option("--output-dir", default=".", show_default=True, help="Output directory for plots/maps.")
def visualize_cmd(
    date: str,
    readings: str,
    route: str | None,
    scored: str | None,
    locations_path: str,
    output_dir: str,
) -> None:
    """Generate trends.png and map_<date>.html."""
    out_dir = Path(output_dir)
    readings_df = pd.read_csv(readings, parse_dates=["date"], dtype={"Location_id": str, "material_type": str})
    trends_path = viz.plot_trends(readings_df, out_dir / "trends.png")

    route_path = Path(route) if route is not None else out_dir / f"route_{date}.json"
    scored_path = Path(scored) if scored is not None else Path("data/processed") / f"scored_{date}.csv"
    scored_df = (
        pd.read_csv(scored_path, dtype={"Location_id": str, "material_type": str})
        if scored_path.is_file()
        else None
    )
    locs_df = locations.load_locations(locations_path) if Path(locations_path).is_file() else None
    map_path = viz.plot_route(
        route_path,
        out_dir / f"map_{date}.html",
        scored=scored_df,
        locations=locs_df,
    )
    click.echo(f"Visualizations written: {trends_path}, {map_path}")


@cli.command("run")
@click.option("--date", "-d", default="2026-04-15", show_default=True, help="Target date (YYYY-MM-DD).")
@click.option(
    "--raw",
    default="data/raw/glass_fill_levels_anonymized_f.csv",
    show_default=True,
    help="Path to raw fill-level CSV.",
)
@click.option(
    "--cleaned",
    default="data/processed/cleaned_readings.csv",
    show_default=True,
    help="Path to cleaned readings CSV.",
)
@click.option(
    "--locations",
    "locations_path",
    default="data/external/locations.csv",
    show_default=True,
    help="Path to canonical locations CSV.",
)
@click.option("--max-stops", default=25, show_default=True, type=int, help="Maximum stops.")
@click.option("--output-dir", default=".", show_default=True, help="Output directory for artifacts.")
def run_cmd(
    date: str,
    raw: str,
    cleaned: str,
    locations_path: str,
    max_stops: int,
    output_dir: str,
) -> None:
    """Run the full pipeline: ingest -> features -> score -> route -> visualize."""
    out_dir = Path(output_dir)
    cleaned_df = ingest.ingest(raw, cleaned)
    feat_df = features.build_features(cleaned_df, date)
    scored_df = scoring.score_containers(feat_df)

    scored_out = Path(cleaned).parent / f"scored_{date}.csv"
    scored_out.parent.mkdir(parents=True, exist_ok=True)
    scored_df.to_csv(scored_out, index=False)

    locs_df = locations.load_locations(locations_path)
    route_data = routing.build_route(
        scored_df,
        locs_df,
        depot=routing.DEFAULT_DEPOT,
        max_stops=max_stops,
        date=date,
        output_dir=out_dir,
    )
    trends_path = viz.plot_trends(cleaned_df, out_dir / "trends.png")
    map_path = viz.plot_route(
        route_data,
        out_dir / f"map_{date}.html",
        scored=scored_df,
        locations=locs_df,
    )

    crit = scored_df[scored_df["critical"]]
    click.echo(
        f"Pipeline complete for {date}: {crit['Location_id'].nunique()} critical locations "
        f"({len(crit)} pairs)."
    )
    click.echo(route_data["comparison"])
    click.echo(
        f"Outputs: {out_dir / f'route_{date}.json'}, {map_path}, {trends_path}"
    )


if __name__ == "__main__":
    cli()
