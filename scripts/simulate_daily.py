"""Generate historical_daily.csv and optimized_daily.csv over the same period.

One world, two policies (docs/MODEL_SPEC.md §1): ``true_fill_rates`` is the fixed
ground-truth demand r_c of every container (ratio of sums over the real readings).
Both sides are replayed against it, start at 0 % at the container's first reading,
reset to exactly 0 % after an emptying and are never capped (110 % only counts an
overflow event). ``mass_ledger(df)`` returns produced / collected / end stock per side
with collected + end_stock == produced == ``produced_total(readings)``.

1. data/outputs/historical_daily.csv (status quo, source='real'):
   the REAL visit dates of each container replayed against the world; each visit
   collects the model fill. n_overflows_simulated is 0 (overflow container-days of the
   status quo are reported in the ledger / docs/KOSTENMODELL.md).

2. data/outputs/optimized_daily.csv (timer policy, source='simulated'):
   the decision rule only sees walk-forward rate estimates from readings with date < d
   (no look-ahead) and empties when the believed fill is >= 80 % or would reach 110 %
   before the next operating day; the truck collects the TRUE fill of the world.
   n_overflows_simulated = container-days with true fill >= 110 %.

Columns: date, n_emptyings, n_containers_overfull_at_visit, avg_fill_at_emptying_pct
(uncapped, may exceed 100 %), tonnage_t (collected in the window), est_km,
vehicles_needed, shift_hours, n_overflows_simulated, source.
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


ContainerKey = tuple[str, str]


def _prepare_inputs(
    readings: pd.DataFrame, locations: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, list[date]]:
    """Normalise readings/locations and return the replay calendar (first..last reading day)."""
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
    return work, locs, all_dates


def true_fill_rates(readings: pd.DataFrame) -> dict[ContainerKey, float]:
    """Ground-truth glass demand per container in %-points of the container per day.

    WORLD, NOT BELIEF (docs/MODEL_SPEC.md §1/§2): this is the demand that *generates*
    glass in every scenario. It uses the whole data set on purpose (the world is fixed);
    decision rules must never read it, they only see walk-forward estimates.

    r_c = Σ level_i / Σ Δt_i over the intervals from the 2nd reading on (ratio of sums;
    each visit empties the container, so level_i is the glass of interval i). This is
    unbiased for a constant rate, unlike the mean of quotients (+15.5 %). Replaying the
    real visit dates against r_c therefore reproduces the measured in-window mass
    Σ_{i≥2} level_i exactly. Containers with < 2 readings get the median rate of their
    material (falls back to DEFAULT_RATES if a material has no fitted container).
    """
    work = readings.copy()
    work["date"] = pd.to_datetime(work["date"])
    work["Location_id"] = work["Location_id"].astype(str)
    work["material_type"] = work["material_type"].astype(str).str.lower()
    work["fill_level_numeric"] = pd.to_numeric(work["fill_level_numeric"])

    rates: dict[ContainerKey, float] = {}
    by_material: dict[str, list[float]] = {}
    for (loc, mat), group in work.sort_values("date").groupby(["Location_id", "material_type"]):
        key = (str(loc), str(mat))
        if len(group) < 2:
            continue
        levels = group["fill_level_numeric"].to_numpy(dtype=float)[1:]
        span_days = (group["date"].iloc[-1] - group["date"].iloc[0]).days
        if span_days <= 0:
            continue
        rate = float(levels.sum() / span_days)
        rates[key] = rate
        by_material.setdefault(key[1], []).append(rate)

    medians = {m: float(np.median(v)) for m, v in by_material.items()}
    for row in work[["Location_id", "material_type"]].drop_duplicates().itertuples(index=False):
        key = (str(row.Location_id), str(row.material_type))
        if key not in rates:
            rates[key] = medians.get(key[1], DEFAULT_RATES.get(key[1], 1.5))
    return rates


def _mass_kg(fill_pct: float, material: str, config: OperationalConfig) -> float:
    """Collected mass for a fill level; uncapped (overflow glass is picked up too)."""
    return (fill_pct / 100.0) * float(config.container_volume_m3) * density_for(config, material)


def _produced_kg(
    world: dict[ContainerKey, float],
    first_dates: dict[ContainerKey, date],
    end_date: date,
    config: OperationalConfig,
) -> float:
    """Glass produced in the window: r_c per day from the day after the first reading on."""
    return float(
        sum(
            _mass_kg(world[c] * (end_date - first_d).days, c[1], config)
            for c, first_d in first_dates.items()
        )
    )


def produced_total(readings: pd.DataFrame, cfg: OperationalConfig | None = None) -> float:
    """Total glass (t) the world produces in the replay window, identical for every scenario.

    produced = Σ_c r_c × active_days_c, active days = window end − first reading of c
    (production starts the day after the first reading, starting stock 0). Every
    scenario must reconcile to it: collected_t + end_stock_t == produced_total.
    """
    config = cfg or OperationalConfig()
    work = readings.copy()
    work["date_only"] = pd.to_datetime(work["date"]).dt.date
    work["Location_id"] = work["Location_id"].astype(str)
    work["material_type"] = work["material_type"].astype(str).str.lower()
    first_dates = {
        (str(loc), str(mat)): d
        for (loc, mat), d in work.groupby(["Location_id", "material_type"])["date_only"].min().items()
    }
    world = true_fill_rates(work)
    return _produced_kg(world, first_dates, work["date_only"].max(), config) / 1000.0


def _empty_row(source: str, overflows: int = 0) -> dict[str, Any]:
    return {
        "n_emptyings": 0,
        "n_containers_overfull_at_visit": 0,
        "avg_fill_at_emptying_pct": 0.0,
        "tonnage_t": 0.0,
        "est_km": 0.0,
        "vehicles_needed": 0,
        "shift_hours": 0.0,
        "n_overflows_simulated": overflows,
        "source": source,
    }


def _ledger(
    produced_kg: float,
    collected_kg: float,
    end_stock_kg: float,
    overflow_container_days: int,
    n_emptyings: int,
    fill_sum_pct: float,
    n_fill: int,
) -> dict[str, float]:
    return {
        "produced_t": produced_kg / 1000.0,
        "collected_t": collected_kg / 1000.0,
        "end_stock_t": end_stock_kg / 1000.0,
        "overflow_container_days": int(overflow_container_days),
        "n_emptyings": int(n_emptyings),
        "avg_fill_at_emptying_pct": fill_sum_pct / n_fill if n_fill else 0.0,
    }


def mass_ledger(daily: pd.DataFrame) -> dict[str, float]:
    """Mass ledger of a replay frame: produced_t, collected_t, end_stock_t (+ overflow days).

    Invariant (exact up to float rounding, per side): collected_t + end_stock_t == produced_t.
    collected_t is the unrounded sum; daily ``tonnage_t`` is rounded to 3 decimals.
    """
    ledger = daily.attrs.get("ledger")
    if ledger is None:
        raise ValueError("frame has no mass ledger (only frames fresh from build_*/simulate_*)")
    return dict(ledger)


def build_historical_daily(
    readings: pd.DataFrame,
    locations: pd.DataFrame,
    cfg: OperationalConfig | None = None,
) -> pd.DataFrame:
    """Status quo: replay the REAL visit dates of every container against the world model.

    Mass accounting (docs/MODEL_SPEC.md §1, identical boundary to the simulation):
    - glass is generated by ``true_fill_rates`` (r_c per day) from the day after the
      container's first reading; the stock at the first reading is 0 (pre-window glass,
      776 t, is outside the system boundary on BOTH sides);
    - the first reading is the START of the system boundary (like the simulation, which
      activates the container there at 0 %): it is not an emptying, not routed and carries
      no mass on either side. Hence n_emptyings = readings − containers = 11,701 − 1,338
      = 10,363. (Counting it as a 0-mass emptying would keep 11,701 but break every
      CSV-weighted average fill: n_emptyings × avg_fill would no longer equal Σ fill.)
    - every later visit collects the current model fill (uncapped) and resets it to exactly 0;
      fill ≥ 110 % at a visit counts as overfull; glass left after the last visit is end stock.
    ``n_overflows_simulated`` stays 0 (column reserved for the simulation); the world's
    overflow container-days of the status quo are in ``mass_ledger(df)``.
    """
    config = cfg or OperationalConfig()
    work, locs, all_dates = _prepare_inputs(readings, locations)
    world = true_fill_rates(work)
    coords = locs.drop_duplicates("Location_id").set_index("Location_id")[["lat", "lon"]]

    visits_by_day: dict[date, list[ContainerKey]] = {}
    first_dates: dict[ContainerKey, date] = {}
    for row in work.sort_values("date").itertuples(index=False):
        key = (str(row.Location_id), str(row.material_type))
        first_dates.setdefault(key, row.date_only)
        visits_by_day.setdefault(row.date_only, []).append(key)
    activation: dict[date, list[ContainerKey]] = {}
    for key, first_d in first_dates.items():
        activation.setdefault(first_d, []).append(key)

    fill: dict[ContainerKey, float] = {}
    collected_kg = 0.0
    overflow_days = 0
    fill_sum = 0.0
    n_fill = 0
    n_total = 0
    rows: list[dict[str, Any]] = []

    for d in all_dates:
        for key in fill:  # glass produced on day d (containers active since an earlier day)
            fill[key] += world[key]
        for key in activation.get(d, []):
            fill[key] = 0.0

        # first reading = activation (boundary start), not an in-window emptying
        day_visits = [k for k in visits_by_day.get(d, []) if first_dates[k] != d]
        if not day_visits:
            overflows = sum(1 for v in fill.values() if v >= MAX_FILL_PCT)
            overflow_days += overflows
            rows.append({"date": str(d), **_empty_row("real")})
            continue

        recs: list[dict[str, Any]] = []
        day_fills: list[float] = []
        for key in day_visits:
            f_val = fill[key]
            m_kg = _mass_kg(f_val, key[1], config)
            recs.append(
                {
                    "Location_id": key[0],
                    "material_type": key[1],
                    "fill": f_val,
                    "mass_kg": m_kg,
                    "volume_m3": (f_val / 100.0) * float(config.container_volume_m3),
                }
            )
            day_fills.append(f_val)
            collected_kg += m_kg
            fill[key] = 0.0
        overflow_days += sum(1 for v in fill.values() if v >= MAX_FILL_PCT)

        sub = pd.DataFrame(recs)
        n_total += len(sub)
        fill_sum += float(sum(day_fills))
        n_fill += len(day_fills)

        merged = sub.join(coords, on="Location_id", how="inner")
        if merged.empty:
            planned_km = 0.0
            vehicles: list[dict[str, Any]] = []
        else:
            sites = merged.groupby(["lat", "lon"], as_index=False).agg(
                Location_id=("Location_id", "min"),
                critical_bins=("Location_id", "size"),
                mass_kg=("mass_kg", "sum"),
                volume_m3=("volume_m3", "sum"),
                score=("fill", lambda s: float(s.max() / 100.0)),
                critical=("fill", lambda s: bool((s >= DUE_FILL_PCT).any())),
                primary_material=("material_type", "first"),
                last_fill_level=("fill", "max"),
                est_fill_level=("fill", "max"),
                source=("Location_id", lambda _: "osm_assigned"),
                confidence=("Location_id", lambda _: "simulated_mapping"),
            )
            _stops, _unloads, vehicles, planned_km, _mass = _simulate_constrained_routes(
                sites, config
            )

        rows.append(
            {
                "date": str(d),
                "n_emptyings": int(len(sub)),
                "n_containers_overfull_at_visit": int((sub["fill"] >= MAX_FILL_PCT).sum()),
                "avg_fill_at_emptying_pct": round(float(np.mean(day_fills)), 2)
                if day_fills
                else 0.0,
                "tonnage_t": round(float(sub["mass_kg"].sum()) / 1000.0, 3),
                "est_km": round(planned_km, 2),
                "vehicles_needed": len(vehicles),
                "shift_hours": round(float(sum(v["shift_hours"] for v in vehicles)), 2),
                "n_overflows_simulated": 0,
                "source": "real",
            }
        )

    end_stock_kg = float(sum(_mass_kg(v, k[1], config) for k, v in fill.items()))
    produced_kg = _produced_kg(world, first_dates, all_dates[-1], config)
    out = pd.DataFrame(rows)[OUTPUT_COLUMNS]
    out.attrs["ledger"] = _ledger(
        produced_kg, collected_kg, end_stock_kg, overflow_days, n_total, fill_sum, n_fill
    )
    return out


def simulate_optimized_daily(
    readings: pd.DataFrame,
    locations: pd.DataFrame,
    cfg: OperationalConfig | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Walk-forward timer policy over the identical date range, against the same world.

    - TRUTH: glass is generated by ``true_fill_rates`` (same r_c and same start as the
      status quo: from the day after the container's first reading, starting at 0).
    - BELIEF: the decision rule only sees rates estimated from readings with date < d
      (mean of level/Δt per container, material median fallback) and its own believed
      fill (estimated rate accumulated since the last emptying). No look-ahead.
    - A due container (belief ≥ 80 % or belief would reach 110 % before the next
      operating day) is routed; served containers hand over their TRUE fill mass
      (uncapped) and reset to exactly 0. Fill ≥ 110 % counts as an overflow event
      (per container-day, ``n_overflows_simulated``), it is never capped.
    ``seed`` is kept for API compatibility; the simulation is deterministic.
    """
    del seed  # deterministic: no random reset any more (was +283 t phantom mass)
    config = cfg or OperationalConfig()
    work, locs, all_dates = _prepare_inputs(readings, locations)
    world = true_fill_rates(work)

    containers = (
        work[["Location_id", "material_type"]]
        .drop_duplicates()
        .merge(locs[["Location_id", "lat", "lon"]].drop_duplicates("Location_id"), on="Location_id", how="inner")
        .sort_values(["Location_id", "material_type"])
        .reset_index(drop=True)
    )
    first_dates: dict[ContainerKey, date] = {
        (str(r.Location_id), str(r.material_type)): r.min_date
        for r in work.groupby(["Location_id", "material_type"])["date_only"]
        .min()
        .reset_index(name="min_date")
        .itertuples(index=False)
    }
    activation: dict[date, list[ContainerKey]] = {}
    for key, first_d in first_dates.items():
        activation.setdefault(first_d, []).append(key)

    readings_by_c: dict[ContainerKey, list[tuple[date, float]]] = {}
    for (loc, mat), g in work.sort_values("date").groupby(["Location_id", "material_type"]):
        readings_by_c[(str(loc), str(mat))] = list(zip(g["date_only"], g["fill_level_numeric"]))

    true_fill: dict[ContainerKey, float] = {}
    belief_fill: dict[ContainerKey, float] = {}
    collected_kg = 0.0
    overflow_days = 0
    fill_sum = 0.0
    n_total = 0
    rows: list[dict[str, Any]] = []

    for d in all_dates:
        # 1. Belief: walk-forward rate estimates strictly from readings before d
        c_rates: dict[ContainerKey, float] = {}
        mat_rates: dict[str, list[float]] = {"white": [], "green": [], "brown": []}
        for key, visits in readings_by_c.items():
            past = [(t, lvl) for t, lvl in visits if t < d]
            if len(past) >= 2:
                r_list = [
                    past[i][1] / (past[i][0] - past[i - 1][0]).days
                    for i in range(1, len(past))
                    if (past[i][0] - past[i - 1][0]).days > 0
                ]
                if r_list:
                    m_r = float(np.mean(r_list))
                    c_rates[key] = m_r
                    mat_rates.setdefault(key[1], []).append(m_r)
        mat_medians = {
            m: float(np.median(v)) if v else DEFAULT_RATES.get(m, 1.5) for m, v in mat_rates.items()
        }
        for key in readings_by_c:
            if key not in c_rates:
                c_rates[key] = mat_medians.get(key[1], DEFAULT_RATES.get(key[1], 1.5))

        # 2. World produces glass on day d; belief advances by the estimated rate
        for key in true_fill:
            true_fill[key] += world[key]
            belief_fill[key] += c_rates[key]
        for key in activation.get(d, []):
            true_fill[key] = 0.0
            belief_fill[key] = 0.0

        # 3. Decision on belief only
        op = is_operating_day(d)
        days_to_next = max(1, (get_next_operating_day(d) - d).days)
        due: list[Any] = []
        if op:
            for c_row in containers.itertuples(index=False):
                key = (str(c_row.Location_id), str(c_row.material_type))
                if key not in true_fill:
                    continue
                b_now = belief_fill[key]
                if b_now >= DUE_FILL_PCT or (b_now + days_to_next * c_rates[key]) >= MAX_FILL_PCT:
                    due.append(c_row)

        if not due:
            overflows = sum(1 for v in true_fill.values() if v >= MAX_FILL_PCT)
            overflow_days += overflows
            rows.append({"date": str(d), **_empty_row("simulated", overflows)})
            continue

        site_dict: dict[tuple[float, float], dict[str, Any]] = {}
        for c_row in due:
            key = (str(c_row.Location_id), str(c_row.material_type))
            pt = (round(float(c_row.lat), 6), round(float(c_row.lon), 6))
            f_true = true_fill[key]
            score = belief_fill[key] / 100.0
            m_kg = _mass_kg(f_true, key[1], config)
            v_m3 = (f_true / 100.0) * float(config.container_volume_m3)
            if pt not in site_dict:
                site_dict[pt] = {
                    "lat": pt[0],
                    "lon": pt[1],
                    "Location_id": key[0],
                    "critical_bins": 0,
                    "mass_kg": 0.0,
                    "volume_m3": 0.0,
                    "score": score,
                    "critical": True,
                    "primary_material": key[1],
                    "last_fill_level": belief_fill[key],
                    "est_fill_level": belief_fill[key],
                    "source": "osm_assigned",
                    "confidence": "simulated_mapping",
                    "container_keys": [],
                }
            site = site_dict[pt]
            site["critical_bins"] += 1
            site["mass_kg"] += m_kg  # the truck carries the real glass, not the belief
            site["volume_m3"] += v_m3
            site["score"] = max(site["score"], score)
            site["container_keys"].append(key)

        sites_df = (
            pd.DataFrame(list(site_dict.values()))
            .sort_values("score", ascending=False)
            .reset_index(drop=True)
        )
        stops, _unloads, vehicles, planned_km, _mass = _simulate_constrained_routes(
            sites_df, config
        )
        served_pts = {
            (round(float(s["lat"]), 6), round(float(s["lon"]), 6))
            for s in stops
            if s.get("stop_type") == "collection"
        }

        emptied: list[float] = []
        mass_today_kg = 0.0
        for pt in served_pts:
            for key in site_dict[pt]["container_keys"]:
                f_true = true_fill[key]
                emptied.append(f_true)
                mass_today_kg += _mass_kg(f_true, key[1], config)
                true_fill[key] = 0.0
                belief_fill[key] = 0.0
        collected_kg += mass_today_kg
        n_total += len(emptied)
        fill_sum += float(sum(emptied))

        overflows = sum(1 for v in true_fill.values() if v >= MAX_FILL_PCT)
        overflow_days += overflows
        rows.append(
            {
                "date": str(d),
                "n_emptyings": len(emptied),
                "n_containers_overfull_at_visit": int(sum(1 for f in emptied if f >= MAX_FILL_PCT)),
                "avg_fill_at_emptying_pct": round(float(np.mean(emptied)), 2) if emptied else 0.0,
                "tonnage_t": round(mass_today_kg / 1000.0, 3),
                "est_km": round(planned_km, 2),
                "vehicles_needed": len(vehicles),
                "shift_hours": round(float(sum(v["shift_hours"] for v in vehicles)), 2),
                "n_overflows_simulated": overflows,
                "source": "simulated",
            }
        )

    end_stock_kg = float(sum(_mass_kg(v, k[1], config) for k, v in true_fill.items()))
    produced_kg = _produced_kg(
        world, {k: v for k, v in first_dates.items() if k in true_fill}, all_dates[-1], config
    )
    out = pd.DataFrame(rows)[OUTPUT_COLUMNS]
    out.attrs["ledger"] = _ledger(
        produced_kg, collected_kg, end_stock_kg, overflow_days, n_total, fill_sum, n_total
    )
    return out


def generate_cost_model_markdown(
    historical_df: pd.DataFrame,
    optimized_df: pd.DataFrame,
) -> str:
    """Generate Markdown summary table for docs/KOSTENMODELL.md (needs fresh frames with ledger)."""
    lh = mass_ledger(historical_df)
    lo = mass_ledger(optimized_df)

    def de(x: float, nd: int = 1) -> str:
        return f"{x:,.{nd}f}".replace(",", "_").replace(".", ",").replace("_", ".")

    h_emptyings = int(historical_df["n_emptyings"].sum())
    o_emptyings = int(optimized_df["n_emptyings"].sum())
    h_avg_fill = float(lh["avg_fill_at_emptying_pct"])
    o_avg_fill = float(lo["avg_fill_at_emptying_pct"])
    h_overfull = int(historical_df["n_containers_overfull_at_visit"].sum())
    o_overfull = int(optimized_df["n_containers_overfull_at_visit"].sum())
    h_ovd = int(lh["overflow_container_days"])
    o_ovd = int(lo["overflow_container_days"])

    h_km = float(historical_df["est_km"].sum())
    o_km = float(optimized_df["est_km"].sum())
    h_veh_days = int(historical_df["vehicles_needed"].sum())
    o_veh_days = int(optimized_df["vehicles_needed"].sum())
    h_shift_h = float(historical_df["shift_hours"].sum())
    o_shift_h = float(optimized_df["shift_hours"].sum())

    def pct(o: float, h: float) -> str:
        return f"{(o - h) / h * 100.0:+.1f} %".replace(".", ",") if h else "–"

    rows = [
        ("Ø Füllstand bei Leerung (wahrer Füllstand, ungekappt)",
         f"{de(h_avg_fill)} %", f"{de(o_avg_fill)} %",
         f"{o_avg_fill - h_avg_fill:+.1f} pp".replace(".", ",")),
        ("Leerungen", de(h_emptyings, 0), de(o_emptyings, 0), pct(o_emptyings, h_emptyings)),
        ("Überfüllte Leerungen (≥ 110 % bei Leerung)", de(h_overfull, 0), de(o_overfull, 0),
         pct(o_overfull, h_overfull)),
        ("Überlauf-Containertage (≥ 110 %, ungeleert)", de(h_ovd, 0), de(o_ovd, 0), pct(o_ovd, h_ovd)),
        ("Fahrstrecke (est. km)", de(h_km), de(o_km), pct(o_km, h_km)),
        ("Fahrzeug-Einsatztage", de(h_veh_days, 0), de(o_veh_days, 0), pct(o_veh_days, h_veh_days)),
        ("Fahrerstunden", f"{de(h_shift_h)} h", f"{de(o_shift_h)} h", pct(o_shift_h, h_shift_h)),
    ]
    table = "\n".join(f"| {a} | **{b}** | **{c}** | {d} |" for a, b, c, d in rows)
    ledger_rows = "\n".join(
        f"| {label} | {de(lh[k])} t | {de(lo[k])} t |"
        for label, k in [
            ("Produziert (Welt, Σ r_c × aktive Tage)", "produced_t"),
            ("Gesammelt im Fenster (`tonnage_t`)", "collected_t"),
            ("Endbestand am 30.09.2026 (steht noch im Container)", "end_stock_t"),
        ]
    )
    total_h = lh["collected_t"] + lh["end_stock_t"]
    total_o = lo["collected_t"] + lo["end_stock_t"]

    return f"""# Kostenmodell & Jahressimulation: Status quo vs. Timer-Modell

Dieses Dokument vergleicht den **Status quo** (die realen Leerungstage aus den 11.701 Messungen, nachgespielt gegen ein festes Weltmodell) mit der **Walk-Forward-Simulation** des Timer-Modells über denselben Zeitraum (**17.10.2025 bis 30.09.2026**, 349 Kalendertage). Generiert von `scripts/simulate_daily.py`; Rechenmodell: [`docs/MODEL_SPEC.md`](MODEL_SPEC.md).

Die Rohdaten liegen als CSVs vor:
- [`data/outputs/historical_daily.csv`](../data/outputs/historical_daily.csv) (Status quo, `source=real`)
- [`data/outputs/optimized_daily.csv`](../data/outputs/optimized_daily.csv) (Timer-Modell, `source=simulated`)

## 1. Massenbilanz (eine Welt, zwei Politiken)

| Posten | Status quo | Timer-Modell |
|---|---:|---:|
{ledger_rows}
| **Gesammelt + Endbestand** | **{de(total_h)} t** | **{de(total_o)} t** |

Beide Seiten gehen auf dieselbe produzierte Menge auf (Test: `tests/test_mass_balance.py`). Die im Fenster gesammelte Tonnage unterscheidet sich nur um den Endbestand: Der Status quo lässt am Stichtag mehr Glas im Container stehen. Routing erzeugt kein Glas.

## 2. Jahres-Kennzahlen im Vergleich

| Kennzahl | Status quo | Timer-Modell | Delta |
|---|---|---|---|
{table}

Ehrlich gelesen: Das Timer-Modell senkt Überläufe stark, leert aber **nicht voller** als heute. Die Walk-Forward-Schätzung `mean(level/Δt)` liegt im Mittel über der wahren Rate, darum leert die Regel zu früh. Mehr Strecke und Stunden sind der Preis für fast keine Überläufe.

## 3. Methodik & Regeln

1. **Welt (Wahrheit):** Jeder Container hat eine feste Glasrate `r_c = Σ level_i / Σ Δt_i` (Intervalle ab der 2. Messung, Quotient der Summen; unter 2 Messungen: Median des Materials). Sie erzeugt das Glas in **beiden** Szenarien, ab dem Tag nach der ersten Messung, Startbestand 0 %.
2. **Systemgrenze:** Die erste Messung je Container ist der Start des Fensters (Glas davor, 775,7 t, zählt auf keiner Seite). Darum zählt der Status quo 11.701 − 1.338 = 10.363 Leerungen. Endbestand am letzten Tag wird ausgewiesen, nicht verschwiegen.
3. **Status quo:** An jedem realen Leerungstag wird der Modell-Füllstand gesammelt und auf exakt 0 % gesetzt. Damit reproduziert der Status quo die gemessene In-Fenster-Masse (Messungen 2…n) exakt.
4. **Timer-Modell, strikter Walk-Forward ohne Look-Ahead:** Die Regel kennt nur Raten aus Messungen mit $\\text{{Datum}} < d$ und den daraus geschätzten Füllstand seit der letzten Leerung. Eingeplant wird bei Schätzung $\\ge 80\\,\\%$ oder wenn bis zum nächsten Betriebstag $\\ge 110\\,\\%$ drohen. Der LKW nimmt den **wahren** Füllstand mit; Reset auf exakt 0 % (kein Zufallsrest mehr).
5. **Keine Kappung:** Der Füllstand wird intern nicht bei 110 % gekappt (übergelaufenes Glas steht neben dem Container und wird mitgenommen). 110 % zählt nur als Überlauf-Ereignis. Ø Füllstand bei Leerung ist daher **ungekappt** und kann über 100 % liegen.
6. **Betriebsrestriktionen (OperationalConfig):**
   Beide Modelle unterliegen exakt denselben Annahmen aus `prezero_config.json`:
   - LKW-Nutzlast: 11.000 kg, Ladevolumen: 26,0 m³, Dichte: 400 kg/m³, Behälter: 2,5 m³
   - Max. Schichtdauer: 8,0 h, Rüstzeit: 2,0 min, Hubzeit: 3,0 min/Behälter, Entladezeit: 20,0 min
   - Umwegfaktor: 1,35 auf Haversine, Geschwindigkeit: 25 km/h
   - Feste Depots: Betriebshof (49.1427, 9.2109), Entladestelle (49.1780, 9.2085)
7. **Geodaten-Transparenz:**
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

    print(f"produced_total: {produced_total(readings, cfg):.2f} t")
    for name, df in (("historical", hist_df), ("optimized", opt_df)):
        lg = mass_ledger(df)
        print(
            f"{name}: produced={lg['produced_t']:.2f} t collected={lg['collected_t']:.2f} t "
            f"end_stock={lg['end_stock_t']:.2f} t emptyings={lg['n_emptyings']} "
            f"avg_fill={lg['avg_fill_at_emptying_pct']:.2f} % "
            f"overfull_at_visit={int(df['n_containers_overfull_at_visit'].sum())} "
            f"overflow_container_days={lg['overflow_container_days']} "
            f"km={df['est_km'].sum():.1f} vehicle_days={int(df['vehicles_needed'].sum())} "
            f"shift_hours={df['shift_hours'].sum():.1f}"
        )

    md = generate_cost_model_markdown(hist_df, opt_df)
    md_path = args.docs_dir / "KOSTENMODELL.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"Written: {md_path}")


if __name__ == "__main__":
    main()
