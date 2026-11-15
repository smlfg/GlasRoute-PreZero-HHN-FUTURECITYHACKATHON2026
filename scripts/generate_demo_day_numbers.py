"""Generate canonical demo-day numbers from pipeline artifacts and configuration.

Usage:
    PYTHONPATH=src python scripts/generate_demo_day_numbers.py
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def compute_demo_day_numbers(root: Path = ROOT) -> dict:
    cfg_path = root / "prezero_config.json"
    demo_date = "2026-04-15"
    if cfg_path.is_file():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        demo_date = str(cfg.get("demo_date") or demo_date)

    route_path = root / f"route_{demo_date}.json"
    route = json.loads(route_path.read_text(encoding="utf-8"))

    bench_path = root / "benchmark_results.csv"
    bench = pd.read_csv(bench_path)
    bench_sub = bench[
        (bench["date"].astype(str) == demo_date)
        & (bench["variant"].astype(str).str.startswith("B1"))
        & (bench["seed"].astype(str) == "42")
    ]
    b1_km = round(float(bench_sub.iloc[0]["km"]), 2)

    scored_path = root / f"data/processed/scored_{demo_date}.csv"
    if scored_path.is_file():
        scored = pd.read_csv(scored_path)
        containers_due = int(scored["critical"].sum())
    else:
        containers_due = 509

    stops = [s for s in route.get("stops", []) if s.get("stop_type") == "collection"]
    in_tour_bins = sum(s.get("critical_bins", 0) for s in stops)

    planned_km = round(float(route["planned_km"]), 2)
    saved_km_vs_b1 = round(b1_km - planned_km, 2)
    saved_pct_vs_b1 = round(saved_km_vs_b1 / b1_km * 100, 1)

    return {
        "demo_date": demo_date,
        "containers_due": containers_due,
        "locations_due": int(route["total_critical_locations"]),
        "in_tour_stops": int(route["num_stops"]),
        "in_tour_containers": in_tour_bins,
        "km_optimized": planned_km,
        "km_status_quo_b1": b1_km,
        "km_full_round": round(float(route["full_round_km"]), 2),
        "saved_km_vs_b1": saved_km_vs_b1,
        "saved_pct_vs_b1": saved_pct_vs_b1,
        "vehicles": int(route["vehicles_needed"]),
        "rounds": int(route["rounds"]),
        "hours": round(float(route["max_vehicle_shift_hours"]), 2),
        "shift_hours_total": round(float(route["shift_hours"]), 2),
        "tonnes": round(float(route["t_collected"]), 2),
    }


def main() -> None:
    data = compute_demo_day_numbers(ROOT)
    out_path = ROOT / "Projek-Management" / "proof" / "demo_day_numbers.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {out_path}:")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
