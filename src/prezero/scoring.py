"""Criticality scoring for containers."""

from __future__ import annotations

import pandas as pd


def score_containers(features: pd.DataFrame, date: str) -> pd.DataFrame:
    """Return criticality score per container for a target date."""
    raise NotImplementedError("Scoring not yet implemented.")
