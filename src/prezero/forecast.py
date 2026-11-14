"""Fill-level forecasts built from the GlasRoute domain model."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

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
        forecast_pct = min(110.0, last_fill + container.avg_daily_increase() * days)
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
