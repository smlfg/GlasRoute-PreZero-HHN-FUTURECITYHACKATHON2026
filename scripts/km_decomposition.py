"""Decompose the km difference between the status quo (d) and other policies (a, e, f, g).

    PYTHONPATH=src python3 scripts/km_decomposition.py

Every scenario runs against the same world (docs/MODEL_SPEC.md §1); km come from the km day
evaluator (routing._simulate_constrained_routes). Each day's route is split into leg types:

* depot      yard -> first stop and last stop -> yard, per vehicle          (component 3)
* unload     stop -> disposal and disposal -> next stop                      (component 4)
* inter-stop all remaining stop -> stop legs                                 (components 1, 2, 5)

The inter-stop delta is split sequentially (method, not a unique attribution):
  hop-count effect  = (hops_x - hops_d) * avg_hop_d
  hop-length effect = hops_x * (avg_hop_x - avg_hop_d)                       (2) scattered due-sets
and the hop-count effect is shared between
  (1) extra emptyings  : stops the policy would need with the status quo's containers-per-stop
  (5) colour splitting : the rest (fewer containers emptied per stop)
in proportion to those stop counts.

Writes data/outputs/scenarios/km_decomposition.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from prezero.locations import load_locations
from prezero.routing import _simulate_constrained_routes, load_config
from prezero.sim.engine import run_scenario, static_view
from prezero.sim.policies import default_policies
from prezero.sim.world import build_world

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ["d_status_quo", "a_zero_overflow", "e_mentor", "f_fixed_areas", "g_co_empty"]


def make_recorder(sink: dict[str, float]):
    def evaluate_day(sites_df: pd.DataFrame, cfg) -> dict[str, Any]:
        stops, unloads, vehicles, km, _mass = _simulate_constrained_routes(sites_df, cfg)
        prev_type: dict[int, str] = {}
        leg_sum: dict[int, float] = {}
        for s in stops:
            v = int(s["vehicle"])
            leg = float(s["leg_km"])
            leg_sum[v] = leg_sum.get(v, 0.0) + leg
            if s["stop_type"] == "unload":
                sink["unload_km"] += leg
            elif v not in prev_type:
                sink["depot_km"] += leg
            elif prev_type[v] == "unload":
                sink["unload_km"] += leg
            else:
                sink["inter_km"] += leg
                sink["hops"] += 1
            prev_type[v] = s["stop_type"]
        for veh in vehicles:
            sink["depot_km"] += float(veh["km"]) - leg_sum.get(int(veh["vehicle"]), 0.0)
        sink["vehicles"] += len(vehicles)
        sink["unloads"] += len(unloads)
        sink["stops"] += sum(1 for s in stops if s["stop_type"] == "collection")
        sink["km"] += float(km)
        return {
            "stops": sum(1 for s in stops if s["stop_type"] == "collection"),
            "km": float(km),
            "vehicles": len(vehicles),
            "hours": float(sum(v["shift_hours"] for v in vehicles)),
            "unloads": len(unloads),
        }

    return evaluate_day


def main() -> None:
    cfg = load_config(ROOT / "prezero_config.json")
    readings = pd.read_csv(ROOT / "data/processed/cleaned_readings.csv")
    locations = load_locations(ROOT / "data/external/locations.csv")
    world = build_world(readings, locations, cfg)
    static = static_view(world)
    pols = {p.id: p for p in default_policies()}

    rows: dict[str, dict[str, float]] = {}
    for pid in POLICIES:
        sink = dict.fromkeys(["depot_km", "unload_km", "inter_km", "hops", "vehicles", "unloads", "stops", "km"], 0.0)
        res = run_scenario(pols[pid], cfg=cfg, world=world, static=static, evaluate_day=make_recorder(sink))
        sink["emptyings"] = float(res.ledger["n_emptyings"])
        rows[pid] = sink

    d = rows["d_status_quo"]
    d_cps = d["emptyings"] / d["stops"]
    d_avg = d["inter_km"] / d["hops"]
    out: dict[str, Any] = {"method": __doc__.split("Writes")[0].strip(), "raw": rows, "decomposition": {}}
    for pid in POLICIES[1:]:
        x = rows[pid]
        x_avg = x["inter_km"] / x["hops"]
        count_eff = (x["hops"] - d["hops"]) * d_avg
        length_eff = x["hops"] * (x_avg - d_avg)
        stops_cf = x["emptyings"] / d_cps
        dstops = x["stops"] - d["stops"]
        share_extra = (stops_cf - d["stops"]) / dstops if dstops else 0.0
        comp = {
            "km_status_quo": round(d["km"], 1),
            "km_policy": round(x["km"], 1),
            "delta_km": round(x["km"] - d["km"], 1),
            "1_extra_emptyings_km": round(count_eff * share_extra, 1),
            "2_scattered_due_sets_km": round(length_eff, 1),
            "3_extra_vehicles_depot_km": round(x["depot_km"] - d["depot_km"], 1),
            "4_extra_unload_trips_km": round(x["unload_km"] - d["unload_km"], 1),
            "5_colour_splitting_km": round(count_eff * (1.0 - share_extra), 1),
            "containers_per_stop": round(x["emptyings"] / x["stops"], 2),
            "containers_per_stop_status_quo": round(d_cps, 2),
            "avg_hop_km": round(x_avg, 3),
            "avg_hop_km_status_quo": round(d_avg, 3),
        }
        parts = sum(v for k, v in comp.items() if k[0] in "12345")
        comp["check_sum_parts_km"] = round(parts, 1)
        out["decomposition"][pid] = comp

    path = ROOT / "data/outputs/scenarios/km_decomposition.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for pid, c in out["decomposition"].items():
        print(pid, {k: v for k, v in c.items() if k[0] in "12345d" or k.startswith("check")})
    print(f"Written: {path}")


if __name__ == "__main__":
    main()
