"""Mass conservation: every scenario must collect the same glass tonnage (docs/MODEL_SPEC.md §1)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from prezero.locations import load_locations
from prezero.routing import load_config

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("simulate_daily", ROOT / "scripts" / "simulate_daily.py")
simulate_daily = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(simulate_daily)


@pytest.fixture(scope="module")
def replay():
    readings = pd.read_csv(ROOT / "data/processed/cleaned_readings.csv")
    locations = load_locations(ROOT / "data/external/locations.csv")
    cfg = load_config(ROOT / "prezero_config.json")
    hist = simulate_daily.build_historical_daily(readings, locations, cfg)
    opt = simulate_daily.simulate_optimized_daily(readings, locations, cfg, seed=42)
    return hist, opt


def test_tonnage_historical_equals_optimized(replay):
    hist, opt = replay
    assert len(hist) == len(opt) == 349
    t_hist = float(hist["tonnage_t"].sum())
    t_opt = float(opt["tonnage_t"].sum())
    assert t_hist > 0
    assert abs(t_hist - t_opt) / t_hist <= 0.02, f"historical={t_hist:.1f} t optimized={t_opt:.1f} t"
