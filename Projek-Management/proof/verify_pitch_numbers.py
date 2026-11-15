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
    "total_critical_locations": 127,
    "total_active_locations": 142,
    "planned_km": 227.23,
    "vehicles_needed": 3,
    "rounds": 16,
    "shift_hours": 19.85,
    "max_vehicle_shift_hours": 7.96,
    "t_collected": 116.18,
    "full_round_km": 1368.78,
    "full_round_vehicles": 21,
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
    "shift_6h": {"vehicles_needed": 4, "max_vehicle_shift_hours": 5.55, "planned_km": 222.51},
    "truck_8t": {"vehicles_needed": 3, "rounds": 16, "planned_km": 253.36},
    "plus_vehicle": {"num_stops": 43, "planned_km": 343.12, "unserved_critical_locations": 84},
    "all_critical": {"num_stops": 127, "planned_km": 923.22, "vehicles_needed": 12},
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

print("\n# Projek-Management/proof/demo_day_numbers.json")
demo_day_path = ROOT / "Projek-Management" / "proof" / "demo_day_numbers.json"
if not demo_day_path.is_file():
    failures.append("demo_day_numbers.json missing")
else:
    demo_nums = json.loads(demo_day_path.read_text(encoding="utf-8"))
    check("demo_day containers_due", demo_nums.get("containers_due"), 509)
    check("demo_day in_tour_stops", demo_nums.get("in_tour_stops"), 25)
    check("demo_day km_optimized", demo_nums.get("km_optimized"), 227.23)
    check("demo_day km_status_quo_b1", demo_nums.get("km_status_quo_b1"), 1662.70)
    check("demo_day vehicles", demo_nums.get("vehicles"), 3)
    check("demo_day hours", demo_nums.get("hours"), 7.96)
    check("demo_day tonnes", demo_nums.get("tonnes"), 116.18)

    # UI cross-check
    print("\n# UI cross-check against demo_day_numbers.json")
    ui_snaps_match = re.search(
        r'<script id="date-snapshots-payload" type="application/json">(.*?)</script>',
        page,
        re.S,
    )
    if ui_snaps_match:
        ui_snaps = json.loads(ui_snaps_match.group(1).replace("<\\/", "</"))
        demo_snap = ui_snaps.get(demo_nums.get("demo_date", "2026-04-15"), {})
        snap_metrics = demo_snap.get("metrics", {})
        check("ui planned_km", snap_metrics.get("planned_km"), demo_nums.get("km_optimized"))
        check("ui num_stops", snap_metrics.get("num_stops"), demo_nums.get("in_tour_stops"))
        check("ui vehicles", snap_metrics.get("vehicles_needed"), demo_nums.get("vehicles"))
        check("ui longest_shift", snap_metrics.get("max_vehicle_shift_hours"), demo_nums.get("hours"))
        check("ui tonnes", snap_metrics.get("t_collected"), demo_nums.get("tonnes"))
        check("ui critical_containers", demo_snap.get("today_critical_containers"), demo_nums.get("containers_due"))

    # Docs (docs/STATUS.md) cross-check
    print("\n# Docs (docs/STATUS.md) cross-check against demo_day_numbers.json")
    status_doc = (ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8")
    for key, text_pattern in [
        ("demo_date", demo_nums.get("demo_date", "2026-04-15")),
        ("containers_due", str(demo_nums.get("containers_due"))),
        ("in_tour_stops", f"{demo_nums.get('in_tour_stops')} von {demo_nums.get('locations_due')}"),
        ("km_optimized", f"{demo_nums.get('km_optimized'):.1f}".replace(".", ",")),
        ("vehicles", f"{demo_nums.get('vehicles')} Fahrzeuge"),
        ("hours", f"{demo_nums.get('hours'):.2f}".replace(".", ",")),
        ("tonnes", f"{demo_nums.get('tonnes'):.1f}".replace(".", ",")),
    ]:
        ok = text_pattern in status_doc
        print(f"{'OK  ' if ok else 'FAIL'}     docs/STATUS.md contains '{text_pattern}' ({key})")
        if not ok:
            failures.append(f"STATUS.md missing {text_pattern}")

    # Pitch (Pitch/NOTES.md + Pitch/deck.md) cross-check
    print("\n# Pitch (Pitch/NOTES.md + Pitch/deck.md) cross-check against demo_day_numbers.json")
    notes_doc = (ROOT / "Pitch" / "NOTES.md").read_text(encoding="utf-8")
    deck_doc = (ROOT / "Pitch" / "deck.md").read_text(encoding="utf-8")
    for key, pattern in [
        ("containers_due", f"{demo_nums.get('containers_due')}"),
        ("in_tour_stops", f"{demo_nums.get('in_tour_stops')} von {demo_nums.get('locations_due')}"),
        ("km_optimized", f"{demo_nums.get('km_optimized'):.1f}".replace(".", ",")),
        ("km_status_quo_b1", "1.662,70"),
        ("vehicles", f"{demo_nums.get('vehicles')} Fahrzeuge"),
        ("hours", f"{demo_nums.get('hours'):.2f}".replace(".", ",")),
        ("tonnes", "116,2"),
    ]:
        ok = pattern in notes_doc
        print(f"{'OK  ' if ok else 'FAIL'}     Pitch/NOTES.md contains '{pattern}' ({key})")
        if not ok:
            failures.append(f"NOTES.md missing {pattern}")

    for key, pattern in [
        ("km_optimized_vs_b1", "227,2 km** vs. **1.662,70 km"),
        ("stops", "25 Standorte bedient"),
        ("vehicles", "3 Fahrzeuge im Einsatz"),
        ("hours", "7,96 h"),
        ("tonnes", "116,18 t"),
    ]:
        ok = pattern in deck_doc
        print(f"{'OK  ' if ok else 'FAIL'}     Pitch/deck.md contains '{pattern}' ({key})")
        if not ok:
            failures.append(f"deck.md missing {pattern}")

print("\nRESULT:", "ALL MATCH" if not failures else f"{len(failures)} MISMATCH: {failures}")
sys.exit(1 if failures else 0)
