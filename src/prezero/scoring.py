"""Criticality scoring for containers."""

from __future__ import annotations

import pandas as pd

MATERIAL_WEIGHTS = {
    "white": 1.0,
    "green": 0.7,
    "brown": 0.4,
}
CRITICAL_THRESHOLD = 0.7


def score_containers(features: pd.DataFrame, date: str | None = None) -> pd.DataFrame:
    """Compute normalized criticality score in [0, 1] and ``critical`` flag."""
    del date  # Season factor is already encoded in the feature table.
    result = features.copy()
    if result.empty:
        result["score"] = pd.Series(dtype=float)
        result["critical"] = pd.Series(dtype=bool)
        return result

    # Current level: the container was emptied at its last visit, so use the estimate
    # (fill rate x days since visit), not the level found before emptying.
    level_col = "est_fill_level" if "est_fill_level" in result.columns else "last_fill_level"
    level_norm = (result[level_col].astype(float) / 110.0).clip(0.0, 1.0)
    overfull = result["overfull_rate"].astype(float).clip(0.0, 1.0)
    material_weight = (
        result["material_type"].astype(str).str.strip().str.lower().map(MATERIAL_WEIGHTS).fillna(0.5)
    )
    season = result["season_factor"].astype(float).clip(0.0, 1.0)
    material_season = (material_weight * season).clip(0.0, 1.0)

    result["score"] = (0.5 * level_norm + 0.3 * overfull + 0.2 * material_season).clip(0.0, 1.0)
    result["critical"] = result["score"] >= CRITICAL_THRESHOLD

    sort_cols = ["score"]
    ascending = [False]
    for col in ("Location_id", "material_type"):
        if col in result.columns:
            sort_cols.append(col)
            ascending.append(True)
    return result.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
