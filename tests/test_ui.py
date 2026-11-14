"""Tests for the 4-view local web UI built strictly from verifiable data."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
import pandas as pd
import pytest

from prezero import viz
from prezero.cli import cli
from prezero.ui import (
    build_ui,
    compute_data_check,
    compute_upload_check,
    render_forecast_timeline_map_html,
)


def _sample_readings() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L1", "L2", "L2", "L2", "L3"],
            "material_type": ["white", "white", "white", "green", "green", "green", "brown"],
            "date": [
                "2026-01-01",
                "2026-01-06",
                "2026-04-12",  # > 90-day gap and > 50 pp jump
                "2026-04-01",
                "2026-04-06",
                "2026-04-11",
                "2026-04-06",
            ],
            "fill_level_perc": ["10", "20", "90", "30", "45", "60", "overfull"],
            "fill_level_numeric": [10.0, 20.0, 90.0, 30.0, 45.0, 60.0, 110.0],
            "is_overfull": [False, False, False, False, False, False, True],
        }
    )


def _sample_scored() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3"],
            "material_type": ["white", "green", "brown"],
            "last_date": ["2026-04-12", "2026-04-11", "2026-04-06"],
            "last_fill_level": [90.0, 60.0, 110.0],
            "days_since_last": [3, 4, 9],
            "overfull_rate": [0.0, 0.0, 1.0],
            "avg_daily_increase": [2.0, 3.0, 0.0],
            "season_factor": [1.0, 1.0, 1.0],
            "reading_count": [3, 3, 1],
            "score": [0.85, 0.55, 0.92],
            "critical": [True, False, True],
        }
    )


def _sample_locations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3"],
            "lat": [49.14, 49.15, 49.16],
            "lon": [9.21, 9.22, 9.23],
            "source": ["osm_assigned", "synthetic_placeholder", "osm_assigned"],
            "confidence": ["simulated_mapping", "synthetic", "simulated_mapping"],
        }
    )


def _sample_route() -> dict:
    return {
        "date": "2026-04-15",
        "depot": {"lat": 49.1427, "lon": 9.2109},
        "num_stops": 2,
        "total_critical_locations": 2,
        "total_active_locations": 3,
        "vehicles_needed": 1,
        "rounds": 1,
        "shift_hours": 1.25,
        "t_collected": 2.0,
        "planned_km": 4.2,
        "full_round_km": 7.5,
        "saved_km": 3.3,
        "saved_pct": 44.0,
        "comparison": "4.2 km planned (2 stops) vs. 7.5 km full round (3 stops)",
        "stops": [
            {
                "order": 1,
                "stop_type": "collection",
                "Location_id": "L1",
                "lat": 49.14,
                "lon": 9.21,
                "score": 0.85,
                "primary_material": "white",
                "last_fill_level": 90.0,
                "source": "osm_assigned",
                "confidence": "simulated_mapping",
                "leg_km": 1.2,
                "cumulative_km": 1.2,
            },
            {
                "order": 2,
                "stop_type": "collection",
                "Location_id": "L3",
                "lat": 49.16,
                "lon": 9.23,
                "score": 0.92,
                "primary_material": "brown",
                "last_fill_level": 110.0,
                "source": "osm_assigned",
                "confidence": "simulated_mapping",
                "leg_km": 1.8,
                "cumulative_km": 3.0,
            },
        ],
    }


def test_compute_upload_check_matches_dataframe() -> None:
    df = _sample_readings()
    check = compute_upload_check(df)
    assert check["row_count"] == 7
    assert check["container_count"] == 3
    assert check["series_count"] == 3
    assert check["date_min"] == "2026-01-01"
    assert check["date_max"] == "2026-04-12"
    assert check["measurement_days"] == 6
    assert check["missing_values"] == 0
    assert check["overfull_count"] == 1


def test_compute_data_check_returns_exact_computed_metrics() -> None:
    df = _sample_readings()
    check = compute_data_check(df)
    assert check["total_series"] == 3
    assert check["evaluable_series"] == 2
    assert check["total_transitions"] == 4
    assert check["jumps_gt_50_total"] == 1
    assert check["jumps_gt_50_pct"] == pytest.approx(25.0)
    assert check["series_with_gap_gt_90d"] == 1
    assert check["overfull_total"] == 1

    for row in check["series"]:
        if row["regularity_score"] is not None:
            assert 0.0 <= row["regularity_score"] <= 1.0

    by_id = {row["Location_id"]: row for row in check["series"]}
    # L2 has constant +3.0 pp/day intervals -> regularity_score == 1.0
    assert by_id["L2"]["regularity_score"] == pytest.approx(1.0)
    assert by_id["L1"]["jumps_gt_50"] == 1
    assert by_id["L1"]["gaps_gt_90d"] == 1

    mat_means = {row["material_type"]: row["mean_fill_pct"] for row in check["material_summary"]}
    assert mat_means["white"] == pytest.approx(40.0)
    assert mat_means["green"] == pytest.approx(45.0)
    assert mat_means["brown"] == pytest.approx(110.0)


def test_forecast_timeline_map_has_no_route_polyline() -> None:
    map_html, summaries = render_forecast_timeline_map_html(
        _sample_scored(), _sample_locations(), "2026-04-15"
    )
    assert len(summaries) == 4
    assert "forecast-week-selector" in map_html
    assert "L.polyline" not in map_html
    assert "Letzte Leerung" not in map_html
    assert "tile.openstreetmap.org" in map_html


def test_build_ui_has_all_four_views_and_no_unbacked_claims(tmp_path: Path) -> None:
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui_2026-04-15.html",
    )
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "tile.openstreetmap.org" in html

    # All 4 views present (ordered Forecast -> Route -> Datacheck -> Upload)
    for view_id in ("view-forecast", "view-route", "view-datacheck", "view-upload"):
        assert f'id="{view_id}"' in html

    # Forecast timeline horizons
    for label in ("Heute", "+7 Tage", "+14 Tage", "+21 Tage"):
        assert label in html

    # Separate route view with Freigeben action and verifiable route numbers
    assert 'id="approve-route-btn"' in html
    assert "Freigeben" in html
    assert "4.2 km" in html
    assert "44.0 %" in html

    # Datacheck & Upload computed metrics
    assert "Regularity Score" in html
    assert 'id="csv-dropzone"' in html
    assert "2026-01-01 bis 2026-04-12" in html

    # Re-exported cleanly from prezero.viz
    assert viz.build_ui is build_ui

    # Strictly NO unbacked events or emptying dates
    for forbidden in ("Weindorf", "Nachweihnachtsspitze", "Letzte Leerung", "last_emptying_date"):
        assert forbidden not in html


def test_cli_ui_command_generates_html(tmp_path: Path) -> None:
    readings_path = tmp_path / "cleaned.csv"
    locs_path = tmp_path / "locations.csv"
    scored_path = tmp_path / "scored.csv"
    route_path = tmp_path / "route.json"
    out_dir = tmp_path / "out"

    _sample_readings().to_csv(readings_path, index=False)
    _sample_locations().to_csv(locs_path, index=False)
    _sample_scored().to_csv(scored_path, index=False)
    route_path.write_text(json.dumps(_sample_route()), encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "ui",
            "--date",
            "2026-04-15",
            "--readings",
            str(readings_path),
            "--scored",
            str(scored_path),
            "--locations",
            str(locs_path),
            "--route",
            str(route_path),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert res.exit_code == 0, res.output
    assert (out_dir / "ui_2026-04-15.html").is_file()
