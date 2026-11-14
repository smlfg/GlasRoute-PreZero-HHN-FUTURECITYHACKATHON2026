"""Data-only weekly fill-level heatmap matrix."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from prezero.model import Site, build_model


START_DATE = pd.Timestamp("2025-10-17")
END_DATE = pd.Timestamp("2026-09-30")
MATERIAL_ORDER = {"glass_white": 0, "glass_green": 1, "glass_brown": 2}


def _week_starts(start: pd.Timestamp, end: pd.Timestamp, freq: str) -> pd.DatetimeIndex:
    if freq != "W":
        return pd.date_range(start=start, end=end, freq=freq)
    first_monday = start - pd.Timedelta(days=int(start.weekday()))
    return pd.date_range(start=first_monday, end=end, freq="7D")


def _forecast_at(container, target: pd.Timestamp) -> float:
    if not container.measurements:
        return 0.0
    ordered = sorted(container.measurements, key=lambda measurement: measurement.timestamp)
    prior = [measurement for measurement in ordered if measurement.timestamp <= target]
    baseline = prior[-1] if prior else ordered[0]
    days = max(0, int((target - baseline.timestamp).days))
    value = baseline.fill_pct + container.avg_daily_increase() * days
    return max(0.0, min(110.0, float(value)))


def build_heatmap_matrix(
    containers: Iterable[Site] | str | Path | pd.DataFrame,
    start: str | pd.Timestamp = START_DATE,
    end: str | pd.Timestamp = END_DATE,
    freq: str = "W",
) -> pd.DataFrame:
    """Build one value per container and calendar week.

    The returned wide DataFrame stores values in the cells and keeps the
    measured/predicted masks and material ordering in ``DataFrame.attrs``.
    """
    if isinstance(containers, (str, Path, pd.DataFrame)):
        sites = build_model(containers)
    else:
        sites = containers

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    week_starts = _week_starts(start_ts, end_ts, freq)
    week_labels = [f"KW {int(day.isocalendar().week):02d}/{day.year}" for day in week_starts]
    rows: list[dict[str, object]] = []
    predicted_rows: list[list[bool]] = []
    materials: list[str] = []
    average_fills: list[float] = []
    overfull_counts: dict[str, int] = {}
    measurement_counts: dict[str, int] = {}

    for site in sites:
        for container in site.containers:
            ordered = sorted(container.measurements, key=lambda measurement: measurement.timestamp)
            values: list[float] = []
            predicted: list[bool] = []
            for week_start in week_starts:
                week_end = min(week_start + pd.Timedelta(days=6), end_ts)
                in_week = [
                    measurement
                    for measurement in ordered
                    if week_start <= measurement.timestamp <= week_end
                ]
                if in_week:
                    values.append(float(in_week[-1].fill_pct))
                    predicted.append(False)
                else:
                    values.append(_forecast_at(container, week_end))
                    predicted.append(True)
            rows.append({"Location_id": container.location_id, **dict(zip(week_labels, values))})
            predicted_rows.append(predicted)
            material = container.waste_stream.name
            materials.append(material)
            average_fills.append(float(sum(values) / len(values)) if values else 0.0)
            overfull_counts[material] = overfull_counts.get(material, 0) + sum(
                measurement.is_overfull for measurement in ordered
            )
            measurement_counts[material] = measurement_counts.get(material, 0) + len(ordered)

    result = pd.DataFrame(rows).set_index("Location_id")
    order = sorted(
        range(len(rows)),
        key=lambda index: (MATERIAL_ORDER.get(materials[index], 99), average_fills[index], rows[index]["Location_id"]),
    )
    result = result.iloc[order]
    result.attrs.update(
        {
            "week_starts": [day.isoformat() for day in week_starts],
            "week_labels": week_labels,
            "predicted": pd.DataFrame(
                [predicted_rows[index] for index in order],
                index=result.index,
                columns=week_labels,
            ),
            "materials": pd.Series([materials[index] for index in order], index=result.index, name="material"),
            "start": start_ts.isoformat(),
            "end": end_ts.isoformat(),
            "freq": freq,
            "overfull_shares": {
                material: (
                    overfull_counts.get(material, 0) / measurement_counts[material]
                    if measurement_counts.get(material, 0)
                    else 0.0
                )
                for material in ("glass_white", "glass_green", "glass_brown")
            },
        }
    )
    return result
