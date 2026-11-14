"""Urgency of each container, derived from its emptying timer.

Measure-and-empty: the driver estimates the level at a visit and empties the container.
From the fill rate since that visit every container gets a timer (``features.build_features``):

* ``est_fill_level``  estimated level now
* ``due_date``        day the estimate reaches ``DUE_FILL_PCT`` (80 %)
* ``days_until_due``  negative = overdue

A container is **critical when its timer has run out** (estimated level >= 80 %).
``score`` is the estimated level scaled to [0, 1] (110 % = 1.0) and only orders the stops.
Earlier versions mixed in overfull history, a material weight and a season weight; the fill
rate already captures how fast a container fills, so those factors were dropped.
"""

from __future__ import annotations

import pandas as pd

from prezero.features import DUE_FILL_PCT, MAX_FILL_PCT

#: Score at which a container is critical (= estimated level reaches the due level).
CRITICAL_THRESHOLD = round(DUE_FILL_PCT / MAX_FILL_PCT, 4)


def score_containers(features: pd.DataFrame, date: str | None = None) -> pd.DataFrame:
    """Add ``score`` (urgency in [0, 1]) and ``critical`` (timer expired) to the feature table."""
    del date  # The timer is already computed for the feature date.
    result = features.copy()
    if result.empty:
        result["score"] = pd.Series(dtype=float)
        result["critical"] = pd.Series(dtype=bool)
        return result

    level_col = "est_fill_level" if "est_fill_level" in result.columns else "last_fill_level"
    level = result[level_col].astype(float)
    result["score"] = (level / MAX_FILL_PCT).clip(0.0, 1.0).round(4)
    result["critical"] = level >= DUE_FILL_PCT

    sort_cols = ["score"]
    ascending = [False]
    if "days_until_due" in result.columns:
        sort_cols = ["days_until_due", "score"]
        ascending = [True, False]
    for col in ("Location_id", "material_type"):
        if col in result.columns:
            sort_cols.append(col)
            ascending.append(True)
    return result.sort_values(sort_cols, ascending=ascending, na_position="last").reset_index(
        drop=True
    )
