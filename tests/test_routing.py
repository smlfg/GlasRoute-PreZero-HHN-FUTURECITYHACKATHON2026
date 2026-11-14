import json

import pandas as pd

from prezero.routing import build_route, haversine_km


def test_haversine_is_zero_for_same_point() -> None:
    assert haversine_km(49.14, 9.21, 49.14, 9.21) == 0


def test_build_route_orders_nearest_and_writes_round_trip(tmp_path) -> None:
    scored = pd.DataFrame(
        [
            ("A", "white", 0.9, True),
            ("B", "green", 0.8, True),
            ("C", "brown", 0.2, False),
        ],
        columns=["Location_id", "material_type", "score", "critical"],
    )
    locations = pd.DataFrame(
        [
            ("A", 49.1428, 9.2109, "simulated"),
            ("B", 49.15, 9.22, "real"),
            ("C", 49.16, 9.23, "simulated"),
        ],
        columns=["Location_id", "lat", "lon", "source"],
    )
    route = build_route(scored, locations, depot=(49.1427, 9.2108), date="2026-04-15", output_dir=tmp_path)
    assert list(route["Location_id"]) == ["A", "B"]
    payload = json.loads((tmp_path / "route_2026-04-15.json").read_text())
    assert payload["full_round_km"] >= payload["planned_km"]
    assert payload["planned_vs_full_round_km"]["full_round"] == payload["full_round_km"]
