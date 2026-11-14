"""Paired daily ledgers: identical arrivals, different service dates."""

from dataclasses import dataclass, field
from math import isclose
import pandas as pd

from prezero.features import DUE_FILL_PCT, MAX_FILL_PCT, fill_rates_after_emptying
from prezero.history import GEOGRAPHY_NOTE, observed_visits, route_day
from prezero.routing import density_for


@dataclass
class Bin:
    last: pd.Timestamp
    rates: list = field(default_factory=list)
    stock: dict = field(default_factory=lambda: dict(historical=0.0, optimized=0.0))


def workload(keys, bins, scenario, geo, cfg):
    if not keys:
        return dict(km=0.0, shift_hours=0.0, vehicles_needed=0, rounds=0)
    frame = pd.DataFrame(
        [(k[0], k[1], bins[k].stock[scenario]) for k in keys],
        columns=["Location_id", "material_type", "fill_pct"],
    )
    return route_day(frame, geo, cfg)


def schedule(due, bins, geo, cfg, fleet):
    """Largest feasible urgency prefix. A failed joint lift waits until tomorrow."""

    def attempt(keys):
        try:
            route = workload(keys, bins, "optimized", geo, cfg)
        except ValueError as err:
            if "exceeds" not in str(err):
                raise
            return None
        return route if route["vehicles_needed"] <= fleet else None

    route = attempt(due)
    if route is not None:
        return due, route
    low, high, best = 0, len(due), attempt([])
    while high - low > 1:
        mid = (low + high) // 2
        route = attempt(due[:mid])
        if route is None:
            high = mid
        else:
            low, best = mid, route
    return due[:low], best


def simulate(raw, geo, cfg, threshold=DUE_FILL_PCT, fleet=3, cold_rate=2.0):
    if not (
        0 < threshold <= MAX_FILL_PCT
        and fleet >= 1
        and int(fleet) == fleet
        and cold_rate >= 0
    ):
        raise ValueError("Invalid replay assumptions")
    visits = observed_visits(raw)
    calendar = {d: g for d, g in visits.groupby("date")}
    bins, rows = {}, []
    kg = {
        m: cfg.container_volume_m3 * density_for(cfg, m) / 100
        for m in visits.material_type.unique()
    }
    for day in pd.date_range(min(calendar), max(calendar)):
        day_visits = calendar.get(day, visits.iloc[:0])
        observed = {
            (r.Location_id, r.material_type): r.fill_pct
            for r in day_visits.itertuples()
        }
        new = set(observed) - bins.keys()
        row = dict(
            timer_absolute_error_pp=0.0,
            timer_predictions=0,
            date=str(day.date()),
            operating_day=int(bool(observed)),
            admitted_kg=0.0,
            generated_kg=0.0,
        )
        scenarios = ("historical", "optimized")
        for s in scenarios:
            row[s + "_spill_kg"] = 0.0
        for k, b in bins.items():
            rate = sum(b.rates) / len(b.rates) if b.rates else cold_rate
            row["generated_kg"] += rate * kg[k[1]]
            for s in scenarios:
                gross = b.stock[s] + rate
                row[s + "_spill_kg"] += max(0.0, gross - MAX_FILL_PCT) * kg[k[1]]
                b.stock[s] = min(MAX_FILL_PCT, gross)
        for k in sorted(new):
            bins[k] = Bin(day, stock=dict.fromkeys(scenarios, observed[k]))
            row["admitted_kg"] += observed[k] * kg[k[1]]
        for k, level in observed.items():
            if bins[k].rates:
                row["timer_absolute_error_pp"] += abs(
                    level - bins[k].stock["historical"]
                )
                row["timer_predictions"] += 1
        for s in scenarios:
            due = sorted(
                (k for k, b in bins.items() if b.stock[s] >= threshold or k in new),
                key=lambda k: (-bins[k].stock[s], k),
            )
            if s == "historical":
                served = list(observed)
                route = workload(served, bins, s, geo, cfg)
                if route["vehicles_needed"] > fleet:
                    raise ValueError(
                        "Historical workload infeasible at assumed fleet size"
                    )
            else:
                served, route = schedule(due if observed else [], bins, geo, cfg, fleet)
            row.update(
                {
                    s + "_" + key: route[key]
                    for key in ("km", "shift_hours", "vehicles_needed", "rounds")
                }
            )
            row[s + "_overflow_bin_days"] = sum(
                b.stock[s] >= MAX_FILL_PCT for b in bins.values()
            )
            row[s + "_emptyings"] = len(served)
            row[s + "_fill_sum"] = sum(bins[k].stock[s] for k in served)
            row[s + "_collected_kg"] = sum(bins[k].stock[s] * kg[k[1]] for k in served)
            for k in served:
                bins[k].stock[s] = 0.0
            row[s + "_ending_kg"] = sum(b.stock[s] * kg[k[1]] for k, b in bins.items())
            row[s + "_due_backlog"] = sum(
                b.stock[s] >= threshold for b in bins.values()
            )
        # End-of-day observation update; the new interval can affect tomorrow only.
        for k, level in observed.items():
            b = bins[k]
            b.rates.extend(fill_rates_after_emptying([b.last, day], [0.0, level]))
            b.last = day
        rows.append(row)
    daily = pd.DataFrame(rows)
    report = dict(
        geography=GEOGRAPHY_NOTE,
        start=rows[0]["date"],
        end=rows[-1]["date"],
        operating_days=int(daily.operating_day.sum()),
        threshold_pct=threshold,
        fleet_limit=fleet,
        cold_rate_pp_day=cold_rate,
        assumptions=cfg.to_dict(),
    )
    for s in ("historical", "optimized"):

        def total(key):
            return float(daily[s + "_" + key].sum())

        stock = dict(
            beginning_kg=0.0,
            admitted_kg=float(daily.admitted_kg.sum()),
            generated_kg=float(daily.generated_kg.sum()),
            collected_kg=total("collected_kg"),
            spill_kg=total("spill_kg"),
            ending_kg=float(daily[s + "_ending_kg"].iloc[-1]),
        )
        if not isclose(
            stock["admitted_kg"] + stock["generated_kg"],
            stock["collected_kg"] + stock["ending_kg"] + stock["spill_kg"],
            abs_tol=1e-6,
        ):
            raise ValueError("Mass balance failed")
        n = int(total("emptyings"))
        report[s] = dict(
            inventory=stock,
            emptyings=n,
            mean_fill_pct=total("fill_sum") / n if n else None,
            overflow_bin_days=int(total("overflow_bin_days")),
            km=total("km"),
            hours=total("shift_hours"),
            vehicle_days=int(total("vehicles_needed")),
            rounds=int(total("rounds")),
            peak=int(daily[s + "_vehicles_needed"].max()),
            due_backlog=int(daily[s + "_due_backlog"].iloc[-1]),
        )

    def measured(g):
        return dict(
            emptyings=len(g),
            mean_fill_pct=float(g.fill_pct.mean()),
            median_fill_pct=float(g.fill_pct.median()),
            histogram={
                str(v): int(n)
                for v, n in g.fill_pct.value_counts().sort_index().items()
            },
            overfull=int(g.overfull.sum()),
            estimated_kg=float(
                sum(r.fill_pct * kg[r.material_type] for r in g.itertuples())
            ),
        )

    report["observed"] = measured(visits)
    report["observed"]["colors"] = {
        m: measured(g) for m, g in visits.groupby("material_type")
    }
    return daily, report
