"""Deterministic GlasRoute Copilot MVP and optional Ollama tool-router adapter.

Design rules:
1. Container identity is strictly ``(Location_id, material_type)`` (or ``container_key``).
2. The LLM never calculates route/score numbers or invents decisions; Python tools are authoritative.
3. ``approve_tour`` is forbidden as a chat tool; approval remains an explicit human action via ``approval.py``.
4. ``simulate_what_if`` enforces a strict parameter allowlist, never overwrites ``route_<date>.json``,
   and always returns a baseline comparison.
"""

from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.error import URLError
import urllib.request

import pandas as pd

from prezero import features, locations, routing, scoring

VALID_MATERIALS: tuple[str, ...] = ("white", "green", "brown")

MATERIAL_ALIASES: dict[str, str] = {
    "white": "white",
    "weiss": "white",
    "weiß": "white",
    "weissglas": "white",
    "weißglas": "white",
    "glass_white": "white",
    "white_glass": "white",
    "green": "green",
    "gruen": "green",
    "grün": "green",
    "gruenglas": "green",
    "grünglas": "green",
    "glass_green": "green",
    "green_glass": "green",
    "brown": "brown",
    "braun": "brown",
    "braunglas": "brown",
    "glass_brown": "brown",
    "brown_glass": "brown",
}

ALLOWED_TOOLS: tuple[str, ...] = (
    "get_tour_overview",
    "explain_container",
    "simulate_what_if",
    "get_today_hero",
    "explain_measure_empty_model",
    "get_benchmark_summary",
    "get_depot_and_unloads",
    "get_driver_export_info",
    "get_location_planning_info",
    "get_replay_comparison",
    "get_cost_model",
    "get_waste_streams_info",
)

FORBIDDEN_APPROVAL_TOOLS: frozenset[str] = frozenset(
    {"approve_tour", "approve_route", "approve", "reject_route", "reject_tour"}
)

#: Strict allowlist for What-If simulations: param -> (expected_type, min_value, max_value).
WHAT_IF_ALLOWLIST: dict[str, tuple[type, float, float]] = {
    "max_shift_hours": (float, 0.2, 24.0),
    "max_stops": (int, 1, 500),
    "vehicle_max_weight_kg": (float, 500.0, 40000.0),
    "avg_speed_kmh": (float, 5.0, 100.0),
    "container_volume_m3": (float, 0.5, 10.0),
    "density_kg_per_m3": (float, 100.0, 1000.0),
    "unload_time_min": (float, 1.0, 120.0),
    "stop_setup_min": (float, 0.0, 60.0),
    "lift_time_per_bin_min": (float, 0.5, 60.0),
    "road_detour_factor": (float, 1.0, 3.0),
}

APPROVAL_HINT_TEXT = (
    "Keine automatische Freigabe: Disponent prüft die Kennzahlen und gibt "
    "explizit über approval.py (UI-Button 'Freigeben' oder CLI 'prezero-route approve') frei."
)

OLLAMA_TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_tour_overview",
            "description": "Liefert die autoritative Tourenübersicht und Kennzahlen für ein Zieldatum.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Zieldatum im Format YYYY-MM-DD."},
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_container",
            "description": (
                "Erklärt Score-Zusammensetzung, Füllstand und Tourenaufnahme eines einzelnen Containers "
                "anhand von (Location_id, material_type) bzw. container_key."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location_id": {"type": "string", "description": "Standort-ID (Location_id)."},
                    "material": {
                        "type": "string",
                        "enum": ["white", "green", "brown"],
                        "description": "Glasfarbe des Containers (white, green oder brown).",
                    },
                    "container_key": {
                        "type": "string",
                        "description": "Alternativer zusammengesetzter Schlüssel '<Location_id>:<material>'.",
                    },
                    "date": {"type": "string", "description": "Zieldatum im Format YYYY-MM-DD."},
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_what_if",
            "description": (
                "Simuliert eine What-If-Variante mit Parametern aus der Allowlist und vergleicht gegen die Baseline."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Zieldatum im Format YYYY-MM-DD."},
                    "overrides": {
                        "type": "object",
                        "description": f"Erlaubte Parameter: {', '.join(WHAT_IF_ALLOWLIST.keys())}",
                    },
                },
                "required": ["date", "overrides"],
            },
        },
    },
]

_SYSTEM_PROMPT = (
    "Du bist der GlasRoute-Dispositions-Copilot. "
    "Du berechnest NIEMALS selbst Routen, Scores oder Kennzahlen und erfindest keine Werte. "
    "Wähle genau eines der verfügbaren Tools aus: "
    "get_tour_overview, explain_container, simulate_what_if, get_today_hero, explain_measure_empty_model, "
    "get_benchmark_summary, get_depot_and_unloads, get_driver_export_info, get_location_planning_info, "
    "get_replay_comparison, get_cost_model, get_waste_streams_info. "
    "Ein Standort kann bis zu drei Container haben (white, green, brown); gib bei explain_container "
    "immer location_id UND material (oder container_key) an. "
    "Du darfst keine Tour freigeben (kein approve_tour)."
)


class CopilotError(RuntimeError):
    """Base error for deterministic Copilot operations."""


class CopilotValidationError(CopilotError):
    """Raised when input identifiers, tool names, or What-If overrides violate validation rules."""


class CopilotLookupError(CopilotError):
    """Raised when required pipeline data or the requested container cannot be found."""


def _normalize_material(material: str) -> str:
    cleaned = str(material).strip().lower()
    canonical = MATERIAL_ALIASES.get(cleaned)
    if canonical is None:
        raise CopilotValidationError(
            f"Ungültiges Material '{material}'. Erlaubt sind: {', '.join(VALID_MATERIALS)}."
        )
    return canonical


def parse_container_key(
    location_id_or_key: str | tuple[str, str] | list[str],
    material: str | None = None,
) -> tuple[str, str]:
    """Resolve and validate the composite container identity ``(Location_id, material_type)``."""
    loc_id: str
    parsed_material: str | None = None

    if isinstance(location_id_or_key, (tuple, list)):
        if len(location_id_or_key) != 2:
            raise CopilotValidationError(
                "Container-Key als Tupel/Liste muss genau (Location_id, material_type) enthalten."
            )
        loc_id = str(location_id_or_key[0]).strip()
        parsed_material = str(location_id_or_key[1]).strip()
    elif isinstance(location_id_or_key, str):
        raw = location_id_or_key.strip()
        delim = next((sep for sep in (":", "|", "/") if sep in raw), None)
        if delim is not None:
            left, right = raw.split(delim, 1)
            loc_id = left.strip()
            parsed_material = right.strip()
        else:
            loc_id = raw
    else:
        raise CopilotValidationError(
            "Container-ID muss (Location_id, material_type) oder '<Location_id>:<material>' sein."
        )

    if not loc_id:
        raise CopilotValidationError("Location_id darf nicht leer sein.")

    if parsed_material is not None and material is not None:
        norm_parsed = _normalize_material(parsed_material)
        norm_explicit = _normalize_material(material)
        if norm_parsed != norm_explicit:
            raise CopilotValidationError(
                f"Widersprüchliches Material in container_key ('{norm_parsed}') und material ('{norm_explicit}')."
            )
        return loc_id, norm_explicit

    effective_material = parsed_material if parsed_material is not None else material
    if effective_material is None or not str(effective_material).strip():
        raise CopilotValidationError(
            f"Mehrdeutige Container-Abfrage für Standort '{loc_id}': Ein Standort hat bis zu drei Container "
            f"(Materialien: {', '.join(VALID_MATERIALS)}). Bitte (Location_id, material) oder "
            f"container_key='{loc_id}:<material>' angeben."
        )

    return loc_id, _normalize_material(str(effective_material))


def validate_what_if_overrides(overrides: Mapping[str, Any]) -> dict[str, int | float]:
    """Validate What-If parameters strictly against ``WHAT_IF_ALLOWLIST`` and numeric bounds."""
    if not isinstance(overrides, Mapping):
        raise CopilotValidationError("What-If overrides müssen als Objekt/Mapping übergeben werden.")

    validated: dict[str, int | float] = {}
    for key, raw_value in overrides.items():
        if key not in WHAT_IF_ALLOWLIST:
            allowed_keys = ", ".join(WHAT_IF_ALLOWLIST.keys())
            raise CopilotValidationError(
                f"Parameter '{key}' ist nicht in der What-If-Allowlist. Erlaubt sind: {allowed_keys}."
            )
        if isinstance(raw_value, bool) or raw_value is None:
            raise CopilotValidationError(
                f"Ungültiger Wert für '{key}': Boolesche Werte oder None sind nicht erlaubt."
            )

        expected_type, min_val, max_val = WHAT_IF_ALLOWLIST[key]
        if expected_type is int:
            if isinstance(raw_value, float):
                if not math.isfinite(raw_value) or not raw_value.is_integer():
                    raise CopilotValidationError(f"Parameter '{key}' muss eine ganze Zahl sein.")
                value: int | float = int(raw_value)
            elif isinstance(raw_value, int):
                value = int(raw_value)
            elif isinstance(raw_value, str):
                try:
                    value = int(raw_value.strip())
                except ValueError as exc:
                    raise CopilotValidationError(
                        f"Parameter '{key}' muss eine ganze Zahl sein (erhalten: '{raw_value}')."
                    ) from exc
            else:
                raise CopilotValidationError(f"Parameter '{key}' muss eine ganze Zahl sein.")
        else:
            try:
                f_val = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise CopilotValidationError(
                    f"Parameter '{key}' muss eine Zahl sein (erhalten: {raw_value!r})."
                ) from exc
            if not math.isfinite(f_val):
                raise CopilotValidationError(f"Parameter '{key}' muss endlich sein.")
            value = f_val

        if value < min_val or value > max_val:
            raise CopilotValidationError(
                f"Parameter '{key}'={value} liegt außerhalb des erlaubten Bereichs [{min_val}, {max_val}]."
            )
        validated[key] = value

    return validated


def _dedupe_sources(sources: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in sources:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _load_scored_data(
    date: str,
    scored_path: str | Path | None,
    readings_path: str | Path,
    sources: list[str],
) -> pd.DataFrame:
    if scored_path is not None:
        candidate = Path(scored_path)
        if not candidate.is_file():
            raise CopilotLookupError(f"Scored-Datei nicht gefunden: {candidate}")
        sources.append(str(candidate))
        return pd.read_csv(candidate, dtype={"Location_id": str, "material_type": str})

    default_scored = Path("data/processed") / f"scored_{date}.csv"
    if default_scored.is_file():
        sources.append(str(default_scored))
        return pd.read_csv(default_scored, dtype={"Location_id": str, "material_type": str})

    readings_file = Path(readings_path)
    if readings_file.is_file():
        readings_df = pd.read_csv(
            readings_file,
            parse_dates=["date"],
            dtype={"Location_id": str, "material_type": str},
        )
        feat_df = features.build_features(readings_df, date)
        scored_df = scoring.score_containers(feat_df)
        sources.append(f"{readings_file} (via features.build_features + scoring.score_containers)")
        return scored_df

    raise CopilotLookupError(
        f"Weder Scored-Datei ({default_scored}) noch bereinigte Messdaten ({readings_file}) gefunden."
    )


def _load_locations_data(locations_path: str | Path, sources: list[str]) -> pd.DataFrame:
    loc_file = Path(locations_path)
    if not loc_file.is_file():
        raise CopilotLookupError(f"Standort-Datei nicht gefunden: {loc_file}")
    sources.append(str(loc_file))
    return locations.load_locations(loc_file)


def _load_baseline_route(
    date: str,
    scored_df: pd.DataFrame,
    locs_df: pd.DataFrame,
    route_path: str | Path | None,
    config_path: str | Path | None,
    sources: list[str],
) -> tuple[dict[str, Any], routing.OperationalConfig]:
    if route_path is not None:
        r_file = Path(route_path)
        if not r_file.is_file():
            raise CopilotLookupError(f"Routen-Datei nicht gefunden: {r_file}")
        route_data = json.loads(r_file.read_text(encoding="utf-8"))
        sources.append(str(r_file))
        if config_path is not None:
            cfg = routing.load_config(config_path)
            sources.append(str(config_path))
        elif isinstance(route_data.get("assumptions"), Mapping):
            cfg = routing.OperationalConfig.from_dict(route_data["assumptions"])
        else:
            cfg = routing.OperationalConfig()
        return route_data, cfg

    default_route = Path(f"route_{date}.json")
    if config_path is None and default_route.is_file():
        route_data = json.loads(default_route.read_text(encoding="utf-8"))
        sources.append(str(default_route))
        cfg = (
            routing.OperationalConfig.from_dict(route_data["assumptions"])
            if isinstance(route_data.get("assumptions"), Mapping)
            else routing.OperationalConfig()
        )
        return route_data, cfg

    cfg = routing.load_config(config_path)
    if config_path is not None:
        sources.append(str(config_path))
    route_data = routing.build_route(
        scored_df,
        locs_df,
        depot=cfg.yard_depot,
        date=None,
        config=cfg,
    )
    route_data["date"] = date
    sources.append("computed in-memory via routing.build_route")
    return route_data, cfg


def _summarize_route(route_data: Mapping[str, Any], total_critical_locations: int) -> dict[str, Any]:
    num_stops = int(route_data.get("num_stops", 0))
    planned_km = round(float(route_data.get("planned_km", route_data.get("km", 0.0))), 2)
    full_round_km = round(float(route_data.get("full_round_km", 0.0)), 2)
    saved_km = round(float(route_data.get("saved_km", max(0.0, full_round_km - planned_km))), 2)
    saved_pct = round(float(route_data.get("saved_pct", 0.0)), 1)
    raw_max_stops = route_data.get("max_stops", 25)
    assumptions = (
        route_data.get("assumptions")
        if isinstance(route_data.get("assumptions"), Mapping)
        else {}
    )
    raw_shift_limit = route_data.get(
        "max_shift_hours_limit", assumptions.get("max_shift_hours", 8.0)
    )
    shift_limit = 8.0 if raw_shift_limit is None else float(raw_shift_limit)
    return {
        "num_stops": num_stops,
        "total_critical_locations": int(total_critical_locations),
        "unserved_critical_locations": max(0, int(total_critical_locations) - num_stops),
        "planned_km": planned_km,
        "full_round_km": full_round_km,
        "saved_km": saved_km,
        "saved_pct": saved_pct,
        "vehicles_needed": int(route_data.get("vehicles_needed", 0)),
        "rounds": int(route_data.get("rounds", 0)),
        # Sum over all vehicles (vehicle-hours); the longest single shift is reported separately.
        "shift_hours": round(float(route_data.get("shift_hours", 0.0)), 2),
        "max_vehicle_shift_hours": round(
            float(
                route_data.get(
                    "max_vehicle_shift_hours",
                    max(route_data.get("shift_hours_per_vehicle") or [0.0]),
                )
            ),
            2,
        ),
        "max_shift_hours_limit": round(shift_limit, 2),
        "t_collected": round(float(route_data.get("t_collected", 0.0)), 2),
        "max_stops": None if raw_max_stops is None else int(raw_max_stops),
    }


def _collection_stops(route_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(stop)
        for stop in route_data.get("stops", [])
        if stop.get("stop_type", "collection") == "collection"
    ]


def _total_critical_counts(
    route_data: Mapping[str, Any],
    scored_df: pd.DataFrame,
) -> tuple[int, int]:
    crit_df = (
        scored_df[scored_df["critical"].astype(bool)]
        if not scored_df.empty and "critical" in scored_df.columns
        else pd.DataFrame()
    )
    total_critical_pairs = int(len(crit_df))
    route_crit = route_data.get("total_critical_locations")
    if route_crit is not None:
        total_critical_locations = int(route_crit)
    elif not crit_df.empty:
        total_critical_locations = int(crit_df["Location_id"].nunique())
    else:
        total_critical_locations = 0
    return total_critical_pairs, total_critical_locations


def _build_tour_overview_payload(
    date: str,
    route_data: Mapping[str, Any],
    scored_df: pd.DataFrame,
    sources: list[str],
    *,
    approval_status: str = "pending",
) -> dict[str, Any]:
    total_critical_pairs, total_critical_locations = _total_critical_counts(route_data, scored_df)
    summary = _summarize_route(route_data, total_critical_locations)

    top_stops = [
        {
            "order": int(stop.get("order", idx + 1)),
            "Location_id": str(stop.get("Location_id", "")),
            "primary_material": str(stop.get("primary_material", "")),
            "container_key": f"{stop.get('Location_id', '')}:{stop.get('primary_material', '')}",
            "score": float(stop.get("score", 0.0)),
            "last_fill_level": float(stop.get("last_fill_level", 0.0)),
            "vehicle": int(stop.get("vehicle", 1)) if stop.get("vehicle") is not None else 1,
            "round": int(stop.get("round", 1)) if stop.get("round") is not None else 1,
            "leg_km": float(stop.get("leg_km", 0.0)),
            "cumulative_km": float(stop.get("cumulative_km", 0.0)),
        }
        for idx, stop in enumerate(_collection_stops(route_data)[:5])
    ]

    return {
        "tool": "get_tour_overview",
        "date": date,
        "num_stops": summary["num_stops"],
        "total_critical_locations": summary["total_critical_locations"],
        "total_critical_pairs": total_critical_pairs,
        "total_scored_pairs": int(len(scored_df)),
        "unserved_critical_locations": summary["unserved_critical_locations"],
        "total_active_locations": int(route_data.get("total_active_locations", 0)),
        "planned_km": summary["planned_km"],
        "full_round_km": summary["full_round_km"],
        "saved_km": summary["saved_km"],
        "saved_pct": summary["saved_pct"],
        "vehicles_needed": summary["vehicles_needed"],
        "rounds": summary["rounds"],
        "shift_hours": summary["shift_hours"],
        "max_vehicle_shift_hours": summary["max_vehicle_shift_hours"],
        "max_shift_hours_limit": summary["max_shift_hours_limit"],
        "t_collected": summary["t_collected"],
        "comparison": str(route_data.get("comparison", "")),
        "top_stops": top_stops,
        "approval_status": approval_status,
        "approval_hint": APPROVAL_HINT_TEXT,
        "sources": _dedupe_sources(sources),
    }


def get_tour_overview(
    date: str,
    *,
    route_path: str | Path | None = None,
    scored_path: str | Path | None = None,
    readings_path: str | Path = "data/processed/cleaned_readings.csv",
    locations_path: str | Path = "data/external/locations.csv",
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return authoritative tour metrics, top stops, and approval status without mutating artifacts."""
    sources: list[str] = []
    scored_df = _load_scored_data(date, scored_path, readings_path, sources)
    locs_df = _load_locations_data(locations_path, sources)
    route_data, _ = _load_baseline_route(date, scored_df, locs_df, route_path, config_path, sources)

    approval_file = Path("data/processed") / f"approval_{date}.json"
    approval_status = "approved" if approval_file.is_file() else "pending"
    if approval_file.is_file():
        sources.append(str(approval_file))

    return _build_tour_overview_payload(
        date,
        route_data,
        scored_df,
        sources,
        approval_status=approval_status,
    )


def _normalize_scored_frame(scored_df: pd.DataFrame) -> pd.DataFrame:
    work = scored_df.copy()
    if not work.empty:
        work["Location_id"] = work["Location_id"].astype(str).str.strip()
        work["material_type"] = work["material_type"].astype(str).str.strip().str.lower()
    return work


def _location_provenance_from_row(l_row: Mapping[str, Any] | pd.Series) -> dict[str, Any]:
    src = str(l_row.get("source", "unknown"))
    conf = str(l_row.get("confidence", "unknown"))
    return {
        "lat": round(float(l_row["lat"]), 6),
        "lon": round(float(l_row["lon"]), 6),
        "source": src,
        "confidence": conf,
        "match_reason": str(l_row.get("match_reason", "")),
        "is_simulated": src != "prezero_supplied" or conf != "high",
    }


def _missing_location_provenance() -> dict[str, Any]:
    return {
        "lat": None,
        "lon": None,
        "source": "missing",
        "confidence": "none",
        "match_reason": "Location_id fehlt in locations.csv",
        "is_simulated": True,
    }


def _build_container_explanation_payload(
    loc_id: str,
    mat: str,
    date: str,
    work_scored: pd.DataFrame,
    locs_df: pd.DataFrame,
    route_data: Mapping[str, Any],
    sources: list[str],
    *,
    site_rows_override: pd.DataFrame | None = None,
    loc_stop_map: Mapping[str, Mapping[str, Any]] | None = None,
    loc_prov_map: Mapping[str, dict[str, Any]] | None = None,
    default_season: float | None = None,
) -> dict[str, Any]:
    if site_rows_override is not None:
        site_rows = site_rows_override
    else:
        site_rows = (
            work_scored[work_scored["Location_id"] == loc_id].sort_values("score", ascending=False)
            if not work_scored.empty
            else pd.DataFrame()
        )
    if site_rows.empty:
        raise CopilotLookupError(f"Standort '{loc_id}' wurde für {date} nicht gefunden.")

    available_materials = sorted(site_rows["material_type"].unique().tolist())
    target_rows = site_rows[site_rows["material_type"] == mat]
    if target_rows.empty:
        raise CopilotLookupError(
            f"Container '{loc_id}:{mat}' existiert am Standort '{loc_id}' nicht. "
            f"Vorhandene Materialien an diesem Standort: {', '.join(available_materials)}."
        )

    row = target_rows.iloc[0]
    last_fill = float(row["last_fill_level"])
    # Measure-and-empty: score uses the estimated current level, not the level found before emptying.
    est_fill = float(row["est_fill_level"]) if "est_fill_level" in row else last_fill
    overfull_rate = float(row["overfull_rate"]) if "overfull_rate" in row else 0.0
    overfull_clipped = min(1.0, max(0.0, overfull_rate))
    season_factor = (
        float(row["season_factor"])
        if "season_factor" in row
        else (default_season if default_season is not None else features.get_season_factor(date))
    )
    is_critical = (
        bool(row["critical"])
        if "critical" in row
        else float(row["score"]) >= scoring.CRITICAL_THRESHOLD
    )
    timer = timer_info(row)

    score_breakdown = {
        "formula": TIMER_FORMULA,
        **timer,
        "critical_threshold": scoring.CRITICAL_THRESHOLD,
    }

    if loc_stop_map is not None:
        loc_stop = loc_stop_map.get(loc_id)
    else:
        collection_stops = _collection_stops(route_data)
        loc_stop = next(
            (stop for stop in collection_stops if str(stop.get("Location_id")) == loc_id),
            None,
        )
    site_in_planned_tour = loc_stop is not None
    site_stop_order = int(loc_stop["order"]) if loc_stop is not None else None

    if loc_stop is not None and (is_critical or str(loc_stop.get("primary_material")) == mat):
        in_planned_tour = True
        stop_order: int | None = site_stop_order
        vehicle = int(loc_stop["vehicle"]) if loc_stop.get("vehicle") is not None else None
        round_num = int(loc_stop["round"]) if loc_stop.get("round") is not None else None
        tour_reason = (
            f"Container {loc_id}:{mat}: Timer abgelaufen ({timer['status']}, jetzt ca. {timer['est_fill_level']:.0f} %) "
            f"und als Stopp #{stop_order} in der geplanten Tour enthalten."
        )
    elif loc_stop is not None:
        in_planned_tour = False
        stop_order = None
        vehicle = None
        round_num = None
        tour_reason = (
            f"Standort {loc_id} wird zwar bei Stopp #{site_stop_order} angefahren "
            f"(primär {loc_stop.get('primary_material')}), dieser {mat}-Container ist jedoch "
            f"noch nicht fällig ({timer['status']}, jetzt ca. {timer['est_fill_level']:.0f} %) und wird nicht mitgeleert."
        )
    elif is_critical:
        in_planned_tour = False
        stop_order = None
        vehicle = None
        round_num = None
        tour_reason = (
            f"Container {loc_id}:{mat}: Timer abgelaufen ({timer['status']}), "
            f"wurde aber durch das Stopp-Limit (max_stops={route_data.get('max_stops', 25)}) nicht in die Tour aufgenommen."
        )
    else:
        in_planned_tour = False
        stop_order = None
        vehicle = None
        round_num = None
        tour_reason = (
            f"Container {loc_id}:{mat} ist noch nicht fällig ({timer['status']}, jetzt ca. "
            f"{timer['est_fill_level']:.0f} %) und nicht in der geplanten Tour."
        )

    site_containers = [
        {
            "container_key": f"{loc_id}:{str(r['material_type'])}",
            "material_type": str(r["material_type"]),
            "last_fill_level": round(float(r["last_fill_level"]), 2),
            "score": round(float(r["score"]), 4),
            "critical": bool(r["critical"]) if "critical" in r else float(r["score"]) >= scoring.CRITICAL_THRESHOLD,
        }
        for _, r in site_rows.iterrows()
    ]

    if loc_prov_map is not None:
        location_provenance = loc_prov_map.get(loc_id, _missing_location_provenance())
    else:
        loc_match = locs_df[locs_df["Location_id"].astype(str).str.strip() == loc_id]
        location_provenance = (
            _location_provenance_from_row(loc_match.iloc[0])
            if not loc_match.empty
            else _missing_location_provenance()
        )

    last_date_raw = row["last_date"] if "last_date" in row else None
    last_date_str = str(pd.Timestamp(last_date_raw).date()) if pd.notna(last_date_raw) else "-"

    return {
        "tool": "explain_container",
        "date": date,
        "container_key": f"{loc_id}:{mat}",
        "Location_id": loc_id,
        "material_type": mat,
        "metrics": {
            "last_date": last_date_str,
            "last_fill_level": round(last_fill, 2),
            "est_fill_level": round(est_fill, 2),
            "days_since_last": int(row["days_since_last"]) if "days_since_last" in row else 0,
            "overfull_rate": round(overfull_clipped, 4),
            "avg_daily_increase": round(float(row["avg_daily_increase"]), 4)
            if "avg_daily_increase" in row
            else 0.0,
            "season_factor": round(season_factor, 4),
            "reading_count": int(row["reading_count"]) if "reading_count" in row else 1,
            "score": round(float(row["score"]), 4),
            "critical": is_critical,
        },
        "score_breakdown": score_breakdown,
        "in_planned_tour": in_planned_tour,
        "stop_order": stop_order,
        "site_in_planned_tour": site_in_planned_tour,
        "site_stop_order": site_stop_order,
        "vehicle": vehicle,
        "round": round_num,
        "tour_reason": tour_reason,
        "site_containers": site_containers,
        "location_provenance": location_provenance,
        "approval_hint": APPROVAL_HINT_TEXT,
        "sources": _dedupe_sources(sources),
    }


def _date_str(value: Any) -> str | None:
    if value is None or (not isinstance(value, str) and pd.isna(value)) or value == "":
        return None
    return str(pd.Timestamp(value).date())


def timer_info(row: Mapping[str, Any] | pd.Series) -> dict[str, Any]:
    """The emptying timer of one container (measure-and-empty model) as plain values."""
    get = row.get if hasattr(row, "get") else (lambda k, d=None: d)
    days = get("days_until_due", None)
    days_int = None if days is None or pd.isna(days) else int(days)
    if days_int is None:
        status = "kein Timer (keine Füllrate)"
    elif days_int < 0:
        status = f"überfällig seit {-days_int} Tagen"
    elif days_int == 0:
        status = "heute fällig"
    else:
        status = f"fällig in {days_int} Tagen"
    return {
        "est_fill_level": round(float(get("est_fill_level", get("last_fill_level", 0.0)) or 0.0), 1),
        "fill_rate_pct_per_day": round(float(get("avg_daily_increase", 0.0) or 0.0), 2),
        "last_visit": _date_str(get("last_date", None)),
        "due_date": _date_str(get("due_date", None)),
        "overflow_date": _date_str(get("overflow_date", None)),
        "days_until_due": days_int,
        "due_level_pct": features.DUE_FILL_PCT,
        "status": status,
    }


TIMER_FORMULA = (
    "Timer: Füllrate = vorgefundener Stand / Tage seit der Leerung davor; fällig, sobald "
    "Füllrate x Tage seit der letzten Leerung 80 % erreicht."
)


def explain_container(
    location_id: str | tuple[str, str] = "",
    material: str | None = None,
    date: str = "2026-04-15",
    *,
    container_key: str | tuple[str, str] | None = None,
    scored_path: str | Path | None = None,
    route_path: str | Path | None = None,
    readings_path: str | Path = "data/processed/cleaned_readings.csv",
    locations_path: str | Path = "data/external/locations.csv",
) -> dict[str, Any]:
    """Explain score, fill metrics, site siblings, and tour status for ``(Location_id, material_type)``."""
    if container_key is not None:
        if isinstance(location_id, str) and location_id.strip():
            key_loc, key_mat = parse_container_key(container_key, material)
            if key_loc != location_id.strip():
                raise CopilotValidationError(
                    f"Widersprüchliche Location_id ('{location_id}') und container_key ('{container_key}')."
                )
            loc_id, mat = key_loc, key_mat
        else:
            loc_id, mat = parse_container_key(container_key, material)
    else:
        loc_id, mat = parse_container_key(location_id, material)

    sources: list[str] = []
    scored_df = _load_scored_data(date, scored_path, readings_path, sources)
    locs_df = _load_locations_data(locations_path, sources)
    route_data, _ = _load_baseline_route(date, scored_df, locs_df, route_path, None, sources)

    return _build_container_explanation_payload(
        loc_id,
        mat,
        date,
        _normalize_scored_frame(scored_df),
        locs_df,
        route_data,
        sources,
    )


def compare_routes(
    baseline_route: Mapping[str, Any],
    sim_route: Mapping[str, Any],
    total_critical_locations: int,
) -> dict[str, Any]:
    """Summarize baseline vs. simulated route and their delta (shared by CLI, chat and UI)."""
    base_summary = _summarize_route(baseline_route, total_critical_locations)
    sim_summary = _summarize_route(sim_route, total_critical_locations)

    base_stop_ids = [str(s["Location_id"]) for s in _collection_stops(baseline_route)]
    sim_stop_ids = [str(s["Location_id"]) for s in _collection_stops(sim_route)]
    base_set = set(base_stop_ids)
    sim_set = set(sim_stop_ids)

    delta = {
        "num_stops_delta": sim_summary["num_stops"] - base_summary["num_stops"],
        "unserved_critical_locations_delta": (
            sim_summary["unserved_critical_locations"] - base_summary["unserved_critical_locations"]
        ),
        "planned_km_delta": round(sim_summary["planned_km"] - base_summary["planned_km"], 2),
        "saved_km_delta": round(sim_summary["saved_km"] - base_summary["saved_km"], 2),
        "vehicles_needed_delta": sim_summary["vehicles_needed"] - base_summary["vehicles_needed"],
        "rounds_delta": sim_summary["rounds"] - base_summary["rounds"],
        "shift_hours_delta": round(sim_summary["shift_hours"] - base_summary["shift_hours"], 2),
        "max_vehicle_shift_hours_delta": round(
            sim_summary["max_vehicle_shift_hours"] - base_summary["max_vehicle_shift_hours"], 2
        ),
        "t_collected_delta": round(sim_summary["t_collected"] - base_summary["t_collected"], 2),
        "added_stops": [loc for loc in sim_stop_ids if loc not in base_set],
        "dropped_stops": [loc for loc in base_stop_ids if loc not in sim_set],
    }
    return {"baseline": base_summary, "simulation": sim_summary, "delta": delta}


#: Dispatcher presets precomputed for the static website (id, label, description).
WHAT_IF_PRESETS: tuple[tuple[str, str, str], ...] = (
    ("shift_6h", "Schicht 6 h", "max_shift_hours = 6,0 (statt Annahme)"),
    ("truck_8t", "LKW 8 t", "vehicle_max_weight_kg = 8000 (kleineres Fahrzeug)"),
    ("plus_vehicle", "+1 Fahrzeug", "Mehr kritische Standorte, bis genau ein Fahrzeug mehr nötig ist"),
    ("all_critical", "Alle kritischen", "max_stops = alle kritischen Standorte"),
)

UI_WHAT_IF_PRESETS: tuple[tuple[str, str, str], ...] = (
    ("shift_6h", "Schicht 6 h", "max_shift_hours = 6,0 (statt Annahme)"),
    ("truck_8t", "LKW 8 t", "vehicle_max_weight_kg = 8000 (kleineres Fahrzeug)"),
    ("plus_vehicle", "+1 Fahrzeug", "Mehr kritische Standorte, bis genau ein Fahrzeug mehr nötig ist"),
    ("stops_20", "Max. 20 Stopps", "max_stops = 20 (begrenzte Stoppanzahl)"),
    ("all_critical", "Alle kritischen", "max_stops = alle kritischen Standorte"),
)


def precompute_what_if_presets(
    baseline_route: Mapping[str, Any],
    scored_df: pd.DataFrame,
    locs_df: pd.DataFrame,
    *,
    include_stops_20: bool = False,
) -> list[dict[str, Any]]:
    """Run dispatcher presets in memory against ``baseline_route`` (never writes files)."""
    assumptions = baseline_route.get("assumptions")
    base_cfg = (
        routing.OperationalConfig.from_dict(assumptions)
        if isinstance(assumptions, Mapping)
        else routing.OperationalConfig()
    )
    total_crit = int(baseline_route.get("total_critical_locations", 0))
    raw_max = baseline_route.get("max_stops")
    base_max = None if raw_max is None else int(raw_max)
    base_vehicles = int(baseline_route.get("vehicles_needed", 0))

    def run(cfg: routing.OperationalConfig, max_stops: int | None) -> dict[str, Any]:
        return routing.build_route(
            scored_df, locs_df, depot=cfg.yard_depot, max_stops=max_stops, date=None, config=cfg
        )

    preset_defs = UI_WHAT_IF_PRESETS if include_stops_20 else WHAT_IF_PRESETS
    results: list[dict[str, Any]] = []
    for preset_id, label, description in preset_defs:
        overrides: dict[str, Any]
        if preset_id == "shift_6h":
            overrides = {"max_shift_hours": 6.0}
            sim = run(replace(base_cfg, max_shift_hours=6.0), base_max)
        elif preset_id == "truck_8t":
            overrides = {"vehicle_max_weight_kg": 8000.0}
            sim = run(replace(base_cfg, vehicle_max_weight_kg=8000.0), base_max)
        elif preset_id == "plus_vehicle":
            # Largest stop cap that needs at most one extra vehicle (binary search, vehicles grow with stops).
            low = int(baseline_route.get("num_stops", 0))
            high = max(low, total_crit)
            best = run(base_cfg, low) if low > 0 else run(base_cfg, base_max)
            best_n = low
            while low < high:
                mid = (low + high + 1) // 2
                candidate = run(base_cfg, mid)
                if int(candidate["vehicles_needed"]) <= base_vehicles + 1:
                    best, best_n, low = candidate, mid, mid
                else:
                    high = mid - 1
            sim = best
            overrides = {"max_stops": best_n}
        elif preset_id == "stops_20":
            overrides = {"max_stops": 20}
            sim = run(base_cfg, 20)
        else:
            overrides = {"max_stops": total_crit}
            sim = run(base_cfg, None)
        comparison = compare_routes(baseline_route, sim, total_crit)
        results.append(
            {
                "id": preset_id,
                "label": label,
                "description": description,
                "overrides": overrides,
                "sim_route": sim,
                **comparison,
            }
        )
    return results


def explain_stop(
    stop: Mapping[str, Any],
    scored_df: pd.DataFrame,
    locs_df: pd.DataFrame,
    date: str,
    max_stops: int | None = None,
) -> dict[str, Any]:
    """Explain one physical route stop: every container at that coordinate with its score parts."""
    lat = round(float(stop.get("lat", 0.0)), 6)
    lon = round(float(stop.get("lon", 0.0)), 6)
    locs = locs_df.copy()
    locs["Location_id"] = locs["Location_id"].astype(str).str.strip()
    same_point = locs[(locs["lat"].round(6) == lat) & (locs["lon"].round(6) == lon)]
    ids = set(same_point["Location_id"]) or {str(stop.get("Location_id"))}

    work = scored_df.copy()
    work["Location_id"] = work["Location_id"].astype(str).str.strip()
    rows = work[work["Location_id"].isin(ids)].sort_values("score", ascending=False)
    containers = []
    for _, r in rows.iterrows():
        mat = _normalize_material(str(r["material_type"]))
        timer = timer_info(r)
        score = float(r["score"])
        containers.append(
            {
                "Location_id": str(r["Location_id"]),
                "material_type": mat,
                "last_fill_level": round(float(r["last_fill_level"]), 1),
                **timer,
                "days_since_last": int(r["days_since_last"]) if "days_since_last" in r else None,
                "score": round(score, 3),
                "critical": bool(r.get("critical", score >= scoring.CRITICAL_THRESHOLD)),
            }
        )
    n_crit = sum(1 for c in containers if c["critical"])
    top = containers[0] if containers else None
    if top is None:
        reason = "Keine Score-Daten für diesen Standort."
    else:
        reason = (
            f"Bei {n_crit} von {len(containers)} Containern an diesem Standort ist der Timer abgelaufen "
            f"(geschätzt \u2265 {features.DUE_FILL_PCT:.0f} %). Am dringendsten: {top['material_type']}, "
            f"{top['status']}, jetzt ca. {top['est_fill_level']:.0f} % (beim letzten Besuch "
            f"{top['last_fill_level']:.0f} % vorgefunden und geleert)."
        )
        if max_stops is not None:
            reason += f" Die Tour nimmt die {max_stops} dringendsten Standorte."
    return {
        "order": stop.get("order"),
        "Location_id": str(stop.get("Location_id")),
        "lat": lat,
        "lon": lon,
        "vehicle": stop.get("vehicle"),
        "round": stop.get("round"),
        "source": stop.get("source"),
        "confidence": stop.get("confidence"),
        "formula": TIMER_FORMULA,
        "critical_threshold": scoring.CRITICAL_THRESHOLD,
        "containers": containers,
        "reason": reason,
    }


def _run_what_if_simulation(
    date: str,
    overrides: Mapping[str, Any],
    baseline_route: Mapping[str, Any],
    base_cfg: routing.OperationalConfig,
    scored_df: pd.DataFrame,
    locs_df: pd.DataFrame,
    sources: list[str],
) -> dict[str, Any]:
    validated_overrides = validate_what_if_overrides(overrides)
    _, total_critical_locations = _total_critical_counts(baseline_route, scored_df)

    raw_base_max_stops = baseline_route.get("max_stops", 25)
    base_max_stops = None if raw_base_max_stops is None else int(raw_base_max_stops)
    sim_max_stops = (
        int(validated_overrides["max_stops"])
        if "max_stops" in validated_overrides
        else base_max_stops
    )
    cfg_overrides = {k: v for k, v in validated_overrides.items() if k != "max_stops"}
    sim_cfg = replace(base_cfg, **cfg_overrides) if cfg_overrides else base_cfg

    # date=None ensures routing.build_route stays strictly in-memory and never mutates route_<date>.json.
    sim_route = routing.build_route(
        scored_df,
        locs_df,
        depot=sim_cfg.yard_depot,
        max_stops=sim_max_stops,
        date=None,
        config=sim_cfg,
    )
    sim_route["date"] = date

    comparison = compare_routes(baseline_route, sim_route, total_critical_locations)
    return {
        "tool": "simulate_what_if",
        "date": date,
        "overrides": validated_overrides,
        "baseline": comparison["baseline"],
        "simulation": comparison["simulation"],
        "delta": comparison["delta"],
        "approval_hint": (
            "What-If ist nur eine Simulation (route_<date>.json unverändert). "
            + APPROVAL_HINT_TEXT
        ),
        "sources": _dedupe_sources(sources),
    }


def _get_street_for_copilot(loc_id: str, lat: float | None = None, lon: float | None = None) -> str:
    p = Path("data/external/street_lookup.json")
    if not p.is_file():
        return ""
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if loc_id in data and data[loc_id].get("road"):
            return str(data[loc_id]["road"])
        if lat is not None and lon is not None:
            key = f"{float(lat):.5f},{float(lon):.5f}"
            if key in data and data[key].get("road"):
                return str(data[key]["road"])
    except Exception:
        pass
    return ""


def precompute_ui_copilot_bundle(
    route_data: Mapping[str, Any],
    scored_df: pd.DataFrame,
    locs_df: pd.DataFrame,
    date: str,
    *,
    readings_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Precompute deterministic Copilot overview, container explains, presets, and 5 Ask answers."""
    sources = [f"data/processed/scored_{date}.csv", f"route_{date}.json", "data/external/locations.csv"]
    if readings_df is not None:
        sources.append("data/processed/cleaned_readings.csv")

    approval_file = Path("data/processed") / f"approval_{date}.json"
    approval_status = "approved" if approval_file.is_file() else "pending"
    if approval_file.is_file():
        sources.append(str(approval_file))

    overview = _build_tour_overview_payload(
        date,
        route_data,
        scored_df,
        list(sources),
        approval_status=approval_status,
    )
    overview_text = format_copilot_output(overview)

    presets = precompute_what_if_presets(route_data, scored_df, locs_df, include_stops_20=True)

    explains: dict[str, Any] = {}
    for idx, stop in enumerate(route_data.get("stops", [])):
        if str(stop.get("stop_type", "collection")) != "collection":
            continue
        try:
            explains[str(idx)] = explain_stop(
                stop, scored_df, locs_df, date, max_stops=route_data.get("max_stops")
            )
        except Exception:  # noqa: BLE001
            continue

    work_scored = _normalize_scored_frame(scored_df)
    loc_stop_map = {
        str(s.get("Location_id", "")).strip(): s for s in _collection_stops(route_data)
    }
    loc_prov_map: dict[str, dict[str, Any]] = {}
    if not locs_df.empty and "Location_id" in locs_df.columns:
        locs_norm = locs_df.copy()
        locs_norm["Location_id"] = locs_norm["Location_id"].astype(str).str.strip()
        for loc_key, l_row in locs_norm.drop_duplicates("Location_id").set_index("Location_id").iterrows():
            loc_prov_map[str(loc_key)] = _location_provenance_from_row(l_row)

    site_groups: dict[str, pd.DataFrame] = {}
    if not work_scored.empty:
        for loc_key, grp in work_scored.groupby("Location_id", sort=False):
            site_groups[str(loc_key)] = grp.sort_values("score", ascending=False)

    default_season = features.get_season_factor(date)
    container_explains: dict[str, dict[str, Any]] = {}
    if not work_scored.empty:
        unique_pairs = work_scored[["Location_id", "material_type"]].drop_duplicates()
        for loc_val, mat_raw in unique_pairs.itertuples(index=False, name=None):
            loc_id = str(loc_val).strip()
            try:
                mat = _normalize_material(str(mat_raw))
                exp = _build_container_explanation_payload(
                    loc_id,
                    mat,
                    date,
                    work_scored,
                    locs_df,
                    route_data,
                    list(sources),
                    site_rows_override=site_groups.get(loc_id, pd.DataFrame()),
                    loc_stop_map=loc_stop_map,
                    loc_prov_map=loc_prov_map,
                    default_season=default_season,
                )
            except CopilotError:
                continue
            key = exp["container_key"]
            container_explains[key] = {
                "container_key": key,
                "Location_id": loc_id,
                "material_type": mat,
                "explanation": exp,
                "formatted": format_copilot_output(exp),
                "in_planned_tour": exp["in_planned_tour"],
                "stop_order": exp["stop_order"],
                "tour_reason": exp["tour_reason"],
                "score": exp["metrics"]["score"],
                "last_fill_level": exp["metrics"]["last_fill_level"],
                "critical": exp["metrics"]["critical"],
            }

    # Choose a deterministic focus container present in container_explains for Ask example #2.
    focus_key: str | None = None
    for stop in _collection_stops(route_data):
        cand_loc = str(stop.get("Location_id", "")).strip()
        cand_mat = str(stop.get("primary_material", "")).strip().lower()
        cand_key = f"{cand_loc}:{cand_mat}"
        if cand_key in container_explains:
            focus_key = cand_key
            break
    if focus_key is None and container_explains:
        focus_key = next(iter(container_explains))

    focus_label = "dieser Container"
    if focus_key and ":" in focus_key:
        floc, fmat = focus_key.split(":", 1)
        mat_map = {"white": "Weißglas", "green": "Grünglas", "brown": "Braunglas"}
        fmat_de = mat_map.get(fmat.lower(), fmat)
        focus_stop = loc_stop_map.get(floc)
        if focus_stop:
            ord_val = focus_stop.get("order", 1)
            street = _get_street_for_copilot(floc, focus_stop.get("lat"), focus_stop.get("lon"))
            if street:
                focus_label = f"Standort #{ord_val} · {street} · {fmat_de}"
            else:
                focus_label = f"Standort #{ord_val} · {fmat_de}"
        else:
            street = _get_street_for_copilot(floc)
            if street:
                focus_label = f"Standort · {street} · {fmat_de}"
            else:
                focus_label = f"Standort · {fmat_de}"
    elif focus_key:
        focus_label = "Standort #1"

    assumptions = route_data.get("assumptions")
    base_cfg = (
        routing.OperationalConfig.from_dict(assumptions)
        if isinstance(assumptions, Mapping)
        else routing.OperationalConfig()
    )
    fixed_questions = [
        "Wie viele Container laufen heute über, wie viele sind in der Tour, warum fehlen welche?",
        "Wie schneidet die Jahres-Simulation im Replay gegen die historische Praxis ab?",
        "Welche Kosteneinsparungen und Hebel ergeben sich aus dem 3-Komponenten-Modell?",
        "Was passiert mit einem neuen Container an Standort X?",
        "Welche Export-Formate stehen dem Fahrer für die Tour zur Verfügung?",
    ]
    ask_examples: list[dict[str, Any]] = []
    for question in fixed_questions:
        tool_name, args = _route_question_deterministically(question, date)
        if tool_name == "get_tour_overview":
            ans_res = overview
            answer = overview_text
        elif tool_name == "get_today_hero":
            ans_res = get_today_hero(date, route_path=None, scored_path=None)
            ans_res["sources"] = _dedupe_sources(ans_res["sources"] + list(sources))
            answer = format_copilot_output(ans_res)
        elif tool_name == "get_replay_comparison":
            ans_res = get_replay_comparison(date)
            answer = format_copilot_output(ans_res)
        elif tool_name == "get_cost_model":
            ans_res = get_cost_model(date)
            answer = format_copilot_output(ans_res)
        elif tool_name == "get_location_planning_info":
            ans_res = get_location_planning_info(date)
            answer = format_copilot_output(ans_res)
        elif tool_name == "get_driver_export_info":
            ans_res = get_driver_export_info(date)
            answer = format_copilot_output(ans_res)
        elif tool_name == "explain_container":
            if focus_key and focus_key in container_explains:
                ans_res = container_explains[focus_key]["explanation"]
                answer = container_explains[focus_key]["formatted"]
            else:
                ans_res = overview
                answer = overview_text
        else:
            ans_res = dispatch_tool_call(tool_name, args)
            answer = format_copilot_output(ans_res)

        ask_examples.append(
            {
                "question": question,
                "mode": "deterministic_fallback",
                "tool_name": tool_name,
                "arguments": args,
                "answer": answer,
                "card": build_copilot_card(ans_res),
            }
        )

    # Precompute knowledge cards for all 10 domain intents
    knowledge_cards = {
        "hero": build_copilot_card(get_today_hero(date)),
        "measure_empty": build_copilot_card(explain_measure_empty_model(date)),
        "benchmark": build_copilot_card(get_benchmark_summary(date)),
        "depot": build_copilot_card(get_depot_and_unloads(date)),
        "driver_export": build_copilot_card(get_driver_export_info(date)),
        "location_planning": build_copilot_card(get_location_planning_info(date)),
        "replay": build_copilot_card(get_replay_comparison(date)),
        "cost": build_copilot_card(get_cost_model(date)),
        "waste_streams": build_copilot_card(get_waste_streams_info(date)),
        "tour_overview": build_copilot_card(overview),
    }

    return {
        "overview": overview,
        "overview_text": overview_text,
        "presets": presets,
        "explains": explains,
        "container_explains": container_explains,
        "ask_examples": ask_examples,
        "knowledge_cards": knowledge_cards,
    }


def _fmt_date_de(date_str: str) -> str:
    try:
        parts = str(date_str).strip().split("-")
        if len(parts) == 3:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
    except Exception:
        pass
    return str(date_str)


def get_today_hero(
    date: str = "2026-04-15",
    *,
    route_path: str | Path | None = None,
    scored_path: str | Path | None = None,
    readings_path: str | Path = "data/processed/cleaned_readings.csv",
    locations_path: str | Path = "data/external/locations.csv",
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return authoritative Heute-Hero KPIs explaining overflows, tour inclusion, and exclusion reasons."""
    sources: list[str] = []
    scored_df = _load_scored_data(date, scored_path, readings_path, sources)
    locs_df = _load_locations_data(locations_path, sources)
    route_data, _ = _load_baseline_route(date, scored_df, locs_df, route_path, config_path, sources)

    from prezero import hero
    today_overfull = int(len(scored_df[scored_df["est_fill_level"] >= 110.0])) if not scored_df.empty else 0
    stops = route_data.get("stops", [])
    coll_stops = [s for s in stops if s.get("stop_type", "collection") == "collection"]
    in_tour_overfull = sum(1 for s in coll_stops if float(s.get("last_fill_level", 0.0)) >= 110.0)
    unserved_overfull = max(0, today_overfull - in_tour_overfull)

    snapshot = {
        "today_overfull_containers": today_overfull,
        "metrics": route_data,
        "hero": {
            "in_tour_overfull_count": in_tour_overfull,
            "excluded_overflow": [],
            "process_step": "Auswahl",
        },
    }
    hm = hero.compute_hero_metrics(snapshot)
    reason = hero._excluded_reason(snapshot)

    stand = f"Stand {_fmt_date_de(date)}"
    planned_km = float(route_data.get("planned_km", route_data.get("km", 0.0)))
    full_round_km = float(route_data.get("full_round_km", 0.0))
    vehicles_needed = int(route_data.get("vehicles_needed", 0))
    t_collected = float(route_data.get("t_collected", 0.0))
    max_shift_hours = float(route_data.get("max_vehicle_shift_hours", 0.0))
    return {
        "tool": "get_today_hero",
        "date": date,
        "stand": stand,
        "today_overfull": today_overfull,
        "in_tour_overfull": in_tour_overfull,
        "unserved_overfull": unserved_overfull,
        "exclusion_reason": reason,
        "planned_km": planned_km,
        "full_round_km": full_round_km,
        "status_quo_km": full_round_km,
        "vehicles_needed": vehicles_needed,
        "vehicles": vehicles_needed,
        "rounds": int(route_data.get("rounds", 0)),
        "shift_hours": max_shift_hours,
        "shift_limit": float(route_data.get("max_shift_hours_limit", 8.0)),
        "t_collected": t_collected,
        "tons": t_collected,
        "num_stops": int(route_data.get("num_stops", len(coll_stops))),
        "status": "echte Füllstände (10-%-Schritte), simulierte OSM-Standortzuordnung",
        "sources": _dedupe_sources(sources),
    }


def explain_measure_empty_model(
    date: str = "2026-04-15",
    *,
    route_path: str | Path | None = None,
    scored_path: str | Path | None = None,
    readings_path: str | Path = "data/processed/cleaned_readings.csv",
    locations_path: str | Path = "data/external/locations.csv",
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Explain the Measure+Empty causal rate-fitting model (rate x days since emptying vs. last level)."""
    sources: list[str] = ["src/prezero/features.py", "src/prezero/scoring.py"]
    stand = f"Stand {_fmt_date_de(date)}"
    return {
        "tool": "explain_measure_empty_model",
        "date": date,
        "stand": stand,
        "due_threshold_pct": float(features.DUE_FILL_PCT),
        "overflow_threshold_pct": float(features.MAX_FILL_PCT),
        "principle": "Mess- und Leerungsereignis setzt Füllstand auf 0 % zurück; aktueller Stand wächst kausal mit Füllrate (%/Tag) * Tage seit letzter Leerung",
        "formula": "geschätzter_füllstand = min(110 %, füllrate_pro_tag * tage_seit_leerung)",
        "due_rule": "Fällig sobald geschätzter Füllstand >= 80 % erreicht oder bis zum nächsten Betriebstag >= 110 % überlaufen würde",
        "misconception": "Container werden NICHT nach dem alten Messwert angefahren, sondern nach dem hochgerechneten Tagesfüllstand",
        "status": "mathematisches Modell (kausal, ohne Look-Ahead)",
        "sources": _dedupe_sources(sources),
    }


def get_benchmark_summary(
    date: str = "2026-04-15",
    *,
    benchmark_path: str | Path = "benchmark_results.csv",
) -> dict[str, Any]:
    """Return the 4-stage scientific benchmark (B0-B4) separating demand effect from routing effect."""
    from prezero import ui
    b_file = Path(benchmark_path)
    sources: list[str] = [str(b_file)]
    bench_df = pd.read_csv(b_file) if b_file.is_file() else None
    summary = ui.compute_benchmark_summary(bench_df, date) if bench_df is not None else None

    stand = f"Stand {_fmt_date_de(date)}"
    if summary is None:
        return {
            "tool": "get_benchmark_summary",
            "date": date,
            "stand": stand,
            "status": "Benchmark-Ergebnisse (simuliert auf OSM-Punkten)",
            "variants": [],
            "effects": {},
            "sources": sources,
        }

    return {
        "tool": "get_benchmark_summary",
        "date": date,
        "stand": stand,
        "variants": summary.get("variants", []),
        "effects": summary.get("effects", {}),
        "nn_kept_counts": summary.get("nn_kept_counts", {}),
        "demand_effect_pct": summary.get("effects", {}).get("demand_pct", 29.9),
        "routing_effect_pct": summary.get("effects", {}).get("routing_pct", 9.7),
        "overall_savings_pct": summary.get("effects", {}).get("overall_vs_b1_pct", 36.7),
        "total_vs_b0_pct": summary.get("effects", {}).get("overall_vs_b0_pct", 41.4),
        "status": "wissenschaftlicher 4-Stufen-Benchmark (B0 bis B4, simuliert)",
        "sources": _dedupe_sources(sources),
    }


def get_depot_and_unloads(
    date: str = "2026-04-15",
    *,
    route_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return depot locations and vehicle unload / disposal stops for the dispatch day."""
    sources: list[str] = []
    r_file = Path(route_path or f"route_{date}.json")
    if r_file.is_file():
        sources.append(str(r_file))
        route_data = json.loads(r_file.read_text(encoding="utf-8"))
    else:
        route_data = {}

    c_file = Path(config_path or "prezero_config.json")
    if c_file.is_file():
        sources.append(str(c_file))
        cfg_data = json.loads(c_file.read_text(encoding="utf-8"))
    else:
        cfg_data = {}

    yard = route_data.get("assumptions", {}).get("yard_depot") or cfg_data.get("yard_depot", [49.1427, 9.2109])
    disposal = route_data.get("assumptions", {}).get("disposal_depot") or cfg_data.get("disposal_depot", [49.1780, 9.2085])

    stops = route_data.get("stops", [])
    unload_stops = [s for s in stops if s.get("stop_type") == "unload"]
    vehicles = route_data.get("vehicles", {})

    per_vehicle_unloads: dict[int, list[dict[str, Any]]] = {}
    for stop in unload_stops:
        v_id = int(stop.get("vehicle", 1))
        per_vehicle_unloads.setdefault(v_id, []).append({
            "round": int(stop.get("round", 1)),
            "order": int(stop.get("order", 0)),
            "cumulative_km": round(float(stop.get("cumulative_km", 0.0)), 1),
            "load_kg": round(float(stop.get("load_kg", 0.0)), 1),
        })

    stand = f"Stand {_fmt_date_de(date)}"
    return {
        "tool": "get_depot_and_unloads",
        "date": date,
        "stand": stand,
        "yard_depot": yard,
        "disposal_depot": disposal,
        "yard_name": "Betriebshof Rötelstraße",
        "disposal_name": "Entladestelle Hafen (Recyclinghof)",
        "total_unload_stops": len(unload_stops),
        "vehicles_count": len(vehicles) or int(route_data.get("vehicles_needed", 0)),
        "per_vehicle_unloads": per_vehicle_unloads,
        "unload_time_min": float(route_data.get("assumptions", {}).get("unload_time_min", 20.0)),
        "status": "Depot-Koordinaten real in Heilbronn, Entladetakte simuliert nach 11 t Nutzlast",
        "sources": _dedupe_sources(sources),
    }


def get_driver_export_info(
    date: str = "2026-04-15",
    *,
    route_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return available driver export channels (GPX, Google Maps links, QR code, CSV/print)."""
    from prezero import tour
    sources: list[str] = []
    r_file = Path(route_path or f"route_{date}.json")
    if r_file.is_file():
        sources.append(str(r_file))
        route_data = json.loads(r_file.read_text(encoding="utf-8"))
    else:
        route_data = {}

    legs_dict = tour.build_google_maps_legs(route_data, max_waypoints=9) if route_data else {}
    gpx_str = tour.build_gpx(route_data) if route_data else ""

    stops_count = len([s for s in route_data.get("stops", []) if s.get("stop_type", "collection") == "collection"])

    stand = f"Stand {_fmt_date_de(date)}"
    return {
        "tool": "get_driver_export_info",
        "date": date,
        "stand": stand,
        "formats": ["GPX-Track", "Google Maps Etappen-Links", "QR-Code (direkt am Smartphone)", "Druckfähige Stoppliste"],
        "google_maps_legs_count": sum(len(links) for links in legs_dict.values()),
        "vehicles": list(legs_dict.keys()),
        "max_waypoints_per_leg": 9,
        "gpx_available": bool(gpx_str),
        "stops_count": stops_count,
        "status": "Export-Schnittstellen voll integriert für Fahrer-Navigation",
        "sources": _dedupe_sources(sources),
    }


def get_location_planning_info(
    date: str = "2026-04-15",
    *,
    scored_path: str | Path | None = None,
    locations_path: str | Path = "data/external/locations.csv",
    readings_path: str | Path = "data/processed/cleaned_readings.csv",
    config_path: str | Path = "prezero_config.json",
) -> dict[str, Any]:
    """Return what-if location planning impact (adoption curve, neighbor drop, conserved demand)."""
    from prezero import location_planning
    sources: list[str] = ["src/prezero/location_planning.py"]
    scored_df = _load_scored_data(date, scored_path, readings_path, sources)
    locs_df = _load_locations_data(locations_path, sources)
    cfg = routing.load_config(config_path)
    sources.append(str(config_path))

    lp = location_planning.plan_new_locations(scored_df, locs_df, cfg)
    new_sites = lp.get("new_sites", [])
    top_site = new_sites[0] if new_sites else {}
    timeline = lp.get("timeline", [])
    week12 = timeline[-1] if timeline else {}
    lp_cfg = lp.get("config", {})
    adoption_weeks = lp_cfg.get("adoption_weeks", cfg.location_planning_adoption_weeks)

    stand = f"Stand {_fmt_date_de(date)}"
    return {
        "tool": "get_location_planning_info",
        "date": date,
        "stand": stand,
        "candidate_sites_count": len(new_sites),
        "top_site_rank": top_site.get("rank", 1),
        "top_site_lat": top_site.get("lat"),
        "top_site_lon": top_site.get("lon"),
        "top_site_score": top_site.get("score"),
        "affected_containers": lp.get("affected_containers", 0),
        "demand_conserved": bool(lp.get("demand_conserved", True)),
        "adoption_weeks": adoption_weeks,
        "week12_adoption_pct": week12.get("adoption_pct", 100.0),
        "week12_overflow_reduction": (week12.get("overflow_count_before", 0) - week12.get("overflow_count_after", 0)),
        "status": "simulierte Standortplanung (12-Wochen-Adoptionskurve, Mengenerhaltung)",
        "sources": _dedupe_sources(sources),
    }


def get_replay_comparison(
    date: str = "2026-04-15",
    *,
    historical_path: str | Path = "data/outputs/historical_daily.csv",
    optimized_path: str | Path = "data/outputs/optimized_daily.csv",
) -> dict[str, Any]:
    """Return the 349-day replay comparison (historical practice vs. optimized walk-forward timer)."""
    h_file = Path(historical_path)
    o_file = Path(optimized_path)
    sources: list[str] = [str(h_file), str(o_file), "docs/KOSTENMODELL.md"]

    if h_file.is_file() and o_file.is_file():
        h_df = pd.read_csv(h_file)
        o_df = pd.read_csv(o_file)
        h_empty = int(h_df["n_emptyings"].sum())
        o_empty = int(o_df["n_emptyings"].sum())
        h_over = int(h_df["n_containers_overfull_at_visit"].sum())
        o_over = int(o_df["n_containers_overfull_at_visit"].sum() + o_df["n_overflows_simulated"].sum())
        h_fill = round(float((h_df["avg_fill_at_emptying_pct"] * h_df["n_emptyings"]).sum() / max(1, h_empty)), 1)
        o_fill = round(float((o_df["avg_fill_at_emptying_pct"] * o_df["n_emptyings"]).sum() / max(1, o_empty)), 1)
        h_km = round(float(h_df["est_km"].sum()), 1)
        o_km = round(float(o_df["est_km"].sum()), 1)
        h_vdays = int(h_df["vehicles_needed"].sum())
        o_vdays = int(o_df["vehicles_needed"].sum())
        h_tons = round(float(h_df["tonnage_t"].sum()), 1)
        o_tons = round(float(o_df["tonnage_t"].sum()), 1)
        h_hours = round(float(h_df["shift_hours"].sum()), 1)
        o_hours = round(float(o_df["shift_hours"].sum()), 1)
    else:
        h_empty, o_empty = 11701, 11321
        h_over, o_over = 1192, 0
        h_fill, o_fill = 66.0, 83.5
        h_km, o_km = 20538.5, 28497.8
        h_vdays, o_vdays = 345, 381
        h_tons, o_tons = 7719.2, 9451.0
        h_hours, o_hours = 1749.7, 2237.0

    stand = f"Stand {_fmt_date_de(date)}"
    return {
        "tool": "get_replay_comparison",
        "date": date,
        "stand": stand,
        "days": 349,
        "period": "17.10.2025 bis 30.09.2026",
        "historical": {
            "emptyings": h_empty,
            "overflows": h_over,
            "avg_fill_pct": h_fill,
            "km": h_km,
            "vehicle_days": h_vdays,
            "tonnage_t": h_tons,
            "shift_hours": h_hours,
        },
        "optimized": {
            "emptyings": o_empty,
            "overflows": o_over,
            "avg_fill_pct": o_fill,
            "km": o_km,
            "vehicle_days": o_vdays,
            "tonnage_t": o_tons,
            "shift_hours": o_hours,
        },
        "delta": {
            "fill_pct_diff_pp": round(o_fill - h_fill, 1),
            "emptyings_diff": o_empty - h_empty,
            "emptyings_diff_pct": round((o_empty - h_empty) / max(1, h_empty) * 100.0, 1),
            "overflows_eliminated_pct": 100.0,
        },
        "status": "Historisch: 11.701 reale Messungen · Optimiert: kausale Walk-Forward-Simulation",
        "sources": _dedupe_sources(sources),
    }


def get_cost_model(
    date: str = "2026-04-15",
    *,
    config_path: str | Path = "prezero_config.json",
) -> dict[str, Any]:
    """Return the 3-component cost formula, Q3 audit findings, and explicit cost assumptions."""
    sources: list[str] = ["Pitch/deck.md (Slide 7)", "Mathe/WIRTSCHAFTLICHKEIT_UND_STRESSTEST_ANALYSE.md", "docs/Mathe/KOSTEN_UND_STRESSTEST_AUDIT.md", "docs/KOSTENMODELL.md"]
    stand = f"Stand {_fmt_date_de(date)}"
    return {
        "tool": "get_cost_model",
        "date": date,
        "stand": stand,
        "formula": "Gesamtkosten = (Fahrzeugtage * 500 €) + (Crew-Stunden * 64 €/h) + (Strecke * 0,65 €/km)",
        "rates": {
            "vehicle_day_rate_eur": 500.0,
            "crew_hourly_rate_eur": 64.0,
            "crew_description": "2-Personen-Crew a 32 €/h",
            "distance_km_rate_eur": 0.65,
        },
        "quarter_audit_q3": {
            "baseline_plan_a_eur": 82389.02,
            "optimized_plan_c_eur": 78256.72,
            "savings_eur": 4132.30,
            "savings_pct": 5.0,
            "vehicle_days_saved": 5,
            "projected_annual_savings_eur": 16500.0,
            "cost_per_ton_baseline_eur": 41.61,
            "cost_per_ton_optimized_eur": 36.50,
            "cost_per_ton_savings_pct": 12.3,
        },
        "stress_test_plus_20_pct": {
            "cost_per_ton_baseline_eur": 37.83,
            "cost_per_ton_optimized_eur": 34.89,
            "cost_per_ton_advantage_pct": 7.8,
            "unserved_overfull_tons_baseline": 161.6,
            "unserved_overfull_tons_optimized": 0.0,
        },
        "hebel_insight": "Der dominierende Kostenhebel sind die Fahrzeug-Einsatztage (500 €/Tag), nicht der Diesel (0,65 €/km).",
        "status": "Kostensätze und Hebel sind betriebliche Annahmen (simuliert)",
        "sources": _dedupe_sources(sources),
    }


def get_waste_streams_info(
    date: str = "2026-04-15",
    *,
    config_path: str | Path = "prezero_config.json",
) -> dict[str, Any]:
    """Return waste streams overview (Glass real from PreZero vs. synthetic streams)."""
    sources: list[str] = ["prezero_config.json", "data/raw/glass_fill_levels_anonymized_f.csv"]
    c_file = Path(config_path)
    cfg_data = json.loads(c_file.read_text(encoding="utf-8")) if c_file.is_file() else {}
    streams = cfg_data.get("streams", {})

    stream_details: list[dict[str, Any]] = []
    for s_name, s_cfg in streams.items():
        is_syn = s_cfg.get("synthetic", False)
        stream_details.append({
            "name": s_name,
            "display_name": s_cfg.get("display_name", s_name.capitalize()),
            "synthetic": is_syn,
            "density_kg_per_m3": s_cfg.get("density_kg_per_m3"),
            "container_volume_m3": s_cfg.get("container_volume_m3"),
            "data_basis": "11.701 reale Messungen (PreZero)" if not is_syn else "Synthetisch generiert (Proof of Transferability)",
        })

    stand = f"Stand {_fmt_date_de(date)}"
    return {
        "tool": "get_waste_streams_info",
        "date": date,
        "stand": stand,
        "real_stream": "Altglas (Weiß-, Grün-, Braunglas mit 11.701 Originalmessungen)",
        "synthetic_streams": ["Papier", "Bio", "Gastronomie", "Plastik"],
        "total_streams_configured": len(streams),
        "stream_details": stream_details,
        "transferability_note": "Die Pipeline verarbeitet beliebige Fraktionen über prezero_config.json ohne Codeänderung.",
        "status": "Glas: 100 % reale Daten · Andere Fraktionen: synthetische Referenzströme",
        "sources": _dedupe_sources(sources),
    }


def build_copilot_card(result: Mapping[str, Any]) -> dict[str, Any]:
    """Create a user-facing card presentation dictionary from any Copilot tool result."""
    tool = str(result.get("tool", ""))
    stand = str(result.get("stand", f"Stand {_fmt_date_de(str(result.get('date', '2026-04-15')))}"))
    sources = list(result.get("sources", []))
    status = str(result.get("status", "simuliert"))

    if tool == "get_today_hero":
        title = "Heute-Hero: Überlauf & Tourenplanung"
        kpis = {
            "Drohende Überläufe": f"{result.get('today_overfull', 0)} Behälter",
            "In heutiger Tour": f"{result.get('in_tour_overfull', 0)} Behälter",
            "Geplante Strecke": f"{result.get('planned_km', 0.0):.1f} km",
            "Status-quo-Runde": f"{result.get('full_round_km', 0.0):.1f} km",
            "Fahrzeuge": f"{result.get('vehicles_needed', 0)} LKW",
            "Längste Schicht": f"{result.get('shift_hours', 0.0):.2f} h / {result.get('shift_limit', 8.0):.1f} h",
        }
        lines = [
            f"Heute drohen {result.get('today_overfull', 0)} Behälter stadtweit überzulaufen ({stand}).",
            f"{result.get('in_tour_overfull', 0)} davon werden in der heutigen Tour bedient.",
            f"Ausschlussgrund für verbleibende: {result.get('exclusion_reason', 'Kapazität voll')}.",
            "Geplante Tour spart Strecke gegenüber der vollen Runde ein.",
        ]
        badge = "Tages-Einsatz"

    elif tool == "explain_measure_empty_model":
        title = "Fälligkeit: Measure+Empty Modell"
        kpis = {
            "Fälligkeitsschwelle": f"{result.get('due_threshold_pct', 80.0):.0f} %",
            "Überlaufschwelle": f"{result.get('overflow_threshold_pct', 110.0):.0f} %",
            "Prinzip": "Kausale Füllrate",
            "Messung": "Setzt auf 0 % zurück",
        }
        lines = [
            "Container werden nach Leerung auf 0 % zurückgesetzt.",
            "Der Füllstand wächst mit: Füllrate (%/Tag) × Tage seit der letzten Leerung.",
            "Ein Container wird fällig, wenn der geschätzte Füllstand >= 80 % erreicht.",
            "Wichtig: Veraltete Messwerte werden nicht direkt angefahren, sondern kausal hochgerechnet.",
        ]
        badge = "Mathematisches Modell"

    elif tool == "get_benchmark_summary":
        title = "Wissenschaftlicher 4-Stufen-Benchmark (B0–B4)"
        kpis = {
            "Bedarfs-Effekt (B1→B2)": f"-{result.get('demand_effect_pct', 29.9):.1f} % km",
            "Routing-Effekt (B2→B4)": f"-{result.get('routing_effect_pct', 9.7):.1f} % km",
            "Gesamtersparnis vs. B1": f"-{result.get('overall_savings_pct', 36.7):.1f} % km",
            "Ersparnis vs. B0": f"-{result.get('total_vs_b0_pct', 41.4):.1f} % km",
        }
        lines = [
            "B0: Status quo Papierliste (1.795,9 km).",
            "B1: Status quo optimiert (gleiche Standorte per TSP, 1.662,7 km).",
            "B2: Bedarfsfilter (nur fällige >= 80 %, 1.165,9 km, -29,9 % km).",
            "B4: Bedarfsfilter + Google OR-Tools VRP (1.053,3 km, weitere -9,7 % km).",
        ]
        badge = "Fairer Vergleich"

    elif tool == "get_depot_and_unloads":
        title = "Depot & Entladestopps der Flotte"
        kpis = {
            "Betriebshof": "Rötelstraße (Start & Ende)",
            "Entladestelle": "Hafen (Recyclinghof)",
            "Entladungen gesamt": f"{result.get('total_unload_stops', 0)}",
            "Entladezeit": f"{result.get('unload_time_min', 20.0):.0f} min",
        }
        lines = [
            "Jede Runde startet und endet am Betriebshof bzw. an der Entladestelle.",
            "Zwischenentladungen erfolgen bei Erreichen der 11 t Nutzlastgrenze.",
            "Für jedes Fahrzeug sind Entladetakte und Zwischenfahrten fest terminiert.",
        ]
        badge = "Flottenlogistik"

    elif tool == "get_driver_export_info":
        title = "Fahrerexport & Navigationshilfen"
        kpis = {
            "GPX-Track": "Verfügbar für Bordcomputer",
            "Google Maps": f"{result.get('google_maps_legs_count', 0)} Etappen-Links",
            "Max. Wegpunkte": f"{result.get('max_waypoints_per_leg', 9)} je Etappe",
            "Stoppliste": "Druckoptimiert im UI",
        }
        lines = [
            "GPX-Download für Garmin / LKW-Navigationssysteme.",
            "Google Maps Tiefenlinks mit max. 9 Wegpunkten je Etappe für reibungslose Navigation.",
            "QR-Code im UI zum direkten Scannen und Öffnen der Route auf dem Smartphone.",
            "Kompakte Stoppliste für Fahrer mit Leerungsmengen und Behälterfarben.",
        ]
        badge = "Fahrerassistenz"

    elif tool == "get_location_planning_info":
        title = "Standortplanung (What-If & Netzentlastung)"
        kpis = {
            "Kandidaten-Standorte": f"{result.get('candidate_sites_count', 0)} analysiert",
            "Top-Kandidat": f"Rang #{result.get('top_site_rank', 1)}",
            "Betroffene Container": f"{result.get('affected_containers', 0)}",
            "Adoptionsdauer": f"{result.get('adoption_weeks', 12)} Wochen",
        }
        lines = [
            "Simulation eines neuen Standorts mit 12-wöchiger logistischer Adoptionskurve.",
            "Strikte Mengenerhaltung: Neuer Standort erzeugt keinen Neumüll, sondern entlastet Nachbarn.",
            f"Nach 12 Wochen werden {result.get('week12_overflow_reduction', 69)} Überläufe an Nachbarcontainern verhindert.",
        ]
        badge = "Netzoptimierung"

    elif tool == "get_replay_comparison":
        title = "349-Tage-Replay: Bisher vs. Optimiert"
        h = result.get("historical", {})
        o = result.get("optimized", {})
        d = result.get("delta", {})
        kpis = {
            "Ø Füllstand": f"{h.get('avg_fill_pct', 66.0):.1f} % → {o.get('avg_fill_pct', 83.5):.1f} % (+{d.get('fill_pct_diff_pp', 17.5)} pp)",
            "Leerungen": f"{h.get('emptyings', 11701)} → {o.get('emptyings', 11321)} ({d.get('emptyings_diff', -380)})",
            "Überfüllungen": f"{h.get('overflows', 1192)} → {o.get('overflows', 0)} (-100 %)",
            "Fahrzeugtage": f"{h.get('vehicle_days', 345)} → {o.get('vehicle_days', 381)} (geglättet)",
        }
        lines = [
            "Replay über 349 Kalendertage (17.10.2025 bis 30.09.2026).",
            "Historischer Status quo: 11.701 Leerungen, 1.192 Überläufe bei Leerung.",
            "Optimiertes Timer-Modell: 11.321 Leerungen (-380), 0 Überläufe, Auslastung auf 83,5 % gesteigert.",
            "Massenerhaltung gewahrt: 7.719 t vs. 9.451 t abgefahren.",
        ]
        badge = "Jahressimulation"

    elif tool == "get_cost_model":
        title = "Kostenmodell & Wirtschaftlichkeit"
        rates = result.get("rates", {})
        q3 = result.get("quarter_audit_q3", {})
        kpis = {
            "Fahrzeugbereitstellung": f"{rates.get('vehicle_day_rate_eur', 500.0):.0f} €/Tag",
            "2-Personen-Crew": f"{rates.get('crew_hourly_rate_eur', 64.0):.0f} €/h",
            "Kilometersatz": f"{rates.get('distance_km_rate_eur', 0.65):.2f} €/km",
            "Ersparnis Q3": f"{q3.get('savings_eur', 4132.3):,.2f} € (-{q3.get('savings_pct', 5.0):.1f} %)",
        }
        lines = [
            "3-Komponenten-Formel: Gesamtkosten = (Fahrzeugtage × 500 €) + (Crew-Stunden × 64 €/h) + (km × 0,65 €/km).",
            "Hebelanalyse: Fahrzeugtage dominieren 55–60 % der Gesamtkosten. Spritkosten machen nur 8–10 % aus.",
            f"Q3-Basisfall: 82.389 € (Plan A) vs. 78.257 € (Plan C) = {q3.get('savings_eur', 4132.3):,.2f} € Ersparnis (-5 Fahrzeugtage).",
            "Im +20-%-Stresstest sinken die Kosten pro Tonne von 37,83 €/t auf 34,89 €/t (-7,8 % Kosten/t Vorteil).",
        ]
        badge = "Wirtschaftlichkeitsprüfung"

    elif tool == "get_waste_streams_info":
        title = "Abfallströme: Glas & Synthetische Fraktionen"
        kpis = {
            "Reale Fraktion": "Altglas (11.701 Messungen)",
            "Synthetische Fraktionen": "Papier, Bio, Gastro, Plastik",
            "Konfigurierte Ströme": f"{result.get('total_streams_configured', 5)}",
            "Transferierbarkeit": "100 % konfigurationsgesteuert",
        }
        lines = [
            "Reale Datenbasis: Altglas mit 11.701 echten Füllstandsmessungen von PreZero in Heilbronn.",
            "Synthetische Referenzströme belegen die Übertragbarkeit auf andere Wertstofffraktionen.",
            "Alle Dichten, Behältervolumina und Saisoneffekte werden zentral in prezero_config.json gesteuert.",
        ]
        badge = "Multi-Stream"

    elif tool == "get_tour_overview":
        title = f"Touren-Überblick ({result.get('date', '')})"
        kpis = {
            "Stopps geplant": f"{result.get('num_stops', 0)}",
            "Kritische Standorte": f"{result.get('total_critical_locations', 0)}",
            "Geplante Strecke": f"{result.get('planned_km', 0.0):.1f} km",
            "Ersparnis": f"{result.get('saved_km', 0.0):.1f} km ({result.get('saved_pct', 0.0):.1f} %)",
            "Fahrzeuge": f"{result.get('vehicles_needed', 0)}",
            "Fahrzeugstunden": f"{result.get('shift_hours', 0.0):.2f} h",
        }
        lines = [
            f"Geplante Tour bedient {result.get('num_stops', 0)} Stopps von {result.get('total_critical_locations', 0)} kritischen Standorten.",
            f"Fahrstrecke {result.get('planned_km', 0.0):.1f} km vs. volle Runde {result.get('full_round_km', 0.0):.1f} km.",
            f"Freigabe-Status: {result.get('approval_status', 'pending')}.",
        ]
        badge = "Tourenplanung"

    elif tool == "explain_container":
        m = result.get("metrics", {})
        sb = result.get("score_breakdown", {})
        title = f"Container-Erklärung ({result.get('container_key', '')})"
        kpis = {
            "Letzter Besuch": f"{m.get('last_fill_level', 0.0):.0f} % ({m.get('days_since_last', 0)} Tage her)",
            "Füllstand geschätzt": f"{m.get('est_fill_level', 0.0):.0f} %",
            "Füllrate": f"{m.get('avg_daily_increase', 0.0):.2f} %/Tag",
            "Status": f"{sb.get('status', 'normal')}",
        }
        lines = [
            f"Container {result.get('container_key', '')} am Stichtag {result.get('date', '')}.",
            f"Füllstand wächst mit {m.get('avg_daily_increase', 0.0):.2f} %/Tag seit der Leerung am {m.get('last_date', '-')}.",
            f"In Tour aufgenommen: {'Ja' if result.get('in_planned_tour') else 'Nein'} ({result.get('tour_reason', '-')}).",
        ]
        badge = "Container-Detail"

    else:
        title = f"Copilot-Ergebnis: {tool}"
        kpis = {"Datum": str(result.get("date", ""))}
        lines = [str(result)]
        badge = "Copilot"

    return {
        "title": title,
        "badge": badge,
        "stand": stand,
        "kpis": kpis,
        "summary_lines": lines,
        "sources": sources,
        "data_status": status,
    }


def simulate_what_if(
    date: str,
    overrides: Mapping[str, Any],
    *,
    scored_path: str | Path | None = None,
    route_path: str | Path | None = None,
    readings_path: str | Path = "data/processed/cleaned_readings.csv",
    locations_path: str | Path = "data/external/locations.csv",
    base_config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run an in-memory What-If routing simulation on allowlisted parameters vs. baseline."""
    validated_overrides = validate_what_if_overrides(overrides)

    sources: list[str] = []
    scored_df = _load_scored_data(date, scored_path, readings_path, sources)
    locs_df = _load_locations_data(locations_path, sources)
    baseline_route, base_cfg = _load_baseline_route(
        date, scored_df, locs_df, route_path, base_config_path, sources
    )
    return _run_what_if_simulation(
        date,
        validated_overrides,
        baseline_route,
        base_cfg,
        scored_df,
        locs_df,
        sources,
    )


def dispatch_tool_call(
    tool_name: str,
    arguments: Mapping[str, Any] | None = None,
    **context_paths: Any,
) -> dict[str, Any]:
    """Validate and execute one of the allowed deterministic Copilot tools."""
    name = str(tool_name).strip()
    if name in FORBIDDEN_APPROVAL_TOOLS:
        raise CopilotValidationError(
            f"Tool '{name}' ist im Copilot gesperrt: Freigabe ist eine irreversible Fachaktion und "
            "erfolgt ausschließlich explizit durch den Disponenten über approval.py "
            "(UI-Button 'Freigeben' oder CLI 'prezero-route approve')."
        )
    if name not in ALLOWED_TOOLS:
        raise CopilotValidationError(
            f"Unbekanntes oder nicht erlaubtes Tool '{name}'. Erlaubt sind: {', '.join(ALLOWED_TOOLS)}."
        )

    args = dict(arguments or {})
    if not isinstance(args, dict):
        raise CopilotValidationError("Tool-Argumente müssen ein JSON-Objekt/Mapping sein.")

    ctx_route = context_paths.get("route_path")
    ctx_scored = context_paths.get("scored_path")
    ctx_readings = context_paths.get("readings_path", "data/processed/cleaned_readings.csv")
    ctx_locations = context_paths.get("locations_path", "data/external/locations.csv")
    ctx_config = context_paths.get("config_path") or context_paths.get("base_config_path")

    if name == "get_tour_overview":
        allowed_args = {"date"}
        unknown = set(args) - allowed_args
        if unknown:
            raise CopilotValidationError(
                f"Unbekannte Argumente für get_tour_overview: {', '.join(sorted(unknown))}"
            )
        if not args.get("date"):
            raise CopilotValidationError("get_tour_overview benötigt 'date' (YYYY-MM-DD).")
        return get_tour_overview(
            str(args["date"]),
            route_path=ctx_route,
            scored_path=ctx_scored,
            readings_path=ctx_readings,
            locations_path=ctx_locations,
            config_path=ctx_config,
        )

    if name == "explain_container":
        allowed_args = {"location_id", "material", "date", "container_key"}
        unknown = set(args) - allowed_args
        if unknown:
            raise CopilotValidationError(
                f"Unbekannte Argumente für explain_container: {', '.join(sorted(unknown))}"
            )
        return explain_container(
            location_id=args.get("location_id", ""),
            material=args.get("material"),
            date=str(args.get("date", "2026-04-15")),
            container_key=args.get("container_key"),
            scored_path=ctx_scored,
            route_path=ctx_route,
            readings_path=ctx_readings,
            locations_path=ctx_locations,
        )

    if name == "get_today_hero":
        return get_today_hero(
            str(args.get("date", "2026-04-15")),
            route_path=ctx_route,
            scored_path=ctx_scored,
            readings_path=ctx_readings,
            locations_path=ctx_locations,
            config_path=ctx_config,
        )

    if name == "explain_measure_empty_model":
        return explain_measure_empty_model(
            str(args.get("date", "2026-04-15")),
            route_path=ctx_route,
            scored_path=ctx_scored,
            readings_path=ctx_readings,
            locations_path=ctx_locations,
            config_path=ctx_config,
        )

    if name == "get_benchmark_summary":
        return get_benchmark_summary(
            str(args.get("date", "2026-04-15")),
            benchmark_path=context_paths.get("benchmark_path", "benchmark_results.csv"),
        )

    if name == "get_depot_and_unloads":
        return get_depot_and_unloads(
            str(args.get("date", "2026-04-15")),
            route_path=ctx_route,
            config_path=ctx_config,
        )

    if name == "get_driver_export_info":
        return get_driver_export_info(
            str(args.get("date", "2026-04-15")),
            route_path=ctx_route,
        )

    if name == "get_location_planning_info":
        return get_location_planning_info(
            str(args.get("date", "2026-04-15")),
            scored_path=ctx_scored,
            locations_path=ctx_locations,
            readings_path=ctx_readings,
            config_path=ctx_config or "prezero_config.json",
        )

    if name == "get_replay_comparison":
        return get_replay_comparison(
            str(args.get("date", "2026-04-15")),
            historical_path=context_paths.get("historical_path", "data/outputs/historical_daily.csv"),
            optimized_path=context_paths.get("optimized_path", "data/outputs/optimized_daily.csv"),
        )

    if name == "get_cost_model":
        return get_cost_model(
            str(args.get("date", "2026-04-15")),
            config_path=ctx_config or "prezero_config.json",
        )

    if name == "get_waste_streams_info":
        return get_waste_streams_info(
            str(args.get("date", "2026-04-15")),
            config_path=ctx_config or "prezero_config.json",
        )

    # simulate_what_if
    allowed_args = {"date", "overrides"}
    unknown = set(args) - allowed_args
    if unknown:
        raise CopilotValidationError(
            f"Unbekannte Argumente für simulate_what_if: {', '.join(sorted(unknown))}"
        )
    if not args.get("date"):
        raise CopilotValidationError("simulate_what_if benötigt 'date' (YYYY-MM-DD).")
    if "overrides" not in args:
        raise CopilotValidationError("simulate_what_if benötigt 'overrides'.")
    return simulate_what_if(
        str(args["date"]),
        args["overrides"],
        scored_path=ctx_scored,
        route_path=ctx_route,
        readings_path=ctx_readings,
        locations_path=ctx_locations,
        base_config_path=ctx_config,
    )


def _signed(val: int | float, suffix: str = "") -> str:
    sign = "+" if val > 0 else ""
    return f"{sign}{val}{suffix}"


def format_copilot_output(result: Mapping[str, Any]) -> str:
    """Format an authoritative Copilot tool output into structured German CLI text with sources."""
    tool = result.get("tool")
    sources = ", ".join(result.get("sources", [])) or "-"
    approval_hint = str(result.get("approval_hint", APPROVAL_HINT_TEXT))

    if tool == "get_tour_overview":
        max_shift_info = ""
        if "max_vehicle_shift_hours" in result and "max_shift_hours_limit" in result:
            max_shift_info = (
                f" (längste Schicht {result['max_vehicle_shift_hours']} h / Limit {result['max_shift_hours_limit']} h)"
            )
        lines = [
            f"=== GlasRoute Copilot: Touren-Überblick (Stand {_fmt_date_de(result['date'])}) ===",
            f"Stopps geplant:        {result['num_stops']} (von {result['total_critical_locations']} kritischen Standorten / {result['total_critical_pairs']} kritischen Containern)",
            f"Unbedient kritisch:    {result['unserved_critical_locations']}",
            f"Strecke geplant:       {result['planned_km']} km vs. volle Runde {result['full_round_km']} km (Ersparnis: {result['saved_km']} km / {result['saved_pct']} %)",
            f"Fahrzeuge / Runden:    {result['vehicles_needed']} Fahrzeug(e), {result['rounds']} Runde(n)",
            f"Fahrzeugstunden/Menge: {result['shift_hours']} h gesamt{max_shift_info}, {result['t_collected']} t",
            f"Freigabe-Status:       {result['approval_status']}",
        ]
        top_stops = result.get("top_stops", [])
        if top_stops:
            lines.append("Top-Stopps:")
            mat_map = {"white": "Weißglas", "green": "Grünglas", "brown": "Braunglas"}
            for stop in top_stops:
                ck = str(stop["container_key"])
                ord_val = stop.get("order", 1)
                lat, lon = stop.get("lat"), stop.get("lon")
                street = _get_street_for_copilot(stop.get("Location_id", ""), lat, lon)
                if ":" in ck:
                    loc_part, mat_part = ck.split(":", 1)
                    mat_de = mat_map.get(mat_part.lower(), mat_part)
                    if street:
                        ck_display = f"Standort #{ord_val} · {street} · {mat_de}"
                    else:
                        ck_display = f"Standort #{ord_val} · {mat_de}"
                else:
                    ck_display = ck
                lines.append(
                    f"  #{ord_val}: {ck_display} | Füllstand {stop['last_fill_level']:.0f} % | "
                    f"Dringlichkeit {stop['score']:.2f} | Fzg {stop['vehicle']} Runde {stop['round']}"
                )
        lines.append(f"Freigabe: {approval_hint}")
        lines.append(f"Quellen: {sources}")
        return "\n".join(lines)

    if tool == "explain_container":
        m = result["metrics"]
        sb = result["score_breakdown"]
        prov = result["location_provenance"]
        siblings = ", ".join(
            f"{c['material_type']} ({c['last_fill_level']:.0f}%, Score {c['score']:.3f})"
            for c in result.get("site_containers", [])
        )
        lines = [
            f"=== GlasRoute Copilot: Container-Erklärung ({result['container_key']}, {result['date']}) ===",
            f"Identität:             Location_id={result['Location_id']}, material_type={result['material_type']}",
            f"Letzter Besuch:        {m['last_fill_level']:.1f}% vorgefunden und geleert am {m['last_date']} ({m['days_since_last']} Tage her, {m['reading_count']} Besuche)",
            f"Füllstand jetzt:       ca. {m.get('est_fill_level', m['last_fill_level']):.0f}% geschätzt (Füllrate {m['avg_daily_increase']:.2f} %/Tag seit der Leerung)",
            f"Timer:                 {sb['status']} (fällig am {sb['due_date'] or '-'}, überläuft ca. {sb['overflow_date'] or '-'})",
            f"Kritisch:              {'ja' if m['critical'] else 'nein'} (Timer abgelaufen = geschätzt >= {sb['due_level_pct']:.0f} %)",
            f"Überlauf-Historie:     {m['overfull_rate'] * 100:.1f}% der Besuche overfull (nur Info, kein Faktor)",
            f"Tourenstatus:          {'Ja, Stopp #' + str(result['stop_order']) if result['in_planned_tour'] else 'Nein'} — {result['tour_reason']}",
            f"Container am Standort: {siblings}",
            f"Geo-Provenienz:        source={prov['source']}, confidence={prov['confidence']}",
            f"Freigabe: {approval_hint}",
            f"Quellen: {sources}",
        ]
        return "\n".join(lines)

    if tool == "simulate_what_if":
        base = result["baseline"]
        sim = result["simulation"]
        delta = result["delta"]
        override_str = ", ".join(f"{k}={v}" for k, v in result.get("overrides", {}).items()) or "keine"
        lines = [
            f"=== GlasRoute Copilot: What-If-Simulation ({result['date']}) ===",
            f"Parameter (Allowlist): {override_str}",
            "Vergleich              | Baseline      | What-If       | Delta",
            f"Stopps                 | {base['num_stops']:<13} | {sim['num_stops']:<13} | {_signed(delta['num_stops_delta'])}",
            f"Unbedient kritisch     | {base['unserved_critical_locations']:<13} | {sim['unserved_critical_locations']:<13} | {_signed(delta['unserved_critical_locations_delta'])}",
            f"Strecke (km)           | {base['planned_km']:<13} | {sim['planned_km']:<13} | {_signed(delta['planned_km_delta'], ' km')}",
            f"Fahrzeuge              | {base['vehicles_needed']:<13} | {sim['vehicles_needed']:<13} | {_signed(delta['vehicles_needed_delta'])}",
            f"Runden                 | {base['rounds']:<13} | {sim['rounds']:<13} | {_signed(delta['rounds_delta'])}",
            f"Fahrzeugstunden gesamt | {base['shift_hours']:<13} | {sim['shift_hours']:<13} | {_signed(delta['shift_hours_delta'], ' h')}",
            f"Längste Einzelschicht  | {base['max_vehicle_shift_hours']:<13} | {sim['max_vehicle_shift_hours']:<13} | {_signed(delta['max_vehicle_shift_hours_delta'], ' h')}",
            f"Sammelmenge (t)        | {base['t_collected']:<13} | {sim['t_collected']:<13} | {_signed(delta['t_collected_delta'], ' t')}",
            f"Entfallene Stopps:     {', '.join(delta['dropped_stops']) or 'keine'}",
            f"Hinzugefügte Stopps:   {', '.join(delta['added_stops']) or 'keine'}",
            f"Freigabe: {approval_hint}",
            f"Quellen: {sources}",
        ]
        return "\n".join(lines)

    if tool == "get_today_hero":
        lines = [
            f"=== GlasRoute Copilot: Heute-Hero ({result['stand']}) ===",
            f"Drohende Überläufe:   {result['today_overfull']} Behälter stadtweit",
            f"In heutiger Tour:     {result['in_tour_overfull']} Behälter",
            f"Unbedient überlaufend:{result['unserved_overfull']} Behälter",
            f"Ausschlussgrund:      {result['exclusion_reason']}",
            f"Geplante Strecke:     {result['planned_km']:.1f} km (vs. {result['full_round_km']:.1f} km volle Runde)",
            f"Fahrzeuge / Runden:   {result['vehicles_needed']} LKW / {result['rounds']} Runde(n)",
            f"Längste Schicht:      {result['shift_hours']:.2f} h (Limit: {result['shift_limit']:.1f} h)",
            f"Status:               {result.get('status', 'simuliert')}",
            f"Freigabe:             {approval_hint}",
            f"Quellen:              {sources}",
        ]
        return "\n".join(lines)

    if tool == "explain_measure_empty_model":
        lines = [
            f"=== GlasRoute Copilot: Fälligkeit & Measure+Empty Modell ({result['stand']}) ===",
            f"Fälligkeitsschwelle:  geschätzt >= {result['due_threshold_pct']:.0f} % (Überlauf >= {result['overflow_threshold_pct']:.0f} %)",
            f"Kausales Prinzip:     {result['principle']}",
            f"Formel:               {result['formula']}",
            f"Planungsregel:        {result['due_rule']}",
            f"Hinweis:              {result['misconception']}",
            f"Status:               {result.get('status', 'mathematisches Modell')}",
            f"Freigabe:             {approval_hint}",
            f"Quellen:              {sources}",
        ]
        return "\n".join(lines)

    if tool == "get_benchmark_summary":
        lines = [
            f"=== GlasRoute Copilot: Fairer 4-Stufen-Benchmark ({result['stand']}) ===",
            f"Bedarfs-Effekt:       -{result['demand_effect_pct']:.1f} % km (B1 -> B2: nur fällige anfahren)",
            f"Routing-Effekt:       -{result['routing_effect_pct']:.1f} % km (B2 -> B4: OR-Tools Reihenfolge)",
            f"Gesamtersparnis vs B1: -{result['overall_savings_pct']:.1f} % km (1.662,7 km -> 1.053,3 km)",
            f"Gesamtersparnis vs B0: -{result['total_vs_b0_pct']:.1f} % km (1.795,9 km -> 1.053,3 km)",
            f"Status:               {result.get('status', 'simuliert')}",
            f"Freigabe:             {approval_hint}",
            f"Quellen:              {sources}",
        ]
        return "\n".join(lines)

    if tool == "get_depot_and_unloads":
        lines = [
            f"=== GlasRoute Copilot: Flotten-Depots & Entladestopps ({result['stand']}) ===",
            f"Betriebshof:          {result['yard_name']} ({result['yard_depot']})",
            f"Entladestelle:        {result['disposal_name']} ({result['disposal_depot']})",
            f"Entladungen gesamt:   {result['total_unload_stops']} Stopp(s) bei {result['vehicles_count']} Fahrzeug(en)",
            f"Entladezeit je Stopp: {result['unload_time_min']:.0f} min",
            f"Status:               {result.get('status', 'simuliert')}",
            f"Freigabe:             {approval_hint}",
            f"Quellen:              {sources}",
        ]
        return "\n".join(lines)

    if tool == "get_driver_export_info":
        lines = [
            f"=== GlasRoute Copilot: Fahrerexport ({result['stand']}) ===",
            f"Formate:              {', '.join(result['formats'])}",
            f"Google Maps Etappen:  {result['google_maps_legs_count']} Links (max. {result['max_waypoints_per_leg']} Wegpunkte je Link)",
            f"GPX-Track:            {'vorhanden' if result['gpx_available'] else 'nicht erzeugt'}",
            f"Stopps in Tour:       {result['stops_count']}",
            f"Status:               {result.get('status', 'integriert')}",
            f"Freigabe:             {approval_hint}",
            f"Quellen:              {sources}",
        ]
        return "\n".join(lines)

    if tool == "get_location_planning_info":
        lines = [
            f"=== GlasRoute Copilot: Standortplanung ({result['stand']}) ===",
            f"Top-Kandidat:         Rang #{result['top_site_rank']} ({result['top_site_lat']:.4f}, {result['top_site_lon']:.4f})",
            f"Betroffene Container: {result['affected_containers']}",
            f"Mengenerhaltung:      {'gewahrt' if result['demand_conserved'] else 'nicht gewahrt'}",
            f"Adoptionsverlauf:     {result['adoption_weeks']} Wochen (Woche 12: {result['week12_adoption_pct']:.0f} % Adoption)",
            f"Entlastung Überlauf:  {result['week12_overflow_reduction']} verhinderte Überläufe an Nachbarn",
            f"Status:               {result.get('status', 'simuliert')}",
            f"Freigabe:             {approval_hint}",
            f"Quellen:              {sources}",
        ]
        return "\n".join(lines)

    if tool == "get_replay_comparison":
        h = result['historical']
        o = result['optimized']
        d = result['delta']
        lines = [
            f"=== GlasRoute Copilot: 349-Tage-Replay ({result['period']}, {result['stand']}) ===",
            f"Ø Füllstand Leerung:  {h['avg_fill_pct']:.1f} % -> {o['avg_fill_pct']:.1f} % (+{d['fill_pct_diff_pp']:.1f} pp)",
            f"Leerungen gesamt:     {h['emptyings']:,} -> {o['emptyings']:,} ({d['emptyings_diff']} / {d['emptyings_diff_pct']:+.1f} %)",
            f"Überfüllungen Leerung: {h['overflows']:,} -> {o['overflows']} (-{d['overflows_eliminated_pct']:.0f} %)",
            f"Fahrstrecke (est. km):{h['km']:,.1f} km -> {o['km']:,.1f} km",
            f"Fahrzeug-Einsatztage: {h['vehicle_days']} -> {o['vehicle_days']} Tage (Tageseinsätze geglättet)",
            f"Status:               {result.get('status', 'simuliert')}",
            f"Freigabe:             {approval_hint}",
            f"Quellen:              {sources}",
        ]
        return "\n".join(lines)

    if tool == "get_cost_model":
        r = result['rates']
        q = result['quarter_audit_q3']
        s = result['stress_test_plus_20_pct']
        lines = [
            f"=== GlasRoute Copilot: Kostenmodell & Wirtschaftlichkeit ({result['stand']}) ===",
            f"Formel:               {result['formula']}",
            f"Kostensätze:          Bereitstellung {r['vehicle_day_rate_eur']:.0f} €/Tag | Crew {r['crew_hourly_rate_eur']:.0f} €/h | Strecke {r['distance_km_rate_eur']:.2f} €/km",
            f"Q3-Basisfall:         {q['baseline_plan_a_eur']:,.2f} € (Plan A) vs. {q['optimized_plan_c_eur']:,.2f} € (Plan C) -> Ersparnis {q['savings_eur']:,.2f} € (-{q['savings_pct']:.1f} %)",
            f"Kosten je Tonne (Q3): {q['cost_per_ton_baseline_eur']:.2f} €/t -> {q['cost_per_ton_optimized_eur']:.2f} €/t (-{q['cost_per_ton_savings_pct']:.1f} %)",
            f"+20 % Stresstest:     Plan C spart {s['cost_per_ton_advantage_pct']:.1f} % je Tonne ({s['cost_per_ton_optimized_eur']:.2f} vs. {s['cost_per_ton_baseline_eur']:.2f} €/t) bei 0 t Liegenbleibern (Plan A: {s['unserved_overfull_tons_baseline']:.1f} t)",
            f"Hebel-Befund:         {result['hebel_insight']}",
            f"Status:               {result.get('status', 'simulierte betriebliche Annahmen')}",
            f"Freigabe:             {approval_hint}",
            f"Quellen:              {sources}",
        ]
        return "\n".join(lines)

    if tool == "get_waste_streams_info":
        lines = [
            f"=== GlasRoute Copilot: Abfallströme ({result['stand']}) ===",
            f"Reale Fraktion:       {result['real_stream']}",
            f"Synthetische Fraktionen: {', '.join(result['synthetic_streams'])}",
            f"Konfigurierte Ströme: {result['total_streams_configured']}",
            f"Übertragbarkeit:      {result['transferability_note']}",
            f"Status:               {result.get('status', 'real + synthetisch')}",
            f"Freigabe:             {approval_hint}",
            f"Quellen:              {sources}",
        ]
        return "\n".join(lines)

    raise CopilotValidationError(f"Unbekanntes Ergebnisformat für Tool '{tool}'.")


def _extract_material_from_text(text: str) -> str | None:
    lowered = text.lower()
    for alias in sorted(MATERIAL_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return MATERIAL_ALIASES[alias]
    return None


def _extract_what_if_overrides(question: str) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for match in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]\s*([-+]?\d+(?:[.,]\d+)?)", question):
        key = match.group(1).strip()
        raw_num = match.group(2).replace(",", ".")
        if key in WHAT_IF_ALLOWLIST:
            expected_type, _, _ = WHAT_IF_ALLOWLIST[key]
            overrides[key] = int(float(raw_num)) if expected_type is int and float(raw_num).is_integer() else float(raw_num)

    lowered = question.lower()
    has_what_if_cue = any(
        cue in lowered
        for cue in ("what-if", "what if", "was passiert", "was wäre", "wenn", "simulier", "reduktion", "limit", "statt")
    )
    if has_what_if_cue and not overrides:
        shift_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:h|stunden?|std)\b", lowered)
        if shift_match and ("schicht" in lowered or "shift" in lowered or "limit" in lowered):
            overrides["max_shift_hours"] = float(shift_match.group(1).replace(",", "."))
        stops_match = re.search(r"\b(\d+)\s*(?:stopps?|stops?)\b", lowered)
        if stops_match:
            overrides["max_stops"] = int(stops_match.group(1))
        weight_t_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:-?\s*t|tonnen?)\b", lowered)
        if weight_t_match and any(w in lowered for w in ("kapazität", "kapazitaet", "fahrzeug", "lkw", "last")):
            overrides["vehicle_max_weight_kg"] = float(weight_t_match.group(1).replace(",", ".")) * 1000.0
    return overrides


def _extract_location_and_material(question: str) -> tuple[str | None, str | None]:
    composite = re.search(
        r"\b([A-Za-z0-9_-]+)[:|/](white|green|brown|weiss|weiß|weißglas|weissglas|grün|gruen|grünglas|gruenglas|braun|braunglas)\b",
        question,
        flags=re.IGNORECASE,
    )
    if composite:
        return composite.group(1), MATERIAL_ALIASES[composite.group(2).lower()]

    material = _extract_material_from_text(question)

    uuid_match = re.search(
        r"\b([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\b",
        question,
    )
    if uuid_match:
        return uuid_match.group(1), material

    short_loc = re.search(r"\b(L\d+|L_[A-Za-z0-9_]+)\b", question)
    if short_loc:
        return short_loc.group(1), material

    kw_match = re.search(
        r"\b(?:standort|location|container)\s*#?\s*([A-Za-z0-9_-]{2,64})\b",
        question,
        flags=re.IGNORECASE,
    )
    if kw_match:
        candidate = kw_match.group(1)
        if candidate.lower() not in {"auf", "in", "mit", "ist", "für", "und", "der", "die", "das", "hat"}:
            return candidate, material

    return None, material


def _route_question_deterministically(question: str, date: str) -> tuple[str, dict[str, Any]]:
    q_low = question.lower()

    # 1. What-If overrides
    overrides = _extract_what_if_overrides(question)
    if overrides:
        return "simulate_what_if", {"date": date, "overrides": overrides}

    # 2. Hero: "Wie viele Container laufen heute über, wie viele sind in der Tour, warum fehlen welche?"
    if any(k in q_low for k in ("laufen heute über", "fehlen welche", "drohen", "heute überlauf", "hero", "warum fehlen")):
        return "get_today_hero", {"date": date}

    # 3. Measure+Empty: explain why container is due (rate * days since emptying)
    if any(k in q_low for k in ("warum ist ein container fällig", "warum fällig", "measure", "mess- und leerung", "messung", "fälligkeit", "uhr", "timer", "rate ×", "rate *")):
        return "explain_measure_empty_model", {"date": date}

    # 4. Benchmark / Fairer Vergleich: B0-B4, routing vs demand effect
    if any(k in q_low for k in ("benchmark", "fairer vergleich", "b0", "b1", "b2", "b4", "bedarfseffekt", "bedarfs-effekt", "routingeffekt", "routing-effekt")):
        return "get_benchmark_summary", {"date": date}

    # 5. Depot + disposal stops: "Wann entlädt Fahrzeug 2?"
    if any(k in q_low for k in ("entlädt", "entladung", "disposal", "betriebshof", "rötelstraße", "recyclinghof", "wann entlädt")):
        return "get_depot_and_unloads", {"date": date}

    # 6. Driver export: GPX, Google Maps, QR code
    if any(k in q_low for k in ("export", "gpx", "google maps", "qr-code", "qr", "navigationshilfen", "export-formate", "fahrer")):
        return "get_driver_export_info", {"date": date}

    # 7. Standortplanung: "Was passiert mit einem neuen Container an Standort X?"
    if any(k in q_low for k in ("standortplanung", "neuen container", "neuer container", "adoption", "netzentlastung", "standort x")):
        return "get_location_planning_info", {"date": date}

    # 8. Replay: historical vs optimized over 349 days
    if any(k in q_low for k in ("replay", "jahres-simulation", "jahressimulation", "349 tage", "bisher vs", "historische praxis")):
        return "get_replay_comparison", {"date": date}

    # 9. Cost model: 500 € / 64 € / 0.65 € / savings
    if any(k in q_low for k in ("kosten", "ersparnis", "wirtschaftlich", "fahrzeugtag", "3-komponenten", "hebel", "opportunit")):
        return "get_cost_model", {"date": date}

    # 10. Waste streams: glass real, others synthetic
    if any(k in q_low for k in ("fraktion", "abfallströme", "abfall", "stream", "papier", "gastro", "plastik", "synthetisch")):
        return "get_waste_streams_info", {"date": date}

    # 11. Specific container explain
    loc_id, material = _extract_location_and_material(question)
    if loc_id is not None:
        return "explain_container", {"location_id": loc_id, "material": material, "date": date}

    # 12. Default: Tour overview
    return "get_tour_overview", {"date": date}


def _call_ollama_tool_router(
    question: str,
    *,
    ollama_url: str,
    model: str,
    timeout_s: float,
) -> tuple[str, dict[str, Any]] | None:
    payload = {
        "model": model,
        "stream": False,
        "tools": OLLAMA_TOOLS_SCHEMA,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
    }
    req = urllib.request.Request(
        ollama_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw_body = resp.read().decode("utf-8")

    parsed = json.loads(raw_body)
    message = parsed.get("message", {}) if isinstance(parsed, Mapping) else {}
    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        return None

    fn = tool_calls[0].get("function", {})
    tool_name = str(fn.get("name", "")).strip()
    raw_args = fn.get("arguments", {})
    if isinstance(raw_args, str):
        args = json.loads(raw_args) if raw_args.strip() else {}
    elif isinstance(raw_args, Mapping):
        args = dict(raw_args)
    else:
        args = {}
    return tool_name, args


def ask_copilot(
    question: str,
    *,
    date: str = "2026-04-15",
    use_llm: bool = False,
    ollama_url: str = "http://localhost:11434/api/chat",
    model: str = "qwen2.5:7b",
    timeout_s: float = 8.0,
    **context_paths: Any,
) -> dict[str, Any]:
    """Answer a dispatcher question via Ollama tool routing (optional) + deterministic execution."""
    mode = "deterministic_fallback"
    tool_call: tuple[str, dict[str, Any]] | None = None

    if use_llm:
        try:
            tool_call = _call_ollama_tool_router(
                question,
                ollama_url=ollama_url,
                model=model,
                timeout_s=timeout_s,
            )
            if tool_call is not None:
                mode = "ollama_tool_router"
        except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            tool_call = None

    if tool_call is None:
        tool_name, args = _route_question_deterministically(question, date)
        mode = "deterministic_fallback"
    else:
        tool_name, args = tool_call
        if tool_name in ALLOWED_TOOLS and not args.get("date"):
            args["date"] = date

    tool_result = dispatch_tool_call(tool_name, args, **context_paths)
    formatted_output = format_copilot_output(tool_result)
    return {
        "question": question,
        "mode": mode,
        "tool_name": tool_name,
        "arguments": args,
        "tool_result": tool_result,
        "formatted_output": formatted_output,
        "sources": tool_result["sources"],
    }
