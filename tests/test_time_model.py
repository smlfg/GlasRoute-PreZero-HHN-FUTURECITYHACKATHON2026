from __future__ import annotations

import pandas as pd
import pytest

from prezero.routing import OperationalConfig
from prezero.sim.time_model import MENTOR_DEFAULTS, classify_area, make_evaluator

URBAN_A = (49.1427, 9.2129)
URBAN_B = (49.1427, 9.2149)
URBAN_C = (49.1427, 9.2169)
URBAN_D = (49.1427, 9.2189)
RURAL_FLEIN = (49.1030, 9.2110)


def sites(points, mass=100.0, vol=0.5):
    return pd.DataFrame(
        [
            {
                "Location_id": f"s{i}", "lat": a, "lon": b, "mass_kg": mass, "volume_m3": vol,
                "critical_bins": 1, "score": 1.0, "critical": True, "primary_material": "glass",
                "last_fill_level": 90.0, "est_fill_level": 95.0, "source": "t", "confidence": "high",
            }
            for i, (a, b) in enumerate(points)
        ]
    )


def test_classify_area_known_points():
    assert classify_area(49.1427, 9.2109) == "urban"
    assert classify_area(49.103, 9.211) == "rural"  # Flein
    assert classify_area(49.073, 9.150) == "rural"  # Lauffen
    assert classify_area(49.229, 9.151) == "rural"  # aeusserer Ort


def test_urban_real():
    ev = make_evaluator("real", depot_leg_min=10.0)
    r = ev(sites([URBAN_A, URBAN_B, URBAN_C]), OperationalConfig())
    assert r["stops"] == 3 and r["vehicles"] == 1 and r["unloads"] == 0
    assert r["hours"] == pytest.approx((10 + 7 + 7 + 10 + 15) / 60)
    assert r["service_h"] == pytest.approx(15 / 60)
    assert r["drive_h"] == pytest.approx(34 / 60)
    assert r["depot_trips"] == 1


def test_rural_hop_real_and_hop_modes():
    pts = [URBAN_A, URBAN_B, RURAL_FLEIN]
    cfg = OperationalConfig()
    real = make_evaluator("real", depot_leg_min=10.0)(sites(pts), cfg)
    assert real["hours"] == pytest.approx((10 + 7 + 15 + 10 + 15) / 60)
    h5 = make_evaluator("hop5")(sites(pts), cfg)
    assert h5["hours"] == pytest.approx((4 * 5 + 15) / 60)
    h10 = make_evaluator("hop10")(sites(pts), cfg)
    assert h10["hours"] == pytest.approx((4 * 10 + 15) / 60)
    assert real["km"] == pytest.approx(h5["km"])  # km stays routing km


def test_capacity_forces_unloads():
    pts = [URBAN_A, URBAN_B, URBAN_C]
    s = sites(pts, mass=6000.0, vol=5.0)  # 2 x 6 t > 11 t
    cfg = OperationalConfig()
    real = make_evaluator("real", depot_leg_min=10.0)(s, cfg)
    assert real["stops"] == 3 and real["unloads"] == 2 and real["vehicles"] == 1
    assert real["unload_h"] == pytest.approx(40 / 60)
    assert real["hours"] == pytest.approx((6 * 10 + 15 + 40) / 60)
    assert real["depot_trips"] == 3
    h5 = make_evaluator("hop5")(s, cfg)
    assert h5["hours"] == pytest.approx((6 * 5 + 15 + 40) / 60)


def test_shift_forces_second_vehicle():
    pts = [URBAN_A, URBAN_B, URBAN_C, URBAN_D]
    cfg = OperationalConfig(max_shift_hours=1.0)
    r = make_evaluator("real", depot_leg_min=10.0)(sites(pts), cfg)
    assert r["stops"] == 4 and r["vehicles"] == 2
    # v1: 10+5+7+5+7+5+10 = 49 ; v2: 10+5+10 = 25
    assert r["hours"] == pytest.approx(74 / 60)


def test_all_sites_served_and_hop_identity():
    import numpy as np

    rng = np.random.default_rng(0)
    pts = [(49.13 + rng.random() * 0.03, 9.19 + rng.random() * 0.05) for _ in range(60)]
    s = sites(pts, mass=900.0, vol=2.0)
    cfg = OperationalConfig()
    r = make_evaluator("hop5")(s, cfg)
    assert r["stops"] == 60
    assert r["unloads"] >= 1
    assert r["hours"] == pytest.approx(
        (5 * (r["stops"] + r["vehicles"] + r["unloads"]) + 5 * r["stops"] + 20 * r["unloads"]) / 60
    )


def test_empty_and_bad_mode():
    assert make_evaluator("real")(sites([]), OperationalConfig())["stops"] == 0
    with pytest.raises(ValueError):
        make_evaluator("fast")
    assert MENTOR_DEFAULTS["service_min"]["value"] == 5.0
