"""Verify that the demo-day route matches the canonical fact sheet.

Run after `prezero-route run` (or directly if route_2026-04-15.json exists):
    PYTHONPATH=src python Projek-Management/proof/verify_demo_day.py

Exit code 0 only if every fact matches. Failures are printed as DIFF lines.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


DEMO_DATE = "2026-04-15"

FACTS = {
    "date": DEMO_DATE,
    "num_stops": 25,
    "total_critical_locations": 127,
    "total_active_locations": 142,
    "planned_km": 227.23,
    "full_round_km": 1368.78,
    "saved_km": 1141.55,
    "saved_pct": 83.4,
    "vehicles_needed": 3,
    "rounds": 16,
    "shift_hours": 19.85,
    "max_vehicle_shift_hours": 7.96,
    "t_collected": 116.18,
    "max_stops": 25,
}

TOLERANCE = {
    "planned_km": 0.05,
    "full_round_km": 0.05,
    "saved_km": 0.05,
    "saved_pct": 0.05,
    "shift_hours": 0.01,
    "max_vehicle_shift_hours": 0.01,
    "t_collected": 0.01,
}


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    route_path = repo_root / f"route_{DEMO_DATE}.json"

    if not route_path.is_file():
        print(f"MISSING: {route_path}")
        print("Run: prezero-route run --date 2026-04-15")
        return 1

    route = json.loads(route_path.read_text(encoding="utf-8"))

    mismatches: list[str] = []
    for key, expected in FACTS.items():
        actual = route.get(key)
        if actual is None:
            mismatches.append(f"{key}: missing in route (expected {expected})")
            continue

        tol = TOLERANCE.get(key)
        if tol is not None:
            if not isinstance(actual, (int, float)) or abs(float(actual) - float(expected)) > tol:
                mismatches.append(
                    f"{key}: expected {_fmt(expected)}, got {_fmt(actual)} (tol {tol})"
                )
        elif actual != expected:
            mismatches.append(f"{key}: expected {_fmt(expected)}, got {_fmt(actual)}")

    # Cross-check against the human-readable fact sheet.
    facts_path = repo_root / "Pitch" / "demo_facts.txt"
    if facts_path.is_file():
        facts_text = facts_path.read_text(encoding="utf-8")
        for line in [
            f"Demo-Tag: {DEMO_DATE}",
            f"Geplante Tour: {FACTS['planned_km']} km",
            f"Fahrzeuge: {FACTS['vehicles_needed']}",
            f"Runden: {FACTS['rounds']}",
            f"Längste Einzelschicht: {FACTS['max_vehicle_shift_hours']} h",
            f"Sammelmenge: {FACTS['t_collected']} t",
        ]:
            if line not in facts_text:
                mismatches.append(f"demo_facts.txt missing line: {line}")

    if mismatches:
        print(f"RESULT: MISMATCH for {DEMO_DATE}")
        for m in mismatches:
            print(f"  DIFF: {m}")
        return 1

    print(f"RESULT: DEMO-DAY {DEMO_DATE} NUMBERS MATCH")
    print(
        f"  {FACTS['num_stops']} stops · {FACTS['planned_km']} km · "
        f"{FACTS['vehicles_needed']} vehicles · {FACTS['rounds']} rounds · "
        f"{FACTS['max_vehicle_shift_hours']} h longest shift · {FACTS['t_collected']} t"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
