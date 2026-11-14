"""One fixed weekday batching rule for the prospective, sensor-assisted scenario."""

from dataclasses import dataclass
from datetime import timedelta
import numpy as np


@dataclass(frozen=True)
class Calendar:
    weekdays: tuple = (0, 1, 2, 3, 4)
    closed_dates: tuple = ()

    def open(self, day):
        return day.weekday() in self.weekdays and str(day.date()) not in self.closed_dates


def manifest(day, stock, rates, coords, calendar, *, emergency=False):
    """Return priority order. Stock is this policy's own pre-dispatch sensor scenario."""
    if not calendar.weekdays or any(d not in range(7) for d in calendar.weekdays):
        raise ValueError("A nonempty operating week is required")
    tomorrow = day + timedelta(days=1)
    while not calendar.open(tomorrow):
        tomorrow += timedelta(days=1)
    gap = (tomorrow - day).days
    urgent = stock + rates * gap > 100
    if not calendar.open(day):
        if not emergency:
            return []
        eligible = urgent
    else:
        eligible = stock >= 60
    if not urgent.any():
        return []
    # One geographic batch around the tightest deadline. Further batches at capacity
    # pressure are left to the next operating day, then checked by the evaluator.
    slack = np.divide(100-stock, rates, out=np.full(len(stock), np.inf), where=rates > 0)
    anchor = np.flatnonzero(urgent)[np.argmin(slack[urgent])]
    distance = np.hypot((coords[:, 0]-coords[anchor, 0])*111,
                        (coords[:, 1]-coords[anchor, 1])*73)
    selected = np.flatnonzero(urgent | (eligible & (distance <= 2.0)))
    return sorted(selected, key=lambda i: (not urgent[i], slack[i] if urgent[i] else distance[i], i))
