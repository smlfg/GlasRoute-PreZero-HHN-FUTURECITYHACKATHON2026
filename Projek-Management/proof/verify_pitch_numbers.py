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

# Numbers as written in the pitch documents (measure-and-empty, volume limit, 14.11.2026 19:00).
EXPECTED_ROUTE = {
    "num_stops": 25,
    "total_critical_locations": 72,
    "total_active_locations": 121,
    "planned_km": 125.21,
    "vehicles_needed": 2,
    "rounds": 7,
    "shift_hours": 10.51,
    "max_vehicle_shift_hours": 7.26,
    "t_collected": 63.58,
    "full_round_km": 1202.24,
    "full_round_vehicles": 20,
}
EXPECTED_BENCH_KM = {"B0": 1795.91, "B1": 1662.70, "B2": 316.31, "B4": 285.79}
EXPECTED_BENCH_STOPS = {"B1": 121, "B2": 73}
EXPECTED_EFFECTS = {
    "demand_pct": 81.0,
    "routing_pct": 9.6,
    "overall_vs_b1_pct": 82.8,
    "overall_vs_b0_pct": 84.1,
}
EXPECTED_SPANS = {
    "demand_pct": (79.7, 97.3),
    "routing_pct": (0.0, 13.0),
    "overall_vs_b1_pct": (80.7, 97.3),
}
EXPECTED_WHAT_IF = {
    "shift_6h": {"vehicles_needed": 2, "max_vehicle_shift_hours": 5.57, "planned_km": 128.72},
    "truck_8t": {"vehicles_needed": 2, "rounds": 10, "planned_km": 177.53},
    "plus_vehicle": {"num_stops": 68, "planned_km": 258.24, "unserved_critical_locations": 4},
    "all_critical": {"num_stops": 72, "planned_km": 270.94, "vehicles_needed": 3},
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

print("\n# data/raw/glass_fill_levels_anonymized_f.csv")
raw = pd.read_csv(ROOT / "data/raw/glass_fill_levels_anonymized_f.csv", dtype=str)
check("raw rows", len(raw), EXPECTED_RAW["rows"])
check("raw ids", raw["Location_id"].nunique(), EXPECTED_RAW["ids"])
fill = raw["fill_level_perc"].str.strip().str.lower()
check("raw overfull", int((fill == "overfull").sum()), EXPECTED_RAW["overfull"])

print("\nRESULT:", "ALL MATCH" if not failures else f"{len(failures)} MISMATCH: {failures}")
sys.exit(1 if failures else 0)
