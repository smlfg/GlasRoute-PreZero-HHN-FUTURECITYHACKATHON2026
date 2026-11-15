"""Cadence model: every container as a producer-consumer system.

Core model (see ``docs/MODEL_SPEC.md``):

* A container fills at an approximately constant rate ``r`` (percentage points per
  day). The rate is estimated from the fill level found at a visit divided by the
  days since the previous visit — every visit is a *measure and reset to 0*.
* The consumer side is the **emptying cadence** ``T`` (days between emptyings).
* The ideal cadence follows from capacity and buffer::

      T = (capacity - buffer) / r

  ``capacity`` is 100 % of the container volume, ``buffer`` is the safety margin
  that is kept free (the "empty at" threshold). ``T`` is recalculated after every
  new measurement.
* Routing is a *secondary* concern: it bundles the due containers into area tours
  and never changes how much glass exists, only how efficiently it is collected.

The module is deliberately free of any routing/geometry logic so that the
cadence numbers can be checked on their own.

Status rules for the dispatcher view:

* **yellow** — emptied too often: the container was found below
  ``LOW_FILL_PCT`` at its last ``LOW_FILL_WINDOW`` visits.
* **red**   — critical: the container overflows (reaches ``MAX_FILL_PCT``)
  before it can be emptied again.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

#: Fill level at which a container is emptied (the "Puffer"/threshold), in percent.
DEFAULT_EMPTY_AT_PCT = 80.0

#: Shortest allowed cadence in days (Annahme).
DEFAULT_MIN_CADENCE_DAYS = 3.0

#: Longest allowed cadence in days (Annahme).
DEFAULT_MAX_CADENCE_DAYS = 14.0

#: Truck-days available per week (Annahme) — the planning budget.
DEFAULT_TRUCK_DAYS_PER_WEEK = 15.0

#: Service time per stop in minutes (Annahme).
DEFAULT_SERVICE_MIN_PER_STOP = 5.0

#: Drive time per hop in minutes: urban (Annahme).
DEFAULT_DRIVE_MIN_URBAN = 7.0

#: Drive time per hop in minutes: rural (Annahme).
DEFAULT_DRIVE_MIN_RURAL = 15.0

#: Readings are capped at this value; ``overfull`` is encoded as 110 %.
MAX_FILL_PCT = 110.0

#: A container found below this level was emptied too early (yellow).
LOW_FILL_PCT = 30.0

#: Number of last visits used for the "emptied too often" rule (yellow).
LOW_FILL_WINDOW = 3

#: Areas recognized for the drive-time assumption (Annahme).
AREA_URBAN = "urban"
AREA_RURAL = "rural"

#: Default container volume in m³ (Annahme).
DEFAULT_CONTAINER_VOLUME_M3 = 2.5

#: Glass density in kg/m³ (Annahme).
DEFAULT_DENSITY_KG_PER_M3 = 400.0


@dataclass(frozen=True)
class CadenceParams:
    """One point of the what-if grid (every field carries its source)."""

    empty_at_pct: float = DEFAULT_EMPTY_AT_PCT
    min_cadence_days: float = DEFAULT_MIN_CADENCE_DAYS
    max_cadence_days: float = DEFAULT_MAX_CADENCE_DAYS
    truck_days_per_week: float = DEFAULT_TRUCK_DAYS_PER_WEEK
    service_min_per_stop: float = DEFAULT_SERVICE_MIN_PER_STOP
    drive_min_urban: float = DEFAULT_DRIVE_MIN_URBAN
    drive_min_rural: float = DEFAULT_DRIVE_MIN_RURAL
    container_volume_m3: float = DEFAULT_CONTAINER_VOLUME_M3
    density_kg_per_m3: float = DEFAULT_DENSITY_KG_PER_M3

    def clamped_cadence(self, raw_days: float) -> float:
        """Return the cadence limited to ``[min_cadence_days, max_cadence_days]``."""
        if raw_days is None or not math.isfinite(float(raw_days)):
            return float(self.max_cadence_days)
        return min(float(self.max_cadence_days), max(float(self.min_cadence_days), float(raw_days)))

    def to_dict(self) -> dict[str, Any]:
        """JSON-serializable representation (decimal point, as in the data files)."""
        return {
            "empty_at_pct": float(self.empty_at_pct),
            "min_cadence_days": float(self.min_cadence_days),
            "max_cadence_days": float(self.max_cadence_days),
            "truck_days_per_week": float(self.truck_days_per_week),
            "service_min_per_stop": float(self.service_min_per_stop),
            "drive_min_urban": float(self.drive_min_urban),
            "drive_min_rural": float(self.drive_min_rural),
            "container_volume_m3": float(self.container_volume_m3),
            "density_kg_per_m3": float(self.density_kg_per_m3),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CadenceParams":
        """Build from a mapping; unknown keys are ignored."""
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass(frozen=True)
class ContainerCadence:
    """Cadence state of one container (a physical bin at a site)."""

    location_id: str
    material: str
    lat: float | None
    lon: float | None
    area: str
    #: Fill rate in percentage points per day.
    rate_pct_per_day: float
    #: Fill rate in kg per day.
    rate_kg_per_day: float
    #: Ideal cadence in days, T = (capacity - buffer) / r.
    cadence_days: float
    #: Cadence actually realised between the last visits.
    current_cadence_days: float | None
    #: Target cadence after clamping to the allowed band.
    proposed_cadence_days: float
    #: Day the container is due next.
    next_due_date: pd.Timestamp | None
    #: "yellow" | "red" | "ok"
    status: str
    visits: int
    avg_fill_at_emptying_pct: float | None
    last_fill_pct: float | None
    days_since_last: int
    #: Fill levels found at the last visits (oldest first), for the sawtooth chart.
    history: tuple[tuple[pd.Timestamp, float], ...] = ()

    @property
    def cadence_change_days(self) -> float | None:
        """Difference proposed minus current cadence in days (None if unknown)."""
        if self.current_cadence_days is None:
            return None
        return float(self.proposed_cadence_days) - float(self.current_cadence_days)

    @property
    def is_low_fill(self) -> bool:
        """True when the container was emptied too often (yellow rule)."""
        return self.status == "yellow"

    @property
    def is_critical(self) -> bool:
        """True when the container overflows before the next visit (red rule)."""
        return self.status == "red"


def ideal_cadence_days(rate_pct_per_day: float, empty_at_pct: float = DEFAULT_EMPTY_AT_PCT) -> float | None:
    """T = (capacity - buffer) / r — the days until the buffer is reached.

    ``capacity`` is 100 % of the container; ``buffer`` is the level at which it is
    emptied. ``None`` if the rate is not positive.
    """
    if rate_pct_per_day is None:
        return None
    rate = float(rate_pct_per_day)
    if not math.isfinite(rate) or rate <= 0.0:
        return None
    span = 100.0 - float(empty_at_pct)
    if span <= 0:
        return None
    return span / rate


def fill_rate_pct_per_day(
    dates: Sequence[pd.Timestamp], levels: Sequence[float]
) -> float | None:
    """Rate of one container in percentage points per day.

    Every visit empties the container, so each interval starts at ~0 % and the
    level found at the visit divided by the interval length is the rate. The
    **quotient of the sums** is used (expectation-preserving for a constant rate)
    instead of the mean of the quotients.
    """
    if len(dates) < 2 or len(levels) < 2:
        return None
    total_days = 0.0
    total_pct = 0.0
    for i in range(1, len(dates)):
        span = (pd.Timestamp(dates[i]) - pd.Timestamp(dates[i - 1])).days
        if span > 0:
            total_days += float(span)
            total_pct += float(levels[i])
    if total_days <= 0:
        return None
    return total_pct / total_days


def observed_cadence_days(dates: Sequence[pd.Timestamp]) -> float | None:
    """Mean number of days between the visits (the cadence actually realised)."""
    if len(dates) < 2:
        return None
    spans = [
        (pd.Timestamp(dates[i]) - pd.Timestamp(dates[i - 1])).days
        for i in range(1, len(dates))
    ]
    spans = [s for s in spans if s > 0]
    if not spans:
        return None
    return float(sum(spans)) / len(spans)


def classify_status(
    levels: Sequence[float],
    rate_pct_per_day: float,
    days_since_last: int,
    params: CadenceParams,
) -> str:
    """Status of a container: "red" (critical), "yellow" (emptied too often) or "ok".

    * **red** — the container reaches ``MAX_FILL_PCT`` before the next possible
      visit, i.e. the overflow risk is higher than the remaining days allow.
    * **yellow** — the last ``LOW_FILL_WINDOW`` visits all found the container
      below ``LOW_FILL_PCT``: it is emptied too often.
    """
    recent = [float(v) for v in levels[-LOW_FILL_WINDOW:]]
    if len(recent) >= LOW_FILL_WINDOW and all(v < LOW_FILL_PCT for v in recent):
        return "yellow"
    if rate_pct_per_day and rate_pct_per_day > 0:
        # Days until the container overflows (110 %).
        days_to_overflow = (MAX_FILL_PCT - float(levels[-1])) / float(rate_pct_per_day) if levels else 0.0
        if days_to_overflow <= max(0, int(days_since_last)):
            return "red"
    return "ok"


#: Distance from the city centre (in degrees) beyond which a container counts as
#: rural. Calibrated against the real coordinate spread: Flein sits at ~0.051,
#: Lauffen at ~0.106 — so 0.05 is the cut that separates the two rural
#: districts from the city (Annahme, to be confirmed by W4).
RURAL_DISTANCE_DEG = 0.05


def assign_area(lat: float | None, lon: float | None) -> str:
    """Assign a container to an area (Annahme — to be confirmed by W4).

    Heilbronn city is "urban"; the rural districts Flein and Lauffen are
    "rural". The split is a distance heuristic around the city centre.
    """
    if lat is None or lon is None:
        return AREA_URBAN
    # City centre of Heilbronn (TechCampus / city centre area).
    distance = ((float(lat) - 49.1427) ** 2 + (float(lon) - 9.2109) ** 2) ** 0.5
    return AREA_RURAL if distance > RURAL_DISTANCE_DEG else AREA_URBAN


def build_container_cadences(
    readings_df: pd.DataFrame,
    params: CadenceParams,
    locations_df: pd.DataFrame | None = None,
    reference_date: str | pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build the per-container cadence table.

    Every number comes from the readings (and the optional coordinates); no
    value is hardcoded. Returns one row per container (Location_id + material).
    """
    if readings_df is None or readings_df.empty:
        return pd.DataFrame(columns=list(CADENCE_COLUMNS))

    work = readings_df.copy()
    work["date"] = pd.to_datetime(work["date"])
    work["Location_id"] = work["Location_id"].astype(str)
    work["material_type"] = work["material_type"].astype(str).str.lower()
    work["fill_level_numeric"] = pd.to_numeric(work["fill_level_numeric"], errors="coerce")

    coords: dict[str, tuple[float, float]] = {}
    if locations_df is not None and not locations_df.empty:
        locs = locations_df.copy()
        locs["Location_id"] = locs["Location_id"].astype(str)
        for row in locs.itertuples(index=False):
            coords[str(row.Location_id)] = (float(row.lat), float(row.lon))

    ref = pd.Timestamp(reference_date) if reference_date is not None else work["date"].max()
    ref = ref.normalize()

    rows: list[dict[str, Any]] = []
    for (loc_id, material), group in work.groupby(["Location_id", "material_type"], sort=True):
        group = group.sort_values("date")
        dates = list(group["date"])
        levels = [float(v) for v in group["fill_level_numeric"]]
        rate = fill_rate_pct_per_day(dates, levels)
        if rate is None:
            # No interval yet: the material median is the fallback (Annahme).
            rate = 0.0
        ideal = ideal_cadence_days(rate, params.empty_at_pct) if rate > 0 else None
        proposed = params.clamped_cadence(ideal) if ideal is not None else float(params.max_cadence_days)
        current = observed_cadence_days(dates)
        last_date = pd.Timestamp(dates[-1]).normalize()
        days_since_last = max(0, int((ref - last_date).days))
        lat, lon = coords.get(str(loc_id), (None, None))
        area = assign_area(lat, lon)
        kg_per_day = (
            rate / 100.0 * float(params.container_volume_m3) * float(params.density_kg_per_m3)
            if rate
            else 0.0
        )
        status = classify_status(levels, rate, days_since_last, params)
        next_due = (
            last_date + pd.Timedelta(days=max(1, int(math.ceil(proposed))))
            if proposed
            else None
        )
        rows.append(
            {
                "location_id": str(loc_id),
                "material": str(material),
                "lat": lat,
                "lon": lon,
                "area": area,
                "rate_pct_per_day": round(float(rate), 4),
                "rate_kg_per_day": round(float(kg_per_day), 4),
                "cadence_days_T": round(float(proposed), 2),
                "ideal_cadence_days": round(float(ideal), 2) if ideal is not None else None,
                "current_cadence_days": round(float(current), 2) if current is not None else None,
                "proposed_cadence_days": round(float(proposed), 2),
                "next_due_date": next_due,
                "status": status,
                "visits": int(len(group)),
                "avg_fill_at_emptying_pct": round(float(sum(levels) / len(levels)), 2),
                "last_fill_pct": round(float(levels[-1]), 1),
                "days_since_last": days_since_last,
                "last_visit_date": last_date,
                "history": tuple(
                    (pd.Timestamp(d).normalize(), float(v)) for d, v in zip(dates, levels)
                ),
            }
        )

    return pd.DataFrame(rows)


#: Columns of ``data/outputs/scenarios/containers.csv``.
CADENCE_COLUMNS = [
    "location_id",
    "material",
    "lat",
    "lon",
    "area",
    "rate_pct_per_day",
    "rate_kg_per_day",
    "cadence_days_T",
    "current_cadence_days",
    "proposed_cadence_days",
    "next_due_date",
    "status",
    "visits",
    "avg_fill_at_emptying_pct",
    "last_fill_pct",
    "days_since_last",
    "last_visit_date",
]


def format_de(value: Any, digits: int = 1) -> str:
    """Format a number the German way: thousands point, comma as decimal.

    ``1234.5`` -> ``"1.234,5"``. ``None`` becomes ``"-"``.
    """
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(number):
        return "-"
    return f"{number:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def status_rank(status: str) -> int:
    """Sort rank of a status: critical first, then yellow, then ok."""
    return {"red": 0, "yellow": 1}.get(str(status), 2)


def explain_cadence_change(row: Mapping[str, Any]) -> str:
    """One plain-German sentence explaining why the cadence changes.

    Example: "Seit 3 Leerungen unter 30 % → Takt 7 → 14 Tage."
    """
    status = str(row.get("status", ""))
    current = row.get("current_cadence_days")
    proposed = row.get("proposed_cadence_days")
    visits = row.get("visits")
    rate = row.get("rate_pct_per_day")
    empty_at = row.get("empty_at_pct", DEFAULT_EMPTY_AT_PCT)

    current_txt = f"{float(current):.0f}" if current is not None else "?"
    proposed_txt = f"{float(proposed):.0f}" if proposed is not None else "?"

    if status == "yellow":
        window = min(LOW_FILL_WINDOW, int(visits)) if visits else LOW_FILL_WINDOW
        return (
            f"Seit {window} Leerungen unter {LOW_FILL_PCT:.0f} % → "
            f"Takt {current_txt} → {proposed_txt} Tage."
        )
    if status == "red":
        return (
            f"Läuft vor dem nächsten Besuch über ({MAX_FILL_PCT:.0f} %) → "
            f"Takt {current_txt} → {proposed_txt} Tage."
        )
    if rate:
        return (
            f"Kommt mit {format_de(rate, 1)} % pro Tag und wird bei {format_de(empty_at, 0)} % geleert → "
            f"Takt {current_txt} → {proposed_txt} Tage."
        )
    return f"Takt {current_txt} → {proposed_txt} Tage."
