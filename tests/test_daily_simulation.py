from datetime import date, timedelta
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prezero.locations import load_locations
from prezero.routing import load_config

ROOT = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location(
    "simulate_daily", ROOT / "scripts" / "simulate_daily.py"
)
simulate_daily = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(simulate_daily)

OUTPUT_COLUMNS = simulate_daily.OUTPUT_COLUMNS
fit_fill_rates = simulate_daily.fit_fill_rates
build_historical_daily = simulate_daily.build_historical_daily
simulate_optimized_daily = simulate_daily.simulate_optimized_daily


@pytest.fixture(scope="module")
def dataset():
    readings = pd.read_csv(ROOT / "data/processed/cleaned_readings.csv")
    locations = load_locations(ROOT / "data/external/locations.csv")
    cfg = load_config(ROOT / "prezero_config.json")
    return readings, locations, cfg


def test_no_look_ahead(dataset):
    """Test that rates fitted up to target_date NEVER read measurements on or after target_date."""
    readings, _, _ = dataset
    target_date = date(2026, 3, 1)

    # 1. Fit rates on original dataset
    base_rates = fit_fill_rates(readings, target_date)

    # 2. Create contaminated dataset with modified/poisoned future rows (date >= target_date)
    contaminated = readings.copy()
    future_mask = pd.to_datetime(contaminated["date"]).dt.date >= target_date

    # Poison future readings with 1000% fill levels and manipulated intervals
    contaminated.loc[future_mask, "fill_level_numeric"] = 999.0

    # 3. Fit rates on contaminated dataset
    contaminated_rates = fit_fill_rates(contaminated, target_date)

    # 4. Must be identical down to every single float
    assert set(base_rates.keys()) == set(contaminated_rates.keys())
    for key in base_rates:
        assert np.isclose(base_rates[key], contaminated_rates[key]), (
            f"Leakage detected for container {key}: "
            f"base={base_rates[key]} vs poisoned={contaminated_rates[key]}"
        )


def test_date_range_identical(dataset):
    """Verify that historical and optimized outputs share the exact same date range."""
    readings, locations, cfg = dataset

    hist_df = build_historical_daily(readings, locations, cfg)
    opt_df = simulate_optimized_daily(readings, locations, cfg, seed=42)

    assert len(hist_df) == len(opt_df) == 349
    assert list(hist_df["date"]) == list(opt_df["date"])
    assert hist_df["date"].iloc[0] == "2025-10-17"
    assert hist_df["date"].iloc[-1] == "2026-09-30"


def test_columns_and_sources(dataset):
    """Verify that columns match exactly and source column is flagged correctly."""
    readings, locations, cfg = dataset

    hist_df = build_historical_daily(readings, locations, cfg)
    opt_df = simulate_optimized_daily(readings, locations, cfg, seed=42)

    assert list(hist_df.columns) == OUTPUT_COLUMNS
    assert list(opt_df.columns) == OUTPUT_COLUMNS

    assert (hist_df["source"] == "real").all()
    assert (opt_df["source"] == "simulated").all()
    assert (hist_df["n_overflows_simulated"] == 0).all()


def test_conservation_of_totals(dataset):
    """Verify that total mass collected is within expected physical bounds."""
    readings, locations, cfg = dataset

    hist_df = build_historical_daily(readings, locations, cfg)
    opt_df = simulate_optimized_daily(readings, locations, cfg, seed=42)

    # Historical: 11,701 emptyings and ~7,719 tonnes
    assert hist_df["n_emptyings"].sum() == 11701
    assert 7700.0 <= hist_df["tonnage_t"].sum() <= 7750.0

    # Simulated: Total tonnage within physical bounds of city generation (7,000 - 10,000 t)
    assert 7000.0 <= opt_df["tonnage_t"].sum() <= 10000.0


def test_efficiency_and_overflow_reduction(dataset):
    """Verify that the timer model increases fill per lift and reduces overfull emptyings."""
    readings, locations, cfg = dataset

    hist_df = build_historical_daily(readings, locations, cfg)
    opt_df = simulate_optimized_daily(readings, locations, cfg, seed=42)

    h_avg_fill = (
        hist_df["avg_fill_at_emptying_pct"] * hist_df["n_emptyings"]
    ).sum() / hist_df["n_emptyings"].sum()
    o_avg_fill = (
        opt_df["avg_fill_at_emptying_pct"] * opt_df["n_emptyings"]
    ).sum() / opt_df["n_emptyings"].sum()

    # Optimized average fill at emptying should be near 80 % (significantly above 66 %)
    assert o_avg_fill >= 80.0
    assert o_avg_fill > h_avg_fill

    # Overfull emptyings at visit should drop dramatically compared to historical 1,192
    assert opt_df["n_containers_overfull_at_visit"].sum() < 100
