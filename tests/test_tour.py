import csv
import math
import xml.etree.ElementTree as ET

import pandas as pd

from prezero import routing, tour
from test_routing import _two_colour_site


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


def test_interleave_keeps_stop_indices_and_adds_yard_rows():
    route = _route(vehicle_max_volume_m3=6.0)
    rows = tour.interleave(route)
    assert rows[0][1]["stop_type"] == "depot_start" and rows[-1][1]["stop_type"] == "depot_end"
    assert [i for i, _ in rows if i is not None] == list(range(len(route["stops"])))
    assert math.isclose(rows[-1][1]["cumulative_km"], route["km"], abs_tol=0.05)


def test_build_gpx_is_valid_and_contains_all_stops_in_order():
    route = _route(vehicle_max_volume_m3=6.0)
    gpx = tour.build_gpx(route)
    root = ET.fromstring(gpx)
    ns = {"g": "http://www.topografix.com/GPX/1/1"}
    assert root.tag == "{http://www.topografix.com/GPX/1/1}gpx"
    assert root.attrib.get("version") == "1.1"

    rtepts = root.findall(".//g:rtept", ns)
    names = [p.find("g:name", ns).text for p in rtepts]
    assert names[0] == "Start Betriebshof"
    assert names[-1] == "Ende Betriebshof"
    assert any("Entladen" in n for n in names)
    # Number of route points equals tour rows (start + stops/unloads + end).
    tours = tour.build_tours(route)
    assert len(rtepts) == sum(len(t["rows"]) for t in tours)


def test_build_google_maps_legs_cover_all_stops_with_overlap():
    route = _route(vehicle_max_volume_m3=6.0)
    # Force splitting by using a tiny waypoint limit.
    legs_by_vehicle = tour.build_google_maps_legs(route, max_waypoints=1)
    assert legs_by_vehicle
    for veh, legs in legs_by_vehicle.items():
        assert len(legs) >= 1
        # Every leg is a Google Maps directions URL.
        for url in legs:
            assert url.startswith("https://www.google.com/maps/dir/?api=1")
            assert "origin=" in url
            assert "destination=" in url
        # Last destination of each leg equals next leg's origin (overlap).
        for i in range(len(legs) - 1):
            this_dest = legs[i].split("destination=")[1].split("&")[0]
            next_origin = legs[i + 1].split("origin=")[1].split("&")[0]
            assert this_dest == next_origin
