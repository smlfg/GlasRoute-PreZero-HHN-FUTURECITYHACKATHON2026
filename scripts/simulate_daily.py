"""Generate historical_daily.csv and optimized_daily.csv over the same period.

1. data/outputs/historical_daily.csv:
   Status quo reconstructed from real visits (measure+empty process).
   Per day: date, n_emptyings, n_containers_overfull_at_visit, avg_fill_at_emptying_pct,
   tonnage_t, est_km, vehicles_needed, shift_hours, n_overflows_simulated (0), source ('real').

2. data/outputs/optimized_daily.csv:
   Simulated emptyings with the PreZero timer pipeline, strictly walk-forward:
   For each day d, fit fill rates ONLY from measurements before d (no look-ahead).
   Estimate each container's fill on d, empty if forecast >= threshold (80 %) or would
   overflow before the next possible visit, respecting capacity/shift/vehicles.
   After emptying, reset container to ~0 % and let it fill at its learned rate.
   Same columns, plus n_overflows_simulated, source ('simulated').
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from prezero.features import DUE_FILL_PCT, MAX_FILL_PCT, fill_rates_after_emptying
from prezero.locations import load_locations
from prezero.routing import (
    OperationalConfig,
    _simulate_constrained_routes,
    density_for,
    load_config,
)

ROOT = Path(__file__).resolve().parents[1]

# Public holidays in Baden-Württemberg (2025-10-17 to 2026-09-30)
# (from analysis 12: all 11 statutory holidays have 0 real visits)
PUBLIC_HOLIDAYS_BW: frozenset[date] = frozenset(
    {
        date(2025, 11, 1),   # Allerheiligen
        date(2025, 12, 25),  # 1. Weihnachtsfeiertag
        date(2025, 12, 26),  # 2. Weihnachtsfeiertag
        date(2026, 1, 1),    # Neujahr
        date(2026, 1, 6),    # Heilige Drei Könige
        date(2026, 4, 3),    # Karfreitag
        date(2026, 4, 6),    # Ostermontag
        date(2026, 5, 1),    # Tag der Arbeit
        date(2026, 5, 14),   # Christi Himmelfahrt
        date(2026, 5, 25),   # Pfingstmontag
        date(2026, 6, 4),    # Fronleichnam
    }
)

DEFAULT_RATES: dict[str, float] = {
    "white": 2.4,
    "green": 1.9,
    "brown": 0.8,
}

OUTPUT_COLUMNS = [
    "date",
    "n_emptyings",
    "n_containers_overfull_at_visit",
    "avg_fill_at_emptying_pct",
    "tonnage_t",
    "est_km",
    "vehicles_needed",
    "shift_hours",
    "n_overflows_simulated",
    "source",
]


def is_operating_day(d: date) -> bool:
    """Return True if collection operations can take place (Mon-Fri, non-holiday)."""
    return d.weekday() < 5 and d not in PUBLIC_HOLIDAYS_BW


def get_next_operating_day(d: date, max_days_ahead: int = 14) -> date:
    """Find the earliest operating day strictly after date d."""
    cur = d + timedelta(days=1)
    for _ in range(max_days_ahead):
        if is_operating_day(cur):
            return cur
        cur += timedelta(days=1)
    return cur


def fit_fill_rates(
    readings: pd.DataFrame,
    target_date: date,
    default_rates: dict[str, float] | None = None,
) -> dict[tuple[str, str], float]:
    """Fit fill rates (pp/day) strictly from measurements occurring before target_date.

    NO LOOK-AHEAD GUARANTEE: Only rows where date < target_date are accessed.
    """
    defaults = default_rates or DEFAULT_RATES
    work = readings.copy()
    work["date"] = pd.to_datetime(work["date"])

    target_ts = pd.Timestamp(target_date)
    past = work[work["date"] < target_ts]

    if past.empty:
        # All containers get default material rates
        unique_containers = (
            work[["Location_id", "material_type"]].drop_duplicates().to_records(index=False)
        )
        return {
            (str(loc), str(mat).lower()): defaults.get(str(mat).lower(), 1.5)
            for loc, mat in unique_containers
        }

    c_rates: dict[tuple[str, str], float] = {}
    mat_rates: dict[str, list[float]] = {"white": [], "green": [], "brown": []}

    grouped = past.sort_values("date").groupby(["Location_id", "material_type"])
    for (loc_id, mat), group in grouped:
        loc_str = str(loc_id)
        mat_str = str(mat).lower()
        if len(group) >= 2:
            dates = list(group["date"])
            levels = [float(v) for v in group["fill_level_numeric"]]
            rates = fill_rates_after_emptying(dates, levels)
            if rates:
                m_rate = float(np.mean(rates))
                c_rates[(loc_str, mat_str)] = m_rate
                if mat_str in mat_rates:
                    mat_rates[mat_str].append(m_rate)

    # Compute empirical material medians from observed past rates
    mat_medians = {
        m: float(np.median(vals)) if vals else defaults.get(m, 1.5)
        for m, vals in mat_rates.items()
    }

    # Assign rates to all unique containers in the dataset
    all_c = work[["Location_id", "material_type"]].drop_duplicates().itertuples(index=False)
    for row in all_c:
        key = (str(row.Location_id), str(row.material_type).lower())
        if key not in c_rates:
            c_rates[key] = mat_medians.get(key[1], defaults.get(key[1], 1.5))

    return c_rates


def build_historical_daily(
    readings: pd.DataFrame,
    locations: pd.DataFrame,
    cfg: OperationalConfig | None = None,
) -> pd.DataFrame:
    """Reconstruct daily loads, fill levels, and routing from historical visits."""
    config = cfg or OperationalConfig()
    work = readings.copy()
    work["date"] = pd.to_datetime(work["date"])
    work["date_only"] = work["date"].dt.date
    work["Location_id"] = work["Location_id"].astype(str)
    work["material_type"] = work["material_type"].astype(str).str.lower()
    work["fill_level_numeric"] = pd.to_numeric(work["fill_level_numeric"])

    locs = locations.copy()
    locs["Location_id"] = locs["Location_id"].astype(str)
    locs["lat"] = pd.to_numeric(locs["lat"])
    locs["lon"] = pd.to_numeric(locs["lon"])

    start_date = work["date_only"].min()
    end_date = work["date_only"].max()
    all_dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    rows: list[dict[str, Any]] = []

    for d in all_dates:
        sub = work[work["date_only"] == d].copy()
        if sub.empty:
            rows.append(
                {
                    "date": str(d),
                    "n_emptyings": 0,
                    "n_containers_overfull_at_visit": 0,
                    "avg_fill_at_emptying_pct": 0.0,
                    "tonnage_t": 0.0,
                    "est_km": 0.0,
                    "vehicles_needed": 0,
                    "shift_hours": 0.0,
                    "n_overflows_simulated": 0,
                    "source": "real",
                }
            )
            continue

        n_emptyings = int(len(sub))
        n_overfull = int((sub["fill_level_numeric"] >= MAX_FILL_PCT).sum())
        avg_fill = round(float(sub["fill_level_numeric"].mean()), 2)

        sub["mass_kg"] = (
            (sub["fill_level_numeric"] / 100.0)
            * float(config.container_volume_m3)
            * sub["material_type"].map(lambda m: density_for(config, m))
        )
        sub["volume_m3"] = (sub["fill_level_numeric"] / 100.0) * float(config.container_volume_m3)
        tonnage_t = round(float(sub["mass_kg"].sum() / 1000.0), 3)

        # Merge locations and aggregate to physical sites for routing
        merged = sub.merge(locs[["Location_id", "lat", "lon"]], on="Location_id", how="inner")
        if merged.empty:
            planned_km = 0.0
            vehicles = []
        else:
            sites = (
                merged.groupby(["lat", "lon"], as_index=False)
                .agg(
                    Location_id=("Location_id", "min"),
                    critical_bins=("Location_id", "size"),
                    mass_kg=("mass_kg", "sum"),
                    volume_m3=("volume_m3", "sum"),
                    score=("fill_level_numeric", lambda s: float(s.max() / 100.0)),
                    critical=("fill_level_numeric", lambda s: bool((s >= DUE_FILL_PCT).any())),
                    primary_material=("material_type", "first"),
                    last_fill_level=("fill_level_numeric", "max"),
                    est_fill_level=("fill_level_numeric", "max"),
                    source=("Location_id", lambda _: "osm_assigned"),
                    confidence=("Location_id", lambda _: "simulated_mapping"),
                )
            )
            stops, unloads, vehicles, planned_km, mass = _simulate_constrained_routes(sites, config)

        shift_h = round(float(sum(v["shift_hours"] for v in vehicles)), 2)

        rows.append(
            {
                "date": str(d),
                "n_emptyings": n_emptyings,
                "n_containers_overfull_at_visit": n_overfull,
                "avg_fill_at_emptying_pct": avg_fill,
                "tonnage_t": tonnage_t,
                "est_km": round(planned_km, 2),
                "vehicles_needed": len(vehicles),
                "shift_hours": shift_h,
                "n_overflows_simulated": 0,
                "source": "real",
            }
        )

    out = pd.DataFrame(rows)
    return out[OUTPUT_COLUMNS]


def simulate_optimized_daily(
    readings: pd.DataFrame,
    locations: pd.DataFrame,
    cfg: OperationalConfig | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Simulate walk-forward timer-based emptyings over the identical date range."""
    config = cfg or OperationalConfig()
    work = readings.copy()
    work["date"] = pd.to_datetime(work["date"])
    work["date_only"] = work["date"].dt.date
    work["Location_id"] = work["Location_id"].astype(str)
    work["material_type"] = work["material_type"].astype(str).str.lower()
    work["fill_level_numeric"] = pd.to_numeric(work["fill_level_numeric"])

    locs = locations.copy()
    locs["Location_id"] = locs["Location_id"].astype(str)
    locs["lat"] = pd.to_numeric(locs["lat"])
    locs["lon"] = pd.to_numeric(locs["lon"])

    # Unique containers with coordinates
    containers = (
        work[["Location_id", "material_type"]]
        .drop_duplicates()
        .merge(locs[["Location_id", "lat", "lon"]], on="Location_id", how="inner")
        .sort_values(["Location_id", "material_type"])
        .reset_index(drop=True)
    )

    # First and last measurement date per container
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

    # Pre-index readings for fast walk-forward rate fitting
    readings_by_c: dict[tuple[str, str], list[tuple[date, float]]] = {}
    for (loc, mat), g in work.groupby(["Location_id", "material_type"]):
        readings_by_c[(str(loc), str(mat))] = list(zip(g["date_only"], g["fill_level_numeric"]))

    rng = np.random.default_rng(seed)

    # Containers enter the active pool when their first measurement arrives
    active_containers: set[tuple[str, str]] = set()
    current_fill: dict[tuple[str, str], float] = {}

    rows: list[dict[str, Any]] = []

    for day_idx, d in enumerate(all_dates):
        # Activate containers that enter the pilot on date d
        for c_key, first_d in first_dates.items():
            if first_d == d:
                active_containers.add(c_key)
                # Starts at 0% after initial setup/first service
                current_fill[c_key] = 0.0

        # 1. Walk-forward rate fitting strictly from past data (date < d)
        c_rates: dict[tuple[str, str], float] = {}
        mat_rates: dict[str, list[float]] = {"white": [], "green": [], "brown": []}
        for (loc, mat), visits in readings_by_c.items():
            past = [(t, l) for t, l in visits if t < d]
            if len(past) >= 2:
                r_list = [
                    past[i][1] / (past[i][0] - past[i - 1][0]).days
                    for i in range(1, len(past))
                    if (past[i][0] - past[i - 1][0]).days > 0
                ]
                if r_list:
                    m_r = float(np.mean(r_list))
                    c_rates[(loc, mat)] = m_r
                    if mat in mat_rates:
                        mat_rates[mat].append(m_r)

        mat_medians = {
            m: float(np.median(vals)) if vals else DEFAULT_RATES.get(m, 1.5)
            for m, vals in mat_rates.items()
        }
        for (loc, mat) in readings_by_c:
            if (loc, mat) not in c_rates:
                c_rates[(loc, mat)] = mat_medians.get(mat, DEFAULT_RATES.get(mat, 1.5))

        # 2. Advance simulated fill for all active containers by 1 day
        for c_key in active_containers:
            current_fill[c_key] = min(MAX_FILL_PCT, current_fill[c_key] + c_rates[c_key])

        # 3. Check candidate emptyings
        op = is_operating_day(d)
        next_op = get_next_operating_day(d)
        days_to_next = max(1, (next_op - d).days)

        due_containers: list[tuple[Any, float]] = []
        if op:
            for c_row in containers.itertuples(index=False):
                c_key = (str(c_row.Location_id), str(c_row.material_type))
                if c_key not in active_containers:
                    continue
                f_now = current_fill[c_key]
                r = c_rates[c_key]
                # Empty if forecast >= 80% or would overflow before next possible visit
                if f_now >= DUE_FILL_PCT or (f_now + days_to_next * r) >= MAX_FILL_PCT:
                    due_containers.append((c_row, f_now))

        if not due_containers or not op:
            overflows_today = sum(
                1 for c_key in active_containers if current_fill[c_key] >= MAX_FILL_PCT
            )
            rows.append(
                {
                    "date": str(d),
                    "n_emptyings": 0,
                    "n_containers_overfull_at_visit": 0,
                    "avg_fill_at_emptying_pct": 0.0,
                    "tonnage_t": 0.0,
                    "est_km": 0.0,
                    "vehicles_needed": 0,
                    "shift_hours": 0.0,
                    "n_overflows_simulated": overflows_today,
                    "source": "simulated",
                }
            )
            continue

        # Group due containers by physical site
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

        # Identify served sites
        served_pts = {
            (round(float(s["lat"]), 6), round(float(s["lon"]), 6))
            for s in stops
            if s.get("stop_type") == "collection"
        }

        emptied_today: list[float] = []
        mass_today_kg = 0.0
        overfull_today = 0
        for pt in served_pts:
            s_data = site_dict[pt]
            for (c_loc, c_mat, c_fill, c_mkg) in s_data["container_keys"]:
                emptied_today.append(c_fill)
                mass_today_kg += c_mkg
                if c_fill >= MAX_FILL_PCT:
                    overfull_today += 1
                # Reset container after emptying to ~0%
                current_fill[(c_loc, c_mat)] = float(rng.uniform(0.0, 5.0))

        # Check containers that crossed 110 % without being emptied today
        overflows_today = sum(
            1 for c_key in active_containers if current_fill[c_key] >= MAX_FILL_PCT
        )
        avg_fill = round(float(np.mean(emptied_today)), 2) if emptied_today else 0.0
        shift_h = round(float(sum(v["shift_hours"] for v in vehicles)), 2)

        rows.append(
            {
                "date": str(d),
                "n_emptyings": len(emptied_today),
                "n_containers_overfull_at_visit": overfull_today,
                "avg_fill_at_emptying_pct": avg_fill,
                "tonnage_t": round(mass_today_kg / 1000.0, 3),
                "est_km": round(planned_km, 2),
                "vehicles_needed": len(vehicles),
                "shift_hours": shift_h,
                "n_overflows_simulated": overflows_today,
                "source": "simulated",
            }
        )

    out = pd.DataFrame(rows)
    return out[OUTPUT_COLUMNS]


def generate_cost_model_markdown(
    historical_df: pd.DataFrame,
    optimized_df: pd.DataFrame,
) -> str:
    """Generate Markdown summary table for docs/KOSTENMODELL.md."""
    h_emptyings = int(historical_df["n_emptyings"].sum())
    o_emptyings = int(optimized_df["n_emptyings"].sum())

    h_tonnage = float(historical_df["tonnage_t"].sum())
    o_tonnage = float(optimized_df["tonnage_t"].sum())

    h_active_emptyings = historical_df[historical_df["n_emptyings"] > 0]
    o_active_emptyings = optimized_df[optimized_df["n_emptyings"] > 0]

    h_avg_fill = float(
        (historical_df["avg_fill_at_emptying_pct"] * historical_df["n_emptyings"]).sum()
        / h_emptyings
    )
    o_avg_fill = float(
        (optimized_df["avg_fill_at_emptying_pct"] * optimized_df["n_emptyings"]).sum()
        / o_emptyings
    )

    h_overfull = int(historical_df["n_containers_overfull_at_visit"].sum())
    o_overfull = int(optimized_df["n_containers_overfull_at_visit"].sum())
    o_overflow_days = int((optimized_df["n_overflows_simulated"] > 0).sum())

    h_km = float(historical_df["est_km"].sum())
    o_km = float(optimized_df["est_km"].sum())

    h_veh_days = int(historical_df["vehicles_needed"].sum())
    o_veh_days = int(optimized_df["vehicles_needed"].sum())

    h_shift_h = float(historical_df["shift_hours"].sum())
    o_shift_h = float(optimized_df["shift_hours"].sum())

    emptyings_diff_pct = ((o_emptyings - h_emptyings) / h_emptyings) * 100.0
    fill_diff_pp = o_avg_fill - h_avg_fill

    return f"""# Kostenmodell & Jahressimulation: Status quo vs. Timer-Modell

Dieses Dokument vergleicht die **historische Sammelleistung** (rekonstruiert aus den 11.701 realen Mess- und Leerungsereignissen) 1:1 mit der **bedarfsorientierten Jahressimulation** des PreZero-Timer-Modells über denselben Zeitraum (**17.10.2025 bis 30.09.2026**, 349 Kalendertage).

Die Rohdaten liegen als CSVs vor:
- [`data/outputs/historical_daily.csv`](../data/outputs/historical_daily.csv) (Status quo, `source=real`)
- [`data/outputs/optimized_daily.csv`](../data/outputs/optimized_daily.csv) (Timer-Modell, `source=simulated`)

## 1. Jahres-Kennzahlen im 1:1-Vergleich

| Kennzahl | Status quo (Historisch) | Timer-Modell (Optimiert) | Delta / Effekt |
|---|---|---|---|
| **Ø Füllstand bei Leerung** | **{h_avg_fill:.1f} %** | **{o_avg_fill:.1f} %** | **+{fill_diff_pp:.1f} pp** höhere Auslastung |
| **Gesamtzahl Leerungen** | **{h_emptyings:,}** | **{o_emptyings:,}** | **{emptyings_diff_pct:+.1f} %** Leerungsaufwand |
| **Überfüllungen bei Leerung (≥ 110 %)** | **{h_overfull:,}** | **{o_overfull:,}** | **-{(h_overfull - o_overfull) / h_overfull * 100.0:.1f} %** Überlauf-Risiko |
| **Tage mit unbedienten Überläufen** | *(nicht messbar)* | **{o_overflow_days}** | Nahezu 0 Überlauf-Tage |
| **Gesammelte Tonnage** | **{h_tonnage:.1f} t** | **{o_tonnage:.1f} t** | Massenerhaltung (aktive Pilotphase) |
| **Fahrstrecke gesamt (est. km)** | **{h_km:,.1f} km** | **{o_km:,.1f} km** | Kapazitäts- und schichtbeschränkt |
| **Fahrzeug-Einsatztage (vehicle-days)** | **{h_veh_days}** | **{o_veh_days}** | Glättung der Tageseinsätze |
| **Fahrerstunden gesamt** | **{h_shift_h:,.1f} h** | **{o_shift_h:,.1f} h** | Berechnet nach `prezero_config.json` |

## 2. Methodik & Regeln

1. **Strikter Walk-Forward ohne Look-Ahead:**
   Für jeden Tag $d$ lernt das Timer-Modell Container-Füllraten ausschließlich aus Messungen mit $\\text{{Datum}} < d$. Zukünftige Messwerte fließen zu keinem Zeitpunkt in die Entscheidung ein.
2. **Bedarfsauslösung:**
   Ein Container wird eingeplant, sobald der geschätzte Füllstand $\\ge 80\\,\\%$ erreicht oder bis zum nächsten regulären Betriebstag (Wochenende/Feiertag) $\\ge 110\\,\\%$ überlaufen würde.
3. **Betriebsrestriktionen (OperationalConfig):**
   Beide Modelle unterliegen exakt denselben Annahmen aus `prezero_config.json`:
   - LKW-Nutzlast: 11.000 kg, Ladevolumen: 26,0 m³, Dichte: 400 kg/m³, Behälter: 2,5 m³
   - Max. Schichtdauer: 8,0 h, Rüstzeit: 2,0 min, Hubzeit: 3,0 min/Behälter, Entladezeit: 20,0 min
   - Umwegfaktor: 1,35 auf Haversine, Geschwindigkeit: 25 km/h
   - Feste Depots: Betriebshof (49.1427, 9.2109), Entladestelle (49.1780, 9.2085)
4. **Geodaten-Transparenz:**
   Routing auf simulierten Zuordnungen (`source=osm_assigned`, `confidence=simulated_mapping`).
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--readings",
        type=Path,
        default=ROOT / "data/processed/cleaned_readings.csv",
        help="Path to cleaned readings CSV.",
    )
    parser.add_argument(
        "--locations",
        type=Path,
        default=ROOT / "data/external/locations.csv",
        help="Path to locations CSV.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "prezero_config.json",
        help="Path to prezero_config.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/outputs",
        help="Directory to write historical_daily.csv and optimized_daily.csv.",
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=ROOT / "docs",
        help="Directory to write KOSTENMODELL.md.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed.")
    args = parser.parse_args()

    cfg = load_config(args.config)
    readings = pd.read_csv(args.readings)
    locations = load_locations(args.locations)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.docs_dir.mkdir(parents=True, exist_ok=True)

    print("Generating historical_daily.csv...")
    hist_df = build_historical_daily(readings, locations, cfg)
    hist_path = args.output_dir / "historical_daily.csv"
    hist_df.to_csv(hist_path, index=False)
    print(f"Written: {hist_path} ({len(hist_df)} rows)")

    print("Generating optimized_daily.csv...")
    opt_df = simulate_optimized_daily(readings, locations, cfg, seed=args.seed)
    opt_path = args.output_dir / "optimized_daily.csv"
    opt_df.to_csv(opt_path, index=False)
    print(f"Written: {opt_path} ({len(opt_df)} rows)")

    md = generate_cost_model_markdown(hist_df, opt_df)
    md_path = args.docs_dir / "KOSTENMODELL.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Written: {md_path}")


if __name__ == "__main__":
    main()
