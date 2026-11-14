"""Check every number used in Pitch/NOTES.md and docs/PITCH.md against the pipeline outputs.

Run from the repo root after `python scripts/benchmark.py` and `prezero-route run --date 2026-04-15`:

    PYTHONPATH=src python Projek-Management/proof/verify_pitch_numbers.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

from prezero.ui import compute_benchmark_summary

ROOT = Path(__file__).resolve().parents[2]

# Numbers as written in the pitch documents (timer model, no season/score factors, 14.11.2026 19:40).
EXPECTED_ROUTE = {
    "num_stops": 25,
    "total_critical_locations": 106,
    "total_active_locations": 121,
    "planned_km": 249.9,
    "vehicles_needed": 4,
    "rounds": 19,
    "shift_hours": 22.68,
    "max_vehicle_shift_hours": 7.58,
    "t_collected": 142.82,
    "full_round_km": 1202.24,
    "full_round_vehicles": 20,
}
EXPECTED_BENCH_KM = {"B0": 1795.91, "B1": 1662.70, "B2": 1165.90, "B4": 1053.29}
EXPECTED_BENCH_STOPS = {"B1": 121, "B2": 112}
EXPECTED_EFFECTS = {
    "demand_pct": 29.9,
    "routing_pct": 9.7,
    "overall_vs_b1_pct": 36.7,
    "overall_vs_b0_pct": 41.4,
}
EXPECTED_SPANS = {
    "demand_pct": (28.6, 67.1),
    "routing_pct": (2.3, 14.1),
    "overall_vs_b1_pct": (32.9, 70.7),
}
EXPECTED_WHAT_IF = {
    "shift_6h": {"vehicles_needed": 5, "max_vehicle_shift_hours": 5.42, "planned_km": 233.56},
    "truck_8t": {"vehicles_needed": 4, "rounds": 21, "planned_km": 271.28},
    "plus_vehicle": {"num_stops": 43, "planned_km": 417.03, "unserved_critical_locations": 63},
    "all_critical": {"num_stops": 106, "planned_km": 900.29, "vehicles_needed": 12},
}
EXPECTED_RAW = {"rows": 11701, "ids": 449, "overfull": 1192}

failures: list[str] = []


def check(label: str, got: object, expected: object) -> None:
    ok = got == expected if not isinstance(expected, float) else abs(float(got) - expected) < 0.005
    print(f"{'OK  ' if ok else 'FAIL'}     {label}: got={got} expected={expected}")
    if not ok:
        failures.append(label)


route = json.loads((ROOT / "route_2026-04-15.json").read_text(encoding="utf-8"))
print("# route_2026-04-15.json (prezero-route run --date 2026-04-15, max_stops 25)")
for key, value in EXPECTED_ROUTE.items():
    check(key, route.get(key), value)

print("\n# benchmark_results.csv (scripts/benchmark.py), 2026-04-15 / seed 42")
summary = compute_benchmark_summary(pd.read_csv(ROOT / "benchmark_results.csv"), "2026-04-15", 42)
assert summary is not None
by_code = {v["code"]: v for v in summary["variants"]}
for code, km in EXPECTED_BENCH_KM.items():
    check(f"{code} km", by_code[code]["km"], km)
for code, stops in EXPECTED_BENCH_STOPS.items():
    check(f"{code} stops", by_code[code]["stops"], stops)
for key, value in EXPECTED_EFFECTS.items():
    check(key, summary["effects"][key], value)
for key, (lo, hi) in EXPECTED_SPANS.items():
    check(f"{key} span over {summary['cases']} cases", (summary["robustness"][key]["min"], summary["robustness"][key]["max"]), (lo, hi))

print("\n# What-if presets embedded in ui_2026-04-15.html")
page = (ROOT / "ui_2026-04-15.html").read_text(encoding="utf-8")
payload = re.search(r'<script id="insights-payload" type="application/json">(.*?)</script>', page, re.S)
assert payload is not None
presets = {p["id"]: p for p in json.loads(payload.group(1).replace("<\\/", "</"))["presets"]}
for preset_id, fields in EXPECTED_WHAT_IF.items():
    for key, value in fields.items():
        check(f"{preset_id}.{key}", presets[preset_id]["simulation"][key], value)

print("\n# backtest_summary.json (scripts/backtest.py): Leerungsrhythmus")
EXPECTED_RHYTHM = {
    ("brown", "ideal_days_median"): 95.4,
    ("brown", "actual_days_median"): 42.0,
    ("brown", "too_often_pct"): 89.1,
    ("white", "ideal_days_median"): 32.5,
    ("white", "too_rarely_pct"): 15.8,
    ("green", "too_often_pct"): 45.1,
}
bt = json.loads((ROOT / "backtest_summary.json").read_text(encoding="utf-8"))
for (mat, key), value in EXPECTED_RHYTHM.items():
    check(f"rhythm {mat}.{key}", bt["rhythm"]["by_material"][mat][key], value)
check("rhythm found_below_50_pct", bt["rhythm"]["found_below_50_pct"], 30.1)
check("rhythm found_overfull_pct", bt["rhythm"]["found_overfull_pct"], 11.2)
check("backtest model mae_pp", bt["overall"]["model"]["mae_pp"], 19.9)
check("backtest mean_past mae_pp", bt["overall"]["mean_past"]["mae_pp"], 22.3)

print("\n# data/raw/glass_fill_levels_anonymized_f.csv")
raw = pd.read_csv(ROOT / "data/raw/glass_fill_levels_anonymized_f.csv", dtype=str)
check("raw rows", len(raw), EXPECTED_RAW["rows"])
check("raw ids", raw["Location_id"].nunique(), EXPECTED_RAW["ids"])
fill = raw["fill_level_perc"].str.strip().str.lower()
check("raw overfull", int((fill == "overfull").sum()), EXPECTED_RAW["overfull"])

print("\nRESULT:", "ALL MATCH" if not failures else f"{len(failures)} MISMATCH: {failures}")
sys.exit(1 if failures else 0)
