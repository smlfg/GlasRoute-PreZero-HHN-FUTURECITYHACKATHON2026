import json
from pathlib import Path

import pytest

from prezero.sim.cost import RATES, annotate_summary, scenario_cost

ROOT = Path(__file__).resolve().parents[1]


def test_cost_formula_hand_example():
    # 3 x 500 + 20 x 64 + 100 x 0.65 = 1500 + 1280 + 65
    c = scenario_cost(3, 20, 100)
    assert c == {"total_eur": 2845.0, "vehicle_days_eur": 1500.0, "crew_eur": 1280.0, "km_eur": 65.0}
    assert RATES == {"vehicle_day_eur": 500.0, "crew_hour_eur": 64.0, "km_eur": 0.65}


def test_annotate_flags_per_time_model_group():
    def e(tm, vd, h, km, ov):
        return {"time_model": tm, "vehicle_days": vd, "hours": h, "km": km, "overflow_events": ov}

    s = {"scenarios": {
        "a": e("fix", 10, 80, 100, 5),
        "b": e("fix", 8, 60, 100, 9),
        "c": e("km", 100, 800, 1000, 0),
        "d": e("km", 120, 900, 900, 3),
    }}
    out = annotate_summary(s)["scenarios"]
    assert out["a"]["cost_eur"] == scenario_cost(10, 80, 100)["total_eur"]
    assert out["b"]["cost_breakdown"]["crew_eur"] == 3840.0
    assert (out["a"]["flags"]["cheapest"], out["b"]["flags"]["cheapest"]) == (False, True)
    assert (out["a"]["flags"]["fewest_overflows"], out["b"]["flags"]["fewest_overflows"]) == (True, False)
    assert (out["c"]["flags"]["cheapest"], out["d"]["flags"]["cheapest"]) == (True, False)
    assert (out["c"]["flags"]["fewest_overflows"], out["d"]["flags"]["fewest_overflows"]) == (True, False)


def test_annotate_accepts_list():
    s = {"scenarios": [{"time_model": "x", "vehicle_days": 1, "hours": 1, "km": 0, "overflow_events": 0}]}
    assert annotate_summary(s)["scenarios"][0]["flags"]["cheapest"] is True


def test_skip_savings_consistent():
    d = json.loads((ROOT / "data/outputs/scenarios/skip_savings.json").read_text())
    for key in ("primary_world_consistent_replay", "cross_check_raw_measured_readings"):
        p = d[key]
        assert p["n_visits_le_20pct"] <= 10363 == p["n_visits"]
        assert p["share_pct"] == pytest.approx(100 * p["n_visits_le_20pct"] / 10363, abs=0.01)
        lo = p["lower_bound_service_only"]
        hi = p["upper_bound_service_plus_hop"]
        assert lo["saved_total_h"] == pytest.approx(p["n_visits_le_20pct"] * 5 / 60, abs=0.01)
        assert lo["saved_total_h"] <= p["site_aware_service_plus_hop_if_whole_site_skipped"]["saved_total_h"] <= hi["saved_total_h"]
        assert hi["saved_truck_days"] == pytest.approx(hi["saved_total_h"] / 8, abs=0.01)
        assert hi["saved_cost_eur"] == scenario_cost(hi["saved_total_h"] / 8, hi["saved_total_h"], 0)["total_eur"] or \
            hi["saved_cost_eur"] == pytest.approx(hi["saved_total_h"] / 8 * 500 + hi["saved_total_h"] * 64, abs=1.0)
