import csv
import math

import pandas as pd

from prezero import routing, tour
from tests.test_routing import _two_colour_site


def _route(tmp_path=None, **cfg):
    scored, locs = _two_colour_site()
    return routing.build_route(scored, locs, config=routing.OperationalConfig(**cfg))


def test_every_tour_starts_and_ends_at_yard():
    for t in tour.build_tours(_route(vehicle_max_volume_m3=6.0)):
        assert t["rows"][0]["label"] == "Start Betriebshof"
        assert t["rows"][-1]["label"] == "Ende Betriebshof"


def test_unload_before_capacity_exceeded():
    route = _route(vehicle_max_volume_m3=6.0)
    assert route["unload_stops"]
    for s in route["stops"]:
        if s["stop_type"] == "collection":
            assert s["load_m3"] <= 6.0 and s["load_kg"] <= 11000.0
    assert any(r["row_type"] == "unload" for t in tour.build_tours(route) for r in t["rows"])


def test_total_km_is_sum_of_legs():
    route = _route(vehicle_max_volume_m3=6.0)
    tours = tour.build_tours(route)
    assert math.isclose(sum(r["leg_km"] for t in tours for r in t["rows"]), route["km"], abs_tol=0.05)


def test_tour_csv_has_yard_rows(tmp_path):
    p = tour.export_tour_csv(_route(vehicle_max_volume_m3=6.0), tmp_path / "t.csv")
    rows = list(csv.DictReader(p.open()))
    assert rows[0]["label"] == "Start Betriebshof" and rows[-1]["label"] == "Ende Betriebshof"
    assert any(r["label"].startswith("Entladen") for r in rows)


def test_default_locations_marked_assumed():
    rows = tour.build_tours(_route())[0]["rows"]
    assert "angenommen" in rows[0]["note"]
