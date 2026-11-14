"""Observed measure-and-empty visits and reconstructed daily route workloads."""

from __future__ import annotations

import json

import pandas as pd

from prezero.ingest import clean
from prezero.routing import OperationalConfig, build_route, density_for

VISIT_KEY = ["date", "Location_id", "material_type"]
GEOGRAPHY_NOTE = "Orte simuliert, Besuchstage aus Daten."


def observed_visits(raw: pd.DataFrame) -> pd.DataFrame:
    readings = clean(raw)
    if len(readings) != len(raw):
        raise ValueError("Incomplete readings would silently reduce the workload")
    readings["date"] = pd.to_datetime(readings.date).dt.normalize()
    groups = readings.groupby(VISIT_KEY, sort=True)
    if (groups.fill_level_numeric.nunique() > 1).any():
        raise ValueError("Conflicting levels for one container visit")
    return groups.agg(
        measurement_records=("fill_level_numeric", "size"),
        fill_pct=("fill_level_numeric", "first"),
        overfull=("is_overfull", "any"),
    ).reset_index()


def route_day(visits: pd.DataFrame, locations: pd.DataFrame, config: OperationalConfig) -> dict:
    """Route every selected bin as critical, aggregating co-located lifts once."""
    if locations.Location_id.duplicated().any() or not visits.Location_id.isin(locations.Location_id).all():
        raise ValueError("Every selected Location_id needs exactly one mapped point")
    scored = visits.assign(
        last_fill_level=visits.fill_pct, est_fill_level=visits.fill_pct,
        critical=True, score=visits.fill_pct / 100,
    )
    route = build_route(scored, locations, config=config, output_dir=None)
    stops = [s for s in route["stops"] if s["stop_type"] == "collection"]
    if sum(s["critical_bins"] for s in stops) != len(visits):
        raise ValueError("Routing omitted selected containers")
    if any(s["load_kg"] > config.vehicle_max_weight_kg or
           s["load_m3"] > config.vehicle_max_volume_m3 for s in stops):
        raise ValueError("Reconstructed load exceeds vehicle capacity")
    if route["max_vehicle_shift_hours"] > config.max_shift_hours:
        raise ValueError("Reconstructed work exceeds shift limit")
    return route


def historical_days(raw: pd.DataFrame, locations: pd.DataFrame, config: OperationalConfig) -> pd.DataFrame:
    visits = observed_visits(raw)
    visits["volume_m3"] = visits.fill_pct * config.container_volume_m3 / 100
    visits["mass_kg"] = visits.volume_m3 * visits.material_type.map(lambda m: density_for(config, m))
    rows = []
    for date, day in visits.groupby("date"):
        route = route_day(day, locations, config)
        material = {}
        for color, group in day.groupby("material_type"):
            material[color] = {
                "containers": len(group), "overfull": int(group.overfull.sum()),
                "fill_pct_counts": group.fill_pct.value_counts().sort_index().to_dict(),
                "estimated_m3": group.volume_m3.sum(), "estimated_kg": group.mass_kg.sum(),
            }
        rows.append({
            "date": date.date().isoformat(), "measurement_records": day.measurement_records.sum(),
            "containers_visited": len(day), "location_ids": day.Location_id.nunique(),
            "modeled_sites": route["num_stops"], "mean_fill_pct": day.fill_pct.mean(),
            "median_fill_pct": day.fill_pct.median(), "overfull_observations": day.overfull.sum(),
            "estimated_volume_m3": day.volume_m3.sum(), "estimated_mass_kg": day.mass_kg.sum(),
            "modeled_km": route["km"], "modeled_vehicle_days": route["vehicles_needed"],
            "modeled_vehicle_hours": route["shift_hours"], "modeled_rounds": route["rounds"],
            "unserved_bins": 0, "material_breakdown": json.dumps(material, sort_keys=True),
            "geography": GEOGRAPHY_NOTE,
        })
    return pd.DataFrame(rows)
