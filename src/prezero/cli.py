"""Command-line interface for GlasRoute / PreZero Route."""

from __future__ import annotations

import json
from pathlib import Path

import click
import pandas as pd

from prezero import approval, features, forecast, ingest, locations, routing, scoring, viz
from prezero.heatmap import END_DATE, START_DATE, build_heatmap_matrix
from prezero.model import build_model


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
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    help="Path to YAML/JSON operational config.",
)
@click.option("--output-dir", default=".", show_default=True, help="Directory for route_<date>.json.")
def route_cmd(
    date: str,
    scored: str | None,
    locations_path: str,
    max_stops: int,
    config_path: str | None,
    output_dir: str,
) -> None:
    """Build nearest-neighbor collection route and write route_<date>.json."""
    scored_path = Path(scored) if scored is not None else Path("data/processed") / f"scored_{date}.csv"
    scored_df = pd.read_csv(scored_path, dtype={"Location_id": str, "material_type": str})
    locs_df = locations.load_locations(locations_path)
    cfg = routing.load_config(config_path)
    route_data = routing.build_route(
        scored_df,
        locs_df,
        depot=cfg.yard_depot,
        max_stops=max_stops,
        date=date,
        output_dir=output_dir,
        config=cfg,
    )
    click.echo(routing.format_route_summary(route_data))


@cli.command("forecast")
@click.option("--date", "-d", required=True, help="Base date (YYYY-MM-DD).")
@click.option(
    "--scored",
    default=None,
    help="Path to scored_<date>.csv. Defaults to data/processed/scored_<date>.csv.",
)
@click.option(
    "--locations",
    "locations_path",
    default="data/external/locations.csv",
    show_default=True,
    help="Path to canonical locations CSV.",
)
@click.option("--output-dir", default=".", show_default=True, help="Directory for the map HTML.")
def forecast_cmd(
    date: str,
    scored: str | None,
    locations_path: str,
    output_dir: str,
) -> None:
    """Print the +0/+7/+14/+21 day forecast and write a forecast-only map.

    The forecast reuses the columns already computed by the pipeline
    (last_fill_level, avg_daily_increase, season_factor); no new model.
    """
    out_dir = Path(output_dir)
    scored_path = Path(scored) if scored else out_dir / "data" / "processed" / f"scored_{date}.csv"
    if not scored_path.is_file():
        scored_path = Path("data/processed") / f"scored_{date}.csv"
    if not scored_path.is_file():
        raise click.ClickException(
            f"Scored data missing: {scored_path}. Run 'prezero-route run --date {date}' first."
        )

    scored_df = pd.read_csv(scored_path, dtype={"Location_id": str, "material_type": str})
    locs_df = locations.load_locations(locations_path)

    forecast_df = forecast.forecast_from_scored(scored_df, date)
    for offset in forecast.FORECAST_OFFSETS:
        frame = forecast_df[forecast_df["offset_days"] == offset]
        target = pd.Timestamp(date) + pd.Timedelta(days=offset)
        counts = frame["status"].value_counts()
        click.echo(
            f"KW {int(target.isocalendar().week)}: "
            f"{int(counts.get('red', 0))} rot, {int(counts.get('black', 0))} schwarz"
        )

    map_frame = forecast_df.merge(
        locs_df[["Location_id", "lat", "lon", "source", "confidence"]],
        on="Location_id",
        how="left",
    )
    map_frame = map_frame.rename(
        columns={
            "Location_id": "location_id",
            "material_type": "material",
            "last_fill_level": "last_fill",
        }
    )
    map_frame["week"] = pd.to_datetime(map_frame["target_date"]).dt.isocalendar().week.astype(int)
    map_path = out_dir / f"forecast_{int(pd.Timestamp(date).isocalendar().week):02d}.html"
    path = viz.plot_forecast_map(map_frame, int(pd.Timestamp(date).isocalendar().week), map_path)
    click.echo(f"Forecast map: {path}")


@cli.command("heatmap")
@click.option("--date", "-d", required=True, help="Week to summarize (YYYY-MM-DD).")
@click.option(
    "--input",
    "readings",
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
@click.option("--output-dir", default=".", show_default=True, help="Directory for heatmap.html.")
def heatmap_cmd(date: str, readings: str, locations_path: str, output_dir: str) -> None:
    """Write the offline data-only container heatmap."""
    selected_date = pd.Timestamp(date)
    if selected_date < START_DATE or selected_date > END_DATE:
        raise click.ClickException(f"--date must be between {START_DATE.date()} and {END_DATE.date()}.")
    readings_df = pd.read_csv(
        readings,
        parse_dates=["date"],
        dtype={"Location_id": str, "material_type": str},
    )
    locations_df = locations.load_locations(locations_path)
    matrix = build_heatmap_matrix(build_model(readings_df, locations_df), START_DATE, END_DATE)
    week_starts = [pd.Timestamp(value) for value in matrix.attrs["week_starts"]]
    selected_index = next(
        index
        for index, week_start in enumerate(week_starts)
        if week_start <= selected_date <= week_start + pd.Timedelta(days=6)
    )
    label = matrix.attrs["week_labels"][selected_index]
    values = matrix.iloc[:, selected_index]
    predicted = matrix.attrs["predicted"].iloc[:, selected_index]
    statuses = values.map(viz._heatmap_status)
    click.echo(
        f"KW {int(week_starts[selected_index].isocalendar().week)}: "
        f"{int((statuses == 'red').sum())} rot, "
        f"{int((statuses == 'black').sum())} schwarz, "
        f"{int((~predicted).sum())} gemessen / {int(predicted.sum())} prognostiziert"
    )
    output = Path(output_dir) / "heatmap.html"
    path = viz.plot_heatmap(matrix, output, selected_week=label)
    click.echo(f"Heatmap: {path}")


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
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    help="Path to YAML/JSON operational config.",
)
@click.option("--output-dir", default=".", show_default=True, help="Output directory for artifacts.")
def run_cmd(
    date: str,
    raw: str,
    cleaned: str,
    locations_path: str,
    max_stops: int,
    config_path: str | None,
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
    cfg = routing.load_config(config_path)
    route_data = routing.build_route(
        scored_df,
        locs_df,
        depot=cfg.yard_depot,
        max_stops=max_stops,
        date=date,
        output_dir=out_dir,
        config=cfg,
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


@cli.command("propose")
@click.option(
    "--route",
    "-r",
    default=None,
    help="Path to route_<date>.json. Defaults to the most recent route file.",
)
@click.option(
    "--output",
    "-o",
    default="data/processed/proposal.json",
    show_default=True,
    help="Where the proposal is written.",
)
def propose_cmd(route: str | None, output: str) -> None:
    """Turn a computed route into a proposal awaiting dispatcher approval."""
    route_path = Path(route) if route else _latest_route_file()
    payload = json.loads(route_path.read_text(encoding="utf-8"))
    proposal = approval.propose_route(payload)
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    click.echo(approval.format_proposal_summary(proposal))
    click.echo(f"Proposal written to {out_path}")
    click.echo("Nothing is dispatched until a dispatcher approves it.")


@cli.command("approve")
@click.option(
    "--proposal",
    "-p",
    default="data/processed/proposal.json",
    show_default=True,
    help="Path to the proposal file.",
)
@click.option(
    "--by",
    "approved_by",
    default="dispatcher",
    show_default=True,
    help="Who takes the decision.",
)
@click.option(
    "--reject",
    "reason",
    default=None,
    help="Reject the proposal with this reason instead of approving it.",
)
@click.option(
    "--output-dir",
    default="data/processed",
    show_default=True,
    help="Directory for the approval record.",
)
def approve_cmd(
    proposal: str,
    approved_by: str,
    reason: str | None,
    output_dir: str,
) -> None:
    """Approve or reject a proposed route and record the decision."""
    loaded = approval.load_proposal(proposal)
    if reason:
        record = approval.rejection_record(
            loaded,
            rejected_by=approved_by,
            reason=reason,
            output_dir=output_dir,
        )
        click.echo(f"Proposal rejected by {approved_by}: {reason}")
    else:
        record = approval.approve_route(
            loaded,
            approved_by=approved_by,
            output_dir=output_dir,
        )
        click.echo(f"Route approved by {approved_by}")
    click.echo(f"Record written to {record['record_path']}")
    click.echo(approval.format_proposal_summary(record))


@cli.command("ui")
@click.option("--date", "-d", default="2026-04-15", show_default=True, help="Target date (YYYY-MM-DD).")
@click.option(
    "--readings",
    default="data/processed/cleaned_readings.csv",
    show_default=True,
    help="Path to cleaned readings CSV.",
)
@click.option(
    "--scored",
    default=None,
    help="Path to scored_<date>.csv. Defaults to data/processed/scored_<date>.csv.",
)
@click.option(
    "--locations",
    "locations_path",
    default="data/external/locations.csv",
    show_default=True,
    help="Path to canonical locations CSV.",
)
@click.option(
    "--route",
    default=None,
    help="Path to route_<date>.json. Defaults to route_<date>.json in the output dir.",
)
@click.option("--output-dir", default=".", show_default=True, help="Directory for ui_<date>.html.")
def ui_cmd(
    date: str,
    readings: str,
    scored: str | None,
    locations_path: str,
    route: str | None,
    output_dir: str,
) -> None:
    """Build the 4-view local HTML UI (ui_<date>.html) from verifiable pipeline outputs."""
    out_dir = Path(output_dir)
    readings_path = Path(readings)
    if not readings_path.is_file():
        raise click.ClickException(f"Readings CSV not found: {readings_path}")

    readings_df = pd.read_csv(
        readings_path,
        parse_dates=["date"],
        dtype={"Location_id": str, "material_type": str},
    )
    locs_df = locations.load_locations(locations_path)

    scored_df: pd.DataFrame | None = None
    scored_candidates = (
        [Path(scored)]
        if scored is not None
        else [out_dir / "data" / "processed" / f"scored_{date}.csv", Path("data/processed") / f"scored_{date}.csv"]
    )
    for candidate in scored_candidates:
        if candidate.is_file():
            scored_df = pd.read_csv(candidate, dtype={"Location_id": str, "material_type": str})
            break
    if scored_df is None:
        feat_df = features.build_features(readings_df, date)
        scored_df = scoring.score_containers(feat_df)

    route_data: dict | None = None
    route_candidates = (
        [Path(route)]
        if route is not None
        else [out_dir / f"route_{date}.json", Path(f"route_{date}.json")]
    )
    for candidate in route_candidates:
        if candidate.is_file():
            route_data = json.loads(candidate.read_text(encoding="utf-8"))
            break
    if route_data is None:
        cfg = routing.load_config()
        route_data = routing.build_route(
            scored_df,
            locs_df,
            depot=cfg.yard_depot,
            date=date,
            output_dir=out_dir,
            config=cfg,
        )

    trends_candidate = out_dir / "trends.png"
    out_path = viz.build_ui(
        date=date,
        readings_df=readings_df,
        scored_df=scored_df,
        locations_df=locs_df,
        route_data=route_data,
        output_path=out_dir / f"ui_{date}.html",
        trends_path=trends_candidate if trends_candidate.is_file() else None,
    )
    click.echo(f"UI written: {out_path}")


def _latest_route_file() -> Path:
    """Find the newest route_<date>.json in the working directory."""
    candidates = sorted(Path(".").glob("route_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise click.ClickException("No route file found. Run 'prezero-route route' first.")
    return candidates[-1]


if __name__ == "__main__":
    cli()
