"""The forecast layers are added to the existing route map."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from prezero import forecast, locations, viz


def _scored() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3"],
            "material_type": ["white", "green", "brown"],
            "last_date": ["2026-04-06", "2026-04-06", "2026-04-06"],
            "last_fill_level": [90.0, 45.0, 110.0],
            "days_since_last": [9, 9, 9],
            "overfull_rate": [0.0, 0.0, 1.0],
            "avg_daily_increase": [10.0, 1.0, 0.0],
            "season_factor": [1.0, 1.0, 1.0],
            "reading_count": [2, 2, 1],
            "score": [1.0, 0.5, 1.0],
            "critical": [True, False, True],
        }
    )


def _locations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3"],
            "lat": [49.14, 49.15, 49.16],
            "lon": [9.21, 9.22, 9.23],
            "source": ["osm_assigned", "synthetic_placeholder", "osm_assigned"],
            "confidence": ["simulated_mapping", "synthetic", "simulated_mapping"],
        }
    )


def _route() -> dict:
    return {
        "date": "2026-04-15",
        "depot": {"lat": 49.1427, "lon": 9.2109},
        "comparison": "planned vs full round",
        "stops": [
            {
                "order": 1,
                "Location_id": "L1",
                "lat": 49.14,
                "lon": 9.21,
                "score": 0.92,
                "primary_material": "white",
                "source": "osm_assigned",
                "confidence": "simulated_mapping",
                "cumulative_km": 0.3,
            }
        ],
    }


def test_forecast_layers_are_added_to_the_route_map(tmp_path: Path) -> None:
    scored = _scored()
    locs = _locations()
    frame = forecast.forecast_from_scored(scored, "2026-04-15")

    out = viz.plot_route(
        _route(),
        tmp_path / "map.html",
        scored=scored,
        locations=locs,
        forecast=frame,
    )
    html = out.read_text(encoding="utf-8")

    # A layer switcher exists with the four horizons.
    assert "L.control.layers" in html
    for label in ("Heute", "+7 Tage", "+14 Tage", "+21 Tage"):
        assert label in html
    assert 'id="forecast-week-selector"' in html
    assert "forecastMap.removeLayer" in html

    # The planned route stays visible.
    assert "L.polyline" in html

    # Per-layer header with the critical count.
    assert "voraussichtlich kritisch" in html

    # Popups carry id, material, last measurement and forecast.
    assert "Prognose (" in html
    assert "Glasfarbe" in html
    assert "Letzte Messung" in html


def test_placeholder_is_dashed_and_real_site_is_solid(tmp_path: Path) -> None:
    scored = _scored()
    locs = _locations()
    frame = forecast.forecast_from_scored(scored, "2026-04-15")
    out = viz.plot_route(_route(), tmp_path / "map.html", scored=scored, locations=locs, forecast=frame)
    html = out.read_text(encoding="utf-8")
    # L2 is a synthetic placeholder -> dashed outline; L1/L3 are OSM -> solid.
    assert 'dashArray": "5, 5"' in html
    assert 'dashArray": null' in html


def test_forecast_summaries_report_counts() -> None:
    frame = forecast.forecast_from_scored(_scored(), "2026-04-15")
    today = frame[frame["offset_days"] == 0]
    assert forecast.count_critical(today) == 2  # L1 red, L3 black
    line = forecast.format_forecast_line(7, frame[frame["offset_days"] == 7])
    assert line.startswith("+7 Tage: ")
    assert "rot" in line and "schwarz" in line
