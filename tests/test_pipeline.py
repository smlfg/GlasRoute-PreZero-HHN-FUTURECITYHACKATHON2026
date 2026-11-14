"""Minimal pipeline tests."""

from pathlib import Path

import pandas as pd

from prezero import ingest

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "glass_fill_levels_anonymized_f.csv"


def test_load_raw() -> None:
    df = ingest.load_raw(RAW)
    assert not df.empty
    assert {"Location_id", "material_type", "date", "fill_level_perc"} <= set(df.columns)


def test_clean() -> None:
    df = ingest.load_raw(RAW)
    cleaned = ingest.clean(df)
    assert "fill_level_numeric" in cleaned.columns
    assert "is_overfull" in cleaned.columns
    assert cleaned["fill_level_numeric"].notna().all()
