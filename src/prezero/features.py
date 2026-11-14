"""Feature engineering for container behavior.

Data semantics (PreZero process): the collection vehicle drives to a container, the driver
**estimates the fill level and then empties it**. Every reading is therefore the level found at a
visit, and the container restarts at ~0 % right after it. Consequences used throughout the package:

* fill rate of an interval = level found at visit i / days since visit i-1 (it started empty);
* estimated level now = fill rate x days since the last visit, capped at 110 %;
* no fixed season factor: the backtest (scripts/backtest.py) showed the hard-coded factor biased
  predictions by about -17 pp; ``season_factor`` is kept only as an informational column.
* ``last_fill_level`` is the level *found* at the last visit, not the current level.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HIGH_SEASON_MONTHS = frozenset({1, 2, 3, 4})
SHOULDER_SEASON_MONTHS = frozenset({5, 12})

FEATURE_COLUMNS = [
    "Location_id",
    "material_type",
    "last_date",
    "last_fill_level",
    "days_since_last",
    "overfull_rate",
    "avg_daily_increase",
    "rate_source",
    "est_fill_level",
    "due_date",
    "days_until_due",
    "overflow_date",
    "season_factor",
    "reading_count",
]

#: Timer: a container is due for emptying once its estimated level reaches this value.
DUE_FILL_PCT = 80.0  # Annahme, von PreZero zu ersetzen

#: Readings are capped at this value; ``overfull`` is encoded as 110 %.
MAX_FILL_PCT = 110.0


def get_season_factor(date: str | pd.Timestamp) -> float:
    """Return seasonal demand factor (Jan-Apr peak = 1.0)."""
    month = pd.Timestamp(date).month
    if month in HIGH_SEASON_MONTHS:
        return 1.0
    if month in SHOULDER_SEASON_MONTHS:
        return 0.7
    return 0.5


def fill_rates_after_emptying(dates: list, levels: list[float]) -> list[float]:
    """Daily fill rates per interval: level found at a visit / days since the previous visit.

    The previous visit emptied the container, so each interval starts at ~0 %.
    """
    rates: list[float] = []
    for i in range(1, len(levels)):
        dt_days = (pd.Timestamp(dates[i]) - pd.Timestamp(dates[i - 1])) / pd.Timedelta(days=1)
        if dt_days > 0:
            rates.append(float(levels[i]) / float(dt_days))
    return rates


def elapsed_days(start: str | pd.Timestamp, end: str | pd.Timestamp) -> float:
    """Whole days from ``start`` to ``end`` (0 if ``end`` is not later)."""
    delta = (pd.Timestamp(end).normalize() - pd.Timestamp(start).normalize()).days
    return float(max(0, delta))


def estimate_fill(rate_per_day: float, effective_days: float) -> float:
    """Estimated current level of a container that was emptied ``effective_days`` ago."""
    value = float(rate_per_day) * max(0.0, float(effective_days))
    return max(0.0, min(MAX_FILL_PCT, value))


def date_reaching(
    rate_per_day: float, last_visit: str | pd.Timestamp, level_pct: float, max_days: int = 730
) -> pd.Timestamp | None:
    """First day the container (emptied at ``last_visit``) is estimated to reach ``level_pct``.

    ``None`` if the rate is 0 or the level is not reached within ``max_days``.
    """
    if rate_per_day is None or float(rate_per_day) <= 0.0:
        return None
    days = int(np.ceil(float(level_pct) / float(rate_per_day)))
    if days > max_days:
        return None
    return pd.Timestamp(last_visit).normalize() + pd.Timedelta(days=max(1, days))


def _avg_fill_rate(group: pd.DataFrame) -> float | None:
    """Mean daily fill rate after emptying, or ``None`` with fewer than two visits."""
    rates = fill_rates_after_emptying(
        list(group["date"]), [float(v) for v in group["fill_level_numeric"]]
    )
    return float(sum(rates) / len(rates)) if rates else None


def build_features(df: pd.DataFrame, date: str | pd.Timestamp) -> pd.DataFrame:
    """Build per-container/material feature table using readings up to ``date``."""
    target_date = pd.Timestamp(date)
    work = df.copy()
    work["date"] = pd.to_datetime(work["date"])
    work = work[work["date"] <= target_date]

    if work.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    work = work.sort_values(["Location_id", "material_type", "date"]).reset_index(drop=True)
    season = get_season_factor(target_date)

    rows: list[dict] = []
    for (loc_id, material), group in work.groupby(["Location_id", "material_type"], sort=True):
        last_row = group.iloc[-1]
        last_date = pd.Timestamp(last_row["date"])
        rows.append(
            {
                "Location_id": loc_id,
                "material_type": material,
                "last_date": last_date,
                "last_fill_level": float(last_row["fill_level_numeric"]),
                "days_since_last": int((target_date - last_date).days),
                "overfull_rate": float((group["fill_level_numeric"] >= MAX_FILL_PCT).mean()),
                "avg_daily_increase": _avg_fill_rate(group),
                "season_factor": season,
                "reading_count": int(len(group)),
            }
        )

    out = pd.DataFrame(rows)
    # Containers with a single visit have no interval: use the median rate of their glass colour.
    known = out["avg_daily_increase"].notna()
    out["rate_source"] = known.map({True: "history", False: "material_median"})
    medians = out[known].groupby("material_type")["avg_daily_increase"].median()
    overall = float(out.loc[known, "avg_daily_increase"].median()) if known.any() else 0.0
    fallback = out["material_type"].map(medians).astype(float).fillna(overall)
    out["avg_daily_increase"] = (
        pd.to_numeric(out["avg_daily_increase"], errors="coerce").astype(float).fillna(fallback)
    )
    out["est_fill_level"] = [
        round(estimate_fill(rate, elapsed_days(last, target_date)), 1)
        for rate, last in zip(out["avg_daily_increase"], out["last_date"])
    ]
    # Timer per container: when must it be emptied (80 %) and when does it overflow (110 %)?
    out["due_date"] = [
        date_reaching(rate, last, DUE_FILL_PCT)
        for rate, last in zip(out["avg_daily_increase"], out["last_date"])
    ]
    out["overflow_date"] = [
        date_reaching(rate, last, MAX_FILL_PCT)
        for rate, last in zip(out["avg_daily_increase"], out["last_date"])
    ]
    out["due_date"] = pd.to_datetime(out["due_date"])
    out["overflow_date"] = pd.to_datetime(out["overflow_date"])
    # Negative = overdue by that many days; NaN = no rate, no timer.
    out["days_until_due"] = (out["due_date"] - target_date.normalize()).dt.days
    return out[FEATURE_COLUMNS]
