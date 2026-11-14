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
    "total_critical_locations": 106,
    "total_active_locations": 121,
    "planned_km": 249.9,
    "full_round_km": 1202.24,
    "saved_km": 952.34,
    "saved_pct": 79.2,
    "vehicles_needed": 4,
    "rounds": 19,
    "shift_hours": 22.68,
    "max_vehicle_shift_hours": 7.58,
    "t_collected": 142.82,
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
