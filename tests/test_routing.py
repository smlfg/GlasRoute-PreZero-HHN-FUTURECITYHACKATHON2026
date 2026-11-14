"""Tests for container routing."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from prezero.routing import DEFAULT_DEPOT, build_route, haversine_km


def _sample_scored_and_locations() -> tuple[pd.DataFrame, pd.DataFrame]:
    scored = pd.DataFrame(
        {
            "Location_id": ["L_near", "L_mid", "L_far", "L_low"],
            "material_type": ["white", "green", "white", "brown"],
            "last_fill_level": [110.0, 95.0, 100.0, 20.0],
            "score": [0.95, 0.85, 0.78, 0.25],
            "critical": [True, True, True, False],
        }
    )
    locations = pd.DataFrame(
        {
            "Location_id": ["L_near", "L_mid", "L_far", "L_low"],
            "lat": [49.1450, 49.1600, 49.1900, 49.2100],
            "lon": [9.2120, 9.2200, 9.2400, 9.2600],
            "source": ["osm_heuristic", "osm_heuristic", "synthetic_placeholder", "osm_heuristic"],
            "confidence": ["low", "low", "synthetic", "low"],
        }
    )
    return scored, locations


def test_nearest_neighbor_respects_max_stops_and_distance_order() -> None:
    scored, locations = _sample_scored_and_locations()
    route = build_route(scored, locations, depot=DEFAULT_DEPOT, max_stops=2)
    # Top 2 by score are L_near (0.95) and L_mid (0.85); nearest to depot is L_near first.
    assert route["num_stops"] == 2
    assert [s["Location_id"] for s in route["stops"]] == ["L_near", "L_mid"]
    assert route["planned_km"] > 0
    assert route["full_round_km"] >= route["planned_km"]


def test_build_route_writes_json_with_comparison(tmp_path: Path) -> None:
    scored, locations = _sample_scored_and_locations()
    route = build_route(
        scored,
        locations,
        depot=DEFAULT_DEPOT,
        max_stops=25,
        date="2026-04-15",
        output_dir=tmp_path,
    )
    out_file = tmp_path / "route_2026-04-15.json"
    assert out_file.is_file()
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["planned_km"] == pytest.approx(route["planned_km"])
    assert payload["full_round_km"] > payload["planned_km"]
    assert "planned" in payload["comparison"] and "full round" in payload["comparison"]
    assert haversine_km(49.1427, 9.2109, 49.1427, 9.2109) == pytest.approx(0.0)
