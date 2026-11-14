"""Tests for the PreZero CLI subcommands and end-to-end run."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
import pandas as pd

from prezero import features, forecast, ingest, scoring
from prezero.cli import cli


def _stage_sample_inputs(tmp_path: Path) -> tuple[Path, Path]:
    raw_path = tmp_path / "raw.csv"
    locs_path = tmp_path / "locations.csv"
    pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L2", "L3"],
            "material_type": ["white", "white", "green", "brown"],
            "date": ["2026-01-10", "2026-04-10", "2026-04-12", "2026-03-01"],
            "fill_level_perc": ["90", "overfull", "85", "30"],
        }
    ).to_csv(raw_path, index=False)
    pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3"],
            "lat": [49.145, 49.152, 49.170],
            "lon": [9.212, 9.218, 9.230],
            "source": ["osm_heuristic", "osm_heuristic", "synthetic_placeholder"],
            "confidence": ["low", "low", "synthetic"],
            "match_reason": ["test osm", "test osm", "test synth"],
        }
    ).to_csv(locs_path, index=False)
    return raw_path, locs_path


def test_cli_run_produces_all_outputs(tmp_path: Path) -> None:
    raw_path, locs_path = _stage_sample_inputs(tmp_path)
    cleaned_path = tmp_path / "cleaned.csv"
    out_dir = tmp_path / "out"
    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "run",
            "--date",
            "2026-04-15",
            "--raw",
            str(raw_path),
            "--cleaned",
            str(cleaned_path),
            "--locations",
            str(locs_path),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert res.exit_code == 0, res.output
    route_file = out_dir / "route_2026-04-15.json"
    map_file = out_dir / "map_2026-04-15.html"
    trends_file = out_dir / "trends.png"
    assert route_file.is_file()
    assert map_file.is_file()
    assert trends_file.is_file()
    payload = json.loads(route_file.read_text(encoding="utf-8"))
    assert payload["num_stops"] >= 1


def test_feedback_csv_reimports_and_changes_forecast(tmp_path: Path) -> None:
    base = pd.DataFrame(
        {
            "Location_id": ["L1", "L1"],
            "material_type": ["white", "white"],
            "date": ["2026-04-01", "2026-04-10"],
            "fill_level_perc": ["20", "40"],
            "geleert": [True, True],
        }
    )
    feedback = pd.DataFrame(
        {
            "Location_id": ["L1"],
            "material_type": ["white"],
            "date": ["2026-04-15"],
            "fill_level_perc": ["90"],
            "geleert": [True],
        }
    )
    base_path = tmp_path / "base.csv"
    feedback_path = tmp_path / "feedback.csv"
    combined_path = tmp_path / "combined.csv"
    base.to_csv(base_path, index=False)
    feedback.to_csv(feedback_path, index=False)
    pd.concat([base, pd.read_csv(feedback_path)], ignore_index=True).to_csv(combined_path, index=False)

    before = ingest.ingest(base_path, tmp_path / "before-cleaned.csv")
    after = ingest.ingest(combined_path, tmp_path / "after-cleaned.csv")
    assert "geleert" in after.columns

    before_scored = scoring.score_containers(features.build_features(before, "2026-04-15"))
    after_scored = scoring.score_containers(features.build_features(after, "2026-04-15"))
    before_forecast = forecast.forecast_from_scored(before_scored, "2026-04-15", offsets=[7])
    after_forecast = forecast.forecast_from_scored(after_scored, "2026-04-15", offsets=[7])
    assert before_forecast["forecast_pct"].tolist() != after_forecast["forecast_pct"].tolist()


def test_cli_run_accepts_input_alias(tmp_path: Path) -> None:
    raw_path, locs_path = _stage_sample_inputs(tmp_path)
    result = CliRunner().invoke(
        cli,
        # --cleaned keeps the test from overwriting the real data/processed/cleaned_readings.csv.
        ["run", "--date", "2026-04-15", "--input", str(raw_path), "--locations", str(locs_path),
         "--cleaned", str(tmp_path / "cleaned.csv"), "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code == 0, result.output


def test_cli_stepwise_score_route_visualize(tmp_path: Path) -> None:
    raw_path, locs_path = _stage_sample_inputs(tmp_path)
    cleaned_path = tmp_path / "cleaned.csv"
    scored_path = tmp_path / "scored.csv"
    out_dir = tmp_path / "out"
    runner = CliRunner()

    r1 = runner.invoke(cli, ["ingest", "-i", str(raw_path), "-o", str(cleaned_path)])
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(cli, ["score", "-d", "2026-04-15", "-i", str(cleaned_path), "-o", str(scored_path)])
    assert r2.exit_code == 0, r2.output

    r3 = runner.invoke(
        cli,
        [
            "route",
            "-d",
            "2026-04-15",
            "--scored",
            str(scored_path),
            "--locations",
            str(locs_path),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert r3.exit_code == 0, r3.output

    r4 = runner.invoke(
        cli,
        [
            "visualize",
            "-d",
            "2026-04-15",
            "--readings",
            str(cleaned_path),
            "--route",
            str(out_dir / "route_2026-04-15.json"),
            "--scored",
            str(scored_path),
            "--locations",
            str(locs_path),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert r4.exit_code == 0, r4.output
    assert (out_dir / "trends.png").is_file()
    assert (out_dir / "map_2026-04-15.html").is_file()


def test_cli_route_with_config_prints_summary_line(tmp_path: Path) -> None:
    raw_path, locs_path = _stage_sample_inputs(tmp_path)
    cleaned_path = tmp_path / "cleaned.csv"
    scored_path = tmp_path / "scored.csv"
    cfg_path = tmp_path / "cfg.json"
    out_dir = tmp_path / "out"
    cfg_path.write_text(
        json.dumps({"vehicle_max_weight_kg": 1500.0, "density_kg_per_m3": 400.0}),
        encoding="utf-8",
    )

    runner = CliRunner()
    assert runner.invoke(cli, ["ingest", "-i", str(raw_path), "-o", str(cleaned_path)]).exit_code == 0
    assert (
        runner.invoke(
            cli, ["score", "-d", "2026-04-15", "-i", str(cleaned_path), "-o", str(scored_path)]
        ).exit_code
        == 0
    )

    res = runner.invoke(
        cli,
        [
            "route",
            "-d",
            "2026-04-15",
            "--scored",
            str(scored_path),
            "--locations",
            str(locs_path),
            "--config",
            str(cfg_path),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert res.exit_code == 0, res.output
    lines = [line for line in res.output.strip().splitlines() if line.strip()]
    assert len(lines) == 1
    line = lines[0]
    assert "Fahrzeug" in line
    assert "Runde" in line
    assert " h, " in line
    assert " t, " in line
    assert line.endswith(" km")

    payload = json.loads((out_dir / "route_2026-04-15.json").read_text(encoding="utf-8"))
    for key in (
        "vehicles_needed",
        "rounds_per_vehicle",
        "t_collected",
        "km",
        "shift_hours_per_vehicle",
        "assumptions",
        "comparison",
    ):
        assert key in payload
    assert payload["assumptions"]["vehicle_max_weight_kg"] == 1500.0
