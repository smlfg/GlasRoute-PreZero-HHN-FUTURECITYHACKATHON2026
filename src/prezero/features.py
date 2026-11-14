"""Feature engineering for container behavior."""

from __future__ import annotations

import pandas as pd


def build_features(df: pd.DataFrame, date: str | pd.Timestamp) -> pd.DataFrame:
    """Build one feature row per location and material up to ``date``."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Location_id",
                "material_type",
                "last_level",
                "days_since_measurement",
                "overfull_rate",
                "avg_daily_increase",
                "season_factor",
            ]
        )

    target = pd.Timestamp(date)
    readings = df.copy()
    readings["date"] = pd.to_datetime(readings["date"])
    readings = readings.loc[readings["date"] <= target].copy()
    if readings.empty:
        return pd.DataFrame(
            columns=[
                "Location_id",
                "material_type",
                "last_level",
                "days_since_measurement",
                "overfull_rate",
                "avg_daily_increase",
                "season_factor",
            ]
        )

    if "fill_level_numeric" not in readings:
        readings["fill_level_numeric"] = readings["fill_level_perc"].map(_numeric_level)
    readings = readings.dropna(subset=["Location_id", "material_type", "date", "fill_level_numeric"])
    readings = readings.sort_values(["Location_id", "material_type", "date"])
    groups = readings.groupby(["Location_id", "material_type"], sort=False)
    result = groups.agg(
        last_level=("fill_level_numeric", "last"),
        last_measurement=("date", "last"),
        overfull_rate=("fill_level_numeric", lambda values: (values == 110).mean()),
    ).reset_index()

    def average_daily_increase(group: pd.DataFrame) -> float:
        days = group["date"].diff().dt.total_seconds().div(86400)
        increases = group["fill_level_numeric"].diff().div(days)
        return float(increases.where(increases > 0).mean()) if increases.notna().any() else 0.0

    rates = groups.apply(average_daily_increase, include_groups=False).rename("avg_daily_increase")
    result = result.merge(rates, on=["Location_id", "material_type"])
    result["days_since_measurement"] = (target - result["last_measurement"]).dt.days
    result["season_factor"] = 1.0 if target.month in [1, 2, 3, 4] else 0.7
    result["season_factor"] = result["season_factor"].astype(float)
    return result.drop(columns=["last_measurement"])


def _numeric_level(value: object) -> float | None:
    if isinstance(value, str) and value.strip().lower() == "overfull":
        return 110.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
