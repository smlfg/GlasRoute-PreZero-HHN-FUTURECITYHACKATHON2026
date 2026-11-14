"""Run the predeclared Q3 holdout and July checkpoint. Run with PYTHONPATH=src."""

import json
from pathlib import Path

import pandas as pd

from prezero.dispatch_trial import trial
from prezero.history import observed_visits
from prezero.ingest import load_raw
from prezero.locations import load_locations
from prezero.routing import OperationalConfig

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Frozen assumptions used for the archived 346-day result.
    config = OperationalConfig(density_kg_per_m3=400, road_detour_factor=1.35)
    prices = dict(vehicle_day=500, crew=2, wage=32, km_cost=0.65)
    visits = observed_visits(
        load_raw(ROOT / "data/raw/glass_fill_levels_anonymized_f.csv")
    )
    geo = load_locations(ROOT / "data/external/locations.csv")
    report = trial(
        visits,
        geo,
        config,
        prices,
        pd.Timestamp("2026-07-01"),
        pd.Timestamp("2026-09-30"),
    )
    stress = trial(
        visits,
        geo,
        config,
        prices,
        pd.Timestamp("2026-07-01"),
        pd.Timestamp("2026-09-30"),
        demand_factor=1.2,
    )
    report["inflow_plus_20_percent"] = stress["checkpoints"][stress["end"]]
    report.update(config=config.to_dict(), prices=prices)
    (ROOT / "data/dispatch_experiment.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
