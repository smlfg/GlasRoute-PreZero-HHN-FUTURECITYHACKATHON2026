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


def _series_values(
    series: pd.DataFrame,
    week_starts: pd.DatetimeIndex,
    end_ts: pd.Timestamp,
) -> tuple[list[float], list[bool]]:
    ordered = series.sort_values("date")
    dates = list(pd.to_datetime(ordered["date"]))
    fills = [float(value) for value in ordered["fill_level_numeric"]]
    rates = [
        (fills[index] - fills[index - 1]) / (dates[index] - dates[index - 1]).days
        for index in range(1, len(fills))
        if (dates[index] - dates[index - 1]).days > 0 and fills[index] >= fills[index - 1]
    ]
    average_increase = sum(rates) / len(rates) if rates else 0.0
    values: list[float] = []
    predicted: list[bool] = []
    for week_start in week_starts:
        week_end = min(week_start + pd.Timedelta(days=6), end_ts)
        in_week = [
            index
            for index, timestamp in enumerate(dates)
            if week_start <= timestamp <= week_end
        ]
        if in_week:
            values.append(fills[in_week[-1]])
            predicted.append(False)
            continue
        prior = [index for index, timestamp in enumerate(dates) if timestamp <= week_end]
        baseline_index = prior[-1] if prior else 0
        days = max(0, int((week_end - dates[baseline_index]).days))
        values.append(max(0.0, min(110.0, fills[baseline_index] + average_increase * days)))
        predicted.append(True)
    return values, predicted


def _build_reading_matrix(
    readings: pd.DataFrame,
    locations: pd.DataFrame,
    week_starts: pd.DatetimeIndex,
    week_labels: list[str],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> pd.DataFrame:
    work = readings.copy()
    work["Location_id"] = work["Location_id"].astype(str).str.strip()
    work["material_type"] = work["material_type"].astype(str).str.strip().str.lower()
    work["date"] = pd.to_datetime(work["date"])
    if "fill_level_numeric" not in work:
        work["fill_level_numeric"] = work["fill_level_perc"].map(
            lambda value: 110.0 if str(value).strip().lower() == "overfull" else float(value)
        )
    series_rows: list[dict[str, object]] = []
    overfull_counts: dict[str, int] = {}
    measurement_counts: dict[str, int] = {}
    for (location_id, material), series in work.groupby(["Location_id", "material_type"], sort=True):
        values, predicted = _series_values(series, week_starts, end_ts)
        key = f"{location_id} · {material}"
        series_rows.append(
            {
                "key": key,
                "location_id": location_id,
                "material": f"glass_{material}",
                "values": values,
                "predicted": predicted,
            }
        )
        overfull_counts[material] = overfull_counts.get(material, 0) + int(
            (series["fill_level_numeric"] >= 110).sum()
        )
        measurement_counts[material] = measurement_counts.get(material, 0) + len(series)

    location_ids = locations["Location_id"].astype(str).tolist()
    rows = []
    predicted_rows = []
    for location_id in location_ids:
        matching = [row for row in series_rows if row["location_id"] == location_id]
        values = [
            sum(row["values"][index] for row in matching) / len(matching)
            if matching
            else 0.0
            for index in range(len(week_labels))
        ]
        predicted = [
            all(row["predicted"][index] for row in matching) if matching else True
            for index in range(len(week_labels))
        ]
        rows.append({"Location_id": location_id, **dict(zip(week_labels, values))})
        predicted_rows.append(predicted)
    result = pd.DataFrame(rows).set_index("Location_id").sort_index()
    location_order = list(result.index)
    result.attrs.update(
        {
            "week_starts": [day.isoformat() for day in week_starts],
            "week_labels": week_labels,
            "predicted": pd.DataFrame(predicted_rows, index=location_order, columns=week_labels),
            "materials": pd.Series("mixed", index=location_order, name="material"),
            "series_values": pd.DataFrame(
                [row["values"] for row in series_rows],
                index=[row["key"] for row in series_rows],
                columns=week_labels,
            ),
            "series_predicted": pd.DataFrame(
                [row["predicted"] for row in series_rows],
                index=[row["key"] for row in series_rows],
                columns=week_labels,
            ),
            "series_materials": pd.Series(
                [row["material"] for row in series_rows],
                index=[row["key"] for row in series_rows],
                name="material",
            ),
            "start": start_ts.isoformat(),
            "end": end_ts.isoformat(),
            "freq": "W",
            "overfull_shares": {
                f"glass_{material}": (
                    overfull_counts.get(material, 0) / measurement_counts[material]
                    if measurement_counts.get(material, 0)
                    else 0.0
                )
                for material in ("white", "green", "brown")
            },
        }
    )
    return result


def build_heatmap_matrix(
    containers: Iterable[Site] | str | Path | pd.DataFrame,
    start: str | pd.Timestamp = START_DATE,
    end: str | pd.Timestamp = END_DATE,
    freq: str = "W",
    locations: pd.DataFrame | None = None,
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
    if isinstance(containers, pd.DataFrame) and locations is not None:
        return _build_reading_matrix(
            containers,
            locations,
            week_starts,
            week_labels,
            start_ts,
            end_ts,
        )
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
