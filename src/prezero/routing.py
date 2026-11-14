"""Routing heuristics."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


HEILBRONN_DEPOT = (49.1427, 9.2108)


def build_route(
    scored: pd.DataFrame,
    locations: pd.DataFrame,
    depot: tuple[float, float] | dict[str, float] = HEILBRONN_DEPOT,
    max_stops: int = 25,
    date: str | None = None,
    output_dir: str | Path = ".",
) -> pd.DataFrame:
    """Build and persist a nearest-neighbour route from scored containers."""
    if max_stops < 1:
        raise ValueError("max_stops must be at least 1")
    depot_point = _depot_point(depot)
    candidates = scored.copy()
    if "critical" in candidates and candidates["critical"].any():
        candidates = candidates[candidates["critical"]]
    candidates = candidates.sort_values("score", ascending=False)
    candidates = (
        candidates.groupby("Location_id", as_index=False)
        .agg(
            score=("score", "max"),
            critical=("critical", "any"),
            material_type=("material_type", lambda values: ",".join(sorted(set(values)))),
        )
        .head(max_stops)
    )
    joined = candidates.merge(locations, on="Location_id", how="inner")
    joined = joined.dropna(subset=["lat", "lon"])
    route_rows = _nearest_neighbour(joined, depot_point)
    route = pd.DataFrame(route_rows)
    if route.empty:
        route = pd.DataFrame(
            columns=[
                "route_order",
                "Location_id",
                "material_type",
                "score",
                "critical",
                "lat",
                "lon",
                "source",
                "distance_from_previous_km",
            ]
        )
    planned_km = float(route["distance_from_previous_km"].sum()) if not route.empty else 0.0
    return_km = (
        haversine_km(float(route.iloc[-1]["lat"]), float(route.iloc[-1]["lon"]), *depot_point)
        if not route.empty
        else 0.0
    )
    full_round_km = planned_km + return_km
    route_date = date or _route_date(scored)
    payload = {
        "date": route_date,
        "depot": {"lat": depot_point[0], "lon": depot_point[1]},
        "stops": _json_records(route),
        "planned_km": round(planned_km, 3),
        "full_round_km": round(full_round_km, 3),
        "planned_vs_full_round_km": {
            "planned": round(planned_km, 3),
            "full_round": round(full_round_km, 3),
        },
    }
    destination = Path(output_dir) / f"route_{route_date}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return route


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two WGS84 points in kilometres."""
    radius = 6371.0088
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(value))


def _nearest_neighbour(
    candidates: pd.DataFrame, depot: tuple[float, float]
) -> list[dict[str, object]]:
    remaining = candidates.to_dict("records")
    current = depot
    route: list[dict[str, object]] = []
    while remaining:
        next_stop = min(
            remaining,
            key=lambda row: haversine_km(current[0], current[1], float(row["lat"]), float(row["lon"])),
        )
        remaining.remove(next_stop)
        distance = haversine_km(current[0], current[1], float(next_stop["lat"]), float(next_stop["lon"]))
        route.append(
            {
                "route_order": len(route) + 1,
                "Location_id": next_stop["Location_id"],
                "material_type": next_stop["material_type"],
                "score": float(next_stop["score"]),
                "critical": bool(next_stop["critical"]),
                "lat": float(next_stop["lat"]),
                "lon": float(next_stop["lon"]),
                "source": next_stop.get("source", "unknown"),
                "distance_from_previous_km": round(distance, 3),
            }
        )
        current = (float(next_stop["lat"]), float(next_stop["lon"]))
    return route


def _depot_point(depot: tuple[float, float] | dict[str, float]) -> tuple[float, float]:
    if isinstance(depot, dict):
        return float(depot["lat"]), float(depot["lon"])
    return float(depot[0]), float(depot[1])


def _route_date(scored: pd.DataFrame) -> str:
    if "date" in scored and not scored["date"].empty:
        return pd.Timestamp(scored["date"].iloc[0]).date().isoformat()
    return "undated"


def _json_records(route: pd.DataFrame) -> list[dict[str, object]]:
    return json.loads(route.to_json(orient="records")) if not route.empty else []
