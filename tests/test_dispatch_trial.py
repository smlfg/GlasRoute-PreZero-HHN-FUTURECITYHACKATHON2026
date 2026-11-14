import json
from pathlib import Path

import pandas as pd
import pytest

from prezero.dispatch_trial import (
    Operations,
    assess_service,
    calibrate,
    price_operations,
    route_for,
)
from prezero.locations import load_locations
from prezero.routing import OperationalConfig


def test_calibration_ignores_holdout_observations_and_new_containers():
    rows = pd.DataFrame(
        {
            "Location_id": ["a", "a", "b"],
            "material_type": ["white"] * 3,
            "date": pd.to_datetime(["2026-02-01", "2026-02-11", "2026-03-01"]),
            "fill_pct": [80.0, 60.0, 90.0],
        }
    )
    start = pd.Timestamp("2026-02-12")
    d = calibrate(rows, start)
    assert list(d.keys) == [("a", "white")]
    assert list(d.rate) == [6.0]
    assert list(d.initial) == [0.0]
    rows.loc[2, "fill_pct"] = 0
    assert list(calibrate(rows, start).rate) == list(d.rate)


def test_terminal_obligation_and_price():
    ref = dict(risk_bin_days=12, overdue_bins=2, excess_kg=50, peak=2, ending_kg=100)
    assert not assess_service(ref, ref | {"risk_bin_days": 13}, 3)["acceptable"]
    gate = assess_service(ref, ref | {"ending_kg": 120}, 3)
    assert gate["acceptable"] and not gate["comparable_cost"]
    ops = Operations(hours=7, km=20, vehicle_days=1, collected_kg=2000).summary()
    p = dict(vehicle_day=500, crew=2, wage=32, km_cost=0.65)
    c = price_operations(ops, p, 1)
    assert c["cost"] == 961 and c["eur_per_t"] == 480.5


def test_actual_router_rejects_oversize_and_shift_violations():
    geo = load_locations()
    key = pd.MultiIndex.from_tuples(
        [(geo.Location_id.iloc[0], "white")], names=["Location_id", "material_type"]
    )
    for cfg in [
        OperationalConfig(vehicle_max_weight_kg=100),
        OperationalConfig(vehicle_max_volume_m3=0.2),
        OperationalConfig(max_shift_hours=0.01),
    ]:
        with pytest.raises(ValueError, match="exceeds"):
            route_for([0], [100], key, geo, cfg)


def test_shared_workload_and_cost_evidence():
    root = Path(__file__).resolve().parents[1]
    r = json.loads((root / "data/dispatch_experiment.json").read_text())
    for day, snapshot in r["checkpoints"].items():
        n = (pd.Timestamp(day) - pd.Timestamp(r["start"])).days + 1
        available = r["opening_kg"] + n * r["daily_inflow_kg"]
        for s in snapshot.values():
            assert s["collected_kg"] + s["ending_kg"] == pytest.approx(available)
            assert s["cost"] == pytest.approx(
                s["deployment_cost"] + s["labor_and_km_cost"]
            )
        assert snapshot["C"]["exceptions"] == 0
