"""Tests for container routing."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from prezero.routing import DEFAULT_DEPOT, OperationalConfig, build_route, haversine_km, load_config


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


def test_per_site_critical_only_mass_no_co_collection() -> None:
    scored = pd.DataFrame(
        {
            "Location_id": ["L1", "L1"],
            "material_type": ["white", "brown"],
            "last_fill_level": [100.0, 40.0],
            "score": [0.90, 0.30],
            "critical": [True, False],
        }
    )
    locations = pd.DataFrame(
        {
            "Location_id": ["L1"],
            "lat": [49.1450],
            "lon": [9.2120],
            "source": ["osm_heuristic"],
            "confidence": ["low"],
        }
    )
    route = build_route(scored, locations)
    # 2.5 m3 * (100/100) * 400 kg/m3 = 1000 kg = 1.0 t; brown bin (40%) is not critical so excluded.
    assert route["t_collected"] == pytest.approx(1.0)
    assert route["stops"][0]["critical_bins"] == 1


def test_weight_limit_forces_unload_stop() -> None:
    scored, locations = _sample_scored_and_locations()
    cfg = OperationalConfig(vehicle_max_weight_kg=1500.0)
    route = build_route(scored, locations, max_stops=2, config=cfg)

    # Top 2 critical stops are L_near (110% -> 1100 kg) and L_mid (95% -> 950 kg).
    # 1100 + 950 > 1500 forces an unload stop at disposal_depot between them.
    assert route["vehicles_needed"] == 1
    assert route["rounds_per_vehicle"] == [2]
    assert route["num_stops"] == 2
    assert len(route["unload_stops"]) == 1
    assert [s["stop_type"] for s in route["stops"]] == ["collection", "unload", "collection"]
    assert route["stops"][1]["Location_id"] == "disposal_depot"
    assert route["t_collected"] == pytest.approx(2.05)


def test_shift_limit_forces_second_vehicle() -> None:
    scored, locations = _sample_scored_and_locations()
    cfg = OperationalConfig(
        max_shift_hours=0.25,
        stop_setup_min=5.0,
        lift_time_per_bin_min=5.0,
    )
    route = build_route(scored, locations, max_stops=3, config=cfg)

    assert route["vehicles_needed"] >= 2
    assert len(route["shift_hours_per_vehicle"]) == route["vehicles_needed"]
    assert len(route["rounds_per_vehicle"]) == route["vehicles_needed"]
    assert route["num_stops"] == 3


def test_config_override_json_and_yaml(tmp_path: Path) -> None:
    json_cfg = tmp_path / "cfg.json"
    json_cfg.write_text(
        json.dumps(
            {
                "density_kg_per_m3": 500.0,
                "vehicle_max_weight_kg": 12000.0,
                "road_detour_factor": 1.5,
                "yard_depot": [49.15, 9.22],
            }
        ),
        encoding="utf-8",
    )
    loaded_json = load_config(json_cfg)
    assert loaded_json.density_kg_per_m3 == pytest.approx(500.0)
    assert loaded_json.vehicle_max_weight_kg == pytest.approx(12000.0)
    assert loaded_json.road_detour_factor == pytest.approx(1.5)
    assert loaded_json.yard_depot == (49.15, 9.22)

    yaml_cfg = tmp_path / "cfg.yaml"
    yaml_cfg.write_text(
        "\n".join(
            [
                "density_kg_per_m3: 300",
                "avg_speed_kmh: 30",
                "max_shift_hours: 6.5",
                "disposal_depot:",
                "  lat: 49.18",
                "  lon: 9.21",
            ]
        ),
        encoding="utf-8",
    )
    loaded_yaml = load_config(yaml_cfg)
    assert loaded_yaml.density_kg_per_m3 == pytest.approx(300.0)
    assert loaded_yaml.avg_speed_kmh == pytest.approx(30.0)
    assert loaded_yaml.max_shift_hours == pytest.approx(6.5)
    assert loaded_yaml.disposal_depot == (49.18, 9.21)

    scored, locations = _sample_scored_and_locations()
    route = build_route(scored, locations, max_stops=1, config=loaded_json)
    # 2.5 m3 * 1.10 * 500 kg/m3 = 1375 kg = 1.38 t
    assert route["t_collected"] == pytest.approx(1.38)
    assert route["assumptions"]["density_kg_per_m3"] == pytest.approx(500.0)
    assert route["assumptions"]["yard_depot"] == [49.15, 9.22]


def test_full_round_uses_same_capacity_rules_as_planned_tour() -> None:
    import pandas as pd

    from prezero import routing

    n = 20
    scored = pd.DataFrame(
        {
            "Location_id": [f"L{i}" for i in range(n)],
            "material_type": ["white"] * n,
            "score": [0.9 if i < 5 else 0.3 for i in range(n)],
            "critical": [i < 5 for i in range(n)],
            "last_fill_level": [100.0] * n,
        }
    )
    locs = pd.DataFrame(
        {
            "Location_id": [f"L{i}" for i in range(n)],
            "lat": [49.12 + 0.003 * i for i in range(n)],
            "lon": [9.20 + 0.002 * i for i in range(n)],
            "source": ["osm_assigned"] * n,
            "confidence": ["simulated_mapping"] * n,
        }
    )
    # 20 full bins x 1 t = 20 t > 11 t: the full round must unload at least once.
    route = routing.build_route(scored, locs, config=routing.OperationalConfig())
    assert route["num_stops"] == 5
    assert route["full_round_km"] > route["planned_km"]
    assert route["full_round_vehicles"] >= route["vehicles_needed"]
    assert "same capacity rules" in route["comparison"]


def _two_colour_site() -> tuple:
    import pandas as pd

    scored = pd.DataFrame(
        {
            "Location_id": ["A", "A", "B", "B"],
            "material_type": ["white", "green", "white", "green"],
            "score": [0.9, 0.9, 0.9, 0.9],
            "critical": [True, True, True, True],
            "last_fill_level": [100.0] * 4,
            "est_fill_level": [100.0] * 4,
        }
    )
    locs = pd.DataFrame(
        {
            "Location_id": ["A", "B"],
            "lat": [49.14, 49.16],
            "lon": [9.21, 9.23],
            "source": ["osm_assigned"] * 2,
            "confidence": ["simulated_mapping"] * 2,
        }
    )
    return scored, locs


def test_density_per_glass_colour_changes_collected_mass() -> None:
    from prezero import routing

    scored, locs = _two_colour_site()
    base = routing.build_route(scored, locs, config=routing.OperationalConfig())
    # 4 full 2.5 m3 bins x 400 kg/m3 = 4.0 t
    assert base["t_collected"] == pytest.approx(4.0)
    heavy_green = routing.OperationalConfig(density_green_kg_per_m3=600.0)
    route = routing.build_route(scored, locs, config=heavy_green)
    # white 2 x 1.0 t + green 2 x 1.5 t = 5.0 t
    assert route["t_collected"] == pytest.approx(5.0)
    assert routing.density_for(heavy_green, "glass_white") == pytest.approx(400.0)


def test_vehicle_volume_limit_forces_unload() -> None:
    from prezero import routing

    scored, locs = _two_colour_site()
    # Each site holds 2 x 2.5 m3 = 5 m3; with 6 m3 capacity the second site needs an unload first.
    cfg = routing.OperationalConfig(vehicle_max_volume_m3=6.0)
    route = routing.build_route(scored, locs, config=cfg)
    assert len(route["unload_stops"]) == 1
    loads = [s["load_m3"] for s in route["stops"] if s.get("stop_type") == "collection"]
    assert max(loads) <= 6.0
    roomy = routing.build_route(scored, locs, config=routing.OperationalConfig())
    assert len(roomy["unload_stops"]) == 0
