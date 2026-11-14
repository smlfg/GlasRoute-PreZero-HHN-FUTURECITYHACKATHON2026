"""Fill-level forecasts built from the GlasRoute domain model."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from prezero.features import elapsed_days, estimate_fill, get_season_factor
from prezero.model import Container, Site, build_model


FORECAST_COLUMNS = [
    "location_id",
    "material",
    "lat",
    "lon",
    "source",
    "last_fill",
    "last_date",
    "forecast_pct",
    "status",
]


def _status(forecast_pct: float) -> str:
    if forecast_pct >= 110.0:
        return "black"
    if forecast_pct > 80.0:
        return "red"
    if forecast_pct >= 50.0:
        return "yellow"
    return "green"


def _iter_containers(containers: Iterable[Site | Container]) -> Iterable[tuple[Site, Container]]:
    for item in containers:
        if isinstance(item, Site):
            yield from ((item, container) for container in item.containers)
        elif isinstance(item, Container):
            raise TypeError("forecast_fill needs Site objects to include coordinates")
        else:
            raise TypeError(f"unsupported domain object: {type(item).__name__}")


def forecast_fill(
    containers: Iterable[Site] | str | Path | pd.DataFrame,
    target_date: str | pd.Timestamp,
) -> pd.DataFrame:
    """Forecast each model container's fill percentage for ``target_date``.

    A path or readings DataFrame is accepted as a convenience; in that case the
    complete domain model is built using the default locations file.
    """
    if isinstance(containers, (str, Path, pd.DataFrame)):
        sites = build_model(containers)
    else:
        sites = containers

    target = pd.Timestamp(target_date)
    rows: list[dict[str, object]] = []
    for site, container in _iter_containers(sites):
        last_measurement = (
            max(container.measurements, key=lambda measurement: measurement.timestamp)
            if container.measurements
            else None
        )
        last_fill = container.last_fill()
        days = container.days_since_last(target)
        # The last visit emptied the container: it refills from ~0 % at the measured rate.
        forecast_pct = container.est_fill(target)
        rows.append(
            {
                "location_id": container.location_id,
                "material": container.waste_stream.name,
                "lat": site.lat,
                "lon": site.lon,
                "source": site.source,
                "last_fill": last_fill,
                "last_date": last_measurement.timestamp if last_measurement else pd.NaT,
                "forecast_pct": forecast_pct,
                "status": _status(forecast_pct),
            }
        )

    return pd.DataFrame(rows, columns=FORECAST_COLUMNS)


#: Forecast horizons in days, as shown in the map layer switcher.
FORECAST_OFFSETS: tuple[int, ...] = (0, 7, 14, 21)

#: Columns the forecast reads from ``scored_<date>.csv``.
SCORED_FORECAST_COLUMNS = [
    "Location_id",
    "material_type",
    "last_fill_level",
    "last_date",
    "avg_daily_increase",
    "days_since_last",
    "season_factor",
]


def _status_for(forecast_pct: float) -> str:
    """Map a forecast percentage onto the traffic-light status."""
    return _status(forecast_pct)


def _days_since_visit(row: object, base: pd.Timestamp) -> float:
    """Days between the last (emptying) visit and ``base``; prefers ``last_date`` when present."""
    last_date = getattr(row, "last_date", None)
    if last_date is not None and not pd.isna(last_date):
        return float(max(0, (base - pd.Timestamp(last_date)).days))
    return float(getattr(row, "days_since_last", 0.0) or 0.0)


def _effective_days(row: object, base: pd.Timestamp, target: pd.Timestamp) -> float:
    """Season-weighted days from the last (emptying) visit to ``target``."""
    visit = base - pd.Timedelta(days=_days_since_visit(row, base))
    return elapsed_days(visit, target)


def forecast_from_scored(
    scored: pd.DataFrame,
    base_date: str | pd.Timestamp,
    offsets: Iterable[int] = FORECAST_OFFSETS,
) -> pd.DataFrame:
    """Forecast every scored container for each horizon in ``offsets``.

    Measure-and-empty: the last visit emptied the container, so
    ``forecast = avg_daily_increase * days since that visit``,
    capped at 110 %. The result carries one row per container and offset.
    """
    if scored.empty:
        return pd.DataFrame(columns=[*SCORED_FORECAST_COLUMNS, "offset_days", "forecast_pct", "status"])

    base = pd.Timestamp(base_date)
    rows: list[dict[str, object]] = []
    for offset in offsets:
        days = int(offset)
        target = base + pd.Timedelta(days=days)
        # The season factor of the *target* date dampens the growth; it is
        # 1.0 in the Jan-Apr peak and lower in the summer.
        season = get_season_factor(target)
        for row in scored.itertuples(index=False):
            last_fill = float(getattr(row, "last_fill_level", 0.0) or 0.0)
            increase = float(getattr(row, "avg_daily_increase", 0.0) or 0.0)
            since_visit = _days_since_visit(row, base)
            forecast_pct = estimate_fill(increase, _effective_days(row, base, target))
            rows.append(
                {
                    "Location_id": getattr(row, "Location_id"),
                    "material_type": getattr(row, "material_type", ""),
                    "last_fill_level": last_fill,
                    "last_date": getattr(row, "last_date", pd.NaT),
                    "avg_daily_increase": increase,
                    "days_since_last": since_visit,
                    "season_factor": season,
                    "offset_days": days,
                    "target_date": target.date().isoformat(),
                    "forecast_pct": forecast_pct,
                    "status": _status_for(forecast_pct),
                }
            )
    return pd.DataFrame(rows)


def format_forecast_line(offset_days: int, frame: pd.DataFrame) -> str:
    """Render one horizon as ``+7 Tage: 38 rot, 12 schwarz``."""
    label = "Heute" if offset_days == 0 else f"+{offset_days} Tage"
    if frame.empty:
        return f"{label}: 0 rot, 0 schwarz"
    counts = frame["status"].value_counts()
    return (
        f"{label}: {int(counts.get('red', 0))} rot, {int(counts.get('black', 0))} schwarz"
    )


def count_critical(frame: pd.DataFrame) -> int:
    """Number of containers that are red or black (critical) in a horizon."""
    if frame.empty:
        return 0
    return int(frame["status"].isin(["red", "black"]).sum())
