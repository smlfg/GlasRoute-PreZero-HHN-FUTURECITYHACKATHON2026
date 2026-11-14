"""Routing heuristics using Haversine distance, capacity, unload, and shift constraints."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
import json
import math
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

# Fixed Heilbronn depot (TechCampus / city center area).
DEFAULT_DEPOT: tuple[float, float] = (49.1427, 9.2109)
EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class OperationalConfig:
    """Configurable operational assumptions for glass collection routing."""

    density_kg_per_m3: float = 400.0  # Annahme, von PreZero zu ersetzen
    container_volume_m3: float = 2.5  # Annahme, von PreZero zu ersetzen
    vehicle_max_weight_kg: float = 11000.0  # Annahme, von PreZero zu ersetzen
    road_detour_factor: float = 1.35  # Annahme, von PreZero zu ersetzen
    avg_speed_kmh: float = 25.0  # Annahme, von PreZero zu ersetzen
    yard_depot: tuple[float, float] = (49.1427, 9.2109)  # Annahme, von PreZero zu ersetzen
    disposal_depot: tuple[float, float] = (49.1780, 9.2085)  # Annahme, von PreZero zu ersetzen
    max_shift_hours: float = 8.0  # Annahme, von PreZero zu ersetzen
    stop_setup_min: float = 2.0  # Annahme, von PreZero zu ersetzen
    lift_time_per_bin_min: float = 3.0  # Annahme, von PreZero zu ersetzen
    unload_time_min: float = 20.0  # Annahme, von PreZero zu ersetzen

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of all operational assumptions."""
        return {
            "density_kg_per_m3": float(self.density_kg_per_m3),
            "container_volume_m3": float(self.container_volume_m3),
            "vehicle_max_weight_kg": float(self.vehicle_max_weight_kg),
            "road_detour_factor": float(self.road_detour_factor),
            "avg_speed_kmh": float(self.avg_speed_kmh),
            "yard_depot": [float(self.yard_depot[0]), float(self.yard_depot[1])],
            "disposal_depot": [float(self.disposal_depot[0]), float(self.disposal_depot[1])],
            "max_shift_hours": float(self.max_shift_hours),
            "stop_setup_min": float(self.stop_setup_min),
            "lift_time_per_bin_min": float(self.lift_time_per_bin_min),
            "unload_time_min": float(self.unload_time_min),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OperationalConfig:
        """Construct OperationalConfig from a mapping, validating field names and coordinates."""
        valid_fields = {f.name for f in fields(cls)}
        unknown = sorted(set(data.keys()) - valid_fields)
        if unknown:
            raise ValueError(f"Unknown OperationalConfig field(s): {', '.join(unknown)}")

        parsed: dict[str, Any] = {}
        for key, value in data.items():
            if key in {"yard_depot", "disposal_depot"}:
                parsed[key] = _parse_coord_pair(value, key)
            else:
                parsed[key] = float(value)
        return cls(**parsed)


def _parse_coord_pair(value: Any, field_name: str) -> tuple[float, float]:
    """Parse a [lat, lon] sequence or {'lat': ..., 'lon': ...} mapping."""
    if isinstance(value, Mapping):
        if "lat" not in value or "lon" not in value:
            raise ValueError(f"{field_name} mapping must contain 'lat' and 'lon'")
        return (float(value["lat"]), float(value["lon"]))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return (float(value[0]), float(value[1]))
    raise ValueError(f"{field_name} must be a [lat, lon] pair or {{'lat': ..., 'lon': ...}}")


def load_config(path: str | Path | None = None) -> OperationalConfig:
    """Load OperationalConfig from a JSON or YAML file, or return defaults when path is None."""
    if path is None:
        return OperationalConfig()

    cfg_path = Path(path)
    raw_text = cfg_path.read_text(encoding="utf-8")
    if cfg_path.suffix.lower() == ".json":
        loaded = json.loads(raw_text)
    else:
        loaded = yaml.safe_load(raw_text)

    if not isinstance(loaded, Mapping):
        raise ValueError(f"Config file {cfg_path} must contain a mapping/object")
    return OperationalConfig.from_dict(loaded)


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


def road_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    config: OperationalConfig,
) -> float:
    """Return estimated road distance using Haversine distance multiplied by road detour factor."""
    return haversine_km(lat1, lon1, lat2, lon2) * float(config.road_detour_factor)


def drive_time_min(distance_km: float, config: OperationalConfig) -> float:
    """Convert road distance in km to travel time in minutes."""
    return (float(distance_km) / float(config.avg_speed_kmh)) * 60.0


def _aggregate_locations(
    scored: pd.DataFrame,
    locations: pd.DataFrame,
    config: OperationalConfig | None = None,
) -> pd.DataFrame:
    """Collapse per-material scores to unique Location_id rows, summing only critical bin mass."""
    if scored.empty:
        return pd.DataFrame()

    cfg = config or OperationalConfig()
    work = scored.copy()
    if "critical" not in work.columns:
        work["critical"] = work["score"] >= 0.7

    work["critical"] = work["critical"].astype(bool)
    work["bin_mass_kg"] = (
        float(cfg.container_volume_m3)
        * (work["last_fill_level"].astype(float) / 100.0)
        * float(cfg.density_kg_per_m3)
    )
    work["crit_mass_kg"] = work["bin_mass_kg"].where(work["critical"], 0.0)

    ordered = work.sort_values(
        ["Location_id", "score", "material_type"],
        ascending=[True, False, True],
    )
    per_loc = ordered.groupby("Location_id", as_index=False).agg(
        score=("score", "max"),
        critical=("critical", "any"),
        primary_material=("material_type", "first"),
        last_fill_level=("last_fill_level", "max"),
        critical_bins=("critical", "sum"),
        mass_kg=("crit_mass_kg", "sum"),
        max_bin_mass_kg=("bin_mass_kg", "max"),
    )

    no_crit = per_loc["critical_bins"] == 0
    per_loc.loc[no_crit, "critical_bins"] = 1
    per_loc.loc[no_crit, "mass_kg"] = per_loc.loc[no_crit, "max_bin_mass_kg"]
    per_loc = per_loc.drop(columns=["max_bin_mass_kg"])

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
    detour_factor: float = 1.0,
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
            )
            * detour_factor,
        )
        chosen = remaining.pop(best_idx)
        leg_km = (
            haversine_km(cur_lat, cur_lon, float(chosen["lat"]), float(chosen["lon"]))
            * detour_factor
        )
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

    return_km = haversine_km(cur_lat, cur_lon, float(depot[0]), float(depot[1])) * detour_factor
    total_km += return_km
    return stops, total_km


def _resolve_config(
    depot: tuple[float, float],
    config: OperationalConfig | None,
) -> OperationalConfig:
    """Resolve effective OperationalConfig honoring explicit depot overrides."""
    depot_pair = (float(depot[0]), float(depot[1]))
    if config is None:
        return OperationalConfig(yard_depot=depot_pair)
    if depot_pair != DEFAULT_DEPOT and config.yard_depot == DEFAULT_DEPOT:
        return replace(config, yard_depot=depot_pair)
    return config


def _simulate_constrained_routes(
    selected: pd.DataFrame,
    cfg: OperationalConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], float, float]:
    """Simulate nearest-neighbor routing with disposal unloads and shift limits."""
    remaining = selected.to_dict(orient="records")
    stops: list[dict[str, Any]] = []
    unload_stops: list[dict[str, Any]] = []
    vehicles: list[dict[str, Any]] = []

    yard_lat, yard_lon = float(cfg.yard_depot[0]), float(cfg.yard_depot[1])
    disp_lat, disp_lon = float(cfg.disposal_depot[0]), float(cfg.disposal_depot[1])
    max_shift_min = float(cfg.max_shift_hours) * 60.0

    total_km = 0.0
    total_mass_kg = 0.0

    vehicle_idx = 1
    cur_lat, cur_lon = yard_lat, yard_lon
    cur_weight_kg = 0.0
    cur_shift_min = 0.0
    cur_vehicle_km = 0.0
    cur_vehicle_mass_kg = 0.0
    cur_round = 1
    cur_vehicle_stops = 0
    cur_vehicle_unloads = 0

    def _close_vehicle() -> None:
        nonlocal total_km, cur_vehicle_km, cur_shift_min
        nonlocal vehicle_idx, cur_lat, cur_lon, cur_weight_kg
        nonlocal cur_vehicle_mass_kg, cur_round, cur_vehicle_stops, cur_vehicle_unloads

        return_km = road_distance_km(cur_lat, cur_lon, yard_lat, yard_lon, cfg)
        total_km += return_km
        cur_vehicle_km += return_km
        cur_shift_min += drive_time_min(return_km, cfg)
        vehicles.append(
            {
                "vehicle": vehicle_idx,
                "rounds": cur_round,
                "stops": cur_vehicle_stops,
                "unloads": cur_vehicle_unloads,
                "t_collected": round(cur_vehicle_mass_kg / 1000.0, 2),
                "km": round(cur_vehicle_km, 2),
                "shift_hours": round(cur_shift_min / 60.0, 2),
            }
        )
        vehicle_idx += 1
        cur_lat, cur_lon = yard_lat, yard_lon
        cur_weight_kg = 0.0
        cur_shift_min = 0.0
        cur_vehicle_km = 0.0
        cur_vehicle_mass_kg = 0.0
        cur_round = 1
        cur_vehicle_stops = 0
        cur_vehicle_unloads = 0

    while remaining:
        best_idx = min(
            range(len(remaining)),
            key=lambda idx: road_distance_km(
                cur_lat, cur_lon, float(remaining[idx]["lat"]), float(remaining[idx]["lon"]), cfg
            ),
        )
        cand = remaining[best_idx]
        cand_lat, cand_lon = float(cand["lat"]), float(cand["lon"])
        cand_mass_kg = float(cand["mass_kg"])
        cand_bins = max(1, int(cand["critical_bins"]))
        service_min = float(cfg.stop_setup_min) + cand_bins * float(cfg.lift_time_per_bin_min)

        if cur_weight_kg > 0.0 and (cur_weight_kg + cand_mass_kg) > float(cfg.vehicle_max_weight_kg):
            leg_to_disp_km = road_distance_km(cur_lat, cur_lon, disp_lat, disp_lon, cfg)
            unload_step_min = drive_time_min(leg_to_disp_km, cfg) + float(cfg.unload_time_min)

            next_after_disp = min(
                remaining,
                key=lambda row: road_distance_km(
                    disp_lat, disp_lon, float(row["lat"]), float(row["lon"]), cfg
                ),
            )
            next_lat, next_lon = float(next_after_disp["lat"]), float(next_after_disp["lon"])
            next_bins = max(1, int(next_after_disp["critical_bins"]))
            next_srv_min = float(cfg.stop_setup_min) + next_bins * float(cfg.lift_time_per_bin_min)
            leg_disp_to_next_km = road_distance_km(disp_lat, disp_lon, next_lat, next_lon, cfg)
            leg_next_to_yard_km = road_distance_km(next_lat, next_lon, yard_lat, yard_lon, cfg)
            min_needed = (
                unload_step_min
                + drive_time_min(leg_disp_to_next_km, cfg)
                + next_srv_min
                + drive_time_min(leg_next_to_yard_km, cfg)
            )

            if cur_shift_min + min_needed <= max_shift_min:
                total_km += leg_to_disp_km
                cur_vehicle_km += leg_to_disp_km
                cur_shift_min += unload_step_min
                unload_entry = {
                    "order": len(stops) + 1,
                    "stop_type": "unload",
                    "Location_id": "disposal_depot",
                    "lat": round(disp_lat, 6),
                    "lon": round(disp_lon, 6),
                    "score": 0.0,
                    "critical": False,
                    "primary_material": "unload",
                    "last_fill_level": 0.0,
                    "source": "config",
                    "confidence": "high",
                    "vehicle": vehicle_idx,
                    "round": cur_round,
                    "mass_kg": 0.0,
                    "unloaded_kg": round(cur_weight_kg, 2),
                    "leg_km": round(leg_to_disp_km, 3),
                    "cumulative_km": round(total_km, 3),
                }
                stops.append(unload_entry)
                unload_stops.append(unload_entry)
                cur_lat, cur_lon = disp_lat, disp_lon
                cur_weight_kg = 0.0
                cur_round += 1
                cur_vehicle_unloads += 1
                continue

            _close_vehicle()
            continue

        leg_to_cand_km = road_distance_km(cur_lat, cur_lon, cand_lat, cand_lon, cfg)
        leg_cand_to_yard_km = road_distance_km(cand_lat, cand_lon, yard_lat, yard_lon, cfg)
        projected_shift_min = (
            cur_shift_min
            + drive_time_min(leg_to_cand_km, cfg)
            + service_min
            + drive_time_min(leg_cand_to_yard_km, cfg)
        )
        if cur_vehicle_stops > 0 and projected_shift_min > max_shift_min:
            _close_vehicle()
            continue

        remaining.pop(best_idx)
        total_km += leg_to_cand_km
        cur_vehicle_km += leg_to_cand_km
        cur_shift_min += drive_time_min(leg_to_cand_km, cfg) + service_min
        cur_weight_kg += cand_mass_kg
        cur_vehicle_mass_kg += cand_mass_kg
        total_mass_kg += cand_mass_kg
        cur_vehicle_stops += 1
        cur_lat, cur_lon = cand_lat, cand_lon

        stops.append(
            {
                "order": len(stops) + 1,
                "stop_type": "collection",
                "Location_id": str(cand["Location_id"]),
                "lat": round(cand_lat, 6),
                "lon": round(cand_lon, 6),
                "score": round(float(cand["score"]), 4),
                "critical": bool(cand["critical"]),
                "primary_material": str(cand["primary_material"]),
                "last_fill_level": float(cand["last_fill_level"]),
                "source": str(cand["source"]),
                "confidence": str(cand["confidence"]),
                "vehicle": vehicle_idx,
                "round": cur_round,
                "critical_bins": cand_bins,
                "mass_kg": round(cand_mass_kg, 2),
                "load_kg": round(cur_weight_kg, 2),
                "leg_km": round(leg_to_cand_km, 3),
                "cumulative_km": round(total_km, 3),
            }
        )

    if cur_vehicle_stops > 0:
        _close_vehicle()

    return stops, unload_stops, vehicles, total_km, total_mass_kg


def format_route_summary(route_data: Mapping[str, Any]) -> str:
    """Format one-line German CLI summary, e.g. '1 Fahrzeug, 2 Runden, 5,4 h, 14,2 t, 87 km'."""
    vehicles = int(route_data.get("vehicles_needed", 0))
    rounds_list = route_data.get("rounds_per_vehicle") or []
    total_rounds = int(route_data.get("rounds", sum(rounds_list)))
    hours_list = route_data.get("shift_hours_per_vehicle") or []
    total_hours = float(route_data.get("shift_hours", sum(hours_list)))
    tons = float(route_data.get("t_collected", 0.0))
    km = float(route_data.get("km", route_data.get("planned_km", 0.0)))

    veh_label = "Fahrzeug" if vehicles == 1 else "Fahrzeuge"
    rnd_label = "Runde" if total_rounds == 1 else "Runden"
    h_str = f"{total_hours:.1f}".replace(".", ",")
    t_str = f"{tons:.1f}".replace(".", ",")
    km_str = f"{round(km):.0f}"
    return f"{vehicles} {veh_label}, {total_rounds} {rnd_label}, {h_str} h, {t_str} t, {km_str} km"


def build_route(
    scored: pd.DataFrame,
    locations: pd.DataFrame,
    depot: tuple[float, float] = DEFAULT_DEPOT,
    max_stops: int = 25,
    date: str | None = None,
    output_dir: str | Path = ".",
    config: OperationalConfig | None = None,
) -> dict[str, Any]:
    """Build a capacity- and shift-constrained nearest-neighbor route vs. full round."""
    cfg = _resolve_config(depot, config)
    loc_scores = _aggregate_locations(scored, locations, cfg)

    if loc_scores.empty:
        route_data: dict[str, Any] = {
            "date": date,
            "depot": {"lat": float(cfg.yard_depot[0]), "lon": float(cfg.yard_depot[1])},
            "disposal_depot": {
                "lat": float(cfg.disposal_depot[0]),
                "lon": float(cfg.disposal_depot[1]),
            },
            "max_stops": int(max_stops),
            "num_stops": 0,
            "total_critical_locations": 0,
            "total_active_locations": 0,
            "vehicles_needed": 0,
            "rounds_per_vehicle": [],
            "rounds": 0,
            "shift_hours_per_vehicle": [],
            "shift_hours": 0.0,
            "t_collected": 0.0,
            "km": 0.0,
            "planned_km": 0.0,
            "full_round_km": 0.0,
            "saved_km": 0.0,
            "saved_pct": 0.0,
            "comparison": "0.0 km planned vs. 0.0 km full round",
            "assumptions": cfg.to_dict(),
            "vehicles": [],
            "unload_stops": [],
            "stops": [],
        }
    else:
        critical_locs = loc_scores[loc_scores["critical"]]
        pool = critical_locs if not critical_locs.empty else loc_scores
        selected = pool.head(max_stops).reset_index(drop=True)

        stops, unload_stops, vehicles, planned_km, total_mass_kg = _simulate_constrained_routes(
            selected, cfg
        )
        _, full_round_km = _nearest_neighbor_tour(
            loc_scores, cfg.yard_depot, detour_factor=float(cfg.road_detour_factor)
        )
        collection_stop_count = len(stops) - len(unload_stops)
        saved_km = max(0.0, full_round_km - planned_km)
        saved_pct = (saved_km / full_round_km * 100.0) if full_round_km > 0 else 0.0
        rounds_per_vehicle = [int(v["rounds"]) for v in vehicles]
        shift_hours_per_vehicle = [round(float(v["shift_hours"]), 2) for v in vehicles]

        route_data = {
            "date": date,
            "depot": {"lat": float(cfg.yard_depot[0]), "lon": float(cfg.yard_depot[1])},
            "disposal_depot": {
                "lat": float(cfg.disposal_depot[0]),
                "lon": float(cfg.disposal_depot[1]),
            },
            "max_stops": int(max_stops),
            "num_stops": collection_stop_count,
            "total_critical_locations": int(len(critical_locs)),
            "total_active_locations": int(len(loc_scores)),
            "vehicles_needed": len(vehicles),
            "rounds_per_vehicle": rounds_per_vehicle,
            "rounds": int(sum(rounds_per_vehicle)),
            "shift_hours_per_vehicle": shift_hours_per_vehicle,
            "shift_hours": round(sum(shift_hours_per_vehicle), 2),
            "t_collected": round(total_mass_kg / 1000.0, 2),
            "km": round(planned_km, 2),
            "planned_km": round(planned_km, 2),
            "full_round_km": round(full_round_km, 2),
            "saved_km": round(saved_km, 2),
            "saved_pct": round(saved_pct, 1),
            "comparison": (
                f"{round(planned_km, 2)} km planned ({collection_stop_count} stops) "
                f"vs. {round(full_round_km, 2)} km full round ({len(loc_scores)} stops)"
            ),
            "assumptions": cfg.to_dict(),
            "vehicles": vehicles,
            "unload_stops": unload_stops,
            "stops": stops,
        }

    if date is not None:
        out_path = Path(output_dir) / f"route_{date}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(route_data, indent=2), encoding="utf-8")

    return route_data
