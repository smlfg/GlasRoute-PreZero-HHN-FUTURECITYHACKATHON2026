"""Routing heuristics using Haversine distance and nearest neighbor."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

# Fixed Heilbronn depot (TechCampus / city center area).
DEFAULT_DEPOT: tuple[float, float] = (49.1427, 9.2109)
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two WGS84 coordinates in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _aggregate_locations(scored: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    """Collapse per-material scores to unique Location_id rows with coordinates."""
    if scored.empty:
        return pd.DataFrame()

    work = scored.copy()
    if "critical" not in work.columns:
        work["critical"] = work["score"] >= 0.7

    ordered = work.sort_values(
        ["Location_id", "score", "material_type"],
        ascending=[True, False, True],
    )
    per_loc = ordered.groupby("Location_id", as_index=False).agg(
        score=("score", "max"),
        critical=("critical", "any"),
        primary_material=("material_type", "first"),
        last_fill_level=("last_fill_level", "max"),
    )
    merged = per_loc.merge(
        locations[["Location_id", "lat", "lon", "source", "confidence"]],
        on="Location_id",
        how="inner",
    )
    return merged.sort_values(["score", "Location_id"], ascending=[False, True]).reset_index(
        drop=True
    )


def _nearest_neighbor_tour(
    candidates: pd.DataFrame,
    depot: tuple[float, float],
) -> tuple[list[dict[str, Any]], float]:
    """Order candidate locations with greedy nearest-neighbor and close the loop."""
    if candidates.empty:
        return [], 0.0

    remaining = candidates.to_dict(orient="records")
    stops: list[dict[str, Any]] = []
    cur_lat, cur_lon = float(depot[0]), float(depot[1])
    total_km = 0.0

    while remaining:
        best_idx = min(
            range(len(remaining)),
            key=lambda idx: haversine_km(
                cur_lat, cur_lon, float(remaining[idx]["lat"]), float(remaining[idx]["lon"])
            ),
        )
        chosen = remaining.pop(best_idx)
        leg_km = haversine_km(cur_lat, cur_lon, float(chosen["lat"]), float(chosen["lon"]))
        total_km += leg_km
        cur_lat, cur_lon = float(chosen["lat"]), float(chosen["lon"])
        stops.append(
            {
                "order": len(stops) + 1,
                "Location_id": str(chosen["Location_id"]),
                "lat": round(cur_lat, 6),
                "lon": round(cur_lon, 6),
                "score": round(float(chosen["score"]), 4),
                "critical": bool(chosen["critical"]),
                "primary_material": str(chosen["primary_material"]),
                "last_fill_level": float(chosen["last_fill_level"]),
                "source": str(chosen["source"]),
                "confidence": str(chosen["confidence"]),
                "leg_km": round(leg_km, 3),
                "cumulative_km": round(total_km, 3),
            }
        )

    return_km = haversine_km(cur_lat, cur_lon, float(depot[0]), float(depot[1]))
    total_km += return_km
    return stops, total_km


def build_route(
    scored: pd.DataFrame,
    locations: pd.DataFrame,
    depot: tuple[float, float] = DEFAULT_DEPOT,
    max_stops: int = 25,
    date: str | None = None,
    output_dir: str | Path = ".",
) -> dict[str, Any]:
    """Build a nearest-neighbor route from critical containers and compare vs. full round."""
    loc_scores = _aggregate_locations(scored, locations)

    if loc_scores.empty:
        route_data: dict[str, Any] = {
            "date": date,
            "depot": {"lat": float(depot[0]), "lon": float(depot[1])},
            "max_stops": int(max_stops),
            "num_stops": 0,
            "total_critical_locations": 0,
            "total_active_locations": 0,
            "planned_km": 0.0,
            "full_round_km": 0.0,
            "saved_km": 0.0,
            "saved_pct": 0.0,
            "comparison": "0.0 km planned vs. 0.0 km full round",
            "stops": [],
        }
    else:
        critical_locs = loc_scores[loc_scores["critical"]]
        pool = critical_locs if not critical_locs.empty else loc_scores
        selected = pool.head(max_stops).reset_index(drop=True)

        stops, planned_km = _nearest_neighbor_tour(selected, depot)
        _, full_round_km = _nearest_neighbor_tour(loc_scores, depot)
        saved_km = max(0.0, full_round_km - planned_km)
        saved_pct = (saved_km / full_round_km * 100.0) if full_round_km > 0 else 0.0

        route_data = {
            "date": date,
            "depot": {"lat": float(depot[0]), "lon": float(depot[1])},
            "max_stops": int(max_stops),
            "num_stops": len(stops),
            "total_critical_locations": int(len(critical_locs)),
            "total_active_locations": int(len(loc_scores)),
            "planned_km": round(planned_km, 2),
            "full_round_km": round(full_round_km, 2),
            "saved_km": round(saved_km, 2),
            "saved_pct": round(saved_pct, 1),
            "comparison": (
                f"{round(planned_km, 2)} km planned ({len(stops)} stops) "
                f"vs. {round(full_round_km, 2)} km full round ({len(loc_scores)} stops)"
            ),
            "stops": stops,
        }

    if date is not None:
        out_path = Path(output_dir) / f"route_{date}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(route_data, indent=2), encoding="utf-8")

    return route_data
