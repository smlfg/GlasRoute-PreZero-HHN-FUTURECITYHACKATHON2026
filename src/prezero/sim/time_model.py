"""Zeitmodell fuer einen Einsatztag (Mentor 15.11.): Fahrzeit je Hop + Service + Entladen + Schichtgrenze.

Reihenfolge und km kommen unveraendert aus ``routing._simulate_constrained_routes`` (km bleibt
vergleichbar); die ZEIT wird hier nach den Mentor-Regeln neu berechnet und die Stopps werden
entsprechend Kapazitaet (11 t / 26 m3 -> Entladefahrt) und Schicht (max_shift_hours -> weiteres
Fahrzeug) neu gepackt. Kein Stopp wird je verworfen, es gibt keine Flottenobergrenze.

Modi:
  real  : Hop = 15 min wenn ein Endpunkt laendlich, sonst 7 min; Depotwege = road_km / avg_speed.
  hop5  : jeder Weg (auch Depotwege) kostet 5 min  -> isoliert Fuellstand-Auswahl von Geografie.
  hop10 : jeder Weg (auch Depotwege) kostet 10 min.

Formeln je Fahrzeug (Minuten):
  t = leg(yard->s1) + sum_i service + sum_i leg(s_i->s_i+1)
      + sum_unloads [leg(s->disposal) + unload_min + leg(disposal->s_next) - leg(s->s_next)]
      + leg(s_n->yard)
Eine Entladefahrt ersetzt den direkten Hop s->s_next durch s->disposal->s_next.
Das letzte Fahrzeugende faehrt direkt zum Hof (wie im bestehenden Routing, keine Schluss-Entladung).
"""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from prezero.routing import OperationalConfig, _simulate_constrained_routes, haversine_km, road_distance_km

HEILBRONN_CENTRE = (49.1427, 9.2109)  # Annahme
FLEIN_CENTRE = (49.103, 9.211)  # Annahme
LAUFFEN_CENTRE = (49.073, 9.150)  # Annahme
URBAN_RADIUS_KM = 7.0  # Annahme
FLEIN_RADIUS_KM = 2.0  # Annahme
LAUFFEN_RADIUS_KM = 2.5  # Annahme

MENTOR_DEFAULTS: dict[str, dict[str, Any]] = {
    "service_min": {"value": 5.0, "unit": "min/Stopp", "source": "Mentor 15.11. (unabhaengig vom Fuellstand)"},
    "urban_hop_min": {"value": 7.0, "unit": "min/Hop", "source": "Mentor 15.11. (Heilbronn)"},
    "rural_hop_min": {"value": 15.0, "unit": "min/Hop", "source": "Mentor 15.11. (Flein, Lauffen, aeussere Orte)"},
    "unload_min": {"value": 20.0, "unit": "min", "source": "Config OperationalConfig.unload_time_min (Annahme)"},
    "max_shift_hours": {"value": 8.0, "unit": "h", "source": "Config OperationalConfig.max_shift_hours (Annahme)"},
    "vehicle_max_weight_kg": {"value": 11000.0, "unit": "kg", "source": "Mentor 15.11. / Config"},
    "vehicle_max_volume_m3": {"value": 26.0, "unit": "m3", "source": "Mentor 15.11. / Config"},
    "hop5_min": {"value": 5.0, "unit": "min/Hop", "source": "Normierter Modus (Annahme)"},
    "hop10_min": {"value": 10.0, "unit": "min/Hop", "source": "Normierter Modus (Annahme)"},
    "depot_leg_real": {"value": "road_distance_km / avg_speed_kmh", "unit": "min", "source": "Config (Annahme: 1,35 / 25 km/h)"},
    "urban_radius_km": {"value": URBAN_RADIUS_KM, "unit": "km", "source": "Annahme (klassifikation)"},
}

MODES = ("real", "hop5", "hop10")


def classify_area(lat: float, lon: float) -> str:
    """Return "urban" or "rural" (Annahme, keine amtliche Abgrenzung).

    Regel: laendlich, wenn (a) mehr als 7 km Luftlinie vom Zentrum Heilbronn (49.1427, 9.2109),
    oder (b) innerhalb 2 km um Flein (49.103, 9.211), oder (c) innerhalb 2,5 km um Lauffen
    (49.073, 9.150). Sonst staedtisch (Heilbronn).
    """
    if haversine_km(lat, lon, *HEILBRONN_CENTRE) > URBAN_RADIUS_KM:
        return "rural"
    if haversine_km(lat, lon, *FLEIN_CENTRE) <= FLEIN_RADIUS_KM:
        return "rural"
    if haversine_km(lat, lon, *LAUFFEN_CENTRE) <= LAUFFEN_RADIUS_KM:
        return "rural"
    return "urban"


_REQUIRED_DEFAULTS: dict[str, Any] = {
    "Location_id": "",
    "score": 0.0,
    "critical": False,
    "primary_material": "glass",
    "last_fill_level": 0.0,
    "est_fill_level": 0.0,
    "source": "sim",
    "confidence": "high",
    "critical_bins": 1,
    "volume_m3": 0.0,
}


def _empty() -> dict[str, Any]:
    return {"stops": 0, "km": 0.0, "vehicles": 0, "hours": 0.0, "unloads": 0, "depot_trips": 0,
            "drive_h": 0.0, "service_h": 0.0, "unload_h": 0.0}


def make_evaluator(
    mode: str = "real",
    cfg: OperationalConfig | None = None,
    service_min: float = 5.0,
    urban_hop_min: float = 7.0,
    rural_hop_min: float = 15.0,
    depot_leg_min: float | None = None,
) -> Callable[[pd.DataFrame, OperationalConfig], dict]:
    """Build ``evaluate_day(sites_df, cfg) -> dict`` for mode real/hop5/hop10.

    Returned keys: stops, km, vehicles, hours (sum over vehicles, incl. drive+service+unload),
    unloads, depot_trips (= vehicles + unloads: Fahrten zum Hof bzw. Entsorgungsdepot),
    drive_h, service_h, unload_h. ``cfg`` here is the default if evaluate_day gets cfg=None.
    ``depot_leg_min``: fixed minutes per depot leg in real mode (else road_km/avg_speed).
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    default_cfg = cfg

    def evaluate_day(sites_df: pd.DataFrame, cfg: OperationalConfig | None = None) -> dict:
        c = cfg or default_cfg or OperationalConfig()
        if sites_df is None or len(sites_df) == 0:
            return _empty()
        df = sites_df.copy()
        for col, val in _REQUIRED_DEFAULTS.items():
            if col not in df.columns:
                df[col] = val
        if "Location_id" in df.columns and (df["Location_id"] == "").all():
            df["Location_id"] = [f"s{i}" for i in range(len(df))]
        stops, _unl, _veh, km, _mass = _simulate_constrained_routes(df, c)
        coll = [s for s in stops if s["stop_type"] == "collection"]
        # Order as produced by routing (order field already sequential).
        coll.sort(key=lambda s: s["order"])
        pts = [(float(s["lat"]), float(s["lon"])) for s in coll]
        rural = [classify_area(a, b) == "rural" for a, b in pts]
        w = [float(s["mass_kg"]) for s in coll]
        v = [float(s["volume_m3"]) for s in coll]

        yard, disp = tuple(c.yard_depot), tuple(c.disposal_depot)

        def depot_leg(p: tuple[float, float], q: tuple[float, float]) -> float:
            if mode == "hop5":
                return 5.0
            if mode == "hop10":
                return 10.0
            if depot_leg_min is not None:
                return float(depot_leg_min)
            return road_distance_km(p[0], p[1], q[0], q[1], c) / float(c.avg_speed_kmh) * 60.0

        def hop(i: int, j: int) -> float:
            if mode == "hop5":
                return 5.0
            if mode == "hop10":
                return 10.0
            return float(rural_hop_min if (rural[i] or rural[j]) else urban_hop_min)

        cap_min = float(c.max_shift_hours) * 60.0
        unload_min = float(c.unload_time_min)
        drive = service = unload = 0.0
        vehicles = unloads = 0
        veh_time = 0.0  # current vehicle total minutes (without return leg)
        n_in_veh = 0
        prev = -1
        load_w = load_v = 0.0
        total_minutes = 0.0

        def close() -> None:
            nonlocal veh_time, n_in_veh, prev, load_w, load_v, total_minutes, drive, vehicles
            back = depot_leg(pts[prev], yard)
            drive += back
            total_minutes += veh_time + back
            vehicles += 1
            veh_time, n_in_veh, prev, load_w, load_v = 0.0, 0, -1, 0.0, 0.0

        i = 0
        while i < len(coll):
            full = n_in_veh > 0 and (
                load_w + w[i] > float(c.vehicle_max_weight_kg) or load_v + v[i] > float(c.vehicle_max_volume_m3)
            )
            if full:
                to_disp = depot_leg(pts[prev], disp)
                from_disp = depot_leg(disp, pts[i])
                need = to_disp + unload_min + from_disp + service_min + depot_leg(pts[i], yard)
                if veh_time + need <= cap_min:
                    veh_time += to_disp + unload_min + from_disp + service_min
                    drive += to_disp + from_disp
                    unload += unload_min
                    service += service_min
                    unloads += 1
                    load_w, load_v = w[i], v[i]
                    prev = i
                    n_in_veh += 1
                    i += 1
                else:
                    close()
                continue
            if n_in_veh == 0:
                leg = depot_leg(yard, pts[i])
            else:
                leg = hop(prev, i)
            proj = veh_time + leg + service_min + depot_leg(pts[i], yard)
            if n_in_veh > 0 and proj > cap_min:
                close()
                continue
            veh_time += leg + service_min
            drive += leg
            service += service_min
            load_w += w[i]
            load_v += v[i]
            prev = i
            n_in_veh += 1
            i += 1
        if n_in_veh > 0:
            close()

        return {
            "stops": len(coll),
            "km": float(km),
            "vehicles": vehicles,
            "hours": total_minutes / 60.0,
            "unloads": unloads,
            "depot_trips": vehicles + unloads,
            "drive_h": drive / 60.0,
            "service_h": service / 60.0,
            "unload_h": unload / 60.0,
        }

    return evaluate_day
