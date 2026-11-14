"""Routing heuristics."""

from __future__ import annotations

import pandas as pd


def build_route(critical: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    """Build a route from critical containers and their coordinates."""
    raise NotImplementedError("Routing not yet implemented.")
