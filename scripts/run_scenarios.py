"""Run all emptying policies (a–f) against ONE world and write the scenario output contract.

    PYTHONPATH=src python3 scripts/run_scenarios.py [--time-model real|hop5|hop10]

Outputs (data/outputs/scenarios/):
  summary.json                    one entry per scenario (tonnage, fill, overflows, stops, km, ...)
  <id>__<time_model>_daily.csv    per-day series
  containers.csv                  per container: area, rates, cadence, status quo vs mentor

Model: docs/MODEL_SPEC.md (§0 core model, §9 decisions). Engine: src/prezero/sim/engine.py,
policies: src/prezero/sim/policies.py. Units: fill in % of 2.5 m³ (100 % = 1 t at 400 kg/m³),
t, h, km. Only the km day evaluator exists so far; --time-model is reserved for W4's
src/prezero/sim/time_model.py and falls back to km while that module is missing.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from prezero.locations import load_locations  # noqa: E402
from prezero.routing import load_config  # noqa: E402
from prezero.sim.engine import ScenarioResult, km_evaluator, run_scenario, static_view  # noqa: E402
from prezero.sim.policies import FixedAreas, Mentor, default_policies, per_colour_policies  # noqa: E402
from prezero.sim.world import build_world  # noqa: E402

DAILY_COLUMNS = [
    "date",
    "n_emptyings",
    "n_overflow_events",
    "avg_fill_at_emptying_pct",
    "tonnage_t",
    "stops",
    "vehicles_needed",
    "shift_hours",
    "km",
    "cost_eur",
]


def resolve_evaluator(time_model: str | None):
    """(evaluate_day, time_model label). Falls back to km if W4's time model is missing."""
    if not time_model or time_model == "km":
        return km_evaluator, "km"
    if not (ROOT / "src/prezero/sim/time_model.py").exists():
        print(f"NOTE: src/prezero/sim/time_model.py missing, --time-model {time_model} ignored, using km.")
        return km_evaluator, "km"
    mod = importlib.import_module("prezero.sim.time_model")
    factory = getattr(mod, "make_evaluator", None)
    if factory is None:
        print("NOTE: prezero.sim.time_model has no make_evaluator(mode), using km.")
        return km_evaluator, "km"
    return factory(time_model), time_model


def scenario_entry(res: ScenarioResult, sq_emptyings: int, time_model: str) -> dict:
    lg, d = res.ledger, res.daily
    balance = abs(lg["collected_t"] + lg["end_stock_t"] - lg["produced_t"]) <= 1e-6
    sid = res.id if res.truck_mode == "multi_chamber" else f"{res.id}_{res.truck_mode}"
    return {
        "id": sid,
        "policy_id": res.id,
        "label": res.label,
        "time_model": time_model,
        "truck_mode": res.truck_mode,
        "co_empty_threshold_pct": res.bundle_threshold,
        "collected_t": round(lg["collected_t"], 2),
        "end_stock_t": round(lg["end_stock_t"], 2),
        "mass_balance_ok": bool(balance),
        "avg_fill_at_emptying_pct": round(lg["avg_fill_at_emptying_pct"], 2),
        "overflow_events": int(lg["overflow_container_days"]),
        "overfull_at_emptying": int(lg["overfull_at_emptying"]),
        "emptyings": int(lg["n_emptyings"]),
        "emptyings_saved_vs_status_quo": int(sq_emptyings - lg["n_emptyings"]),
        "extra_emptyings_co": int(res.events["bundled"].sum()),
        "stops": int(d["stops"].sum()),
        "vehicle_days": int(d["vehicles_needed"].sum()),
        "hours": round(float(d["shift_hours"].sum()), 1),
        "km": round(float(d["km"].sum()), 1),
        "cost_eur": None,
        "cost_breakdown": None,
        "flags": {"cheapest": None, "fewest_overflows": False},
        "source": f"scripts/run_scenarios.py (engine=prezero.sim.engine, evaluator={time_model})",
        "runtime_s": round(res.runtime_s, 2),
    }


def run_all(readings, locations, cfg, evaluate_day=None):
    """All policies in multi_chamber, plus a/d/g in per_colour, against ONE world."""
    world = build_world(readings, locations, cfg)
    static = static_view(world)
    pols = default_policies()
    kw = {"cfg": cfg, "world": world, "static": static, "evaluate_day": evaluate_day}
    results = [run_scenario(p, truck_mode="multi_chamber", **kw) for p in pols]
    results += [run_scenario(p, truck_mode="per_colour", **kw) for p in per_colour_policies()]
    return world, pols, results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--readings", type=Path, default=ROOT / "data/processed/cleaned_readings.csv")
    ap.add_argument("--locations", type=Path, default=ROOT / "data/external/locations.csv")
    ap.add_argument("--config", type=Path, default=ROOT / "prezero_config.json")
    ap.add_argument("--output-dir", type=Path, default=ROOT / "data/outputs/scenarios")
    ap.add_argument("--time-model", nargs="+", choices=["km", "real", "hop5", "hop10"], default=["km"],
                    help="one or more day evaluators; all go into one summary.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    readings = pd.read_csv(args.readings)
    locations = load_locations(args.locations)
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    first = None
    for tm_req in args.time_model:
        evaluate_day, tm = resolve_evaluator(tm_req)
        world, pols, results = run_all(readings, locations, cfg, evaluate_day)
        produced = world.produced_kg() / 1000.0
        by_id = {r.id: r for r in results if r.truck_mode == "multi_chamber"}
        sq_empt = int(by_id["d_status_quo"].ledger["n_emptyings"])
        for r in results:
            e = scenario_entry(r, sq_empt, tm)
            assert e["mass_balance_ok"], e["id"]
            entries.append(e)
            sid = r.id if r.truck_mode == "multi_chamber" else f"{r.id}_{r.truck_mode}"
            r.daily[DAILY_COLUMNS].to_csv(out / f"{sid}__{tm}_daily.csv", index=False)
        assert all(abs(r.ledger["produced_t"] - produced) < 1e-9 for r in results)
        if first is None:
            first = (world, pols, results, by_id)
    world, pols, results, by_id = first
    sq = by_id["d_status_quo"]
    produced = world.produced_kg() / 1000.0
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "period": {"start": str(world.dates[0]), "end": str(world.dates[-1]), "days": len(world.dates)},
        "produced_t": round(produced, 2),
        "units": "fill % of 2.5 m3 (100 % = 1 t at 400 kg/m3); t; h; km",
        "model_spec": "docs/MODEL_SPEC.md",
        "scenarios": entries,
    }
    try:  # W5: cost (Annahme) + cheapest/fewest_overflows per time_model group
        from prezero.sim.cost import annotate_summary

        summary = annotate_summary(summary)
    except ImportError:
        print("NOTE: prezero.sim.cost missing, cost fields stay null.")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # containers.csv
    f_pol = next(p for p in pols if isinstance(p, FixedAreas))
    m_pol = next(p for p in pols if isinstance(p, Mentor))
    mentor = by_id[m_pol.id]
    buffer = 20.0
    cont = pd.DataFrame(
        {
            "location_id": world.location_id,
            "material": world.material,
            "lat": world.lat,
            "lon": world.lon,
            "area": f_pol.area,
            "rate_pct_per_day": np.round(world.rate, 4),
            "rate_kg_per_day": np.round(world.rate * world.kg_per_pct, 3),
            "cadence_days_T": np.round((100.0 - buffer) / np.maximum(world.rate, 1e-9), 1),
            "emptyings_status_quo": sq.containers["emptyings"].to_numpy(),
            "emptyings_mentor": mentor.containers["emptyings"].to_numpy(),
            "avg_fill_status_quo_pct": sq.containers["avg_fill_pct"].round(2).to_numpy(),
            "avg_fill_mentor_pct": mentor.containers["avg_fill_pct"].round(2).to_numpy(),
            "overflow_events_status_quo": sq.containers["overflow_events"].to_numpy(),
            "skip_14d": m_pol.skipped_ever.astype(int),
        }
    )
    cont.to_csv(out / "containers.csv", index=False)

    print(f"produced_t={produced:.2f}  period={world.dates[0]}..{world.dates[-1]} ({len(world.dates)} d)  evaluator={tm}")
    hdr = f"{'id':30s} {'coll_t':>8s} {'end_t':>7s} {'fill%':>6s} {'ovf':>6s} {'ovfE':>5s} {'empt':>6s} {'stops':>6s} {'veh':>4s} {'h':>7s} {'km':>9s} {'co':>5s} {'s':>5s}"
    print(hdr)
    for e in entries:
        print(
            f"{e['id']:30s} {e['collected_t']:8.2f} {e['end_stock_t']:7.2f} {e['avg_fill_at_emptying_pct']:6.2f} "
            f"{e['overflow_events']:6d} {e['overfull_at_emptying']:5d} {e['emptyings']:6d} {e['stops']:6d} "
            f"{e['vehicle_days']:4d} {e['hours']:7.1f} {e['km']:9.1f} {e['extra_emptyings_co']:5d} {e['runtime_s']:5.2f}"
        )
    print(f"Written: {out}")


if __name__ == "__main__":
    main()
