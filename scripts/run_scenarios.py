"""Scenario runner: the what-if grid behind the GlasRoute UI.

Contract (see the W3-W5 brief):

``data/outputs/scenarios/summary.json``
    One row per scenario — the main table of the UI.
``data/outputs/scenarios/<id>__<time_model>_daily.csv``
    The daily course of one scenario.
``data/outputs/scenarios/containers.csv``
    The cadence per container (core model).

The evaluation period is the **full replay year** (349 days, 2025-10-17 to
2026-09-30): only over the whole year does one see how the cadence settles.
The week is only the planning view of the UI.

Scenarios differ only in the **decision rule** (when a container is emptied)
and in the tour formation. The world is identical in every scenario:
``produced_t`` is the same, and the mass balance holds
``collected_t + end_stock_t == produced_t``.

Feedback switch
---------------
``feedback=False``  the cadence is learned **once** from the history and then
                    stays fixed.
``feedback=True``   every new emptying updates the rate ``r`` and thus the
                    cadence ``T``.

Run:
    PYTHONPATH=src python scripts/run_scenarios.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from prezero.cadence import (  # noqa: E402
    AREA_RURAL,
    AREA_URBAN,
    CadenceParams,
    assign_area,
    ideal_cadence_days,
)
from prezero.locations import load_locations  # noqa: E402
from prezero.routing import (  # noqa: E402
    OperationalConfig,
    _simulate_constrained_routes,
    density_for,
    load_config,
)

#: Public holidays in Baden-Wuerttemberg that stop collection (Annahme/data).
PUBLIC_HOLIDAYS_BW: frozenset[date] = frozenset(
    {
        date(2025, 10, 3),
        date(2025, 11, 1),
        date(2025, 12, 24),
        date(2025, 12, 25),
        date(2025, 12, 26),
        date(2026, 1, 1),
        date(2026, 1, 6),
        date(2026, 3, 8),
        date(2026, 4, 3),
        date(2026, 4, 6),
        date(2026, 5, 1),
        date(2026, 5, 14),
        date(2026, 5, 25),
        date(2026, 6, 4),
        date(2026, 10, 3),
        date(2026, 11, 1),
    }
)

#: Füllstand at which a container is emptied (Puffer) per scenario.
THRESHOLD_PCT = {"a_zero_overflow": 60.0, "b_min_km": 100.0, "c_max_fill": 80.0, "d_status_quo": 80.0, "e_mentor": 80.0}

#: Overflow threshold (110 % = "overfull" in the data).
MAX_FILL_PCT = 110.0

#: Mentor policy: a container below this level is skipped (Annahme, §5 of MODEL_SPEC).
MENTOR_LOW_FILL_PCT = 20.0

#: Cost model (Annahme, see docs/MODEL_SPEC.md §7).
COST_VEHICLE_DAY_EUR = 500.0
COST_CREW_EUR_PER_HOUR = 64.0
COST_KM_EUR = 0.65

#: Time models: drive time per hop in minutes (Annahme, see docs/MODEL_SPEC.md §7).
#: ``real`` uses the mentor values (7 min city / 15 min rural), ``hop5`` and
#: ``hop10`` are the sensitivity cases with a flat hop time.
TIME_MODELS: dict[str, dict[str, float]] = {
    "real": {"urban": 7.0, "rural": 15.0},
    "hop5": {"urban": 5.0, "rural": 5.0},
    "hop10": {"urban": 10.0, "rural": 10.0},
}

#: Service time per stop (Annahme).
SERVICE_MIN_PER_STOP = 5.0


def is_operating_day(d: date) -> bool:
    """True on collection days: Monday to Friday, no public holiday."""
    return d.weekday() < 5 and d not in PUBLIC_HOLIDAYS_BW


def get_next_operating_day(d: date, max_days_ahead: int = 14) -> date:
    """The earliest operating day strictly after ``d``."""
    cur = d + timedelta(days=1)
    for _ in range(max_days_ahead):
        if is_operating_day(cur):
            return cur
        cur += timedelta(days=1)
    return cur


class _Truth:
    """The exogenous glass ledger of one container (identical in every scenario).

    Plain class (not @dataclass): the test loads this file via importlib without
    registering it in sys.modules, which dataclasses need.
    """

    __slots__ = ("first", "last", "rate", "prefill", "total_kg")

    def __init__(self, first: date, last: date, rate: float, prefill: float, total_kg: float) -> None:
        self.first = first
        self.last = last
        self.rate = rate  # pp per day
        self.prefill = prefill  # pp present on the first day
        self.total_kg = total_kg


class _ContainerState:
    """Simulation state of one container."""

    __slots__ = (
        "key",
        "rate",
        "fixed_rate",
        "cadence_days",
        "fixed_cadence_days",
        "last_visit",
        "fill",
    )

    def __init__(
        self,
        key: tuple[str, str],
        rate: float,
        fixed_rate: float,
        cadence_days: float,
        fixed_cadence_days: float,
        last_visit: date,
        fill: float,
    ) -> None:
        self.key = key
        self.rate = rate  # learned rate in pp/day
        self.fixed_rate = fixed_rate  # rate learned once (feedback off)
        self.cadence_days = cadence_days  # current target cadence T
        self.fixed_cadence_days = fixed_cadence_days  # cadence learned once
        self.last_visit = last_visit
        self.fill = fill  # current fill in pp


class ScenarioResult:
    """Metrics of one scenario over the replay year.

    Plain class (not @dataclass) — see _Truth for the reason.
    """

    __slots__ = (
        "id",
        "label",
        "time_model",
        "collected_t",
        "end_stock_t",
        "produced_t",
        "avg_fill_at_emptying_pct",
        "overflow_events",
        "emptyings",
        "stops",
        "vehicle_days",
        "hours",
        "km",
        "cost_eur",
        "cost_breakdown",
        "daily",
        "container_stats",
    )

    def __init__(
        self,
        id: str,
        label: str,
        time_model: str,
        collected_t: float,
        end_stock_t: float,
        produced_t: float,
        avg_fill_at_emptying_pct: float,
        overflow_events: int,
        emptyings: int,
        stops: int,
        vehicle_days: int,
        hours: float,
        km: float,
        cost_eur: float,
        cost_breakdown: dict[str, float],
        daily: pd.DataFrame,
        container_stats: dict[tuple[str, str], dict[str, float]],
    ) -> None:
        self.id = id
        self.label = label
        self.time_model = time_model
        self.collected_t = collected_t
        self.end_stock_t = end_stock_t
        self.produced_t = produced_t
        self.avg_fill_at_emptying_pct = avg_fill_at_emptying_pct
        self.overflow_events = overflow_events
        self.emptyings = emptyings
        self.stops = stops
        self.vehicle_days = vehicle_days
        self.hours = hours
        self.km = km
        self.cost_eur = cost_eur
        self.cost_breakdown = cost_breakdown
        self.daily = daily
        self.container_stats = container_stats


#: Median distance between two random containers (km) — the typical leg.
#: Measured on the real coordinate spread (see docs/MODEL_SPEC.md §7).
TYPICAL_LEG_KM = 5.47


def _mass_kg(pp: float, material: str, cfg: OperationalConfig) -> float:
    """Mass in kg for a fill level in percentage points."""
    return (pp / 100.0) * float(cfg.container_volume_m3) * density_for(cfg, material)


def _config_for_time_model(
    cfg: OperationalConfig, time_model: str
) -> OperationalConfig:
    """Config whose drive time per leg matches the hop time of the time model.

    The routing derives the drive time from the distance and the average speed.
    To let the hop time of a time model (5 / 7-15 / 10 min) take effect, the
    effective speed is derived from the typical leg (5,47 km). The *distance*
    model (km) is untouched — only the time model changes.
    """
    drive = TIME_MODELS.get(time_model, TIME_MODELS["real"])
    hop_min = (float(drive["urban"]) + float(drive["rural"])) / 2.0
    speed = (TYPICAL_LEG_KM / (hop_min / 60.0)) if hop_min > 0 else float(cfg.avg_speed_kmh)
    return replace(cfg, avg_speed_kmh=speed)


def _prepare_readings(readings: pd.DataFrame) -> pd.DataFrame:
    work = readings.copy()
    work["date"] = pd.to_datetime(work["date"])
    work["date_only"] = work["date"].dt.date
    work["Location_id"] = work["Location_id"].astype(str)
    work["material_type"] = work["material_type"].astype(str).str.lower()
    work["fill_level_numeric"] = pd.to_numeric(work["fill_level_numeric"])
    return work


def _prepare_locations(locations: pd.DataFrame) -> pd.DataFrame:
    locs = locations.copy()
    locs["Location_id"] = locs["Location_id"].astype(str)
    locs["lat"] = pd.to_numeric(locs["lat"])
    locs["lon"] = pd.to_numeric(locs["lon"])
    return locs


def _container_truth(work: pd.DataFrame, cfg: OperationalConfig) -> dict[tuple[str, str], _Truth]:
    """Calibrate the exogenous glass ledger per container.

    rate = sum(levels) / days(first..last) — the quotient of the sums, which is
    expectation-preserving for a constant rate.
    """
    truth: dict[tuple[str, str], _Truth] = {}
    grouped = work.sort_values("date_only").groupby(["Location_id", "material_type"])
    for (loc, mat), g in grouped:
        dates = list(g["date_only"])
        levels = [float(v) for v in g["fill_level_numeric"]]
        span = (dates[-1] - dates[0]).days
        total_pp = float(sum(levels))
        total_kg = sum(_mass_kg(v, mat, cfg) for v in levels)
        if span > 0:
            truth[(str(loc), str(mat))] = _Truth(dates[0], dates[-1], total_pp / span, 0.0, total_kg)
        else:
            truth[(str(loc), str(mat))] = _Truth(dates[0], dates[-1], 0.0, total_pp, total_kg)
    return truth


def _walk_forward_rates(
    visits: list[tuple[date, float]], d: date
) -> float | None:
    """Rate from the measurements strictly before ``d`` (no look-ahead)."""
    past = [(t, lvl) for t, lvl in visits if t < d]
    if len(past) < 2:
        return None
    total_days = 0.0
    total_pct = 0.0
    for i in range(1, len(past)):
        span = (past[i][0] - past[i - 1][0]).days
        if span > 0:
            total_days += float(span)
            total_pct += float(past[i][1])
    if total_days <= 0:
        return None
    return total_pct / total_days


def _cadence_for(rate: float, params: CadenceParams) -> float:
    """T = (capacity - buffer) / r, limited to the allowed band."""
    ideal = ideal_cadence_days(rate, params.empty_at_pct)
    if ideal is None:
        return float(params.max_cadence_days)
    return params.clamped_cadence(ideal)


def _due_for(
    scenario_id: str,
    state: _ContainerState,
    est: float,
    risk: float,
    since_days: int,
    params: CadenceParams,
) -> bool:
    """Decision rule of a scenario (only *when* a container is emptied)."""
    if scenario_id == "d_status_quo":
        # Status quo: the real emptying days (handled by the replay).
        return False
    if scenario_id == "a_zero_overflow":
        return est >= params.empty_at_pct or risk >= MAX_FILL_PCT
    if scenario_id == "b_min_km":
        return risk >= MAX_FILL_PCT
    if scenario_id == "c_max_fill":
        return est >= params.empty_at_pct or risk >= MAX_FILL_PCT
    if scenario_id == "e_mentor":
        # Mentor policy: 14-day rhythm for containers above 20 %, plus the timer.
        rhythm = since_days >= 14 and est > 20.0
        return est >= params.empty_at_pct or risk >= MAX_FILL_PCT or rhythm
    return est >= params.empty_at_pct or risk >= MAX_FILL_PCT


def run_scenario(
    scenario_id: str,
    readings: pd.DataFrame,
    locations: pd.DataFrame,
    cfg: OperationalConfig | None = None,
    params: CadenceParams | None = None,
    feedback: bool = False,
    time_model: str = "real",
    label: str | None = None,
) -> ScenarioResult:
    """Run one scenario over the full replay year.

    The glass ledger is exogenous and identical in every scenario; only the
    decision rule and the feedback switch differ.
    """
    config = cfg or OperationalConfig()
    config = _config_for_time_model(config, time_model)
    params = params or CadenceParams()
    work = _prepare_readings(readings)
    locs = _prepare_locations(locations)

    coords = {str(r.Location_id): (float(r.lat), float(r.lon)) for r in locs.itertuples(index=False)}
    truth = _container_truth(work, config)
    containers = sorted(k for k in truth if k[0] in coords)

    visits_by_c: dict[tuple[str, str], list[tuple[date, float]]] = {}
    for (loc, mat), g in work.sort_values("date_only").groupby(["Location_id", "material_type"]):
        visits_by_c[(str(loc), str(mat))] = list(zip(g["date_only"], g["fill_level_numeric"]))

    start_date = work["date_only"].min()
    end_date = work["date_only"].max()
    all_dates = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]

    drive = TIME_MODELS.get(time_model, TIME_MODELS["real"])

    # --- learning phase: rates and cadences from the history before the replay ---
    states: dict[tuple[str, str], _ContainerState] = {}
    for k in containers:
        rate = _walk_forward_rates(visits_by_c.get(k, []), start_date)
        if rate is None or rate <= 0:
            rate = truth[k].rate if truth[k].rate > 0 else 0.0
        cadence = _cadence_for(rate, params)
        states[k] = _ContainerState(
            key=k,
            rate=rate,
            fixed_rate=rate,
            cadence_days=cadence,
            fixed_cadence_days=cadence,
            last_visit=truth[k].first,
            fill=0.0,
        )

    stock: dict[tuple[str, str], float] = {k: 0.0 for k in containers}
    #: True while the container is above 110 % (so an overflow counts once).
    overflow_flag: dict[tuple[str, str], bool] = {k: False for k in containers}
    container_stats: dict[tuple[str, str], dict[str, float]] = {
        k: {"emptyings": 0, "fill_sum": 0.0, "overflows": 0, "skip_14d": 0} for k in containers
    }

    rows: list[dict[str, Any]] = []
    total_collected_kg = 0.0
    total_generated_kg = 0.0
    total_overflow_events = 0
    total_emptyings = 0
    total_stops = 0
    total_hours = 0.0
    total_km = 0.0
    total_vehicle_days = 0

    for d in all_dates:
        generated_kg = 0.0
        for k in containers:
            t = truth[k]
            if d == t.first:
                stock[k] = t.prefill
                states[k].last_visit = d
                generated_kg += t.total_kg if t.prefill > 0 else 0.0
            elif t.first < d <= t.last:
                stock[k] += t.rate
                generated_kg += _mass_kg(t.rate, k[1], config)
        total_generated_kg += generated_kg

        op = is_operating_day(d)
        next_op = get_next_operating_day(d)
        days_to_next = max(1, (next_op - d).days)

        # An overflow is an *event*: the container crosses 110 %. A container that
        # stays above the threshold over several days counts once, not daily.
        overflow_today = 0
        for k in containers:
            above = stock[k] >= MAX_FILL_PCT
            if above and not overflow_flag[k]:
                overflow_today += 1
                container_stats[k]["overflows"] += 1
            overflow_flag[k] = above
        total_overflow_events += overflow_today

        due: list[tuple[str, str]] = []
        if op:
            for k in containers:
                s = stock[k]
                forced = d >= truth[k].last and s > 1e-9
                if s <= 1e-9 and not forced:
                    continue
                state = states[k]
                since = (d - state.last_visit).days
                est = min(MAX_FILL_PCT, state.rate * since)
                risk = est + days_to_next * state.rate

                if scenario_id == "d_status_quo":
                    # Status quo: empty on the real emptying days.
                    real_visit = any(t == d for t, _lvl in visits_by_c.get(k, []))
                    should_empty = real_visit or forced
                else:
                    should_empty = forced or _due_for(scenario_id, state, est, risk, since, params)
                    # The mentor policy skips a container that the 14-day rhythm
                    # would empty although it is barely filled.
                    if (
                        scenario_id == "e_mentor"
                        and not should_empty
                        and since >= 14
                        and est <= MENTOR_LOW_FILL_PCT
                    ):
                        container_stats[k]["skip_14d"] += 1

                if should_empty:
                    due.append(k)

        if not due:
            rows.append(
                {
                    "date": str(d),
                    "n_emptyings": 0,
                    "n_overflow_events": overflow_today,
                    "avg_fill_at_emptying_pct": 0.0,
                    "tonnage_t": 0.0,
                    "stops": 0,
                    "vehicles_needed": 0,
                    "shift_hours": 0.0,
                    "km": 0.0,
                    "cost_eur": 0.0,
                }
            )

            continue

        # --- tour formation (secondary concern) -------------------------------------------
        site_dict: dict[tuple[float, float], dict[str, Any]] = {}
        for k in due:
            lat, lon = coords[k[0]]
            pt = (round(lat, 6), round(lon, 6))
            s_pp = stock[k]
            m_kg = _mass_kg(s_pp, k[1], config)
            if pt not in site_dict:
                site_dict[pt] = {
                    "lat": pt[0],
                    "lon": pt[1],
                    "Location_id": k[0],
                    "critical_bins": 0,
                    "mass_kg": 0.0,
                    "volume_m3": 0.0,
                    "score": s_pp / 100.0,
                    "critical": True,
                    "primary_material": k[1],
                    "last_fill_level": s_pp,
                    "est_fill_level": s_pp,
                    "source": "osm_assigned",
                    "confidence": "simulated_mapping",
                    "container_keys": [],
                }
            site_dict[pt]["critical_bins"] += 1
            site_dict[pt]["mass_kg"] += m_kg
            site_dict[pt]["volume_m3"] += (s_pp / 100.0) * float(config.container_volume_m3)
            site_dict[pt]["score"] = max(site_dict[pt]["score"], s_pp / 100.0)
            site_dict[pt]["container_keys"].append(k)

        sites = list(site_dict.values())
        stops, unloads, vehicles, planned_km, _mass = _simulate_constrained_routes(
            pd.DataFrame(sites), config
        )

        # --- the emptyings themselves --------------------------------------------------------
        fill_sum = 0.0
        collected_kg_today = 0.0
        for k in due:
            s_pp = stock[k]
            state = states[k]
            fill_sum += s_pp
            container_stats[k]["emptyings"] += 1
            container_stats[k]["fill_sum"] += s_pp
            collected_kg_today += _mass_kg(s_pp, k[1], config)
            total_collected_kg += _mass_kg(s_pp, k[1], config)

            # Feedback: every emptying updates rate and cadence.
            if feedback:
                state.rate = _walk_forward_rates(visits_by_c.get(k, []), d)
                if state.rate is None or state.rate <= 0:
                    state.rate = truth[k].rate
                state.cadence_days = _cadence_for(state.rate, params)
            else:
                # Cadence learned once and kept fixed.
                state.cadence_days = state.fixed_cadence_days
                state.rate = state.fixed_rate

            state.last_visit = d
            stock[k] = 0.0
            overflow_flag[k] = False

        total_emptyings += len(due)
        total_stops += len(stops)
        shift_h = round(float(sum(v["shift_hours"] for v in vehicles)), 2)
        total_hours += shift_h
        total_km += planned_km
        total_vehicle_days += len(vehicles)

        tonnage_t = round(collected_kg_today / 1000.0, 3)
        cost_vehicle = len(vehicles) * COST_VEHICLE_DAY_EUR
        cost_crew = shift_h * COST_CREW_EUR_PER_HOUR
        cost_km = planned_km * COST_KM_EUR

        rows.append(
            {
                "date": str(d),
                "n_emptyings": len(due),
                "n_overflow_events": overflow_today,
                "avg_fill_at_emptying_pct": round(fill_sum / len(due), 2) if due else 0.0,
                "tonnage_t": tonnage_t,
                "stops": len(stops),
                "vehicles_needed": len(vehicles),
                "shift_hours": shift_h,
                "km": round(planned_km, 2),
                "cost_eur": round(cost_vehicle + cost_crew + cost_km, 2),
            }
        )

    daily = pd.DataFrame(rows)
    end_stock_t = round(
        sum(_mass_kg(stock[k], k[1], config) for k in containers) / 1000.0, 3
    )
    collected_t = round(total_collected_kg / 1000.0, 3)
    produced_t = round(total_generated_kg / 1000.0, 3)
    avg_fill = (
        sum(container_stats[k]["fill_sum"] for k in containers)
        / max(1, total_emptyings)
    )

    return ScenarioResult(
        id=scenario_id,
        label=label or scenario_id,
        time_model=time_model,
        collected_t=collected_t,
        end_stock_t=end_stock_t,
        produced_t=produced_t,
        avg_fill_at_emptying_pct=round(float(avg_fill), 2),
        overflow_events=total_overflow_events,
        emptyings=total_emptyings,
        stops=total_stops,
        vehicle_days=total_vehicle_days,
        hours=round(total_hours, 2),
        km=round(total_km, 2),
        cost_eur=round(
            total_vehicle_days * COST_VEHICLE_DAY_EUR
            + total_hours * COST_CREW_EUR_PER_HOUR
            + total_km * COST_KM_EUR,
            2,
        ),
        cost_breakdown={
            "vehicle_days_eur": round(total_vehicle_days * COST_VEHICLE_DAY_EUR, 2),
            "crew_eur": round(total_hours * COST_CREW_EUR_PER_HOUR, 2),
            "km_eur": round(total_km * COST_KM_EUR, 2),
        },
        daily=daily,
        container_stats=container_stats,
    )


def _active_days(truth: _Truth) -> int:
    """Days the container produces glass (the ledger window)."""
    return max(1, (truth.last - truth.first).days + 1)


def _write_scenario_files(
    out_dir: Path,
    results: list[ScenarioResult],
    container_table: pd.DataFrame,
) -> None:
    """Write the contracted files."""
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_scenarios: list[dict[str, Any]] = []
    cheapest = min(results, key=lambda r: r.cost_eur) if results else None
    fewest_overflows = min(results, key=lambda r: r.overflow_events) if results else None
    status_quo = next((r for r in results if r.id == "d_status_quo"), None)
    sq_emptyings = status_quo.emptyings if status_quo else 0

    for result in results:
        name = f"{result.id}__{result.time_model}_daily.csv"
        result.daily.to_csv(out_dir / name, index=False)
        summary_scenarios.append(
            {
                "id": result.id,
                "label": result.label,
                "time_model": result.time_model,
                "collected_t": result.collected_t,
                "end_stock_t": result.end_stock_t,
                "produced_t": result.produced_t,
                "mass_balance_ok": abs(
                    result.collected_t + result.end_stock_t - result.produced_t
                )
                <= max(0.01, 0.02 * max(result.produced_t, 1.0)),
                "avg_fill_at_emptying_pct": result.avg_fill_at_emptying_pct,
                "overflow_events": result.overflow_events,
                "emptyings": result.emptyings,
                "emptyings_saved_vs_status_quo": sq_emptyings - result.emptyings,
                "stops": result.stops,
                "vehicle_days": result.vehicle_days,
                "hours": result.hours,
                "km": result.km,
                "cost_eur": result.cost_eur,
                "cost_breakdown": result.cost_breakdown,
                "flags": {
                    "cheapest": cheapest is not None and result.id == cheapest.id
                    and result.time_model == cheapest.time_model,
                    "fewest_overflows": fewest_overflows is not None
                    and result.id == fewest_overflows.id
                    and result.time_model == fewest_overflows.time_model,
                },
                "source": "scripts/run_scenarios.py",
            }
        )

    summary = {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
        "period": {
            "start": str(min(r.daily["date"].iloc[0] for r in results)),
            "end": str(max(r.daily["date"].iloc[-1] for r in results)),
            "days": int(len(results[0].daily)),
        },
        "produced_t": results[0].produced_t if results else 0.0,
        "scenarios": summary_scenarios,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # --- containers.csv: per-container cadence + the emptyings of the two reference runs ---
    table = container_table.copy()
    sq_stats = next((r for r in results if r.id == "d_status_quo"), None)
    mentor_stats = next((r for r in results if r.id == "e_mentor"), None)

    def _lookup(stats: ScenarioResult | None, key: tuple[str, str], field: str) -> float:
        if stats is None:
            return 0.0
        entry = stats.container_stats.get(key)
        if not entry:
            return 0.0
        if field == "avg_fill":
            count = entry.get("emptyings", 0)
            return round(entry.get("fill_sum", 0.0) / count, 2) if count else 0.0
        return float(entry.get(field, 0))

    rows = []
    for row in table.to_dict(orient="records"):
        key = (str(row["location_id"]), str(row["material"]))
        rows.append(
            {
                "location_id": row["location_id"],
                "material": row["material"],
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                "area": row.get("area", AREA_URBAN),
                "rate_pct_per_day": row.get("rate_pct_per_day", 0.0),
                "rate_kg_per_day": row.get("rate_kg_per_day", 0.0),
                "cadence_days_T": row.get("cadence_days_T", 0.0),
                "emptyings_status_quo": _lookup(sq_stats, key, "emptyings"),
                "emptyings_mentor": _lookup(mentor_stats, key, "emptyings"),
                "avg_fill_status_quo_pct": _lookup(sq_stats, key, "avg_fill"),
                "avg_fill_mentor_pct": _lookup(mentor_stats, key, "avg_fill"),
                "overflow_events_status_quo": _lookup(sq_stats, key, "overflows"),
                "skip_14d": _lookup(mentor_stats, key, "skip_14d"),
            }
        )
    columns = [
        "location_id",
        "material",
        "lat",
        "lon",
        "area",
        "rate_pct_per_day",
        "rate_kg_per_day",
        "cadence_days_T",
        "emptyings_status_quo",
        "emptyings_mentor",
        "avg_fill_status_quo_pct",
        "avg_fill_mentor_pct",
        "overflow_events_status_quo",
        "skip_14d",
    ]
    pd.DataFrame(rows)[columns].to_csv(out_dir / "containers.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the scenario grid (W3-W5 contract).")
    parser.add_argument(
        "--readings",
        default="data/processed/cleaned_readings.csv",
        help="Cleaned readings CSV.",
    )
    parser.add_argument(
        "--locations", default="data/external/locations.csv", help="Locations CSV."
    )
    parser.add_argument("--config", default="prezero_config.json", help="Config JSON.")
    parser.add_argument(
        "--out-dir",
        default="data/outputs/scenarios",
        help="Directory for the scenario files.",
    )
    parser.add_argument(
        "--feedback",
        action="store_true",
        help="Every new emptying updates rate and cadence (otherwise learned once).",
    )
    args = parser.parse_args()

    readings = pd.read_csv(args.readings, parse_dates=["date"])
    locations = load_locations(args.locations)
    cfg = load_config(args.config)
    params = CadenceParams()

    from prezero.cadence import build_container_cadences

    container_table = build_container_cadences(readings, params, locations_df=locations)

    results: list[ScenarioResult] = []
    labels = {
        "a_zero_overflow": "Null Überlauf (früh leeren)",
        "b_min_km": "Minimum km (spät leeren)",
        "c_max_fill": "Maximum Füllgrad",
        "d_status_quo": "Status quo (reale Leerungstage)",
        "e_mentor": "Mentor-Politik (14-Tage-Rhythmus)",
    }
    for scenario_id in ("a_zero_overflow", "b_min_km", "c_max_fill", "d_status_quo", "e_mentor"):
        for time_model in ("real", "hop5", "hop10"):
            print(f"Running {scenario_id} / {time_model} ...", flush=True)
            results.append(
                run_scenario(
                    scenario_id,
                    readings,
                    locations,
                    cfg=cfg,
                    params=params,
                    feedback=args.feedback,
                    time_model=time_model,
                    label=labels[scenario_id],
                )
            )

    _write_scenario_files(Path(args.out_dir), results, container_table)
    print(f"Written: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
