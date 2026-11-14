import numpy as np
import pandas as pd

from prezero.dispatch_policy import Calendar, manifest


def planned(date, stocks, rates, **kwargs):
    return manifest(pd.Timestamp(date), np.array(stocks, dtype=float), np.array(rates),
                    np.zeros((len(stocks), 2)), Calendar(), **kwargs)


def test_safe_eligible_waits_but_deadline_seeds_colocated_pickup():
    assert planned("2026-06-01", [65], [2]) == []
    assert planned("2026-06-01", [99, 65], [2, 2]) == [0, 1]


def test_friday_anticipates_weekend_and_exceptions_are_explicit():
    assert planned("2026-06-05", [95], [2]) == [0]
    assert planned("2026-06-06", [99], [2]) == []
    assert planned("2026-06-06", [99], [2], emergency=True) == [0]
