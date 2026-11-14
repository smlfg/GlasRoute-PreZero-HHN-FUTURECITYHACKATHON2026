"""Feature engineering for container behavior."""

from __future__ import annotations

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
    "season_factor",
    "reading_count",
]


def get_season_factor(date: str | pd.Timestamp) -> float:
    """Return seasonal demand factor (Jan-Apr peak = 1.0)."""
    month = pd.Timestamp(date).month
    if month in HIGH_SEASON_MONTHS:
        return 1.0
    if month in SHOULDER_SEASON_MONTHS:
        return 0.7
    return 0.5


def _avg_positive_daily_increase(group: pd.DataFrame) -> float:
    """Compute average daily fill increase across non-emptying intervals."""
    if len(group) < 2:
        return 0.0
    dates = group["date"].to_numpy()
    levels = group["fill_level_numeric"].to_numpy(dtype=float)
    rates: list[float] = []
    for i in range(1, len(group)):
        dt_days = (dates[i] - dates[i - 1]) / pd.Timedelta(days=1)
        delta = levels[i] - levels[i - 1]
        if dt_days > 0 and delta >= 0:
            rates.append(float(delta / dt_days))
    if not rates:
        return 0.0
    return float(sum(rates) / len(rates))


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
                "overfull_rate": float((group["fill_level_numeric"] >= 110.0).mean()),
                "avg_daily_increase": _avg_positive_daily_increase(group),
                "season_factor": season,
                "reading_count": int(len(group)),
            }
        )

    return pd.DataFrame(rows, columns=FEATURE_COLUMNS)
