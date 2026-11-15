"""Pluggable scenario engine: one world, many policies (docs/MODEL_SPEC.md §0/§1/§4/§9).

Day loop over the replay calendar (first..last reading day, 349 days):

1. WORLD: every container active since an earlier day gains its TRUE rate r_c (uncapped);
   containers whose first reading is today are activated at exactly 0 %.
2. BELIEF: the walk-forward estimator ingests all readings with date < d
   (ratio of sums Σ level / Σ Δt from the 2nd reading, material median fallback; §9.2).
3. POLICY decides which containers to empty, seeing ONLY the ``DayContext``
   (estimates, age since last emptying, calendar) and the ``Static`` view (no true rate,
   no true fill).
4. CO-EMPTY: if a container at a stop (physical lat/lon point) is emptied, the stop's other
   active containers with ESTIMATED fill ≥ ``bundle_threshold`` are emptied too
   (None = off, the default: only due containers; §9.5/§10). In per_colour only same colour.
5. Emptied containers hand over their TRUE fill (uncapped) and reset to exactly 0.
   Container-days with true fill ≥ 110 % after the decision count as overflow events.
6. DAY EVALUATOR turns the served sites into stops / km / vehicles / hours / unloads.
   Pluggable: ``evaluate_day(sites_df, cfg) -> dict``; default ``km_evaluator`` wraps
   ``routing._simulate_constrained_routes`` (nearest neighbour, shift and payload limits).
   ``truck_mode``: ``multi_chamber`` (default) = one stop serves all colours at a point;
   ``per_colour`` = one tour per colour, evaluate_day is called per colour and summed.

Invariant per scenario: collected + end_stock == produced (same produced in every scenario).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

import numpy as np
import pandas as pd

from prezero.routing import OperationalConfig, _simulate_constrained_routes
from prezero.sim.world import World, build_world, calendar_arrays, simulate_daily

OVERFLOW_PCT = 110.0
DEFAULT_BUNDLE_THRESHOLD: float | None = None
TRUCK_MODES = ("multi_chamber", "per_colour")

EvaluateDay = Callable[[pd.DataFrame, OperationalConfig], dict[str, Any]]


# ---------------------------------------------------------------- estimator (§9.2)
class WalkForwardEstimator:
    """Incremental walk-forward rate per container, strictly from readings with date < d.

    r̂_c(d) = Σ level_i / (t_last − t_first) over the visible readings i ≥ 2 (ratio of sums;
    each reading is a visit that empties, so level_i is the glass of interval i).
    Containers with < 2 visible readings get the median r̂ of their material over the
    containers that have one; if a material has none yet, ``DEFAULT_RATES`` of W1.
    Never mean(level/Δt) (biased, MODEL_SPEC §2).
    """

    def __init__(self, readings: pd.DataFrame, n: int, materials: np.ndarray, day_of: dict[date, int]):
        order = readings.sort_values("date_only", kind="stable")
        self._day = np.array([day_of[d] for d in order["date_only"]], dtype=int)
        self._c = order["c"].to_numpy(dtype=int)
        self._lvl = order["fill_level_numeric"].to_numpy(dtype=float)
        self._p = 0
        self.n = n
        self.first = np.full(n, -1, dtype=int)
        self.last = np.full(n, -1, dtype=int)
        self.seen = np.zeros(n, dtype=int)
        self.sum_after_first = np.zeros(n, dtype=float)
        self.materials = materials
        self._mat_masks = {m: materials == m for m in np.unique(materials)}
        self._defaults = simulate_daily().DEFAULT_RATES
        self.rate = np.array([self._defaults.get(m, 1.5) for m in materials], dtype=float)
        self.visible_until = -1  # all readings with day index < visible_until are ingested

    def advance(self, day: int) -> np.ndarray:
        """Ingest readings with day index < ``day`` and return r̂ (copy-safe array)."""
        changed = False
        while self._p < len(self._day) and self._day[self._p] < day:
            c, t, lvl = self._c[self._p], self._day[self._p], self._lvl[self._p]
            if self.seen[c] == 0:
                self.first[c] = t
            else:
                self.sum_after_first[c] += lvl
            self.last[c] = t
            self.seen[c] += 1
            self._p += 1
            changed = True
        self.visible_until = day
        if changed:
            span = self.last - self.first
            ok = (self.seen >= 2) & (span > 0)
            rate = np.zeros(self.n, dtype=float)
            rate[ok] = self.sum_after_first[ok] / span[ok]
            for m, mask in self._mat_masks.items():
                fitted = rate[mask & ok]
                fallback = float(np.median(fitted)) if fitted.size else self._defaults.get(m, 1.5)
                rate[mask & ~ok] = fallback
            self.rate = rate
        return self.rate


# ---------------------------------------------------------------- policy interface
@dataclass(frozen=True)
class Static:
    """What a policy may know up front: geometry, calendar, real visit dates (for replays)."""

    keys: list[tuple[str, str]]
    material: np.ndarray
    lat: np.ndarray
    lon: np.ndarray
    site: np.ndarray
    site_lat: np.ndarray
    site_lon: np.ndarray
    activation: np.ndarray
    dates: list[date]
    is_op: np.ndarray
    gap: np.ndarray  # days to the next operating day
    visit_days: list[list[int]]

    @property
    def n(self) -> int:
        return len(self.keys)


@dataclass
class DayContext:
    day: int
    date: date
    is_op: bool
    gap: int
    active: np.ndarray  # bool
    age: np.ndarray  # days since last emptying / activation (0 for inactive)
    est_rate: np.ndarray  # walk-forward r̂ (%/day)

    @property
    def est_fill(self) -> np.ndarray:
        return np.where(self.active, self.est_rate * self.age, 0.0)


class Policy(Protocol):
    id: str
    label: str

    def setup(self, static: Static) -> None: ...

    def decide(self, ctx: DayContext) -> np.ndarray: ...


# ---------------------------------------------------------------- day evaluator
def km_evaluator(sites_df: pd.DataFrame, cfg: OperationalConfig) -> dict[str, Any]:
    """Default day evaluator: W1's km routing model (``_simulate_constrained_routes``)."""
    stops, unloads, vehicles, km, mass = _simulate_constrained_routes(sites_df, cfg)
    return {
        "stops": sum(1 for s in stops if s.get("stop_type") == "collection"),
        "km": float(km),
        "vehicles": len(vehicles),
        "hours": float(sum(float(v["shift_hours"]) for v in vehicles)),
        "unloads": len(unloads),
        "mass_kg": float(mass),
        "vehicle_detail": vehicles,
        "time_model": "km",
    }


# ---------------------------------------------------------------- result
@dataclass
class ScenarioResult:
    id: str
    label: str
    daily: pd.DataFrame
    containers: pd.DataFrame
    ledger: dict[str, float]
    events: pd.DataFrame  # one row per emptying: day, date, c, fill_pct, mass_kg, bundled
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    runtime_s: float = 0.0
    time_model: str = "km"
    truck_mode: str = "multi_chamber"
    bundle_threshold: float | None = None


def static_view(world: World) -> Static:
    is_op, gap = calendar_arrays(world.dates)
    return Static(
        keys=world.keys,
        material=world.material,
        lat=world.lat,
        lon=world.lon,
        site=world.site,
        site_lat=world.site_lat,
        site_lon=world.site_lon,
        activation=world.activation,
        dates=world.dates,
        is_op=is_op,
        gap=gap,
        visit_days=world.visit_days,
    )


def run_scenario(
    policy: Policy,
    readings: pd.DataFrame | None = None,
    locations: pd.DataFrame | None = None,
    cfg: OperationalConfig | None = None,
    evaluate_day: EvaluateDay | None = None,
    bundle_threshold: float | None | str = "policy",
    world: World | None = None,
    static: Static | None = None,
    truck_mode: str = "multi_chamber",
) -> ScenarioResult:
    """Run one policy over the full calendar against the shared world.

    ``bundle_threshold="policy"`` uses ``policy.bundle_threshold`` (default 50 %, None = off).
    Pass ``world``/``static`` to reuse a prebuilt world across scenarios (same r_c).
    """
    import time

    t0 = time.perf_counter()
    config = cfg or OperationalConfig()
    if world is None:
        assert readings is not None and locations is not None
        world = build_world(readings, locations, config)
    static = static or static_view(world)
    evaluate = evaluate_day or km_evaluator
    if bundle_threshold == "policy":
        bundle_threshold = getattr(policy, "bundle_threshold", DEFAULT_BUNDLE_THRESHOLD)
    if truck_mode not in TRUCK_MODES:
        raise ValueError(f"truck_mode must be one of {TRUCK_MODES}")
    mat_codes = np.unique(world.material, return_inverse=True)[1]
    # co-empty group: the stop (multi_chamber) or stop × colour (per_colour)
    group = world.site * 3 + mat_codes if truck_mode == "per_colour" else world.site.copy()

    n, n_days = world.n, len(world.dates)
    day_of = {d: i for i, d in enumerate(world.dates)}
    est = WalkForwardEstimator(world.readings, n, world.material, day_of)
    policy.setup(static)

    fill = np.zeros(n)
    active = np.zeros(n, dtype=bool)
    last_empty = world.activation.copy()
    n_empt = np.zeros(n, dtype=int)
    fill_sum = np.zeros(n)
    overfull = np.zeros(n, dtype=int)
    ovf_days = np.zeros(n, dtype=int)
    collected_kg = 0.0
    rows: list[dict[str, Any]] = []
    ev_rows: list[tuple[int, int, float, float, bool]] = []
    diags: list[dict[str, Any]] = []
    time_model = "km"

    for di, d in enumerate(world.dates):
        fill[active] += world.rate[active]
        new = world.activation == di
        fill[new] = 0.0
        active |= new

        rate_hat = est.advance(di)
        age = np.where(active, di - last_empty, 0)
        ctx = DayContext(
            day=di, date=d, is_op=bool(static.is_op[di]), gap=int(static.gap[di]),
            active=active.copy(), age=age, est_rate=rate_hat.copy(),
        )
        chosen = np.asarray(policy.decide(ctx), dtype=bool) & active
        sel = chosen.copy()
        if bundle_threshold is not None and chosen.any():
            groups = np.unique(group[chosen])
            sel |= active & np.isin(group, groups) & (ctx.est_fill >= float(bundle_threshold))
        idx = np.flatnonzero(sel)

        f_emp = fill[idx].copy()
        fill_before = np.zeros(n)
        fill_before[idx] = f_emp
        m_emp = f_emp * world.kg_per_pct[idx]
        collected_kg += float(m_emp.sum())
        n_empt[idx] += 1
        fill_sum[idx] += f_emp
        overfull[idx] += f_emp >= OVERFLOW_PCT
        for c, f_v, m_v in zip(idx, f_emp, m_emp):
            ev_rows.append((di, int(c), float(f_v), float(m_v), bool(not chosen[c])))
        fill[idx] = 0.0
        last_empty[idx] = di
        on_emptied = getattr(policy, "on_emptied", None)
        if on_emptied is not None:
            on_emptied(ctx, sel)

        ovf_mask = active & (fill >= OVERFLOW_PCT)
        ovf_days += ovf_mask
        n_ovf = int(ovf_mask.sum())

        res: dict[str, Any] = {"stops": 0, "km": 0.0, "vehicles": 0, "hours": 0.0, "unloads": 0}
        if idx.size:
            if truck_mode == "per_colour":
                parts = [idx[world.material[idx] == m] for m in np.unique(world.material[idx])]
            else:
                parts = [idx]
            res = {}
            day_sites = []
            for part in parts:
                sites_df, uniq = _sites_frame(world, part, fill_before[part], config)
                r = evaluate(sites_df, config)
                time_model = str(r.get("time_model", time_model))
                for k, v in r.items():
                    if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
                        res[k] = res.get(k, 0) + v
                day_sites.append(
                    sites_df[["lat", "lon", "critical_bins", "mass_kg", "primary_material"]]
                    .assign(site=uniq)
                    .rename(columns={"critical_bins": "n_containers"})
                )
            diags.append(
                {
                    "date": str(d),
                    "sites": pd.concat(day_sites).to_dict(orient="records"),
                    "vehicles": int(res.get("vehicles", 0)),
                    "unloads": int(res.get("unloads", 0)),
                    "km": float(res.get("km", 0.0)),
                    "hours": float(res.get("hours", 0.0)),
                }
            )
        rows.append(
            {
                "date": str(d),
                "n_emptyings": int(idx.size),
                "n_overflow_events": n_ovf,
                "avg_fill_at_emptying_pct": round(float(f_emp.mean()), 2) if idx.size else 0.0,
                "tonnage_t": round(float(m_emp.sum()) / 1000.0, 3),
                "stops": int(res.get("stops", 0)),
                "vehicles_needed": int(res.get("vehicles", 0)),
                "shift_hours": round(float(res.get("hours", 0.0)), 2),
                "km": round(float(res.get("km", 0.0)), 2),
                "cost_eur": None,
                "n_overfull_at_emptying": int((f_emp >= OVERFLOW_PCT).sum()),
                "unloads": int(res.get("unloads", 0)),
            }
        )

    end_stock_kg = float(np.sum(fill * world.kg_per_pct))
    produced_kg = world.produced_kg()
    total_empt = int(n_empt.sum())
    ledger = {
        "produced_t": produced_kg / 1000.0,
        "collected_t": collected_kg / 1000.0,
        "end_stock_t": end_stock_kg / 1000.0,
        "overflow_container_days": int(ovf_days.sum()),
        "overfull_at_emptying": int(overfull.sum()),
        "n_emptyings": total_empt,
        "avg_fill_at_emptying_pct": float(fill_sum.sum() / total_empt) if total_empt else 0.0,
    }
    containers = pd.DataFrame(
        {
            "location_id": world.location_id,
            "material": world.material,
            "lat": world.lat,
            "lon": world.lon,
            "site": world.site,
            "emptyings": n_empt,
            "avg_fill_pct": np.where(n_empt > 0, fill_sum / np.maximum(n_empt, 1), np.nan),
            "overfull_at_emptying": overfull,
            "overflow_events": ovf_days,
        }
    )
    events = pd.DataFrame(ev_rows, columns=["day", "c", "fill_pct", "mass_kg", "bundled"])
    events["date"] = [world.dates[i] for i in events["day"]]
    return ScenarioResult(
        id=getattr(policy, "id", "scenario"),
        label=getattr(policy, "label", ""),
        daily=pd.DataFrame(rows),
        containers=containers,
        ledger=ledger,
        events=events,
        diagnostics=diags,
        runtime_s=time.perf_counter() - t0,
        time_model=time_model,
        truck_mode=truck_mode,
        bundle_threshold=None if bundle_threshold is None else float(bundle_threshold),
    )


def _sites_frame(
    world: World, idx: np.ndarray, f_emp: np.ndarray, config: OperationalConfig
) -> tuple[pd.DataFrame, np.ndarray]:
    """Served containers -> one row per stop (lat/lon point), sorted by site index."""
    m_emp = f_emp * world.kg_per_pct[idx]
    uniq, inv = np.unique(world.site[idx], return_inverse=True)
    cnt = np.bincount(inv)
    fmax = np.zeros(len(uniq))
    np.maximum.at(fmax, inv, f_emp)
    first_loc = [str(world.location_id[idx[inv == k]].min()) for k in range(len(uniq))]
    first_mat = [str(world.material[idx[np.flatnonzero(inv == k)[0]]]) for k in range(len(uniq))]
    sites_df = pd.DataFrame(
        {
            "lat": world.site_lat[uniq],
            "lon": world.site_lon[uniq],
            "Location_id": first_loc,
            "critical_bins": cnt,
            "mass_kg": np.bincount(inv, weights=m_emp),
            "volume_m3": np.bincount(inv, weights=f_emp / 100.0 * float(config.container_volume_m3)),
            "score": fmax / 100.0,
            "critical": True,
            "primary_material": first_mat,
            "last_fill_level": fmax,
            "est_fill_level": fmax,
            "source": "osm_assigned",
            "confidence": "simulated_mapping",
        }
    )
    return sites_df, uniq
