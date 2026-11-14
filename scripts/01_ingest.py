#!/usr/bin/env python3
"""Step 1: ingest and clean raw data."""

from pathlib import Path

from prezero import ingest

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "raw" / "glass_fill_levels_anonymized_f.csv"
OUTPUT = ROOT / "data" / "processed" / "cleaned_readings.csv"

if __name__ == "__main__":
    df = ingest.ingest(INPUT, OUTPUT)
    ingest.print_stats(df)
