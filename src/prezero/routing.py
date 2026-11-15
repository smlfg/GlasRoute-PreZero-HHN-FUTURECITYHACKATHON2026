"""Routing heuristics using Haversine distance, capacity, unload, and shift constraints."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
import json
import math
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import yaml

from prezero.model import WASTE_STREAMS, stream_for_material

# Fixed Heilbronn depot (TechCampus / city center area).
DEFAULT_DEPOT: tuple[float, float] = (49.1427, 9.2109)
EARTH_RADIUS_KM = 6371.0


@dataclass(frozen=True)
class OperationalConfig:
    """Configurable operational assumptions for glass collection routing."""

    density_kg_per_m3: float = 400.0  # Annahme, von PreZero zu ersetzen (alle Abfallströme)
    # Optional per waste stream (glass colour); None = use density_kg_per_m3.
    density_white_kg_per_m3: float | None = None  # Annahme, von PreZero zu ersetzen
    density_green_kg_per_m3: float | None = None  # Annahme, von PreZero zu ersetzen
    density_brown_kg_per_m3: float | None = None  # Annahme, von PreZero zu ersetzen
    container_volume_m3: float = 2.5  # Annahme, von PreZero zu ersetzen
    vehicle_max_weight_kg: float = 11000.0  # Annahme, von PreZero zu ersetzen
    vehicle_max_volume_m3: float = 26.0  # Annahme, von PreZero zu ersetzen
    road_detour_factor: float = 1.35  # Annahme, von PreZero zu ersetzen
    avg_speed_kmh: float = 25.0  # Annahme, von PreZero zu ersetzen
    yard_depot: tuple[float, float] = (49.1427, 9.2109)  # Annahme, von PreZero zu ersetzen
    disposal_depot: tuple[float, float] = (49.1780, 9.2085)  # Annahme, von PreZero zu ersetzen
    max_shift_hours: float = 8.0  # Annahme, von PreZero zu ersetzen
    stop_setup_min: float = 2.0  # Annahme, von PreZero zu ersetzen
    lift_time_per_bin_min: float = 3.0  # Annahme, von PreZero zu ersetzen
    unload_time_min: float = 20.0  # Annahme, von PreZero zu ersetzen
    # Standortplanung-What-if (reine Simulation, keine Auswirkung auf echte Route)
    location_planning_radius_m: float = 500.0
    location_planning_adoption_weeks: float = 8.0
    location_planning_logistic_steepness: float = 1.0
    # Optional per-material densities from the "streams" section of prezero_config.json.
    stream_density_overrides: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of all operational assumptions."""
        return {
            "density_kg_per_m3": float(self.density_kg_per_m3),
            "density_white_kg_per_m3": _opt_float(self.density_white_kg_per_m3),
            "density_green_kg_per_m3": _opt_float(self.density_green_kg_per_m3),
            "density_brown_kg_per_m3": _opt_float(self.density_brown_kg_per_m3),
            "container_volume_m3": float(self.container_volume_m3),
            "vehicle_max_weight_kg": float(self.vehicle_max_weight_kg),
            "vehicle_max_volume_m3": float(self.vehicle_max_volume_m3),
            "road_detour_factor": float(self.road_detour_factor),
            "avg_speed_kmh": float(self.avg_speed_kmh),
            "yard_depot": [float(self.yard_depot[0]), float(self.yard_depot[1])],
            "disposal_depot": [float(self.disposal_depot[0]), float(self.disposal_depot[1])],
            "max_shift_hours": float(self.max_shift_hours),
            "stop_setup_min": float(self.stop_setup_min),
            "lift_time_per_bin_min": float(self.lift_time_per_bin_min),
            "unload_time_min": float(self.unload_time_min),
            "location_planning_radius_m": float(self.location_planning_radius_m),
            "location_planning_adoption_weeks": float(self.location_planning_adoption_weeks),
            "location_planning_logistic_steepness": float(self.location_planning_logistic_steepness),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OperationalConfig:
        """Construct OperationalConfig from a mapping, validating field names and coordinates.

        Unknown keys (e.g. ``streams``) are ignored so the same config file can carry
        extra sections used by other parts of the pipeline.
        """
        valid_fields = {f.name for f in fields(cls)}

        stream_density_overrides: dict[str, float] = {}
        streams_section = data.get("streams")
        if isinstance(streams_section, Mapping):
            for stream_cfg in streams_section.values():
                if not isinstance(stream_cfg, Mapping):
                    continue
                density = stream_cfg.get("density_kg_per_m3")
                if density is None:
                    continue
                for material in stream_cfg.get("materials", []) or []:
                    stream_density_overrides[str(material).strip().lower()] = float(density)

        parsed: dict[str, Any] = {"stream_density_overrides": stream_density_overrides}
        for key, value in data.items():
            if key not in valid_fields or key == "stream_density_overrides":
                continue
            if key in {"yard_depot", "disposal_depot"}:
                parsed[key] = _parse_coord_pair(value, key)
            elif value is None:
                parsed[key] = None
            else:
                parsed[key] = float(value)
        return cls(**parsed)


def density_for(cfg: OperationalConfig, material: str) -> float:
    """Bulk density for one waste stream; falls back to config defaults.

    Precedence: legacy per-glass colour overrides, then the per-material
    densities from the ``streams`` config section, then the WasteStream value
    for synthetic streams, then the generic ``density_kg_per_m3`` override.
    """
    key = str(material).strip().lower()
    stream = stream_for_material(key)
    material_key = stream.name.replace("glass_", "")
    # Legacy per-glass overrides still win when present.
    if stream.name.startswith("glass_"):
        specific = {
            "white": cfg.density_white_kg_per_m3,
            "green": cfg.density_green_kg_per_m3,
            "brown": cfg.density_brown_kg_per_m3,
        }.get(material_key)
        if specific is not None:
            return float(specific)
    if material_key in cfg.stream_density_overrides:
        return float(cfg.stream_density_overrides[material_key])
    if stream.synthetic:
        return float(stream.density_kg_per_m3)
    return float(cfg.density_kg_per_m3)


def _opt_int(value: Any) -> int | None:
    return None if value is None or pd.isna(value) else int(value)


def _opt_date(value: Any) -> str | None:
    return None if value is None or pd.isna(value) else str(pd.Timestamp(value).date())


def _opt_float(value: float | None) -> float | None:
    return None if value is None else float(value)


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


def _split_oversized_rows(
    per_loc: pd.DataFrame,
    cfg: OperationalConfig,
) -> pd.DataFrame:
    """Split any site whose critical or total load exceeds vehicle capacity.

    A site with more bins than fit into one vehicle round is turned into multiple
    stops at the same coordinate. This keeps the nearest-neighbour routing honest:
    every collection stop respects the 11 t / 26 m³ limits, even when it is the
    first stop of a vehicle.
    """
    if per_loc.empty:
        return per_loc

    max_w = float(cfg.vehicle_max_weight_kg)
    max_v = float(cfg.vehicle_max_volume_m3)
    rows: list[dict[str, Any]] = []

    for record in per_loc.to_dict("records"):
        crit_bins = max(1, int(record.get("critical_bins") or 1))
        total_bins = max(1, int(record.get("bins") or crit_bins))
        crit_mass = float(record.get("mass_kg") or 0.0)
        crit_vol = float(record.get("volume_m3") or 0.0)
        total_mass = float(record.get("total_mass_kg") or crit_mass)
        total_vol = float(record.get("total_volume_m3") or crit_vol)

        n_crit = max(
            1,
            math.ceil(crit_mass / max_w) if crit_mass > 0 else 1,
            math.ceil(crit_vol / max_v) if crit_vol > 0 else 1,
        )
        n_total = max(
            1,
            math.ceil(total_mass / max_w) if total_mass > 0 else 1,
            math.ceil(total_vol / max_v) if total_vol > 0 else 1,
        )
        n = max(n_crit, n_total)

        if n <= 1:
            rows.append(record)
            continue

        # Distribute total bins as evenly as possible.
        base, extra = divmod(total_bins, n)
        split_total_bins = [base + (1 if i < extra else 0) for i in range(n)]

        # Distribute critical bins as evenly as possible.
        base_c, extra_c = divmod(crit_bins, n)
        split_crit_bins = [base_c + (1 if i < extra_c else 0) for i in range(n)]

        for i in range(n):
            tb = int(split_total_bins[i])
            cb = int(split_crit_bins[i])
            new = dict(record)
            new["bins"] = tb
            new["critical_bins"] = cb
            new["mass_kg"] = round(crit_mass * cb / crit_bins, 2) if crit_bins else 0.0
            new["volume_m3"] = round(crit_vol * cb / crit_bins, 2) if crit_bins else 0.0
            new["total_mass_kg"] = round(total_mass * tb / total_bins, 2) if total_bins else 0.0
            new["total_volume_m3"] = round(total_vol * tb / total_bins, 2) if total_bins else 0.0
            rows.append(new)

    return pd.DataFrame(rows)


def _aggregate_locations(
    scored: pd.DataFrame,
    locations: pd.DataFrame,
    config: OperationalConfig | None = None,
) -> pd.DataFrame:
    """Collapse per-material scores to physical sites, summing bin mass at each point."""
    if scored.empty:
        return pd.DataFrame()

    cfg = config or OperationalConfig()
    work = scored.copy()
    if "critical" not in work.columns:
        work["critical"] = work["score"] >= 0.7

    work["critical"] = work["critical"].astype(bool)
    # Mass to collect = current (estimated) level; the last reading was taken before emptying.
    if "est_fill_level" not in work.columns:
        work["est_fill_level"] = work["last_fill_level"]
    if "days_until_due" not in work.columns:
        work["days_until_due"] = float("nan")
    if "due_date" not in work.columns:
        work["due_date"] = pd.NaT
    work["bin_volume_m3"] = float(cfg.container_volume_m3) * (
        work["est_fill_level"].astype(float).clip(lower=0.0) / 100.0
    )
    work["bin_mass_kg"] = work["bin_volume_m3"] * work["material_type"].map(
        lambda m: density_for(cfg, m)
    )
    work["crit_mass_kg"] = work["bin_mass_kg"].where(work["critical"], 0.0)
    work["crit_volume_m3"] = work["bin_volume_m3"].where(work["critical"], 0.0)

    merged = work.merge(
        locations[["Location_id", "lat", "lon", "source", "confidence"]],
        on="Location_id",
        how="inner",
    )
    merged["_lat_key"] = merged["lat"].round(6)
    merged["_lon_key"] = merged["lon"].round(6)
    ordered = merged.sort_values(
        ["_lat_key", "_lon_key", "score", "material_type", "Location_id"],
        ascending=[True, True, False, True, True],
    )
    per_loc = ordered.groupby(["_lat_key", "_lon_key"], as_index=False).agg(
        Location_id=("Location_id", "min"),
        score=("score", "max"),
        critical=("critical", "any"),
        primary_material=("material_type", "first"),
        last_fill_level=("last_fill_level", "max"),
        est_fill_level=("est_fill_level", "max"),
        # Timer of the most urgent container at the site (negative = overdue).
        days_until_due=("days_until_due", "min"),
        due_date=("due_date", "min"),
        critical_bins=("critical", "sum"),
        bins=("Location_id", "size"),
        mass_kg=("crit_mass_kg", "sum"),
        total_mass_kg=("bin_mass_kg", "sum"),
        max_bin_mass_kg=("bin_mass_kg", "max"),
        volume_m3=("crit_volume_m3", "sum"),
        total_volume_m3=("bin_volume_m3", "sum"),
        max_bin_volume_m3=("bin_volume_m3", "max"),
        source=("source", "first"),
        confidence=("confidence", "first"),
    )

    no_crit = per_loc["critical_bins"] == 0
    per_loc.loc[no_crit, "critical_bins"] = 1
    per_loc.loc[no_crit, "mass_kg"] = per_loc.loc[no_crit, "max_bin_mass_kg"]
    per_loc.loc[no_crit, "volume_m3"] = per_loc.loc[no_crit, "max_bin_volume_m3"]
    per_loc = per_loc.drop(columns=["max_bin_mass_kg", "max_bin_volume_m3"])

    per_loc["lat"] = per_loc["_lat_key"]
    per_loc["lon"] = per_loc["_lon_key"]
    per_loc = _split_oversized_rows(per_loc, cfg)
    return per_loc.sort_values(["score", "Location_id"], ascending=[False, True]).reset_index(
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
    cur_volume_m3 = 0.0
    cur_shift_min = 0.0
    cur_vehicle_km = 0.0
    cur_vehicle_mass_kg = 0.0
    cur_round = 1
    cur_vehicle_stops = 0
    cur_vehicle_unloads = 0

    def _close_vehicle() -> None:
        nonlocal total_km, cur_vehicle_km, cur_shift_min
        nonlocal vehicle_idx, cur_lat, cur_lon, cur_weight_kg, cur_volume_m3
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
        cur_volume_m3 = 0.0
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
        cand_volume_m3 = float(cand.get("volume_m3", 0.0) or 0.0)
        cand_bins = max(1, int(cand["critical_bins"]))
        service_min = float(cfg.stop_setup_min) + cand_bins * float(cfg.lift_time_per_bin_min)

        over_weight = (cur_weight_kg + cand_mass_kg) > float(cfg.vehicle_max_weight_kg)
        over_volume = (cur_volume_m3 + cand_volume_m3) > float(cfg.vehicle_max_volume_m3)
        if (cur_weight_kg > 0.0 or cur_volume_m3 > 0.0) and (over_weight or over_volume):
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
                cur_volume_m3 = 0.0
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
        cur_volume_m3 += cand_volume_m3
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
                "est_fill_level": float(cand["est_fill_level"]),
                "days_until_due": _opt_int(cand.get("days_until_due")),
                "due_date": _opt_date(cand.get("due_date")),
                "source": str(cand["source"]),
                "confidence": str(cand["confidence"]),
                "vehicle": vehicle_idx,
                "round": cur_round,
                "critical_bins": cand_bins,
                "mass_kg": round(cand_mass_kg, 2),
                "load_kg": round(cur_weight_kg, 2),
                "volume_m3": round(cand_volume_m3, 2),
                "load_m3": round(cur_volume_m3, 2),
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


STOPS_CSV_COLUMNS: list[str] = [
    "order",
    "vehicle",
    "round",
    "stop_type",
    "Location_id",
    "lat",
    "lon",
    "primary_material",
    "critical_bins",
    "est_fill_level",
    "last_fill_level",
    "mass_kg",
    "load_kg",
    "volume_m3",
    "load_m3",
    "leg_km",
    "cumulative_km",
    "score",
    "source",
    "confidence",
]


def stops_to_dataframe(route_data: Mapping[str, Any]) -> pd.DataFrame:
    """Return all route stops strictly in driving order (never score order)."""
    raw_stops = list(route_data.get("stops") or [])
    if not raw_stops:
        return pd.DataFrame(columns=STOPS_CSV_COLUMNS)
    frame = pd.DataFrame(raw_stops)
    for col in STOPS_CSV_COLUMNS:
        if col not in frame.columns:
            frame[col] = None
    frame["order"] = pd.to_numeric(frame["order"], errors="coerce").fillna(0).astype(int)
    frame = frame.sort_values("order", kind="mergesort").reset_index(drop=True)
    return frame[STOPS_CSV_COLUMNS]


def export_stops_csv(route_data: Mapping[str, Any], output_path: str | Path) -> Path:
    """Write the driver stop list in driving order to CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stops_to_dataframe(route_data).to_csv(path, index=False)
    return path


def build_route(
    scored: pd.DataFrame,
    locations: pd.DataFrame,
    depot: tuple[float, float] = DEFAULT_DEPOT,
    max_stops: int | None = None,
    date: str | None = None,
    output_dir: str | Path | None = ".",
    config: OperationalConfig | None = None,
    output_prefix: str | None = None,
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
            "max_stops": None if max_stops is None else int(max_stops),
            "num_stops": 0,
            "total_critical_locations": 0,
            "total_active_locations": 0,
            "vehicles_needed": 0,
            "rounds_per_vehicle": [],
            "rounds": 0,
            "shift_hours_per_vehicle": [],
            "shift_hours": 0.0,
            "max_vehicle_shift_hours": 0.0,
            "max_shift_hours_limit": float(cfg.max_shift_hours),
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
        selected = pool if max_stops is None else pool.head(max_stops)
        selected = selected.reset_index(drop=True)

        stops, unload_stops, vehicles, planned_km, total_mass_kg = _simulate_constrained_routes(
            selected, cfg
        )
        # Status quo empties every bin at every site, under the SAME capacity/shift/unload
        # rules as the planned tour (otherwise the comparison is not like-for-like).
        status_quo = loc_scores.assign(
            mass_kg=loc_scores["total_mass_kg"],
            volume_m3=loc_scores["total_volume_m3"],
            critical_bins=loc_scores["bins"],
        )
        _, _, full_vehicles, full_round_km, _ = _simulate_constrained_routes(status_quo, cfg)
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
            "max_stops": None if max_stops is None else int(max_stops),
            "num_stops": collection_stop_count,
            "total_critical_locations": int(len(critical_locs)),
            "total_active_locations": int(len(loc_scores)),
            "vehicles_needed": len(vehicles),
            "rounds_per_vehicle": rounds_per_vehicle,
            "rounds": int(sum(rounds_per_vehicle)),
            "shift_hours_per_vehicle": shift_hours_per_vehicle,
            # shift_hours is the SUM over all vehicles (vehicle-hours), not one shift.
            "shift_hours": round(sum(shift_hours_per_vehicle), 2),
            "max_vehicle_shift_hours": round(max(shift_hours_per_vehicle, default=0.0), 2),
            "max_shift_hours_limit": float(cfg.max_shift_hours),
            "t_collected": round(total_mass_kg / 1000.0, 2),
            "km": round(planned_km, 2),
            "planned_km": round(planned_km, 2),
            "full_round_km": round(full_round_km, 2),
            "full_round_vehicles": len(full_vehicles),
            "full_round_vehicle_hours": round(sum(float(v["shift_hours"]) for v in full_vehicles), 2),
            "saved_km": round(saved_km, 2),
            "saved_pct": round(saved_pct, 1),
            "comparison": (
                f"{round(planned_km, 2)} km planned ({collection_stop_count} stops) "
                f"vs. {round(full_round_km, 2)} km full round ({len(loc_scores)} stops, same capacity rules)"
            ),
            "assumptions": cfg.to_dict(),
            "vehicles": vehicles,
            "unload_stops": unload_stops,
            "stops": stops,
        }

    if date is not None and output_dir is not None:
        prefix = f"{output_prefix}_" if output_prefix else ""
        out_path = Path(output_dir) / f"{prefix}route_{date}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(route_data, indent=2), encoding="utf-8")
        export_stops_csv(route_data, Path(output_dir) / f"{prefix}stops_{date}.csv")

    return route_data
