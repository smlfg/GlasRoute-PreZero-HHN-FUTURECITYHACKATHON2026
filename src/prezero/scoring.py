"""Criticality scoring for containers."""

from __future__ import annotations

import pandas as pd


MATERIAL_FACTORS = {"brown": 0.7, "green": 0.85, "white": 1.0}


def score_containers(features: pd.DataFrame, date: str | None = None) -> pd.DataFrame:
    """Return normalized criticality scores for feature rows."""
    scored = features.copy()
    if scored.empty:
        scored["score"] = pd.Series(dtype=float)
        scored["critical"] = pd.Series(dtype=bool)
        return scored

    level = scored["last_level"].clip(lower=0, upper=110).div(110)
    overfull = scored["overfull_rate"].clip(lower=0, upper=1)
    material = scored["material_type"].map(MATERIAL_FACTORS).fillna(0.8)
    seasonal_material = material * scored["season_factor"].clip(lower=0, upper=1)
    scored["score"] = (
        0.5 * level + 0.3 * overfull + 0.2 * seasonal_material
    ).clip(lower=0, upper=1)
    scored["critical"] = scored["score"] >= 0.7
    return scored
