"""Holdout trial: measured historical operations plus a shared prospective ledger."""

from dataclasses import dataclass

import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from prezero.dispatch_policy import Calendar, manifest
from prezero.history import route_day
from prezero.routing import density_for


@dataclass(frozen=True)
class Demand:
    keys: pd.MultiIndex
    rate: np.ndarray
    initial: np.ndarray


def calibrate(visits, start):
    """Freeze inventory roster and ratio of prior interval fills to exposure days."""
    past = visits.loc[visits.date < start].sort_values("date").copy()
    key = ["Location_id", "material_type"]
    past["days"] = past.groupby(key).date.diff().dt.days
    intervals = past.dropna(subset=["days"])
    groups = intervals.groupby(key)
    rates = groups.fill_pct.sum() / groups.days.sum()
    last = past.groupby(key).date.max()
    rates = rates.reindex(last.index)
    color_groups = intervals.groupby("material_type")
    fallback = color_groups.fill_pct.sum() / color_groups.days.sum()
    rates = rates.fillna(
        pd.Series(last.index.get_level_values(1).map(fallback), index=last.index)
    )
    if rates.isna().any() or rates.empty:
        raise ValueError("Insufficient prior material history")
    initial = np.minimum(110.0, rates * ((start - last).dt.days - 1))
    return Demand(last.index, rates.to_numpy(), initial.to_numpy())


@dataclass
class Operations:
    driving_days: int = 0
    vehicle_days: int = 0
    peak: int = 0
    km: float = 0
    hours: float = 0
    emptyings: int = 0
    fill_sum: float = 0
    collected_kg: float = 0
    exceptions: int = 0

    def record(self, route, fills, kg, exception):
        vehicles = route["vehicles_needed"]
        self.driving_days += 1
        self.vehicle_days += vehicles
        self.peak = max(self.peak, vehicles)
        self.km += route["km"]
        self.hours += route["shift_hours"]
        self.emptyings += len(fills)
        self.fill_sum += sum(fills)
        self.collected_kg += float(fills @ kg)
        self.exceptions += int(exception)

    def summary(self):
        return {
            **vars(self),
            "mean_fill": self.fill_sum / self.emptyings if self.emptyings else None,
        }


def price_operations(ops, prices, days):
    """Price a single manifest with the dashboard's component calculator."""
    scenario = dict(ops, inventory={"collected_kg": ops["collected_kg"]})
    js = (
        "const [s,p,d]=JSON.parse(require('fs').readFileSync(0)); "
        "console.log(JSON.stringify(require(process.argv[1]).collectionCost(s,p,d)))"
    )
    result = subprocess.run(
        ["node", "-e", js, str(Path(__file__).with_name("economics.js"))],
        input=json.dumps([scenario, prices | {"annual_days": 365}, days]),
        text=True,
        capture_output=True,
        check=True,
    )
    c = json.loads(result.stdout)
    return dict(
        deployment_cost=c["vehicle"],
        labor_and_km_cost=c["drive"] + c["labor"],
        cost=c["total"],
        eur_per_t=c["perTonne"],
    )


def route_for(ids, loads, keys, geo, cfg):
    frame = keys[ids].to_frame(index=False)
    frame["fill_pct"] = loads
    return route_day(frame, geo, cfg)


def feasible_prefix(ids, stocks, keys, geo, cfg, fleet):
    """Dispatch only an executable priority prefix. Own daily level readings assumed."""

    def attempt(n):
        try:
            route = route_for(
                ids[:n], np.minimum(110.0, stocks[ids[:n]]), keys, geo, cfg
            )
        except ValueError as err:
            if "exceeds" not in str(err):
                raise
            return None
        return route if route["vehicles_needed"] <= fleet else None

    if not len(ids):
        return ids, None
    best = attempt(len(ids))
    if best is not None:
        return ids, best
    lo, hi = 0, len(ids)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        route = attempt(mid)
        if route is None:
            hi = mid
        else:
            lo, best = mid, route
    return ids[:lo], best


def trial(
    visits,
    geo,
    cfg,
    prices,
    start,
    end,
    calendar=Calendar(),
    fleet=3,
    demand_factor=1.0,
):
    demand = calibrate(visits, start)
    keys, rate = demand.keys, demand.rate
    coords = (
        geo.set_index("Location_id")
        .loc[keys.get_level_values(0), ["lat", "lon"]]
        .to_numpy()
    )
    kg = np.array(
        [cfg.container_volume_m3 * density_for(cfg, m) / 100 for _, m in keys]
    )
    holdout = visits.loc[visits.date.between(start, end)].copy()
    holdout["bin"] = keys.get_indexer(
        pd.MultiIndex.from_frame(holdout[list(keys.names)])
    )
    excluded = int((holdout.bin < 0).sum())
    known = holdout.loc[holdout.bin >= 0]
    by_day = dict(tuple(known.groupby("date")))
    names = ("A", "B", "B_weekday", "C")
    stock = {s: demand.initial.copy() for s in names}
    ops = {s: Operations() for s in names}
    measured_ops = Operations()
    risk = dict.fromkeys(names, 0)
    checkpoints = {}
    for n, day in enumerate(pd.date_range(start, end), 1):
        measured = by_day.get(day, known.iloc[:0])
        historical_ids = measured.bin.to_numpy(dtype=int)
        if len(measured):
            levels = measured.fill_pct.to_numpy()
            route = route_for(historical_ids, levels, keys, geo, cfg)
            measured_ops.record(
                route, levels, kg[historical_ids], not calendar.open(day)
            )
        for s in names:
            levels = stock[s]
            levels += rate * demand_factor
            risk[s] += int((levels > 100 + 1e-9).sum())
            if s == "A":
                ids = historical_ids
                route = (
                    route_for(ids, np.minimum(110.0, levels[ids]), keys, geo, cfg)
                    if len(ids)
                    else None
                )
            else:
                if s in ("B", "B_weekday"):
                    # Legacy immediate 60% rule on its original all-days calendar.
                    eligible = np.flatnonzero(
                        (levels >= 60) & (s == "B" or calendar.open(day))
                    )
                    ids = eligible[np.argsort(-levels[eligible], kind="stable")][
                        : fleet * 25
                    ]
                else:
                    ids = np.array(
                        manifest(day, levels, rate, coords, calendar)[: fleet * 25],
                        dtype=int,
                    )
                ids, route = feasible_prefix(ids, levels, keys, geo, cfg, fleet)
            if route is not None:
                lifts = np.minimum(110.0, levels[ids])
                ops[s].record(route, lifts, kg[ids], not calendar.open(day))
                levels[ids] -= lifts
            expected = (demand.initial + rate * n * demand_factor) @ kg
            if not np.isclose(
                expected, levels @ kg + ops[s].collected_kg, rtol=0, atol=1e-5
            ):
                raise ValueError("Inventory conservation failed")
        if day == end or n == 31:
            snapshots = {}
            for s in names:
                levels = stock[s]
                snapshots[s] = {
                    **ops[s].summary(),
                    "risk_bin_days": risk[s],
                    "ending_kg": float(levels @ kg),
                    "overdue_bins": int((levels > 100 + 1e-9).sum()),
                    "excess_kg": float(np.maximum(0.0, levels - 100) @ kg),
                }
            for item in snapshots.values():
                item.update(price_operations(item, prices, n))
            checkpoints[str(day.date())] = snapshots
    result = checkpoints[str(end.date())]
    historical = result["A"]
    for name, candidate in result.items():
        candidate["service"] = assess_service(historical, candidate, fleet)
    return {
        "opening_kg": float(demand.initial @ kg),
        "daily_inflow_kg": float((rate * demand_factor) @ kg),
        "start": str(start.date()),
        "end": str(end.date()),
        "bins": len(keys),
        "excluded_visits_unknown_at_start": excluded,
        "observed_overfull": int(known.overfull.sum()),
        "measured_A": measured_ops.summary()
        | price_operations(measured_ops.summary(), prices, n),
        "checkpoints": checkpoints,
    }


def assess_service(reference, candidate, fleet):
    """Higher safe stock may pass service. Suppress a savings claim until its burden is priced."""
    checks = {
        "risk": candidate["risk_bin_days"] <= reference["risk_bin_days"],
        "overdue_count": candidate["overdue_bins"] <= reference["overdue_bins"],
        "overdue_mass": candidate["excess_kg"] <= reference["excess_kg"] + 1e-6,
        "fleet": max(reference["peak"], candidate["peak"]) <= fleet,
    }
    deferred = max(0.0, candidate["ending_kg"] - reference["ending_kg"])
    return {
        "checks": checks,
        "acceptable": all(checks.values()),
        "additional_ending_kg": deferred,
        "comparable_cost": all(checks.values()) and deferred <= 1e-6,
    }
