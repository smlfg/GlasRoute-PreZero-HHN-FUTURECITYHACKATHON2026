"""Visualizations."""

from __future__ import annotations

import pandas as pd


def plot_trends(df: pd.DataFrame, output_path: str) -> None:
    """Plot seasonal/material trends."""
    raise NotImplementedError("Visualization not yet implemented.")


def plot_route(route: pd.DataFrame, output_path: str) -> None:
    """Render route map."""
    raise NotImplementedError("Route map not yet implemented.")
