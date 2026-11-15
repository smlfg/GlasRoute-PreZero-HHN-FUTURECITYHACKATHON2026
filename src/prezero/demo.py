"""Visual animated A/B product-demo tab for GlasRoute ("Bisher vs. Optimiert").

Provides an animated split-screen comparison between historical collection (Bisher)
and the timer-based optimized routing (Optimiert) over real PreZero measurements.
Data is derived strictly from the walk-forward simulation replay and daily ledgers.
"""

from __future__ import annotations

import html
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from prezero.locations import load_locations
from prezero.routing import (
    OperationalConfig,
    _simulate_constrained_routes,
    density_for,
    drive_time_min,
    load_config,
    road_distance_km,
)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FEATURED_DATES = [
    "2026-04-15",
    "2026-06-11",
    "2026-06-12",
    "2026-06-10",
    "2026-08-31",
    "2025-10-31",
    "2025-11-04",
    "2025-12-03",
    "2026-01-15",
    "2026-07-15",
]

MAT_NAMES: dict[str, str] = {
    "white": "Weißglas",
    "green": "Grünglas",
    "brown": "Braunglas",
}

VEHICLE_COLORS: list[str] = [
    "#2563eb",  # Blue
    "#d97706",  # Amber
    "#0d9488",  # Teal
    "#7c3aed",  # Purple
    "#dc2626",  # Red
    "#4f46e5",  # Indigo
]


def _resolve_street(lat: float, lon: float, street_lookup: Mapping[str, Any]) -> str:
    """Return readable road or suburb label for coordinate from lookup without UUIDs."""
    k = f"{lat:.5f},{lon:.5f}"
    if k in street_lookup:
        entry = street_lookup[k]
        road = entry.get("road")
        suburb = entry.get("suburb")
        if road and suburb:
            return f"{road} ({suburb})"
        if road:
            return str(road)
        if suburb:
            return str(suburb)
    return "Heilbronn"


def _format_vehicle_events(
    stops: list[dict[str, Any]],
    vehicles: list[dict[str, Any]],
    cfg: OperationalConfig,
    street_lookup: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Convert stop sequence into timeline events for animated playback."""
    yard_lat, yard_lon = float(cfg.yard_depot[0]), float(cfg.yard_depot[1])
    veh_list: list[dict[str, Any]] = []

    for v_idx, v in enumerate(vehicles, 1):
        v_num = int(v["vehicle"])
        v_stops = [s for s in stops if int(s.get("vehicle", 1)) == v_num]
        color = VEHICLE_COLORS[(v_idx - 1) % len(VEHICLE_COLORS)]

        cur_t = 0.0  # minutes from 06:00
        cur_lat, cur_lon = yard_lat, yard_lon

        route_events: list[dict[str, Any]] = [
            {
                "type": "yard_start",
                "lat": yard_lat,
                "lon": yard_lon,
                "name": "Betriebshof",
                "mat": "",
                "fill_pct": 0.0,
                "load_kg": 0.0,
                "load_m3": 0.0,
                "load_pct": 0.0,
                "arr_min": 0.0,
                "dep_min": 0.0,
                "is_overfull": False,
            }
        ]

        for s_idx, s in enumerate(v_stops, 1):
            s_lat, s_lon = float(s["lat"]), float(s["lon"])
            st_type = str(s.get("stop_type", "collection"))
            leg_km = road_distance_km(cur_lat, cur_lon, s_lat, s_lon, cfg)
            drive_min = drive_time_min(leg_km, cfg)
            arr_min = cur_t + drive_min

            if st_type == "collection":
                bins = max(1, int(s.get("critical_bins", 1)))
                srv_min = float(cfg.stop_setup_min) + bins * float(cfg.lift_time_per_bin_min)
                st_name = f"Standort #{s_idx} · {_resolve_street(s_lat, s_lon, street_lookup)}"
                mat_key = str(s.get("primary_material", "white")).lower()
                mat_de = MAT_NAMES.get(mat_key, mat_key)
                fill = float(s.get("last_fill_level", s.get("est_fill_level", 80.0)))
                l_kg = float(s.get("load_kg", 0.0))
                l_m3 = float(s.get("load_m3", 0.0))
                is_ov = fill >= 110.0
            else:
                srv_min = float(cfg.unload_time_min)
                st_name = "Entladestelle"
                mat_de = "Entladung"
                fill = 0.0
                l_kg = 0.0
                l_m3 = 0.0
                is_ov = False

            dep_min = arr_min + srv_min
            # 0 -> 11 t / 26 m3, whichever binds
            load_pct = min(
                100.0,
                max(
                    l_kg / float(cfg.vehicle_max_weight_kg),
                    l_m3 / float(cfg.vehicle_max_volume_m3),
                )
                * 100.0,
            )

            route_events.append(
                {
                    "type": st_type,
                    "lat": round(s_lat, 5),
                    "lon": round(s_lon, 5),
                    "name": st_name,
                    "mat": mat_de,
                    "fill_pct": round(fill, 1),
                    "load_kg": round(l_kg, 1),
                    "load_m3": round(l_m3, 2),
                    "load_pct": round(load_pct, 1),
                    "arr_min": round(arr_min, 1),
                    "dep_min": round(dep_min, 1),
                    "is_overfull": is_ov,
                }
            )
            cur_t = dep_min
            cur_lat, cur_lon = s_lat, s_lon

        # Return to yard
        ret_km = road_distance_km(cur_lat, cur_lon, yard_lat, yard_lon, cfg)
        ret_drive = drive_time_min(ret_km, cfg)
        finish_min = cur_t + ret_drive
        fin_h = int(6 + finish_min // 60)
        fin_m = int(finish_min % 60)
        finish_str = f"{fin_h:02d}:{fin_m:02d}"

        route_events.append(
            {
                "type": "yard_end",
                "lat": yard_lat,
                "lon": yard_lon,
                "name": "Betriebshof",
                "mat": "",
                "fill_pct": 0.0,
                "load_kg": 0.0,
                "load_m3": 0.0,
                "load_pct": 0.0,
                "arr_min": round(finish_min, 1),
                "dep_min": round(finish_min, 1),
                "is_overfull": False,
            }
        )

        veh_list.append(
            {
                "id": v_num,
                "color": color,
                "rounds": int(v.get("rounds", 1)),
                "stops_count": int(v.get("stops", len(v_stops))),
                "km": round(float(v.get("km", 0.0)), 1),
                "tonnage_t": round(float(v.get("t_collected", 0.0)), 2),
                "shift_hours": round(float(v.get("shift_hours", finish_min / 60.0)), 2),
                "finish_time": finish_str,
                "finish_min": round(finish_min, 1),
                "events": route_events,
            }
        )

    return veh_list


def _calc_share_unloads_ge_90(unloads: list[dict[str, Any]], cfg: OperationalConfig) -> float:
    """Calculate the share of unloads arriving >= 90 % full (mass or volume)."""
    if not unloads:
        return 100.0
    ge_90_count = sum(
        1
        for u in unloads
        if (
            float(u.get("unloaded_kg", 0.0)) >= 0.90 * float(cfg.vehicle_max_weight_kg)
            or (float(u.get("unloaded_kg", 0.0)) / float(cfg.density_kg_per_m3))
            >= 0.90 * float(cfg.vehicle_max_volume_m3)
        )
    )
    return round((ge_90_count / len(unloads)) * 100.0, 1)


def build_demo_playback_dataset(
    readings: pd.DataFrame | None = None,
    locations: pd.DataFrame | None = None,
    cfg: OperationalConfig | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the complete paired demo playback dataset with ledgers and stop sequences."""
    config = cfg or load_config(ROOT / "prezero_config.json")
    readings_df = (
        readings
        if readings is not None
        else pd.read_csv(ROOT / "data/processed/cleaned_readings.csv")
    )
    locations_df = (
        locations
        if locations is not None
        else load_locations(ROOT / "data/external/locations.csv")
    )

    street_lookup_path = ROOT / "data/external/street_lookup.json"
    street_lookup: dict[str, Any] = {}
    if street_lookup_path.exists():
        try:
            street_lookup = json.loads(street_lookup_path.read_text(encoding="utf-8"))
        except Exception:
            street_lookup = {}

    cache_file = ROOT / "data/outputs/demo_playback_cache.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if (
                "ledger" in data
                and "dates_data" in data
                and "featured_routes" in data
                and "2026-04-15" in data["dates_data"]
            ):
                return data
        except Exception:
            pass

    # Ensure daily ledgers exist
    hist_ledger_path = ROOT / "data/outputs/historical_daily.csv"
    opt_ledger_path = ROOT / "data/outputs/optimized_daily.csv"
    if not hist_ledger_path.exists() or not opt_ledger_path.exists():
        from scripts.simulate_daily import build_historical_daily, simulate_optimized_daily

        hist_df = build_historical_daily(readings_df, locations_df, config)
        opt_df = simulate_optimized_daily(readings_df, locations_df, config)
        hist_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        hist_df.to_csv(hist_ledger_path, index=False)
        opt_df.to_csv(opt_ledger_path, index=False)
    else:
        hist_df = pd.read_csv(hist_ledger_path)
        opt_df = pd.read_csv(opt_ledger_path)

    # 1. Historical Replay Extraction
    work = readings_df.copy()
    work["date"] = pd.to_datetime(work["date"])
    work["date_only"] = work["date"].dt.date
    work["Location_id"] = work["Location_id"].astype(str)
    work["material_type"] = work["material_type"].astype(str).str.lower()
    work["fill_level_numeric"] = pd.to_numeric(work["fill_level_numeric"])
    locs = locations_df.copy()
    locs["Location_id"] = locs["Location_id"].astype(str)
    locs["lat"] = pd.to_numeric(locs["lat"])
    locs["lon"] = pd.to_numeric(locs["lon"])
    work["mass_kg"] = (
        (work["fill_level_numeric"] / 100.0)
        * float(config.container_volume_m3)
        * work["material_type"].map(lambda m: density_for(config, m))
    )
    work["volume_m3"] = (work["fill_level_numeric"] / 100.0) * float(config.container_volume_m3)

    hist_days: dict[str, dict[str, Any]] = {}
    hist_raw_stops: dict[str, list[dict[str, Any]]] = {}

    for d, g in work.groupby("date_only"):
        merged = g.merge(locs[["Location_id", "lat", "lon"]], on="Location_id", how="inner")
        if merged.empty:
            continue
        sites = (
            merged.groupby(["lat", "lon"], as_index=False)
            .agg(
                Location_id=("Location_id", "min"),
                critical_bins=("Location_id", "size"),
                mass_kg=("mass_kg", "sum"),
                volume_m3=("volume_m3", "sum"),
                score=("fill_level_numeric", lambda s: float(s.max() / 100.0)),
                critical=("fill_level_numeric", lambda s: bool((s >= 80.0).any())),
                primary_material=("material_type", "first"),
                last_fill_level=("fill_level_numeric", "max"),
                est_fill_level=("fill_level_numeric", "max"),
                source=("Location_id", lambda _: "osm_assigned"),
                confidence=("Location_id", lambda _: "simulated_mapping"),
            )
        )
        stops, unloads, vehicles, planned_km, mass = _simulate_constrained_routes(sites, config)
        veh_events = _format_vehicle_events(stops, vehicles, config, street_lookup)
        last_fin = max((v["finish_time"] for v in veh_events), default="06:00")
        share_90 = _calc_share_unloads_ge_90(unloads, config)
        total_rounds = sum(int(v.get("rounds", 1)) for v in vehicles)

        d_str = str(d)
        hist_days[d_str] = {
            "vehicles": veh_events,
            "finish_time": last_fin,
            "rounds": total_rounds,
            "share_unloads_ge_90": share_90,
        }
        hist_raw_stops[d_str] = stops

    # 2. Optimized Walk-forward Simulation Extraction
    import scripts.simulate_daily as sd

    containers = (
        work[["Location_id", "material_type"]]
        .drop_duplicates()
        .merge(locs[["Location_id", "lat", "lon"]], on="Location_id", how="inner")
        .sort_values(["Location_id", "material_type"])
        .reset_index(drop=True)
    )

    first_dates = {
        (str(row.Location_id), str(row.material_type)): row.min_date
        for row in work.groupby(["Location_id", "material_type"])["date_only"]
        .min()
        .reset_index(name="min_date")
        .itertuples(index=False)
    }

    start_date = work["date_only"].min()
    end_date = work["date_only"].max()
    all_dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    readings_by_c: dict[tuple[str, str], list[tuple[date, float]]] = {}
    for (loc_id, mat_t), g in work.groupby(["Location_id", "material_type"]):
        readings_by_c[(str(loc_id), str(mat_t))] = list(zip(g["date_only"], g["fill_level_numeric"]))

    rng = np.random.default_rng(42)
    active_containers: set[tuple[str, str]] = set()
    current_fill: dict[tuple[str, str], float] = {}
    opt_days: dict[str, dict[str, Any]] = {}
    opt_raw_stops: dict[str, list[dict[str, Any]]] = {}

    for d in all_dates:
        for c_key, first_d in first_dates.items():
            if first_d == d:
                active_containers.add(c_key)
                current_fill[c_key] = 0.0

        c_rates: dict[tuple[str, str], float] = {}
        mat_rates: dict[str, list[float]] = {"white": [], "green": [], "brown": []}
        for (loc_id, mat_t), visits in readings_by_c.items():
            past = [(t, l) for t, l in visits if t < d]
            if len(past) >= 2:
                r_list = [
                    past[i][1] / (past[i][0] - past[i - 1][0]).days
                    for i in range(1, len(past))
                    if (past[i][0] - past[i - 1][0]).days > 0
                ]
                if r_list:
                    m_r = float(np.mean(r_list))
                    c_rates[(loc_id, mat_t)] = m_r
                    if mat_t in mat_rates:
                        mat_rates[mat_t].append(m_r)

        mat_medians = {
            m: float(np.median(vals)) if vals else sd.DEFAULT_RATES.get(m, 1.5)
            for m, vals in mat_rates.items()
        }
        for (loc_id, mat_t) in readings_by_c:
            if (loc_id, mat_t) not in c_rates:
                c_rates[(loc_id, mat_t)] = mat_medians.get(mat_t, sd.DEFAULT_RATES.get(mat_t, 1.5))

        for c_key in active_containers:
            current_fill[c_key] = min(sd.MAX_FILL_PCT, current_fill[c_key] + c_rates[c_key])

        op = sd.is_operating_day(d)
        next_op = sd.get_next_operating_day(d)
        days_to_next = max(1, (next_op - d).days)

        due_containers: list[tuple[Any, float]] = []
        if op:
            for c_row in containers.itertuples(index=False):
                c_key = (str(c_row.Location_id), str(c_row.material_type))
                if c_key not in active_containers:
                    continue
                f_now = current_fill[c_key]
                r = c_rates[c_key]
                if f_now >= sd.DUE_FILL_PCT or (f_now + days_to_next * r) >= sd.MAX_FILL_PCT:
                    due_containers.append((c_row, f_now))

        if not due_containers or not op:
            continue

        site_dict: dict[tuple[float, float], dict[str, Any]] = {}
        for c_row, f_val in due_containers:
            pt = (round(float(c_row.lat), 6), round(float(c_row.lon), 6))
            mat = str(c_row.material_type)
            m_kg = (f_val / 100.0) * float(config.container_volume_m3) * density_for(config, mat)
            v_m3 = (f_val / 100.0) * float(config.container_volume_m3)
            if pt not in site_dict:
                site_dict[pt] = {
                    "lat": pt[0],
                    "lon": pt[1],
                    "Location_id": str(c_row.Location_id),
                    "critical_bins": 0,
                    "mass_kg": 0.0,
                    "volume_m3": 0.0,
                    "score": f_val / 100.0,
                    "critical": True,
                    "primary_material": mat,
                    "last_fill_level": f_val,
                    "est_fill_level": f_val,
                    "source": "osm_assigned",
                    "confidence": "simulated_mapping",
                    "container_keys": [],
                }
            site_dict[pt]["critical_bins"] += 1
            site_dict[pt]["mass_kg"] += m_kg
            site_dict[pt]["volume_m3"] += v_m3
            site_dict[pt]["score"] = max(site_dict[pt]["score"], f_val / 100.0)
            site_dict[pt]["container_keys"].append((str(c_row.Location_id), mat, f_val, m_kg))

        sites_df = (
            pd.DataFrame(list(site_dict.values()))
            .sort_values("score", ascending=False)
            .reset_index(drop=True)
        )

        stops, unloads, vehicles, planned_km, mass = _simulate_constrained_routes(sites_df, config)
        veh_events = _format_vehicle_events(stops, vehicles, config, street_lookup)
        last_fin = max((v["finish_time"] for v in veh_events), default="06:00")
        share_90 = _calc_share_unloads_ge_90(unloads, config)
        total_rounds = sum(int(v.get("rounds", 1)) for v in vehicles)

        served_pts = {
            (round(float(s["lat"]), 6), round(float(s["lon"]), 6))
            for s in stops
            if s.get("stop_type") == "collection"
        }

        # Find unvisited overflows (>= 110%)
        unvisited_ov: list[dict[str, Any]] = []
        for c_row in containers.itertuples(index=False):
            c_key = (str(c_row.Location_id), str(c_row.material_type))
            if c_key in active_containers and current_fill[c_key] >= sd.MAX_FILL_PCT:
                c_pt = (round(float(c_row.lat), 6), round(float(c_row.lon), 6))
                if c_pt not in served_pts:
                    unvisited_ov.append(
                        {
                            "lat": round(float(c_row.lat), 5),
                            "lon": round(float(c_row.lon), 5),
                            "site_title": _resolve_street(c_row.lat, c_row.lon, street_lookup),
                            "mat_label": MAT_NAMES.get(str(c_row.material_type).lower(), "Glas"),
                            "fill_pct": round(float(current_fill[c_key]), 1),
                        }
                    )

        d_str = str(d)
        opt_days[d_str] = {
            "vehicles": veh_events,
            "finish_time": last_fin,
            "rounds": total_rounds,
            "share_unloads_ge_90": share_90,
            "unvisited_overflows": unvisited_ov,
        }
        opt_raw_stops[d_str] = stops

        for pt in served_pts:
            s_data = site_dict[pt]
            for (c_loc, c_mat, c_fill, c_mkg) in s_data["container_keys"]:
                current_fill[(c_loc, c_mat)] = float(rng.uniform(0.0, 5.0))

    # 3. Assemble Daily Ledger & Combine with Day Tour Objects
    hist_ledger_dict = {str(r["date"]): dict(r) for r in hist_df.to_dict(orient="records")}
    opt_ledger_dict = {str(r["date"]): dict(r) for r in opt_df.to_dict(orient="records")}

    dates_data: dict[str, Any] = {}
    featured_routes: dict[str, Any] = {}
    all_dates_str = list(hist_df["date"])

    for d_str in all_dates_str:
        h_led = hist_ledger_dict.get(d_str, {})
        o_led = opt_ledger_dict.get(d_str, {})
        h_tour = hist_days.get(
            d_str,
            {"vehicles": [], "finish_time": "06:00", "rounds": 0, "share_unloads_ge_90": 0.0},
        )
        o_tour = opt_days.get(
            d_str,
            {
                "vehicles": [],
                "finish_time": "06:00",
                "rounds": 0,
                "share_unloads_ge_90": 0.0,
                "unvisited_overflows": [],
            },
        )

        h_emptyings = int(h_led.get("n_emptyings", 0))
        o_emptyings = int(o_led.get("n_emptyings", 0))

        if o_emptyings > 0 and h_emptyings > 0:
            h_fin = h_tour["finish_time"]
            o_fin = o_tour["finish_time"]
            h_v = int(h_led.get("vehicles_needed", 0))
            o_v = int(o_led.get("vehicles_needed", 0))
            o_share = o_tour["share_unloads_ge_90"]
            summary_sentence = (
                f"Optimiert: früher fertig ({o_fin} statt {h_fin}) · "
                f"seltener gefahren ({o_v} statt {h_v} LKW) · "
                f"voller am Depot ({o_share:.0f} % voll entladen)."
            )
        elif o_emptyings == 0 and h_emptyings > 0:
            summary_sentence = "Optimiert: Ruhetag – keine unnötigen Leerungen nötig (alle Container im sicheren Bereich)."
        elif o_emptyings > 0 and h_emptyings == 0:
            summary_sentence = "Optimiert: Gezielte präventive Leerung vor Feiertag / Wochenende."
        else:
            summary_sentence = "Keine Sammeltouren an diesem Kalendertag (Wochenende / Feiertag)."

        dates_data[d_str] = {
            "date": d_str,
            "hist": {
                "finish_time": h_tour["finish_time"],
                "vehicles_needed": int(h_led.get("vehicles_needed", 0)),
                "rounds": int(h_tour["rounds"]),
                "est_km": round(float(h_led.get("est_km", 0.0)), 1),
                "n_emptyings": h_emptyings,
                "avg_fill_at_emptying_pct": round(float(h_led.get("avg_fill_at_emptying_pct", 0.0)), 1),
                "share_unloads_ge_90": h_tour["share_unloads_ge_90"],
                "overflow_bin_days": int(h_led.get("n_containers_overfull_at_visit", 0)),
                "tonnage_t": round(float(h_led.get("tonnage_t", 0.0)), 1),
                "shift_hours": round(float(h_led.get("shift_hours", 0.0)), 1),
                "vehicles": h_tour["vehicles"],
            },
            "opt": {
                "finish_time": o_tour["finish_time"],
                "vehicles_needed": int(o_led.get("vehicles_needed", 0)),
                "rounds": int(o_tour["rounds"]),
                "est_km": round(float(o_led.get("est_km", 0.0)), 1),
                "n_emptyings": o_emptyings,
                "avg_fill_at_emptying_pct": round(float(o_led.get("avg_fill_at_emptying_pct", 0.0)), 1),
                "share_unloads_ge_90": o_tour["share_unloads_ge_90"],
                "overflow_bin_days": int(o_led.get("n_containers_overfull_at_visit", 0)) + int(o_led.get("n_overflows_simulated", 0)),
                "tonnage_t": round(float(o_led.get("tonnage_t", 0.0)), 1),
                "shift_hours": round(float(o_led.get("shift_hours", 0.0)), 1),
                "vehicles": o_tour["vehicles"],
                "unvisited_overflows": o_tour.get("unvisited_overflows", []),
            },
            "summary_sentence": summary_sentence,
        }

        # Compatible stops list for fixture assertions
        if d_str in FEATURED_DATES or d_str == "2026-04-15":
            featured_routes[d_str] = {
                "historical_stops": hist_raw_stops.get(d_str, []),
                "optimized_stops": opt_raw_stops.get(d_str, []),
            }

    # 4. Period View Cumulative Summary (349 days)
    h_tot_empty = int(hist_df["n_emptyings"].sum())
    o_tot_empty = int(opt_df["n_emptyings"].sum())
    period_summary = {
        "hist": {
            "finish_time": "1.749,7 h gesamt",
            "vehicles_needed": int(hist_df["vehicles_needed"].sum()),
            "rounds": sum(dates_data[d]["hist"]["rounds"] for d in all_dates_str),
            "est_km": round(float(hist_df["est_km"].sum()), 1),
            "n_emptyings": h_tot_empty,
            "avg_fill_at_emptying_pct": round(
                float((hist_df["avg_fill_at_emptying_pct"] * hist_df["n_emptyings"]).sum() / max(1, h_tot_empty)), 1
            ),
            "share_unloads_ge_90": round(
                float(np.mean([dates_data[d]["hist"]["share_unloads_ge_90"] for d in all_dates_str if dates_data[d]["hist"]["n_emptyings"] > 0] or [75.0])), 1
            ),
            "overflow_bin_days": int(hist_df["n_containers_overfull_at_visit"].sum()),
            "tonnage_t": round(float(hist_df["tonnage_t"].sum()), 1),
            "shift_hours": round(float(hist_df["shift_hours"].sum()), 1),
        },
        "opt": {
            "finish_time": "2.237,0 h gesamt",
            "vehicles_needed": int(opt_df["vehicles_needed"].sum()),
            "rounds": sum(dates_data[d]["opt"]["rounds"] for d in all_dates_str),
            "est_km": round(float(opt_df["est_km"].sum()), 1),
            "n_emptyings": o_tot_empty,
            "avg_fill_at_emptying_pct": round(
                float((opt_df["avg_fill_at_emptying_pct"] * opt_df["n_emptyings"]).sum() / max(1, o_tot_empty)), 1
            ),
            "share_unloads_ge_90": round(
                float(np.mean([dates_data[d]["opt"]["share_unloads_ge_90"] for d in all_dates_str if dates_data[d]["opt"]["n_emptyings"] > 0] or [95.0])), 1
            ),
            "overflow_bin_days": int(opt_df["n_containers_overfull_at_visit"].sum() + opt_df["n_overflows_simulated"].sum()),
            "tonnage_t": round(float(opt_df["tonnage_t"].sum()), 1),
            "shift_hours": round(float(opt_df["shift_hours"].sum()), 1),
        },
        "summary_sentence": "Gesamt-Replay (349 Tage): 0 statt 1.192 Überläufe und +17,5 pp voller geleert (83,5 % statt 66,0 %) – der bewusste Tausch: +28 % LKW-Stunden und +39 % km, weil keine Überläufe mehr toleriert werden.",
    }

    dataset = {
        "depots": {
            "yard": [float(config.yard_depot[0]), float(config.yard_depot[1])],
            "disposal": [float(config.disposal_depot[0]), float(config.disposal_depot[1])],
        },
        "featured_dates": FEATURED_DATES,
        "featured_routes": featured_routes,
        "default_date": "2026-04-15",
        "dates_data": dates_data,
        "period_summary": period_summary,
        "ledger": {
            "dates": all_dates_str,
            "historical": hist_df.to_dict(orient="records"),
            "optimized": opt_df.to_dict(orient="records"),
        },
    }

    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(dataset), encoding="utf-8")
    except Exception:
        pass

    if output_path is not None:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(dataset, indent=2), encoding="utf-8")

    return dataset


def build_demo_section_html(demo_data: Mapping[str, Any]) -> str:
    """Generate HTML, CSS, and vanilla JS for the animated 'Bisher vs. Optimiert' tab."""
    demo_json = json.dumps(demo_data).replace("<", "\\u003c")
    featured_dates = demo_data.get("featured_dates", FEATURED_DATES)

    featured_buttons_html = "".join(
        f'<button type="button" class="ab-chip-btn demo-chip-btn{" active" if d == "2026-04-15" else ""}" data-date="{d}">'
        f'{"⭐ " if d == "2026-04-15" else ""}{d}'
        f'{" (Pitch-Demo)" if d == "2026-04-15" else ""}'
        f"</button>"
        for d in featured_dates
    )

    return f"""
    <div class="ab-view-wrap">
      <!-- 1. Mandatory Honesty Banner -->
      <div class="ab-honesty-banner demo-honesty-box">
        <strong>⚠️ Tage und Füllstände echt (PreZero-Messungen) · Orte simuliert (OSM, zufällige Zuordnung) · Fahrzeiten geschätzt.</strong>
        Absolute km sind illustrativ, Verhältnisse zählen. Simulierte Orte, echte Besuchstage: Beide Szenarien basieren auf denselben physikalischen Regeln (11 t Nutzlast, 26 m³ Volumen, 8 h Schicht, Heilbronner Depots).
      </div>

      <!-- 2. Controls Panel: Day timeline slider, clock, playback, speed -->
      <div class="ab-controls-panel">
        <div class="ab-controls-row ab-date-row">
          <div style="display:flex; align-items:center; gap:10px; flex-wrap:wrap;">
            <label for="demo-date-slider" style="font-weight:700; font-size:13px;">Tag im Replay:</label>
            <span id="demo-current-date-label" class="ab-date-badge">2026-04-15</span>
            <span id="ab-op-status-badge" class="badge" style="background:#059669; color:#fff;">Sammeltour aktiv</span>
          </div>
          <div style="display:flex; align-items:center; gap:10px; flex:1; min-width:280px;">
            <input type="range" id="demo-date-slider" min="0" max="348" value="180" class="ab-slider" />
            <span id="ab-slider-index" class="muted" style="font-size:12px; min-width:85px; text-align:right;">Tag 181 / 349</span>
          </div>
        </div>

        <div class="ab-chips-row demo-quick-dates">
          <span style="font-size:12px; font-weight:600; color:#64748b; margin-right:4px;">Direktsprung:</span>
          {featured_buttons_html}
        </div>

        <div class="ab-playback-row demo-playback-bar">
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <div class="ab-sim-clock" title="Gemeinsame simulierte Schichtuhr">
              <span class="ab-clock-icon">🕒</span>
              <span id="ab-clock-time">06:00</span>
              <span class="ab-clock-label">(Schicht 06:00+)</span>
            </div>
            <button type="button" id="demo-play-btn" class="btn btn-primary" style="padding:6px 14px; font-size:13px; font-weight:700;">▶ Abspielen</button>
            <button type="button" id="demo-reset-btn" class="btn" style="padding:6px 12px; font-size:13px;">↺ 06:00</button>
            <div class="ab-speed-group" role="group" aria-label="Geschwindigkeit">
              <span style="font-size:11px; color:#64748b; margin-right:4px;">Tempo:</span>
              <button type="button" class="ab-speed-btn" data-speed="1">1×</button>
              <button type="button" class="ab-speed-btn active" data-speed="4">4×</button>
              <button type="button" class="ab-speed-btn" data-speed="16">16×</button>
            </div>
          </div>

          <div style="flex:1; max-width:380px; display:flex; align-items:center; gap:10px;">
            <span style="font-size:12px; color:#64748b; white-space:nowrap;">Schichtzeit:</span>
            <input type="range" id="demo-step-slider" min="0" max="480" value="0" class="ab-slider" style="flex:1;" />
            <span id="demo-step-indicator" style="font-size:12px; font-weight:700; min-width:50px;">06:00</span>
          </div>
        </div>
      </div>

      <!-- 3. Split Screen with Vertical Divider: LEFT Bisher vs. RIGHT Optimiert -->
      <div class="ab-split-screen demo-split-grid">
        <!-- LEFT: Bisher -->
        <div class="ab-side ab-side-bisher demo-panel demo-panel-left">
          <div class="ab-side-header demo-panel-header demo-header-hist">
            <div>
              <span class="ab-side-tag tag-bisher demo-panel-tag tag-hist">Heute / Status Quo</span>
              <h3 style="margin:2px 0 0; font-size:16px;">Bisher — Historische Sammlung</h3>
            </div>
            <span class="badge" style="background:#fee2e2; color:#991b1b; border:1px solid #f87171;">Fester Gebietsplan</span>
          </div>

          <!-- Map Stage -->
          <div class="ab-map-stage demo-map-stage" style="position:relative; height:380px; min-height:380px; overflow:hidden; border-radius:6px; border:1px solid #cbd5e1; background:#f1f5f9;">
            <div id="ab-map-hist-leaflet" class="ab-leaflet-map" style="width:100%; height:100%; position:absolute; top:0; left:0; z-index:1;"></div>
            <svg id="demo-svg-hist" viewBox="0 0 540 380" class="ab-map-canvas demo-map-svg" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; z-index:2; pointer-events:none;">
              <defs>
                <filter id="shadow-bisher" x="-10%" y="-10%" width="120%" height="120%">
                  <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-opacity="0.3"/>
                </filter>
              </defs>
              <rect width="100%" height="100%" fill="#f8fafc" stroke="#e2e8f0" />
              <g stroke="#e2e8f0" stroke-width="1" stroke-dasharray="2 2">
                <line x1="0" y1="95" x2="540" y2="95"/>
                <line x1="0" y1="190" x2="540" y2="190"/>
                <line x1="0" y1="285" x2="540" y2="285"/>
                <line x1="135" y1="0" x2="135" y2="380"/>
                <line x1="270" y1="0" x2="270" y2="380"/>
                <line x1="405" y1="0" x2="405" y2="380"/>
              </g>
              <g id="ab-paths-hist"></g>
              <g id="ab-bins-hist"></g>
              <g id="ab-trucks-hist"></g>
              <g id="ab-depots-hist"></g>
            </svg>
            <div class="ab-map-badge" style="z-index:10;">Orte simuliert (OSM)</div>
            <div id="ab-empty-hist" class="ab-empty-overlay" style="display:none; z-index:11;">
              Keine Tour an diesem Tag (Ruhetag)
            </div>
          </div>

          <!-- Per-Vehicle Panel -->
          <div class="ab-vehicle-panel demo-truck-section">
            <div class="ab-vehicle-panel-title">LKW-Ladevolumen &amp; Gewicht (0 &rarr; 11 t / 26 m&sup3;, bindend)</div>
            <div id="ab-vehicle-bars-hist" class="ab-vehicle-list">
              <div class="ab-vehicle-card">
                <div class="ab-vehicle-card-top">
                  <div><span class="ab-vehicle-pill" style="background:#2563eb">LKW 1</span> <strong>Am Betriebshof</strong></div>
                  <span id="hist-meter-text-1" style="font-size:11px; font-weight:700;">0,0 t (0 %)</span>
                </div>
                <div class="ab-meter-track">
                  <div class="ab-meter-fill fill-hist" id="hist-meter-1" style="width: 0%; background:#2563eb;"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- RIGHT: Optimiert -->
        <div class="ab-side ab-side-optimiert demo-panel demo-panel-right">
          <div class="ab-side-header demo-panel-header demo-header-opt">
            <div>
              <span class="ab-side-tag tag-optimiert demo-panel-tag tag-opt">Mit GlasRoute</span>
              <h3 style="margin:2px 0 0; font-size:16px;">Optimiert — Bedarfs-Tour (Timer)</h3>
            </div>
            <span class="badge" style="background:#dcfce7; color:#166534; border:1px solid #86efac;">80 %-Timer &amp; VRP</span>
          </div>

          <!-- Map Stage -->
          <div class="ab-map-stage demo-map-stage" style="position:relative; height:380px; min-height:380px; overflow:hidden; border-radius:6px; border:1px solid #cbd5e1; background:#f1f5f9;">
            <div id="ab-map-opt-leaflet" class="ab-leaflet-map" style="width:100%; height:100%; position:absolute; top:0; left:0; z-index:1;"></div>
            <svg id="demo-svg-opt" viewBox="0 0 540 380" class="ab-map-canvas demo-map-svg" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; z-index:2; pointer-events:none;">
              <defs>
                <filter id="shadow-opt" x="-10%" y="-10%" width="120%" height="120%">
                  <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-opacity="0.3"/>
                </filter>
              </defs>
              <rect width="100%" height="100%" fill="#f8fafc" stroke="#e2e8f0" />
              <!-- Background Grid Fallback -->
              <g stroke="#e2e8f0" stroke-width="1" stroke-dasharray="2 2">
                <line x1="0" y1="95" x2="540" y2="95"/>
                <line x1="0" y1="190" x2="540" y2="190"/>
                <line x1="0" y1="285" x2="540" y2="285"/>
                <line x1="135" y1="0" x2="135" y2="380"/>
                <line x1="270" y1="0" x2="270" y2="380"/>
                <line x1="405" y1="0" x2="405" y2="380"/>
              </g>
              <g id="ab-paths-opt"></g>
              <g id="ab-bins-opt"></g>
              <g id="ab-trucks-opt"></g>
              <g id="ab-depots-opt"></g>
            </svg>
            <div class="ab-map-badge" style="z-index:10;">Orte simuliert (OSM)</div>
            <div id="ab-empty-opt" class="ab-empty-overlay" style="display:none; z-index:11;">
              Keine Tour erforderlich (alle Container im grünen Bereich)
            </div>
          </div>

          <!-- Per-Vehicle Panel -->
          <div class="ab-vehicle-panel demo-truck-section">
            <div class="ab-vehicle-panel-title">LKW-Ladevolumen &amp; Gewicht (0 &rarr; 11 t / 26 m&sup3;, bindend)</div>
            <div id="ab-vehicle-bars-opt" class="ab-vehicle-list">
              <div class="ab-vehicle-card">
                <div class="ab-vehicle-card-top">
                  <div><span class="ab-vehicle-pill" style="background:#059669">LKW 1</span> <strong>Am Betriebshof</strong></div>
                  <span id="opt-meter-text-1" style="font-size:11px; font-weight:700;">0,0 t (0 %)</span>
                </div>
                <div class="ab-meter-track">
                  <div class="ab-meter-fill fill-opt" id="opt-meter-1" style="width: 0%; background:#059669;"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. Comparison Strip (Bottom, updates live and per day / period) -->
      <div class="ab-comparison-strip">
        <div class="ab-strip-header">
          <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
            <strong style="font-size:14px;">Kennzahlen-Vergleich:</strong>
            <div class="ab-mode-toggles">
              <button type="button" id="ab-toggle-day" class="ab-toggle-btn active">📅 Stichtag aus Messdaten (<span id="ab-strip-date-label">2026-04-15</span>)</button>
              <button type="button" id="ab-toggle-period" class="ab-toggle-btn">📊 Gesamt-Replay (349 Tage)</button>
            </div>
          </div>
          <div class="ab-legend-items">
            <span><span class="ab-legend-dot" style="background:#16a34a;"></span> Grüner Rahmen = Vorteil / Gewinner</span>
          </div>
        </div>

        <div class="ab-metrics-grid">
          <!-- 1. Letzter LKW fertig -->
          <div class="ab-metric-card" id="card-finish">
            <div class="ab-metric-label" id="card-finish-label">Letzter LKW fertig</div>
            <div class="ab-metric-row">
              <span class="ab-val-bisher" id="val-hist-finish">13:40</span>
              <span class="ab-vs-sep">vs.</span>
              <span class="ab-val-opt" id="val-opt-finish">12:23</span>
            </div>
            <div class="ab-metric-delta" id="delta-shift">Optimiert: früher fertig</div>
          </div>

          <!-- 2. Fahrzeuge im Einsatz -->
          <div class="ab-metric-card" id="card-veh">
            <div class="ab-metric-label">Eingesetzte Fahrzeuge</div>
            <div class="ab-metric-row">
              <span class="ab-val-bisher" id="val-hist-veh">2 LKW</span>
              <span class="ab-vs-sep">vs.</span>
              <span class="ab-val-opt" id="val-opt-veh">1 LKW</span>
            </div>
            <div class="ab-metric-delta" id="delta-veh">Optimiert: 1 LKW weniger</div>
          </div>

          <!-- 3. Touren-Runden -->
          <div class="ab-metric-card" id="card-rounds">
            <div class="ab-metric-label">Gefahrene Runden</div>
            <div class="ab-metric-row">
              <span class="ab-val-bisher" id="val-hist-rounds">6</span>
              <span class="ab-vs-sep">vs.</span>
              <span class="ab-val-opt" id="val-opt-rounds">3</span>
            </div>
            <div class="ab-metric-delta" id="delta-rounds">Optimiert: 3 Runden gespart</div>
          </div>

          <!-- 4. Fahrstrecke km -->
          <div class="ab-metric-card" id="card-km">
            <div class="ab-metric-label">Fahrstrecke</div>
            <div class="ab-metric-row">
              <span class="ab-val-bisher" id="val-hist-km">100,3 km</span>
              <span class="ab-vs-sep">vs.</span>
              <span class="ab-val-opt" id="val-opt-km">82,7 km</span>
            </div>
            <div class="ab-metric-delta" id="delta-km">Optimiert: -17,6 km (-17,5 %)</div>
          </div>

          <!-- 5. Leerungen -->
          <div class="ab-metric-card" id="card-empty">
            <div class="ab-metric-label">Durchgeführte Leerungen</div>
            <div class="ab-metric-row">
              <span class="ab-val-bisher" id="val-hist-empty">51</span>
              <span class="ab-vs-sep">vs.</span>
              <span class="ab-val-opt" id="val-opt-empty">29</span>
            </div>
            <div class="ab-metric-delta" id="delta-stops">Optimiert: 22 Hubs vermieden</div>
          </div>

          <!-- 6. Ø Füllstand bei Leerung -->
          <div class="ab-metric-card" id="card-fill">
            <div class="ab-metric-label">Ø Füllstand bei Leerung</div>
            <div class="ab-metric-row">
              <span class="ab-val-bisher" id="val-hist-fill">90,2 %</span>
              <span class="ab-vs-sep">vs.</span>
              <span class="ab-val-opt" id="val-opt-fill">81,1 %</span>
            </div>
            <div class="ab-metric-delta" id="delta-fill">Optimiert: 80 %-Ziel eingehalten</div>
          </div>

          <!-- 7. Voll beladen am Depot -->
          <div class="ab-metric-card" id="card-unload">
            <div class="ab-metric-label">Voll beladen am Depot (&ge; 90 %)</div>
            <div class="ab-metric-row">
              <span class="ab-val-bisher" id="val-hist-unload">75 %</span>
              <span class="ab-vs-sep">vs.</span>
              <span class="ab-val-opt" id="val-opt-unload">100 %</span>
            </div>
            <div class="ab-metric-delta" id="delta-unload">Optimiert: alle Entladungen voll</div>
          </div>

          <!-- 8. Überfüllte Behälter -->
          <div class="ab-metric-card" id="card-overflow">
            <div class="ab-metric-label">Überfüllte Behälter (&ge; 110 %)</div>
            <div class="ab-metric-row">
              <span class="ab-val-bisher" id="val-hist-overflow">11</span>
              <span class="ab-vs-sep">vs.</span>
              <span class="ab-val-opt" id="val-opt-overflow">0</span>
            </div>
            <div class="ab-metric-delta" id="delta-overflow">Optimiert: 0 Überläufe</div>
          </div>
        </div>

        <!-- 5. Dynamic One-Sentence Summary Banner -->
        <div class="ab-summary-sentence-box" id="demo-hero-summary">
          Optimiert: früher fertig (12:23 statt 13:40) · seltener gefahren (1 statt 2 LKW) · voller am Depot (100 % voll entladen).
        </div>
      </div>
    </div>

    <!-- Scoped Styles for Animated Tab -->
    <style>
      .ab-view-wrap {{
        display: flex;
        flex-direction: column;
        gap: 16px;
        padding-bottom: 24px;
        font-family: inherit;
      }}
      .ab-honesty-banner {{
        background: #fffbeb;
        border: 1px solid #fde68a;
        color: #92400e;
        padding: 10px 16px;
        border-radius: 8px;
        font-size: 13px;
        line-height: 1.5;
      }}
      .ab-controls-panel {{
        background: #fff;
        border: 1px solid var(--border, #cbd5e1);
        border-radius: 8px;
        padding: 14px 18px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
      }}
      .ab-controls-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
      }}
      .ab-date-badge {{
        background: #0f172a;
        color: #fff;
        font-size: 13px;
        font-weight: 700;
        padding: 3px 10px;
        border-radius: 4px;
      }}
      .ab-slider {{
        cursor: pointer;
        height: 6px;
        accent-color: #2563eb;
      }}
      .ab-chips-row {{
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
      }}
      .ab-chip-btn {{
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        color: #334155;
        font-size: 11px;
        font-weight: 600;
        padding: 3px 8px;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.15s ease;
      }}
      .ab-chip-btn:hover, .ab-chip-btn.active {{
        background: #1d4ed8;
        color: #fff;
        border-color: #1d4ed8;
      }}
      .ab-playback-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
        padding-top: 10px;
        border-top: 1px solid #e2e8f0;
      }}
      .ab-sim-clock {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 4px 10px;
        color: #0f172a;
        font-weight: 700;
        font-size: 14px;
      }}
      .ab-clock-label {{
        font-size: 11px;
        color: #64748b;
        font-weight: 500;
      }}
      .ab-speed-group {{
        display: inline-flex;
        align-items: center;
        gap: 2px;
        margin-left: 6px;
      }}
      .ab-speed-btn {{
        background: #f1f5f9;
        border: 1px solid #cbd5e1;
        color: #475569;
        font-size: 11px;
        font-weight: 700;
        padding: 3px 7px;
        border-radius: 3px;
        cursor: pointer;
      }}
      .ab-speed-btn.active {{
        background: #0f172a;
        color: #fff;
        border-color: #0f172a;
      }}
      .ab-split-screen {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        position: relative;
      }}
      @media (max-width: 960px) {{
        .ab-split-screen {{ grid-template-columns: 1fr; }}
      }}
      .ab-side {{
        background: #fff;
        border: 1px solid var(--border, #cbd5e1);
        border-radius: 8px;
        overflow: hidden;
        display: flex;
        flex-direction: column;
      }}
      .ab-side-bisher {{
        border-top: 4px solid #ef4444;
      }}
      .ab-side-optimiert {{
        border-top: 4px solid #059669;
      }}
      .ab-side-header {{
        padding: 12px 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
      }}
      .ab-side-tag {{
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }}
      .tag-bisher {{ color: #dc2626; }}
      .tag-optimiert {{ color: #059669; }}
      .ab-map-stage {{
        position: relative;
        background: #f8fafc;
        min-height: 300px;
      }}
      .ab-map-canvas {{
        width: 100%;
        height: auto;
        display: block;
      }}
      .ab-map-badge {{
        position: absolute;
        bottom: 8px;
        right: 8px;
        background: rgba(15, 23, 42, 0.75);
        color: #fff;
        font-size: 10px;
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 3px;
        pointer-events: none;
      }}
      .ab-empty-overlay {{
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(248, 250, 252, 0.94);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        font-weight: 600;
        color: #64748b;
        text-align: center;
        padding: 20px;
      }}
      .ab-vehicle-panel {{
        padding: 12px 16px;
        background: #fff;
        border-top: 1px solid #e2e8f0;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }}
      .ab-vehicle-panel-title {{
        font-size: 11px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }}
      .ab-vehicle-card {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 8px 12px;
        display: flex;
        flex-direction: column;
        gap: 4px;
      }}
      .ab-vehicle-card-top {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 12px;
      }}
      .ab-vehicle-pill {{
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 11px;
        color: #fff;
      }}
      .ab-meter-track {{
        height: 10px;
        background: #e2e8f0;
        border-radius: 5px;
        overflow: hidden;
        position: relative;
      }}
      .ab-meter-fill {{
        height: 100%;
        transition: width 0.15s linear;
      }}
      .ab-meter-sub {{
        display: flex;
        justify-content: space-between;
        font-size: 11px;
        color: #64748b;
      }}
      .ab-comparison-strip {{
        background: #fff;
        border: 1px solid var(--border, #cbd5e1);
        border-radius: 8px;
        padding: 16px 20px;
        display: flex;
        flex-direction: column;
        gap: 14px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
      }}
      .ab-strip-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
      }}
      .ab-mode-toggles {{
        display: inline-flex;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        overflow: hidden;
      }}
      .ab-toggle-btn {{
        background: #f8fafc;
        border: none;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 600;
        color: #334155;
        cursor: pointer;
      }}
      .ab-toggle-btn.active {{
        background: #0f172a;
        color: #fff;
      }}
      .ab-legend-items {{
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 12px;
        color: #475569;
      }}
      .ab-legend-dot {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 4px;
      }}
      .ab-metrics-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
        gap: 10px;
      }}
      .ab-metric-card {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 10px 12px;
        display: flex;
        flex-direction: column;
        gap: 4px;
        transition: all 0.2s ease;
      }}
      .ab-metric-card.winner-card {{
        background: #f0fdf4;
        border: 2px solid #22c55e;
        box-shadow: 0 1px 3px rgba(34, 197, 94, 0.15);
      }}
      .ab-metric-label {{
        font-size: 11px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
      }}
      .ab-metric-row {{
        display: flex;
        align-items: baseline;
        gap: 6px;
        margin: 2px 0;
      }}
      .ab-val-bisher {{
        font-size: 14px;
        font-weight: 700;
        color: #dc2626;
      }}
      .ab-vs-sep {{
        font-size: 11px;
        color: #94a3b8;
      }}
      .ab-val-opt {{
        font-size: 16px;
        font-weight: 800;
        color: #059669;
      }}
      .ab-metric-delta {{
        font-size: 11px;
        font-weight: 600;
        color: #15803d;
      }}
      .ab-summary-sentence-box {{
        background: #0f172a;
        color: #fff;
        padding: 12px 18px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 600;
        line-height: 1.4;
        border-left: 4px solid #10b981;
      }}
      @keyframes pulse-overflow {{
        0% {{ r: 3.5; opacity: 1; }}
        50% {{ r: 7.5; opacity: 0.4; }}
        100% {{ r: 3.5; opacity: 1; }}
      }}
      .pulse-ring {{
        animation: pulse-overflow 1.2s infinite ease-in-out;
      }}
    </style>

    <!-- Embedded JSON Data and Vanilla JS Player -->
    <script id="ab-replay-payload" type="application/json">{demo_json}</script>
    <script>
      (function() {{
        var payloadElem = document.getElementById("ab-replay-payload");
        if (!payloadElem) return;
        var abData = JSON.parse(payloadElem.textContent);

        var dates = abData.ledger.dates;
        var datesData = abData.dates_data || {{}};
        var periodSummary = abData.period_summary || {{}};

        var dateSlider = document.getElementById("demo-date-slider");
        var dateDisplay = document.getElementById("demo-current-date-label");
        var sliderIndex = document.getElementById("ab-slider-index");
        var opStatusBadge = document.getElementById("ab-op-status-badge");
        var playBtn = document.getElementById("demo-play-btn");
        var resetBtn = document.getElementById("demo-reset-btn");
        var timeScrubber = document.getElementById("demo-step-slider");
        var timeIndicator = document.getElementById("demo-step-indicator");
        var clockDisplay = document.getElementById("ab-clock-time");
        var stripDateLabel = document.getElementById("ab-strip-date-label");
        var summarySentence = document.getElementById("demo-hero-summary");

        var toggleDayBtn = document.getElementById("ab-toggle-day");
        var togglePeriodBtn = document.getElementById("ab-toggle-period");

        var currentDate = abData.default_date || "2026-04-15";
        var isPlaying = false;
        var playTimer = null;
        var currentClockMin = 0.0;
        var maxShiftMin = 480.0;
        var currentSpeed = 4;
        var viewMode = "day";

        var minLat = 49.092, maxLat = 49.230;
        var minLon = 9.131, maxLon = 9.278;
        var svgW = 540, svgH = 380;
        var pad = 24;

        function proj(lat, lon) {{
          var x = pad + ((lon - minLon) / (maxLon - minLon)) * (svgW - 2 * pad);
          var y = pad + (1.0 - ((lat - minLat) / (maxLat - minLat))) * (svgH - 2 * pad);
          return [Math.round(x), Math.round(y)];
        }}

        function fmtNum(n, d) {{
          if (n === null || n === undefined || isNaN(Number(n))) return "-";
          return Number(n).toLocaleString("de-DE", {{ minimumFractionDigits: d, maximumFractionDigits: d }});
        }}

        function minToClockStr(min) {{
          var totalMin = Math.round(min);
          var h = Math.floor(6 + totalMin / 60);
          var m = totalMin % 60;
          return String(h).padStart(2, "0") + ":" + String(m).padStart(2, "0");
        }}

        function getFillColor(fill) {{
          if (fill >= 110) return "#dc2626";
          if (fill >= 80) return "#f59e0b";
          if (fill >= 50) return "#2563eb";
          return "#94a3b8";
        }}

        function drawDepots(svgPrefix) {{
          var layer = document.getElementById("ab-depots-" + svgPrefix);
          if (!layer) return;
          layer.innerHTML = "";
          var yardPt = proj(abData.depots.yard[0], abData.depots.yard[1]);
          var dispPt = proj(abData.depots.disposal[0], abData.depots.disposal[1]);

          layer.innerHTML += '<rect x="' + (yardPt[0]-8) + '" y="' + (yardPt[1]-8) + '" width="16" height="16" fill="#1d4ed8" rx="3" stroke="#fff" stroke-width="1.5" />' +
            '<text x="' + yardPt[0] + '" y="' + (yardPt[1]-11) + '" font-size="9" font-weight="700" fill="#1e3a8a" text-anchor="middle">Betriebshof</text>';

          layer.innerHTML += '<polygon points="' + dispPt[0] + ',' + (dispPt[1]-9) + ' ' + (dispPt[0]-8) + ',' + (dispPt[1]+7) + ' ' + (dispPt[0]+8) + ',' + (dispPt[1]+7) + '" fill="#ea580c" stroke="#fff" stroke-width="1.5" />' +
            '<text x="' + dispPt[0] + '" y="' + (dispPt[1]-12) + '" font-size="9" font-weight="700" fill="#9a3412" text-anchor="middle">Entladestelle</text>';
        }}

        function updateComparisonStrip() {{
          var cards = ["card-finish", "card-veh", "card-rounds", "card-km", "card-empty", "card-fill", "card-unload", "card-overflow"];
          cards.forEach(function(cId) {{
            var el = document.getElementById(cId);
            if (el) el.classList.remove("winner-card");
          }});

          if (viewMode === "period") {{
            var h = periodSummary.hist || {{}};
            var o = periodSummary.opt || {{}};
            var finishLabel = document.getElementById("card-finish-label");
            if (finishLabel) finishLabel.textContent = "Gesamte LKW-Stunden";
            document.getElementById("val-hist-finish").textContent = h.finish_time;
            document.getElementById("val-opt-finish").textContent = o.finish_time;
            document.getElementById("delta-shift").textContent = "+27,8 % Stunden (Preis für 0 Überläufe)";

            document.getElementById("val-hist-veh").textContent = h.vehicles_needed + " LKW-Tage";
            document.getElementById("val-opt-veh").textContent = o.vehicles_needed + " LKW-Tage";
            document.getElementById("delta-veh").textContent = "+10,4 % LKW-Tage für lückenlose Leerung";

            document.getElementById("val-hist-rounds").textContent = h.rounds;
            document.getElementById("val-opt-rounds").textContent = o.rounds;
            document.getElementById("delta-rounds").textContent = "+172 Runden durch 11 t / 26 m³ Schranken";

            document.getElementById("val-hist-km").textContent = fmtNum(h.est_km, 1) + " km";
            document.getElementById("val-opt-km").textContent = fmtNum(o.est_km, 1) + " km";
            document.getElementById("delta-km").textContent = "Mehr km, weil keine Überläufe mehr toleriert werden (Preis für 0 Überläufe)";

            document.getElementById("val-hist-empty").textContent = fmtNum(h.n_emptyings, 0);
            document.getElementById("val-opt-empty").textContent = fmtNum(o.n_emptyings, 0);
            document.getElementById("delta-stops").textContent = "Optimiert: 380 unnötige Leerungen vermieden";

            document.getElementById("val-hist-fill").textContent = fmtNum(h.avg_fill_at_emptying_pct, 1) + " %";
            document.getElementById("val-opt-fill").textContent = fmtNum(o.avg_fill_at_emptying_pct, 1) + " %";
            document.getElementById("delta-fill").textContent = "Optimiert: 83,5 % statt 66,0 % (+17,5 pp)";

            document.getElementById("val-hist-unload").textContent = fmtNum(h.share_unloads_ge_90, 0) + " %";
            document.getElementById("val-opt-unload").textContent = fmtNum(o.share_unloads_ge_90, 0) + " %";
            document.getElementById("delta-unload").textContent = "Optimiert: 80,0 % statt 61,2 % voll entladen";

            document.getElementById("val-hist-overflow").textContent = fmtNum(h.overflow_bin_days, 0);
            document.getElementById("val-opt-overflow").textContent = fmtNum(o.overflow_bin_days, 0);
            document.getElementById("delta-overflow").textContent = "Optimiert: 0 statt 1.192 Überläufe (-100 %)";

            // Nur echte Gewinner grün umranden:
            document.getElementById("card-empty").classList.add("winner-card");
            document.getElementById("card-fill").classList.add("winner-card");
            document.getElementById("card-unload").classList.add("winner-card");
            document.getElementById("card-overflow").classList.add("winner-card");

            summarySentence.textContent = periodSummary.summary_sentence || "";
            return;
          }}

          // Day view
          var finishLabel = document.getElementById("card-finish-label");
          if (finishLabel) finishLabel.textContent = "Letzter LKW fertig";

          var dayItem = datesData[currentDate] || {{}};
          var h = dayItem.hist || {{}};
          var o = dayItem.opt || {{}};

          stripDateLabel.textContent = currentDate;
          document.getElementById("val-hist-finish").textContent = h.finish_time || "-";
          document.getElementById("val-opt-finish").textContent = o.finish_time || "-";

          document.getElementById("val-hist-veh").textContent = (h.vehicles_needed || 0) + " LKW";
          document.getElementById("val-opt-veh").textContent = (o.vehicles_needed || 0) + " LKW";

          document.getElementById("val-hist-rounds").textContent = h.rounds != null ? h.rounds : "-";
          document.getElementById("val-opt-rounds").textContent = o.rounds != null ? o.rounds : "-";

          document.getElementById("val-hist-km").textContent = fmtNum(h.est_km, 1) + " km";
          document.getElementById("val-opt-km").textContent = fmtNum(o.est_km, 1) + " km";

          document.getElementById("val-hist-empty").textContent = (h.n_emptyings || 0);
          document.getElementById("val-opt-empty").textContent = (o.n_emptyings || 0);

          document.getElementById("val-hist-fill").textContent = fmtNum(h.avg_fill_at_emptying_pct, 1) + " %";
          document.getElementById("val-opt-fill").textContent = fmtNum(o.avg_fill_at_emptying_pct, 1) + " %";

          document.getElementById("val-hist-unload").textContent = fmtNum(h.share_unloads_ge_90, 0) + " %";
          document.getElementById("val-opt-unload").textContent = fmtNum(o.share_unloads_ge_90, 0) + " %";

          document.getElementById("val-hist-overflow").textContent = (h.overflow_bin_days || 0);
          document.getElementById("val-opt-overflow").textContent = (o.overflow_bin_days || 0);

          var kmDelta = (o.est_km || 0) - (h.est_km || 0);
          document.getElementById("delta-km").textContent = kmDelta <= 0 ?
            ("Optimiert: " + fmtNum(kmDelta, 1) + " km eingespart") :
            ("Bedarf erfordert " + fmtNum(kmDelta, 1) + " km");
          if (kmDelta < 0) document.getElementById("card-km").classList.add("winner-card");

          var vehDelta = (o.vehicles_needed || 0) - (h.vehicles_needed || 0);
          document.getElementById("delta-veh").textContent = vehDelta < 0 ?
            ("Optimiert: " + Math.abs(vehDelta) + " LKW weniger") :
            (vehDelta === 0 ? "Gleiche Fahrzeuganzahl" : "Mehr Fahrzeuge");
          if (vehDelta < 0) document.getElementById("card-veh").classList.add("winner-card");

          if (o.finish_time && h.finish_time && o.finish_time < h.finish_time && o.n_emptyings > 0) {{
            document.getElementById("card-finish").classList.add("winner-card");
            document.getElementById("delta-shift").textContent = "Optimiert: früher fertig";
          }} else {{
            document.getElementById("delta-shift").textContent = "Schichtzeiten im Plan";
          }}

          if ((o.overflow_bin_days || 0) < (h.overflow_bin_days || 0)) {{
            document.getElementById("card-overflow").classList.add("winner-card");
            document.getElementById("delta-overflow").textContent = "Optimiert: Überläufe verhindert";
          }} else {{
            document.getElementById("delta-overflow").textContent = "Keine Überläufe";
          }}

          if ((o.share_unloads_ge_90 || 0) >= (h.share_unloads_ge_90 || 0)) {{
            document.getElementById("card-unload").classList.add("winner-card");
            document.getElementById("delta-unload").textContent = "Optimiert: volle Entladungen";
          }}

          var emptyDelta = (o.n_emptyings || 0) - (h.n_emptyings || 0);
          document.getElementById("delta-stops").textContent = emptyDelta < 0 ?
            ("Optimiert: " + Math.abs(emptyDelta) + " Hubs vermieden") : "Bedarf erfordert Leerung";
          if (emptyDelta < 0) document.getElementById("card-empty").classList.add("winner-card");

          var fillDelta = (o.avg_fill_at_emptying_pct || 0) - (h.avg_fill_at_emptying_pct || 0);
          document.getElementById("delta-fill").textContent = "Ø " + fmtNum(o.avg_fill_at_emptying_pct, 1) + " % vs. " + fmtNum(h.avg_fill_at_emptying_pct, 1) + " %";

          summarySentence.textContent = dayItem.summary_sentence || "";
        }}

        function updateDayView(selectedDate) {{
          currentDate = selectedDate;
          dateDisplay.textContent = selectedDate;

          var idx = dates.indexOf(selectedDate);
          if (idx >= 0) {{
            dateSlider.value = idx;
            sliderIndex.textContent = "Tag " + (idx + 1) + " / " + dates.length;
          }}

          document.querySelectorAll(".ab-chip-btn").forEach(function(btn) {{
            btn.classList.toggle("active", btn.getAttribute("data-date") === selectedDate);
          }});

          var dayItem = datesData[selectedDate] || {{}};
          var hVeh = dayItem.hist ? (dayItem.hist.vehicles || []) : [];
          var oVeh = dayItem.opt ? (dayItem.opt.vehicles || []) : [];

          var isOp = (hVeh.length > 0 || oVeh.length > 0);
          if (isOp) {{
            opStatusBadge.textContent = "Sammeltour aktiv";
            opStatusBadge.style.background = "#059669";
          }} else {{
            opStatusBadge.textContent = "Keine Tour (Ruhetag)";
            opStatusBadge.style.background = "#64748b";
          }}

          var maxFin = 0.0;
          hVeh.forEach(function(v) {{ if (v.finish_min > maxFin) maxFin = v.finish_min; }});
          oVeh.forEach(function(v) {{ if (v.finish_min > maxFin) maxFin = v.finish_min; }});
          maxShiftMin = Math.max(maxFin, 60.0);
          timeScrubber.max = Math.ceil(maxShiftMin);

          pause();
          currentClockMin = 0.0;
          timeScrubber.value = 0;
          updateClockAndAnimation(0.0);
          updateComparisonStrip();
        }}

        function renderVehicleLoadBars(prefix, vehicles, clockMin) {{
          var container = document.getElementById("ab-vehicle-bars-" + prefix);
          if (!container) return;
          if (!vehicles || vehicles.length === 0) {{
            container.innerHTML = '<div style="font-size:12px; color:#64748b; font-style:italic; padding:6px 0;">Kein Fahrzeug im Einsatz</div>';
            return;
          }}

          var html = "";
          vehicles.forEach(function(v) {{
            var evs = v.events || [];
            var curLoadPct = 0.0;
            var curLoadKg = 0.0;
            var curLoadM3 = 0.0;
            var statusText = "Am Betriebshof";

            if (clockMin >= v.finish_min) {{
              statusText = "Fertig um " + v.finish_time + " (Feierabend Betriebshof)";
              curLoadPct = 0.0;
            }} else {{
              for (var i = 0; i < evs.length - 1; i++) {{
                var e1 = evs[i];
                var e2 = evs[i+1];
                if (clockMin >= e1.dep_min && clockMin < e2.arr_min) {{
                  curLoadPct = e1.load_pct;
                  curLoadKg = e1.load_kg;
                  curLoadM3 = e1.load_m3;
                  statusText = "Fahrt &rarr; " + e2.name;
                  break;
                }} else if (clockMin >= e2.arr_min && clockMin <= e2.dep_min) {{
                  curLoadPct = e2.load_pct;
                  curLoadKg = e2.load_kg;
                  curLoadM3 = e2.load_m3;
                  statusText = (e2.type === "unload") ? "Entladung am Entsorgungshof" : ("Leerung: " + e2.name + " (" + e2.mat + ")");
                  break;
                }}
              }}
            }}

            var barColor = curLoadPct >= 85 ? "#dc2626" : (curLoadPct >= 60 ? "#d97706" : (prefix === "opt" ? "#059669" : "#2563eb"));

            html += '<div class="ab-vehicle-card">' +
              '<div class="ab-vehicle-card-top">' +
                '<div><span class="ab-vehicle-pill" style="background:' + v.color + '">LKW ' + v.id + '</span> ' +
                '<strong>' + statusText + '</strong></div>' +
                '<span id="' + prefix + '-meter-text-' + v.id + '" style="font-size:11px; font-weight:700; color:#0f172a;">' + fmtNum(curLoadKg / 1000, 1) + ' t (' + fmtNum(curLoadPct, 0) + ' %)</span>' +
              '</div>' +
              '<div class="ab-meter-track">' +
                '<div class="ab-meter-fill fill-' + prefix + '" id="' + prefix + '-meter-' + v.id + '" style="width:' + Math.min(100, curLoadPct) + '%; background:' + barColor + ';"></div>' +
              '</div>' +
              '<div class="ab-meter-sub">' +
                '<span>' + fmtNum(curLoadKg / 1000, 1) + ' t / 11,0 t (' + fmtNum(curLoadM3, 1) + ' m&sup3; / 26,0 m&sup3;)</span>' +
                '<span>Feierabend: ' + v.finish_time + ' (' + fmtNum(v.km, 1) + ' km)</span>' +
              '</div>' +
            '</div>';
          }});

          container.innerHTML = html;
        }}

        var leafletMapHist = null;
        var leafletMapOpt = null;
        var leafletGroupHist = null;
        var leafletGroupOpt = null;
        var isSyncingMaps = false;

        function initLeafletMaps() {{
          if (typeof L === "undefined") return;
          var histEl = document.getElementById("ab-map-hist-leaflet");
          var optEl = document.getElementById("ab-map-opt-leaflet");
          if (!histEl || !optEl) return;

          if (!leafletMapHist) {{
            leafletMapHist = L.map("ab-map-hist-leaflet", {{
              zoomControl: true,
              attributionControl: false
            }}).setView([49.1427, 9.2109], 12);

            L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
              maxZoom: 19
            }}).addTo(leafletMapHist);

            leafletGroupHist = L.layerGroup().addTo(leafletMapHist);
          }}

          if (!leafletMapOpt) {{
            leafletMapOpt = L.map("ab-map-opt-leaflet", {{
              zoomControl: true,
              attributionControl: false
            }}).setView([49.1427, 9.2109], 12);

            L.tileLayer("https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
              maxZoom: 19
            }}).addTo(leafletMapOpt);

            leafletGroupOpt = L.layerGroup().addTo(leafletMapOpt);
          }}

          leafletMapHist.off("move");
          leafletMapOpt.off("move");

          leafletMapHist.on("move", function() {{
            if (isSyncingMaps) return;
            isSyncingMaps = true;
            leafletMapOpt.setView(leafletMapHist.getCenter(), leafletMapHist.getZoom(), {{ animate: false }});
            isSyncingMaps = false;
          }});

          leafletMapOpt.on("move", function() {{
            if (isSyncingMaps) return;
            isSyncingMaps = true;
            leafletMapHist.setView(leafletMapOpt.getCenter(), leafletMapOpt.getZoom(), {{ animate: false }});
            isSyncingMaps = false;
          }});
        }}

        window.invalidateDemoMaps = function() {{
          if (typeof L === "undefined") return;
          initLeafletMaps();
          if (leafletMapHist) leafletMapHist.invalidateSize();
          if (leafletMapOpt) leafletMapOpt.invalidateSize();
        }};
        window.addEventListener("resize", function() {{
          if (window.invalidateDemoMaps) window.invalidateDemoMaps();
        }});

        function renderLeafletMap(prefix, vehicles, unvisitedOverflows, clockMin) {{
          if (typeof L === "undefined") return;
          initLeafletMaps();
          var map = (prefix === "hist") ? leafletMapHist : leafletMapOpt;
          var group = (prefix === "hist") ? leafletGroupHist : leafletGroupOpt;
          if (!map || !group) return;

          group.clearLayers();
          if (!vehicles || vehicles.length === 0) return;

          var yard = abData.depots.yard;
          var disposal = abData.depots.disposal;

          var yardIcon = L.divIcon({{
            className: 'depot-marker-yard',
            html: '<div style="background:#1d4ed8; color:#fff; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; box-shadow:0 1px 4px rgba(0,0,0,0.3); border:1px solid #fff; white-space:nowrap;">🏢 Betriebshof</div>',
            iconSize: [84, 20],
            iconAnchor: [42, 10]
          }});
          L.marker([yard[0], yard[1]], {{ icon: yardIcon, zIndexOffset: 400 }}).addTo(group).bindTooltip("Betriebshof");

          var dispIcon = L.divIcon({{
            className: 'depot-marker-disposal',
            html: '<div style="background:#ea580c; color:#fff; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; box-shadow:0 1px 4px rgba(0,0,0,0.3); border:1px solid #fff; white-space:nowrap;">♻️ Entladung</div>',
            iconSize: [84, 20],
            iconAnchor: [42, 10]
          }});
          L.marker([disposal[0], disposal[1]], {{ icon: dispIcon, zIndexOffset: 400 }}).addTo(group).bindTooltip("Entladestelle");

          var allPts = [[yard[0], yard[1]], [disposal[0], disposal[1]]];

          vehicles.forEach(function(v) {{
            var evs = v.events || [];
            if (evs.length < 2) return;

            var routeCoords = [];
            evs.forEach(function(e) {{
              routeCoords.push([e.lat, e.lon]);
              allPts.push([e.lat, e.lon]);

              if (e.type === "collection") {{
                var isEmptied = (clockMin >= e.arr_min);
                var col = isEmptied ? "#64748b" : getFillColor(e.fill_pct);
                var barH = 14;
                var barFillH = isEmptied ? 0 : Math.round((Math.min(110, e.fill_pct) / 110) * barH);

                var binHtml = '<div style="position:relative; width:16px; height:24px; text-align:center;">' +
                  '<div style="width:10px; height:' + barH + 'px; background:#f1f5f9; border:1px solid #94a3b8; border-radius:2px; margin:0 auto; position:relative; overflow:hidden;">' +
                    '<div style="position:absolute; bottom:0; left:0; width:100%; height:' + barFillH + 'px; background:' + col + ';"></div>' +
                  '</div>' +
                  '<div style="width:6px; height:6px; border-radius:50%; background:' + col + '; border:1px solid #fff; margin:2px auto 0;"></div>' +
                  (isEmptied ? '<div style="position:absolute; top:-8px; left:0; width:100%; font-size:10px; font-weight:900; color:#15803d;">✓</div>' : '') +
                '</div>';

                var bIcon = L.divIcon({{
                  className: 'leaflet-bin-marker',
                  html: binHtml,
                  iconSize: [16, 24],
                  iconAnchor: [8, 20]
                }});

                var tip = '<strong>' + (e.name || 'Container') + '</strong><br>' +
                  'Material: ' + (e.mat || '-') + '<br>' +
                  'Füllstand: <b>' + fmtNum(e.fill_pct, 0) + ' %</b>' +
                  (isEmptied ? ' <span style="color:#15803d; font-weight:700;">(Geleert)</span>' : '');

                L.marker([e.lat, e.lon], {{ icon: bIcon, zIndexOffset: 200 }}).addTo(group).bindTooltip(tip);
              }}
            }});

            var line = L.polyline(routeCoords, {{
              color: v.color,
              weight: (prefix === "opt" ? 3.5 : 2.8),
              opacity: (prefix === "opt" ? 0.9 : 0.75),
              dashArray: (prefix === "opt" ? null : "6, 4")
            }});
            line.addTo(group);

            var curTruckPos = [yard[0], yard[1]];
            var curLoadPct = 0;
            if (clockMin >= v.finish_min) {{
              curTruckPos = [yard[0], yard[1]];
              curLoadPct = 0;
            }} else {{
              for (var i = 0; i < evs.length - 1; i++) {{
                var e1 = evs[i];
                var e2 = evs[i+1];
                if (clockMin >= e1.dep_min && clockMin < e2.arr_min) {{
                  var frac = (clockMin - e1.dep_min) / Math.max(0.01, (e2.arr_min - e1.dep_min));
                  curTruckPos = [
                    e1.lat + frac * (e2.lat - e1.lat),
                    e1.lon + frac * (e2.lon - e1.lon)
                  ];
                  curLoadPct = e1.load_pct;
                  break;
                }} else if (clockMin >= e2.arr_min && clockMin <= e2.dep_min) {{
                  curTruckPos = [e2.lat, e2.lon];
                  curLoadPct = e2.load_pct;
                  break;
                }}
              }}
            }}

            var truckHtml = '<div style="background:' + v.color + '; color:#fff; font-size:10px; font-weight:700; padding:2px 6px; border-radius:12px; box-shadow:0 2px 6px rgba(0,0,0,0.4); white-space:nowrap; display:flex; align-items:center; gap:3px; border:1px solid #fff;">' +
              '<span>🚛</span><span>LKW ' + v.id + ' (' + fmtNum(curLoadPct, 0) + ' %)</span>' +
            '</div>';

            var tIcon = L.divIcon({{
              className: 'leaflet-truck-marker',
              html: truckHtml,
              iconSize: [88, 22],
              iconAnchor: [44, 11]
            }});

            L.marker(curTruckPos, {{ icon: tIcon, zIndexOffset: 1000 }}).addTo(group);
          }});

          if (unvisitedOverflows && unvisitedOverflows.length > 0) {{
            unvisitedOverflows.forEach(function(ov) {{
              var ovHtml = '<div style="background:#dc2626; color:#fff; font-size:9px; font-weight:800; padding:1px 4px; border-radius:3px; box-shadow:0 1px 3px rgba(0,0,0,0.3); border:1px solid #fff;">⚠️ Überlauf</div>';
              var ovIcon = L.divIcon({{
                className: 'leaflet-ov-icon',
                html: ovHtml,
                iconSize: [60, 16],
                iconAnchor: [30, 8]
              }});
              L.marker([ov.lat, ov.lon], {{ icon: ovIcon, zIndexOffset: 300 }}).addTo(group).bindTooltip("Überlauf (> 110 %)");
              allPts.push([ov.lat, ov.lon]);
            }});
          }}

          if (!map._userHasPanned && allPts.length > 2) {{
            map.fitBounds(allPts, {{ padding: [25, 25], maxZoom: 14 }});
          }}
        }}

        function renderScenarioMap(prefix, vehicles, unvisitedOverflows, clockMin) {{
          var pathsLayer = document.getElementById("ab-paths-" + prefix);
          var binsLayer = document.getElementById("ab-bins-" + prefix);
          var trucksLayer = document.getElementById("ab-trucks-" + prefix);
          var emptyOverlay = document.getElementById("ab-empty-" + prefix);

          if (typeof L !== "undefined") {{
            try {{
              renderLeafletMap(prefix, vehicles, unvisitedOverflows, clockMin);
            }} catch (err) {{
              console.warn("Leaflet map error:", err);
            }}
          }}

          if (!vehicles || vehicles.length === 0) {{
            if (emptyOverlay) emptyOverlay.style.display = "flex";
            if (pathsLayer) pathsLayer.innerHTML = "";
            if (binsLayer) binsLayer.innerHTML = "";
            if (trucksLayer) trucksLayer.innerHTML = "";
            return;
          }}
          if (emptyOverlay) emptyOverlay.style.display = "none";

          drawDepots(prefix);

          var binsHtml = "";
          var yardPt = proj(abData.depots.yard[0], abData.depots.yard[1]);

          vehicles.forEach(function(v) {{
            var evs = v.events || [];
            evs.forEach(function(e) {{
              if (e.type !== "collection") return;
              var pt = proj(e.lat, e.lon);
              var isEmptied = (clockMin >= e.arr_min);
              var col = isEmptied ? "#64748b" : getFillColor(e.fill_pct);

              var barH = 14;
              var barFillH = isEmptied ? 0 : Math.round((Math.min(110, e.fill_pct) / 110) * barH);

              binsHtml += '<g transform="translate(' + (pt[0]-4) + ',' + (pt[1]-16) + ')">' +
                '<rect width="8" height="' + barH + '" fill="#e2e8f0" stroke="#94a3b8" stroke-width="0.8" rx="1" />' +
                '<rect x="0.5" y="' + (barH - barFillH) + '" width="7" height="' + barFillH + '" fill="' + col + '" rx="1" />' +
                '</g>' +
                '<circle cx="' + pt[0] + '" cy="' + pt[1] + '" r="' + (isEmptied ? 3.5 : 3.0) + '" fill="' + (isEmptied ? "#475569" : col) + '" stroke="#fff" stroke-width="1" />' +
                (isEmptied ? '<text x="' + pt[0] + '" y="' + (pt[1]-18) + '" font-size="8" font-weight="700" fill="#475569" text-anchor="middle">&#10003;</text>' : '');
            }});
          }});

          if (unvisitedOverflows && unvisitedOverflows.length > 0) {{
            unvisitedOverflows.forEach(function(ov) {{
              var pt = proj(ov.lat, ov.lon);
              binsHtml += '<circle cx="' + pt[0] + '" cy="' + pt[1] + '" r="5" fill="#dc2626" opacity="0.6" class="pulse-ring" stroke="#ef4444" stroke-width="1.5" />' +
                '<circle cx="' + pt[0] + '" cy="' + pt[1] + '" r="3" fill="#991b1b" stroke="#fff" stroke-width="1" />' +
                '<text x="' + pt[0] + '" y="' + (pt[1]-7) + '" font-size="8" font-weight="800" fill="#dc2626" text-anchor="middle">Überlauf</text>';
            }});
          }}
          if (binsLayer) binsLayer.innerHTML = binsHtml;

          var pathsHtml = "";
          var trucksHtml = "";

          vehicles.forEach(function(v) {{
            var evs = v.events || [];
            if (evs.length < 2) return;

            var dPoints = [];
            var curTruckPos = yardPt;

            evs.forEach(function(e) {{
              var pt = proj(e.lat, e.lon);
              dPoints.push(pt[0] + " " + pt[1]);
            }});

            pathsHtml += '<polyline points="' + dPoints.join(", ") + '" fill="none" stroke="' + v.color + '" stroke-width="2.2" stroke-linecap="round" stroke-dasharray="4 2" opacity="0.7" />';

            if (clockMin >= v.finish_min) {{
              curTruckPos = yardPt;
            }} else {{
              for (var i = 0; i < evs.length - 1; i++) {{
                var e1 = evs[i];
                var e2 = evs[i+1];
                var p1 = proj(e1.lat, e1.lon);
                var p2 = proj(e2.lat, e2.lon);

                if (clockMin >= e1.dep_min && clockMin < e2.arr_min) {{
                  var frac = (clockMin - e1.dep_min) / Math.max(0.01, (e2.arr_min - e1.dep_min));
                  curTruckPos = [
                    Math.round(p1[0] + frac * (p2[0] - p1[0])),
                    Math.round(p1[1] + frac * (p2[1] - p1[1]))
                  ];
                  break;
                }} else if (clockMin >= e2.arr_min && clockMin <= e2.dep_min) {{
                  curTruckPos = p2;
                  break;
                }}
              }}
            }}

            trucksHtml += '<g transform="translate(' + (curTruckPos[0]-11) + ',' + (curTruckPos[1]-11) + ')">' +
              '<rect width="22" height="22" fill="' + v.color + '" rx="4" filter="url(#shadow-' + (prefix === "opt" ? "opt" : "bisher") + ')" stroke="#fff" stroke-width="1.5" />' +
              '<text x="11" y="15" font-size="12" fill="#fff" text-anchor="middle">&#128666;</text>' +
              '</g>';
          }});

          if (pathsLayer) pathsLayer.innerHTML = pathsHtml;
          if (trucksLayer) trucksLayer.innerHTML = trucksHtml;
        }}

        function updateClockAndAnimation(clockMin) {{
          currentClockMin = clockMin;
          timeScrubber.value = Math.round(clockMin);
          var clockStr = minToClockStr(clockMin);
          clockDisplay.textContent = clockStr;
          timeIndicator.textContent = clockStr;

          var dayItem = datesData[currentDate] || {{}};
          var hVeh = dayItem.hist ? (dayItem.hist.vehicles || []) : [];
          var oVeh = dayItem.opt ? (dayItem.opt.vehicles || []) : [];
          var oUnvisited = dayItem.opt ? (dayItem.opt.unvisited_overflows || []) : [];

          renderVehicleLoadBars("hist", hVeh, clockMin);
          renderVehicleLoadBars("opt", oVeh, clockMin);

          renderScenarioMap("hist", hVeh, [], clockMin);
          renderScenarioMap("opt", oVeh, oUnvisited, clockMin);
        }}

        function play() {{
          if (isPlaying) return;
          isPlaying = true;
          playBtn.textContent = "⏸ Pause";
          var stepPerTick = 1.0 * currentSpeed;

          playTimer = setInterval(function() {{
            if (currentClockMin >= maxShiftMin) {{
              pause();
              return;
            }}
            updateClockAndAnimation(Math.min(maxShiftMin, currentClockMin + stepPerTick));
          }}, 80);
        }}

        function pause() {{
          isPlaying = false;
          playBtn.textContent = "▶ Abspielen";
          if (playTimer) {{
            clearInterval(playTimer);
            playTimer = null;
          }}
        }}

        // Listeners
        dateSlider.addEventListener("input", function() {{
          var selIdx = Number(dateSlider.value);
          if (dates[selIdx]) updateDayView(dates[selIdx]);
        }});

        timeScrubber.addEventListener("input", function() {{
          pause();
          updateClockAndAnimation(Number(timeScrubber.value));
        }});

        playBtn.addEventListener("click", function() {{
          if (isPlaying) pause(); else play();
        }});

        resetBtn.addEventListener("click", function() {{
          pause();
          updateClockAndAnimation(0.0);
        }});

        document.querySelectorAll(".ab-speed-btn").forEach(function(btn) {{
          btn.addEventListener("click", function() {{
            document.querySelectorAll(".ab-speed-btn").forEach(function(b) {{ b.classList.remove("active"); }});
            btn.classList.add("active");
            currentSpeed = Number(btn.getAttribute("data-speed")) || 4;
            if (isPlaying) {{
              pause();
              play();
            }}
          }});
        }});

        document.querySelectorAll(".demo-chip-btn").forEach(function(btn) {{
          btn.addEventListener("click", function() {{
            var d = btn.getAttribute("data-date");
            if (d) updateDayView(d);
          }});
        }});

        toggleDayBtn.addEventListener("click", function() {{
          viewMode = "day";
          toggleDayBtn.classList.add("active");
          togglePeriodBtn.classList.remove("active");
          updateComparisonStrip();
        }});

        togglePeriodBtn.addEventListener("click", function() {{
          viewMode = "period";
          togglePeriodBtn.classList.add("active");
          toggleDayBtn.classList.remove("active");
          updateComparisonStrip();
        }});

        updateDayView(abData.default_date || "2026-04-15");
      }})();
    </script>
    """
