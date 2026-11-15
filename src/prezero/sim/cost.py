"""Kostenmodell je Szenario (docs/MODEL_SPEC.md §7). Alle Sätze sind Annahmen."""

from __future__ import annotations

# Annahme: Fahrzeugtag 500 EUR, Crew 2 Personen x 32 EUR/h = 64 EUR/h (Crew-h = Schicht-h), 0,65 EUR/km.
RATES = {"vehicle_day_eur": 500.0, "crew_hour_eur": 64.0, "km_eur": 0.65}


def scenario_cost(vehicle_days: float, hours: float, km: float, rates: dict | None = None) -> dict:
    """Kosten = Fahrzeugtage x 500 + Crew-h x 64 + km x 0,65 (Annahme)."""
    r = rates or RATES
    veh = vehicle_days * r["vehicle_day_eur"]
    crew = hours * r["crew_hour_eur"]
    kmc = km * r["km_eur"]
    return {
        "total_eur": round(veh + crew + kmc, 2),
        "vehicle_days_eur": round(veh, 2),
        "crew_eur": round(crew, 2),
        "km_eur": round(kmc, 2),
    }


def annotate_summary(summary: dict, rates: dict | None = None) -> dict:
    """Fill cost_eur/cost_breakdown per scenario; flag cheapest/fewest_overflows per time_model."""
    scenarios = summary["scenarios"]
    entries = scenarios.values() if isinstance(scenarios, dict) else scenarios
    entries = list(entries)
    for e in entries:
        c = scenario_cost(e["vehicle_days"], e["hours"], e["km"], rates)
        e["cost_eur"] = c["total_eur"]
        e["cost_breakdown"] = c
        e.setdefault("flags", {})
    groups: dict = {}
    for e in entries:
        groups.setdefault(e.get("time_model"), []).append(e)
    for g in groups.values():
        min_cost = min(e["cost_eur"] for e in g)
        min_ovf = min(e["overflow_events"] for e in g)
        for e in g:
            e["flags"]["cheapest"] = e["cost_eur"] == min_cost
            e["flags"]["fewest_overflows"] = e["overflow_events"] == min_ovf
    return summary
