"""Standortplanung-What-if: simulierte Vorschläge für neue Glascontainer-Standorte.

Alle Ergebnisse basieren auf den vorhandenen (teils simulierten) Koordinaten. Dieses Modul
macht keine Aussage über reale Standorte — es zeigt nur, welche Gebiete nach den
vorhandenen Daten unterversorgt erscheinen und wie sich ein hypothetischer neuer Standort
über die ersten Wochen entwickeln könnte.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from prezero.locations import HEILBRONN_BBOX
from prezero.routing import OperationalConfig, haversine_km

GRID_CELLS_PER_AXIS = 40
MAX_NEW_SITES = 5
MIN_SITE_SEPARATION_M = 300.0
WEEKS = 13  # Woche 0 bis 12
OVERFULL_THRESHOLD = 110.0
CRITICAL_THRESHOLD = 80.0
EARTH_RADIUS_M = 6_371_000.0


def _get_numeric_series(scored_df: pd.DataFrame, column: str) -> pd.Series:
    """Return a numeric Series for ``column`` even if it is missing."""
    raw = scored_df.get(column, pd.Series(dtype=float))
    if not isinstance(raw, pd.Series):
        raw = pd.Series(dtype=float)
    return pd.to_numeric(raw, errors="coerce").fillna(0.0)


@dataclass(frozen=True)
class LocationPlanningConfig:
    """Subset of OperationalConfig used by the location-planning what-if."""

    radius_m: float = 500.0
    adoption_weeks: float = 8.0
    logistic_steepness: float = 1.0
    road_detour_factor: float = 1.35

    @classmethod
    def from_operational_config(cls, cfg: OperationalConfig | None) -> "LocationPlanningConfig":
        if cfg is None:
            return cls()
        return cls(
            radius_m=float(cfg.location_planning_radius_m),
            adoption_weeks=float(cfg.location_planning_adoption_weeks),
            logistic_steepness=float(cfg.location_planning_logistic_steepness),
            road_detour_factor=float(cfg.road_detour_factor),
        )


def _haversine_m(
    lat1: float, lon1: float, lat2: float | pd.Series, lon2: float | pd.Series
) -> float | pd.Series:
    """Great-circle distance in meters (scalar or vectorized against pandas Series)."""
    scalar_other = isinstance(lat2, (int, float)) and isinstance(lon2, (int, float))
    phi1 = math.radians(lat1)
    lambda1 = math.radians(lon1)
    phi2 = np.radians(lat2)
    lambda2 = np.radians(lon2)
    d_phi = phi2 - phi1
    d_lambda = lambda2 - lambda1
    a = np.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * np.cos(phi2) * np.sin(d_lambda / 2.0) ** 2
    distances = 2.0 * EARTH_RADIUS_M * np.arcsin(np.minimum(1.0, np.sqrt(a)))
    if scalar_other:
        return float(distances)
    return pd.Series(distances, index=lat2.index if hasattr(lat2, "index") else None)


def _make_grid(bbox: tuple[float, float, float, float] | None = None) -> pd.DataFrame:
    """Return a regular lat/lon grid over the bbox with one row per cell."""
    south, west, north, east = bbox or HEILBRONN_BBOX
    lats = np.linspace(south, north, GRID_CELLS_PER_AXIS)
    lons = np.linspace(west, east, GRID_CELLS_PER_AXIS)
    records: list[dict[str, float]] = []
    for lat in lats:
        for lon in lons:
            records.append({"lat": round(float(lat), 6), "lon": round(float(lon), 6)})
    return pd.DataFrame(records)


def _score_grid_cells(
    grid: pd.DataFrame,
    locations_df: pd.DataFrame,
    scored_df: pd.DataFrame,
    cfg: LocationPlanningConfig,
) -> pd.DataFrame:
    """Score each grid cell by nearby overfull demand and distance coverage gap."""
    work = grid.copy()

    # Per-container demand proxy: avg_daily_increase (pp/day). Fall back to 0.
    scored = scored_df.copy()
    scored["Location_id"] = scored["Location_id"].astype(str).str.strip()
    scored["demand"] = _get_numeric_series(scored, "avg_daily_increase")
    scored["overfull_rate"] = _get_numeric_series(scored, "overfull_rate")
    scored["est_fill_level"] = _get_numeric_series(scored, "est_fill_level")

    locs = locations_df.copy()
    locs["Location_id"] = locs["Location_id"].astype(str).str.strip()
    merged = scored.merge(locs[["Location_id", "lat", "lon"]], on="Location_id", how="left")
    merged = merged.dropna(subset=["lat", "lon"])

    demand_scores: list[float] = []
    gap_scores: list[float] = []

    for _, cell in work.iterrows():
        distances = (
            _haversine_m(cell["lat"], cell["lon"], merged["lat"], merged["lon"])
            if not merged.empty
            else pd.Series(dtype=float)
        )
        nearby = merged[distances <= cfg.radius_m]
        if nearby.empty:
            demand_scores.append(0.0)
            gap_scores.append(cfg.radius_m)
            continue

        # Weight high overfull rate and high demand more; inverse distance weighting.
        weights = 1.0 / (1.0 + distances[distances <= cfg.radius_m] / cfg.radius_m)
        demand_score = float((nearby["demand"] * (1.0 + 5.0 * nearby["overfull_rate"]) * weights).sum())
        demand_scores.append(demand_score)

        # Coverage gap: distance to nearest existing container (closer = worse candidate).
        nearest_m = float(distances.min()) if not distances.empty else cfg.radius_m
        gap_scores.append(min(cfg.radius_m, nearest_m))

    work["demand_score"] = demand_scores
    # Prefer cells with high demand and also some distance from existing sites.
    work["gap_score"] = np.array(gap_scores) / cfg.radius_m
    work["total_score"] = work["demand_score"] * (0.4 + 0.6 * work["gap_score"])
    return work.sort_values("total_score", ascending=False).reset_index(drop=True)


def _select_sites(
    scored_grid: pd.DataFrame,
    max_sites: int = MAX_NEW_SITES,
    min_separation_m: float = MIN_SITE_SEPARATION_M,
) -> pd.DataFrame:
    """Pick top-scoring cells respecting a minimum separation."""
    picked: list[dict[str, Any]] = []
    for _, row in scored_grid.iterrows():
        if len(picked) >= max_sites:
            break
        too_close = any(
            _haversine_m(row["lat"], row["lon"], p["lat"], p["lon"]) < min_separation_m
            for p in picked
        )
        if too_close:
            continue
        picked.append(row.to_dict())
    return pd.DataFrame(picked)


def _adoption_share(week: int, adoption_weeks: float, steepness: float) -> float:
    """Logistic adoption curve from 0 % to ~100 % over adoption_weeks."""
    if week <= 0:
        return 0.0
    if adoption_weeks <= 0:
        return 1.0
    midpoint = adoption_weeks / 2.0
    # Logistic: L / (1 + exp(-k*(x - x0))). L=1, x0=midpoint, k=steepness.
    share = 1.0 / (1.0 + math.exp(-steepness * (week - midpoint)))
    return float(share)


def _compute_demand_transfer(
    sites: pd.DataFrame,
    scored_df: pd.DataFrame,
    locations_df: pd.DataFrame,
    cfg: LocationPlanningConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """For each existing container compute the demand share taken over by each new site."""
    if sites.empty:
        empty_transfer = scored_df.copy()
        empty_transfer["new_site_idx"] = pd.Series(dtype=int)
        empty_transfer["share_taken"] = 0.0
        return empty_transfer, pd.DataFrame()

    scored = scored_df.copy()
    scored["Location_id"] = scored["Location_id"].astype(str).str.strip()
    locs = locations_df.copy()
    locs["Location_id"] = locs["Location_id"].astype(str).str.strip()
    merged = scored.merge(locs[["Location_id", "lat", "lon"]], on="Location_id", how="left")
    merged = merged.dropna(subset=["lat", "lon"]).copy()
    merged["demand"] = _get_numeric_series(merged, "avg_daily_increase")
    merged["est_fill_level"] = _get_numeric_series(merged, "est_fill_level")

    transfer_rows: list[dict[str, Any]] = []
    for site_idx, site in sites.iterrows():
        distances = _haversine_m(site["lat"], site["lon"], merged["lat"], merged["lon"])
        in_radius = distances <= cfg.radius_m
        if not in_radius.any():
            continue
        # Inverse-distance weights within radius.
        inv_dist = (cfg.radius_m - distances[in_radius].clip(upper=cfg.radius_m)) / cfg.radius_m
        weights = inv_dist / inv_dist.sum() if inv_dist.sum() > 0 else inv_dist
        for (idx, weight) in zip(merged[in_radius].index, weights, strict=False):
            transfer_rows.append(
                {
                    "Location_id": merged.loc[idx, "Location_id"],
                    "material_type": merged.loc[idx, "material_type"],
                    "new_site_idx": int(site_idx),
                    "share_taken": float(weight),
                    "demand": float(merged.loc[idx, "demand"]),
                    "est_fill_level": float(merged.loc[idx, "est_fill_level"]),
                }
            )

    transfer = pd.DataFrame(transfer_rows)
    return merged, transfer


def _estimate_tour_km(
    locations: pd.DataFrame,
    fill_levels: pd.Series,
    cfg: LocationPlanningConfig,
    depot: tuple[float, float] = (49.1427, 9.2109),
) -> float:
    """Rough nearest-neighbor km estimate for critical containers (>=80 %) plus depot."""
    if locations.empty or fill_levels.empty:
        return 0.0
    # Align by position; fill_levels may have a MultiIndex from set_index().
    mask = fill_levels.to_numpy() >= CRITICAL_THRESHOLD
    crit = locations[mask].copy() if len(mask) == len(locations) else locations.iloc[:0].copy()
    if crit.empty:
        return 0.0

    # Greedy nearest neighbor from depot.
    remaining = crit.to_dict(orient="records")
    total_km = 0.0
    cur_lat, cur_lon = depot
    while remaining:
        best_idx = min(
            range(len(remaining)),
            key=lambda i: haversine_km(cur_lat, cur_lon, remaining[i]["lat"], remaining[i]["lon"]),
        )
        chosen = remaining.pop(best_idx)
        total_km += haversine_km(cur_lat, cur_lon, chosen["lat"], chosen["lon"])
        cur_lat, cur_lon = chosen["lat"], chosen["lon"]
    total_km += haversine_km(cur_lat, cur_lon, depot[0], depot[1])
    return round(total_km * cfg.road_detour_factor, 2)


def plan_new_locations(
    scored_df: pd.DataFrame,
    locations_df: pd.DataFrame,
    operational_cfg: OperationalConfig | None = None,
) -> dict[str, Any]:
    """Run the full Standortplanung what-if and return a serializable result bundle."""
    cfg = LocationPlanningConfig.from_operational_config(operational_cfg)

    grid = _make_grid()
    scored_grid = _score_grid_cells(grid, locations_df, scored_df, cfg)
    sites = _select_sites(scored_grid)

    merged, transfer = _compute_demand_transfer(sites, scored_df, locations_df, cfg)

    if merged.empty:
        return {
            "simulated": True,
            "config": {
                "radius_m": cfg.radius_m,
                "adoption_weeks": cfg.adoption_weeks,
                "logistic_steepness": cfg.logistic_steepness,
            },
            "new_sites": [],
            "affected_containers": 0,
            "total_existing_demand_pp_day": 0.0,
            "total_transferred_demand_pp_day": 0.0,
            "total_new_site_demand_pp_day": 0.0,
            "demand_conserved": True,
            "tour_km_before": 0.0,
            "tour_km_after": 0.0,
            "timeline": [
                {
                    "week": w,
                    "adoption_pct": round(_adoption_share(w, cfg.adoption_weeks, cfg.logistic_steepness) * 100.0, 1),
                    "new_container_fill_pct": 0.0,
                    "avg_neighbor_drop_pct": 0.0,
                    "overflow_count_before": 0,
                    "overflow_count_after": 0,
                    "tour_km_before": 0.0,
                    "tour_km_after": 0.0,
                }
                for w in range(WEEKS)
            ],
        }

    # Aggregate transfer per container and cap at 1.0 (never take >100 % of one container).
    if transfer.empty:
        total_taken = pd.DataFrame(
            columns=["Location_id", "material_type", "total_share_taken", "demand", "est_fill_level"]
        )
    else:
        total_taken = (
            transfer.groupby(["Location_id", "material_type"], as_index=False)
            .agg(
                raw_share=("share_taken", "sum"),
                demand=("demand", "first"),
                est_fill_level=("est_fill_level", "first"),
            )
            .reset_index(drop=True)
        )
        total_taken["total_share_taken"] = total_taken["raw_share"].clip(upper=1.0)

    # Build a lookup keyed by (Location_id, material_type).
    lookup = {
        (str(row["Location_id"]).strip(), str(row["material_type"]).strip().lower()): row
        for _, row in total_taken.iterrows()
    }

    # Demand actually transferred from each container (after capping).
    container_transferred: dict[tuple[str, str], float] = {
        key: float(row["demand"]) * float(row["total_share_taken"])
        for key, row in lookup.items()
    }
    total_transferred_demand = sum(container_transferred.values())

    # Demand received by each new site = sum of its proportional shares, scaled by cap.
    new_site_demand: dict[int, float] = {int(idx): 0.0 for idx in sites.index}
    if not transfer.empty:
        # Re-join cap to each transfer row.
        cap_map = {key: float(row["total_share_taken"]) for key, row in lookup.items()}
        raw_share_sum: dict[tuple[str, str], float] = {
            (str(row["Location_id"]).strip(), str(row["material_type"]).strip().lower()): float(row["raw_share"])
            for _, row in total_taken.iterrows()
        }
        for _, row in transfer.iterrows():
            key = (str(row["Location_id"]).strip(), str(row["material_type"]).strip().lower())
            raw_total = raw_share_sum.get(key, 1.0)
            cap = cap_map.get(key, 1.0)
            scaling = cap / raw_total if raw_total > 0 else 0.0
            site_idx = int(row["new_site_idx"])
            new_site_demand[site_idx] += float(row["demand"]) * float(row["share_taken"]) * scaling

    # Timeline week 0..12.
    timeline: list[dict[str, Any]] = []
    base_fill = merged.set_index(["Location_id", "material_type"])["est_fill_level"]

    for week in range(WEEKS):
        adoption = _adoption_share(week, cfg.adoption_weeks, cfg.logistic_steepness)

        # Existing containers lose demand share * adoption.
        adjusted_fill = base_fill.copy()
        for key, row in lookup.items():
            if key in adjusted_fill.index:
                drop = row["demand"] * 7.0 * row["total_share_taken"] * adoption
                adjusted_fill[key] = max(0.0, adjusted_fill[key] - drop)

        # New containers accumulate the taken demand.
        new_fills: list[float] = []
        for site_idx in sites.index:
            fill = new_site_demand.get(int(site_idx), 0.0) * 7.0 * adoption
            new_fills.append(min(OVERFULL_THRESHOLD, fill))

        overflow_before = int((base_fill >= OVERFULL_THRESHOLD).sum())
        overflow_after = int((adjusted_fill >= OVERFULL_THRESHOLD).sum()) + sum(
            1 for f in new_fills if f >= OVERFULL_THRESHOLD
        )

        avg_neighbor_drop = 0.0
        if lookup:
            drops = [
                row["demand"] * 7.0 * row["total_share_taken"] * adoption
                for row in lookup.values()
            ]
            avg_neighbor_drop = float(np.mean(drops)) if drops else 0.0

        timeline.append(
            {
                "week": week,
                "adoption_pct": round(adoption * 100.0, 1),
                "new_container_fill_pct": round(float(np.mean(new_fills)) if new_fills else 0.0, 1),
                "avg_neighbor_drop_pct": round(avg_neighbor_drop, 1),
                "overflow_count_before": overflow_before,
                "overflow_count_after": overflow_after,
            }
        )

    # Tour km estimate: before = baseline critical containers; after = week 12 adjusted + new sites.
    tour_km_before = _estimate_tour_km(
        merged[["lat", "lon"]].copy(), base_fill, cfg
    )
    final_week = timeline[-1]
    final_adoption = _adoption_share(WEEKS - 1, cfg.adoption_weeks, cfg.logistic_steepness)
    after_fill = base_fill.copy()
    for key, row in lookup.items():
        if key in after_fill.index:
            drop = row["demand"] * 7.0 * row["total_share_taken"] * final_adoption
            after_fill[key] = max(0.0, after_fill[key] - drop)

    after_locations = merged[["lat", "lon"]].copy()
    after_fills = after_fill.copy()
    if not sites.empty:
        new_rows = sites[["lat", "lon"]].copy()
        new_fills_series = pd.Series(
            [
                min(OVERFULL_THRESHOLD, new_site_demand.get(int(idx), 0.0) * 7.0 * final_adoption)
                for idx in sites.index
            ],
            index=pd.MultiIndex.from_tuples(
                [(f"NEW_{i}", "mixed") for i in range(len(sites))], names=["Location_id", "material_type"]
            ),
        )
        # Append new sites as extra rows; index alignment not needed for _estimate_tour_km.
        after_locations_extra = pd.concat([after_locations.reset_index(drop=True), new_rows.reset_index(drop=True)], ignore_index=True)
        after_fills_extra = pd.concat([after_fill.reset_index(drop=True), new_fills_series.reset_index(drop=True)], ignore_index=True)
    else:
        after_locations_extra = after_locations
        after_fills_extra = after_fills

    tour_km_after = _estimate_tour_km(after_locations_extra, after_fills_extra, cfg)

    # Attach tour km to timeline as reference lines (constant before/after).
    for entry in timeline:
        entry["tour_km_before"] = tour_km_before
        entry["tour_km_after"] = tour_km_after

    # Demand conservation check: total demand rate must stay constant.
    total_existing_demand = float(merged["demand"].sum())
    total_new_site_demand = sum(new_site_demand.values())
    existing_demand_after = total_existing_demand - total_transferred_demand
    demand_conserved = bool(
        abs(existing_demand_after + total_new_site_demand - total_existing_demand) < 1e-6
        and total_transferred_demand <= total_existing_demand + 1e-6
    )

    return {
        "simulated": True,
        "config": {
            "radius_m": cfg.radius_m,
            "adoption_weeks": cfg.adoption_weeks,
            "logistic_steepness": cfg.logistic_steepness,
        },
        "new_sites": [
            {
                "rank": i + 1,
                "lat": round(float(row["lat"]), 6),
                "lon": round(float(row["lon"]), 6),
                "score": round(float(row["total_score"]), 4),
                "demand_score": round(float(row["demand_score"]), 4),
                "gap_score": round(float(row["gap_score"]), 4),
            }
            for i, row in sites.iterrows()
        ],
        "affected_containers": len(total_taken),
        "affected_location_material_keys": [
            {"Location_id": key[0], "material_type": key[1]}
            for key in lookup.keys()
        ],
        "total_existing_demand_pp_day": round(total_existing_demand, 3),
        "total_transferred_demand_pp_day": round(total_transferred_demand, 3),
        "total_new_site_demand_pp_day": round(total_new_site_demand, 3),
        "demand_conserved": demand_conserved,
        "tour_km_before": tour_km_before,
        "tour_km_after": tour_km_after,
        "timeline": timeline,
    }
