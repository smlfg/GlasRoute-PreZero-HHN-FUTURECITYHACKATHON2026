"""The fixed world every scenario runs against (docs/MODEL_SPEC.md §0/§1).

Single source of truth is W1's ``scripts/simulate_daily.py`` (loaded via importlib, not
copied): ``true_fill_rates`` (r_c, ratio of sums), the BW holiday calendar and the
operating-day helpers. This module only turns them into dense numpy arrays so the
scenario engine can run a 349-day loop in well under a second per policy.

The world exposes the TRUE rate ``rate`` to the engine only. Policies never get the
``World`` object; they see a ``Static`` view (coordinates, sites, real visit dates for the
replay policies) and a per-day ``DayContext`` with walk-forward estimates (engine.py).
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType

import numpy as np
import pandas as pd

from prezero.routing import OperationalConfig, density_for

ROOT = Path(__file__).resolve().parents[3]

_SIM_DAILY: ModuleType | None = None


def simulate_daily() -> ModuleType:
    """W1's world model module (scripts/simulate_daily.py), loaded once via importlib."""
    global _SIM_DAILY
    if _SIM_DAILY is None:
        spec = importlib.util.spec_from_file_location(
            "simulate_daily_w1", ROOT / "scripts" / "simulate_daily.py"
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _SIM_DAILY = mod
    return _SIM_DAILY


def is_operating_day(d: date) -> bool:
    return bool(simulate_daily().is_operating_day(d))


def next_operating_day(d: date) -> date:
    return simulate_daily().get_next_operating_day(d)


@dataclass
class World:
    """Dense arrays over containers c = 0..n-1 (sorted by Location_id, material)."""

    keys: list[tuple[str, str]]
    location_id: np.ndarray  # str
    material: np.ndarray  # str
    lat: np.ndarray
    lon: np.ndarray
    site: np.ndarray  # int site index (identical rounded lat/lon = one stop)
    site_lat: np.ndarray
    site_lon: np.ndarray
    rate: np.ndarray  # TRUE r_c in %-points per day (engine only)
    kg_per_pct: np.ndarray  # mass of one %-point of fill
    activation: np.ndarray  # day index of the first reading (fill 0, production from next day)
    dates: list[date]
    readings: pd.DataFrame  # normalised: Location_id, material_type, date_only, fill_level_numeric, c
    visit_days: list[list[int]] = field(default_factory=list)  # real visits after the first reading

    @property
    def n(self) -> int:
        return len(self.keys)

    def produced_kg(self) -> float:
        """Σ_c r_c × (window end − first reading) × kg/%; identical for every scenario."""
        active_days = (len(self.dates) - 1) - self.activation
        return float(np.sum(self.rate * active_days * self.kg_per_pct))


def build_world(
    readings: pd.DataFrame, locations: pd.DataFrame, cfg: OperationalConfig | None = None
) -> World:
    config = cfg or OperationalConfig()
    sd = simulate_daily()
    work, locs, all_dates = sd._prepare_inputs(readings, locations)
    truth = sd.true_fill_rates(work)
    coords = locs.drop_duplicates("Location_id").set_index("Location_id")[["lat", "lon"]]

    keys = sorted({(str(a), str(b)) for a, b in zip(work["Location_id"], work["material_type"])})
    keys = [k for k in keys if k[0] in coords.index]
    index = {k: i for i, k in enumerate(keys)}
    day_index = {d: i for i, d in enumerate(all_dates)}

    loc_arr = np.array([k[0] for k in keys], dtype=object)
    mat_arr = np.array([k[1] for k in keys], dtype=object)
    lat = coords.loc[loc_arr, "lat"].to_numpy(dtype=float)
    lon = coords.loc[loc_arr, "lon"].to_numpy(dtype=float)
    pts = list(zip(np.round(lat, 6), np.round(lon, 6)))
    uniq = sorted(set(pts))
    site_of = {p: i for i, p in enumerate(uniq)}
    site = np.array([site_of[p] for p in pts], dtype=int)

    rate = np.array([truth[k] for k in keys], dtype=float)
    vol = float(config.container_volume_m3)
    kg_per_pct = np.array([vol * density_for(config, m) / 100.0 for m in mat_arr], dtype=float)

    work = work[[(a, b) in index for a, b in zip(work["Location_id"], work["material_type"])]].copy()
    work["c"] = [index[(a, b)] for a, b in zip(work["Location_id"], work["material_type"])]
    work = work.sort_values(["c", "date_only"]).reset_index(drop=True)
    first = work.groupby("c")["date_only"].min()
    activation = np.array([day_index[first[i]] for i in range(len(keys))], dtype=int)

    visit_days: list[list[int]] = [[] for _ in keys]
    for c, d in zip(work["c"], work["date_only"]):
        di = day_index[d]
        if di != activation[c]:
            visit_days[c].append(di)

    return World(
        keys=keys,
        location_id=loc_arr,
        material=mat_arr,
        lat=lat,
        lon=lon,
        site=site,
        site_lat=np.array([p[0] for p in uniq], dtype=float),
        site_lon=np.array([p[1] for p in uniq], dtype=float),
        rate=rate,
        kg_per_pct=kg_per_pct,
        activation=activation,
        dates=list(all_dates),
        readings=work[["Location_id", "material_type", "date_only", "fill_level_numeric", "c"]],
        visit_days=visit_days,
    )


def calendar_arrays(dates: list[date]) -> tuple[np.ndarray, np.ndarray]:
    """(is_operating_day, days until the next operating day) per day index."""
    op = np.array([is_operating_day(d) for d in dates], dtype=bool)
    gap = np.array([(next_operating_day(d) - d).days for d in dates], dtype=int)
    return op, np.maximum(gap, 1)


def day_after(d: date, n: int = 1) -> date:
    return d + timedelta(days=n)
