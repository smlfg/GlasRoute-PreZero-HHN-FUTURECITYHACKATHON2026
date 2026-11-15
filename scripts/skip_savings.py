"""Zeitersparnis, wenn Container mit Fuellstand <= 20 % NICHT geleert werden (Mentor 15.11.).

Status quo, welt-konsistenter Replay (W1): Fuellstand beim Besuch = r_c x Tage seit letztem Besuch.
Das Glas bleibt stehen und wird spaeter geholt - es geht NICHT verloren.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pandas as pd

from prezero.sim.cost import RATES, scenario_cost

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("simulate_daily", ROOT / "scripts" / "simulate_daily.py")
sd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sd)

THRESH = 20.0
SERVICE_MIN = 5.0
URBAN_HOP_MIN = 7.0
RURAL_HOP_MIN = 15.0
SHIFT_H = 8.0
CENTRE = (49.1427, 9.2109)
RURAL_KM = 6.0


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def summarize(v: pd.DataFrame, fill_col: str) -> dict:
    """v: visits (2nd reading on) with fill, mass_t, rural, site_all_low columns."""
    low = v[v[fill_col] <= THRESH]
    n = len(low)
    service_h = n * SERVICE_MIN / 60.0
    hop_min = low["rural"].map(lambda r: RURAL_HOP_MIN if r else URBAN_HOP_MIN)
    hop_upper_h = float(hop_min.sum()) / 60.0
    hop_site_h = float(hop_min[low["site_all_low"]].sum()) / 60.0
    out = {
        "n_visits": int(len(v)),
        "n_visits_le_20pct": int(n),
        "share_pct": round(100.0 * n / len(v), 2),
        "tonnage_in_those_visits_t": round(float(low["mass_t"].sum()), 3),
        "tonnage_note": "Glas bleibt im Container stehen und wird beim naechsten Besuch geholt - nicht verloren.",
    }
    for label, hours in (
        ("lower_bound_service_only", service_h),
        ("site_aware_service_plus_hop_if_whole_site_skipped", service_h + hop_site_h),
        ("upper_bound_service_plus_hop", service_h + hop_upper_h),
    ):
        out[label] = {
            "saved_service_h": round(service_h, 2),
            "saved_drive_h": round(hours - service_h, 2),
            "saved_total_h": round(hours, 2),
            "saved_truck_days": round(hours / SHIFT_H, 2),
            "saved_cost_eur": scenario_cost(hours / SHIFT_H, hours, 0.0)["total_eur"],
        }
    return out


def main() -> None:
    readings = pd.read_csv(ROOT / "data/processed/cleaned_readings.csv")
    locs = pd.read_csv(ROOT / "data/external/locations.csv").drop_duplicates("Location_id").set_index("Location_id")
    rates = sd.true_fill_rates(readings)
    cfg = sd.OperationalConfig()

    df = readings.copy()
    df["Location_id"] = df["Location_id"].astype(str)
    df["material_type"] = df["material_type"].astype(str).str.lower()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["Location_id", "material_type", "date"])
    g = df.groupby(["Location_id", "material_type"])
    df["days"] = g["date"].diff().dt.days
    df["order"] = g.cumcount()
    v = df[df["order"] >= 1].copy()  # 1st reading = system start, not an emptying

    v["model_fill"] = [
        rates[(l, m)] * d for l, m, d in zip(v["Location_id"], v["material_type"], v["days"])
    ]
    v["mass_t"] = [sd._mass_kg(f, m, cfg) / 1000.0 for f, m in zip(v["model_fill"], v["material_type"])]
    v["mass_meas_t"] = [
        sd._mass_kg(float(f), m, cfg) / 1000.0 for f, m in zip(v["fill_level_numeric"], v["material_type"])
    ]

    def rural(loc):
        if loc not in locs.index:
            return False
        r = locs.loc[loc]
        return haversine_km(CENTRE[0], CENTRE[1], float(r["lat"]), float(r["lon"])) > RURAL_KM

    v["rural"] = v["Location_id"].map(rural)

    def with_site(frame, fill_col):
        f = frame.copy()
        f["_low"] = f[fill_col] <= THRESH
        f["site_all_low"] = f.groupby(["Location_id", "date"])["_low"].transform("all")
        return f

    model = summarize(with_site(v, "model_fill"), "model_fill")
    meas = v.rename(columns={"mass_meas_t": "_m"}).copy()
    meas["mass_t"] = meas["_m"]
    measured = summarize(with_site(meas, "fill_level_numeric"), "fill_level_numeric")

    out = {
        "question": "Zeitersparnis im Status quo, wenn Container mit Fuellstand <= 20 % nicht geleert werden (Mentor 15.11.)",
        "primary_world_consistent_replay": model,
        "cross_check_raw_measured_readings": {
            "label": "Kreuzprobe mit gemessenen Fuellstaenden (level <= 20), nicht weltkonsistent",
            **measured,
        },
        "reference_status_quo_emptyings_w1": 10363,
        "assumptions": {
            "service_min_per_stop": SERVICE_MIN,
            "hop_urban_min": URBAN_HOP_MIN,
            "hop_rural_min": RURAL_HOP_MIN,
            "rural_rule": f"Annahme: Abstand zum Zentrum Heilbronn {CENTRE} > {RURAL_KM} km = laendlich (W4 besitzt die verbindliche Regel)",
            "shift_h": SHIFT_H,
            "rates": RATES,
            "rates_label": "Annahme",
            "km_note": "km unbekannt -> 0 angesetzt; Kosten = Fahrzeugtage + Crew-h",
            "bounds": "lower = nur 5 min Service (andere Container am Standort werden ohnehin geleert); "
            "upper = Service + Fahrzeit-Hop je uebersprungenem Stopp; site_aware = Hop nur, wenn alle Container des Standorts am Tag <= 20 %.",
        },
    }
    dest = ROOT / "data/outputs/scenarios/skip_savings.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
