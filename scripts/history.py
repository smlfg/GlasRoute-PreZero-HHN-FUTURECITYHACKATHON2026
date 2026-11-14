"""Rebuild the historical collection-day table from the challenge CSV."""

from pathlib import Path

from prezero.history import historical_days
from prezero.ingest import load_raw
from prezero.locations import load_locations
from prezero.routing import load_config

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    raw = load_raw(ROOT / "data/raw/glass_fill_levels_anonymized_f.csv")
    geo = load_locations(ROOT / "data/external/locations.csv")
    history = historical_days(raw, geo, load_config(ROOT / "prezero_config.json"))
    history.to_csv(ROOT / "data/history_tours.csv", index=False)
