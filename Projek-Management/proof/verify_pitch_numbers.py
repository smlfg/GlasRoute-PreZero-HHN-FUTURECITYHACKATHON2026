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

# Numbers as written in the pitch documents.
EXPECTED_ROUTE = {
    "num_stops": 25,
    "total_critical_locations": 97,
    "total_active_locations": 121,
    "planned_km": 194.54,
    "vehicles_needed": 2,
    "rounds": 11,
    "shift_hours": 15.47,
    "max_vehicle_shift_hours": 7.83,
    "t_collected": 84.4,
    "full_round_km": 1179.03,
    "full_round_vehicles": 20,
}
EXPECTED_BENCH_KM = {"B0": 1838.75, "B1": 1736.53, "B2": 508.36, "B4": 475.43}
EXPECTED_BENCH_STOPS = {"B1": 121, "B2": 95}
EXPECTED_EFFECTS = {
    "demand_pct": 70.7,
    "routing_pct": 6.5,
    "overall_vs_b1_pct": 72.6,
    "overall_vs_b0_pct": 74.1,
}
EXPECTED_SPANS = {
    "demand_pct": (68.6, 97.8),
    "routing_pct": (1.1, 16.8),
    "overall_vs_b1_pct": (72.6, 97.9),
}
EXPECTED_WHAT_IF = {
    "shift_6h": {"vehicles_needed": 3, "max_vehicle_shift_hours": 5.55, "planned_km": 174.61},
    "truck_8t": {"vehicles_needed": 3, "planned_km": 218.87},
    "plus_vehicle": {"num_stops": 48, "planned_km": 244.32, "unserved_critical_locations": 49},
    "all_critical": {"num_stops": 97, "planned_km": 382.87, "vehicles_needed": 5},
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
