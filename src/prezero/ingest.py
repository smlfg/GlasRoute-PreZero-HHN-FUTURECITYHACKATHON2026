"""Data ingestion and cleaning for PreZero fill-level data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_raw(path: str | Path) -> pd.DataFrame:
    """Load raw CSV and return a DataFrame."""
    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
        parse_dates=["date"],
        dtype={"Location_id": str, "material_type": str},
    )
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Clean readings: normalize overfull, add numeric level flag, sort."""
    df = df.copy()

    # Normalize overfull to a numeric value above 100 for downstream math.
    df["fill_level_numeric"] = df["fill_level_perc"].apply(_normalize_level)
    df["is_overfull"] = df["fill_level_perc"].astype(str).str.lower() == "overfull"

    # Drop rows with missing essential data.
    df = df.dropna(subset=["Location_id", "material_type", "date", "fill_level_numeric"])

    # Sort for time-series operations.
    df = df.sort_values(["Location_id", "material_type", "date"]).reset_index(drop=True)
    return df


def _normalize_level(value) -> float | None:
    """Convert a fill level to a numeric value."""
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "overfull":
            return 110.0
        try:
            return float(lowered)
        except ValueError:
            return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def ingest(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    """Load raw data, clean it, and write cleaned CSV."""
    df = load_raw(input_path)
    df_clean = clean(df)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(output_path, index=False)
    return df_clean


def print_stats(df: pd.DataFrame) -> None:
    """Print basic stats about the cleaned data."""
    n_rows = len(df)
    n_locations = df["Location_id"].nunique()
    n_overfull = df["is_overfull"].sum()
    materials = df["material_type"].value_counts().to_dict()
    date_min, date_max = df["date"].min(), df["date"].max()

    print(f"Rows: {n_rows}")
    print(f"Locations: {n_locations}")
    print(f"Overfull events: {int(n_overfull)}")
    print(f"Materials: {materials}")
    print(f"Date range: {date_min.date()} to {date_max.date()}")
