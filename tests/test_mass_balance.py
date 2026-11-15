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
    produced = simulate_daily.produced_total(readings, cfg)
    return hist, opt, produced


def test_tonnage_historical_equals_optimized(replay):
    """Same glass on both sides within ±2 %.

    Both sides use the identical final-day accounting: glass collected in the window plus
    the end stock still standing in the containers on the last day (docs/MODEL_SPEC.md §1:
    gesammelt + Endbestand). The in-window collected tonnage alone differs by exactly the
    end-stock difference (status quo leaves more glass standing), see the next test.
    """
    hist, opt, _ = replay
    assert len(hist) == len(opt) == 349
    lh, lo = simulate_daily.mass_ledger(hist), simulate_daily.mass_ledger(opt)
    t_hist = float(hist["tonnage_t"].sum()) + lh["end_stock_t"]
    t_opt = float(opt["tonnage_t"].sum()) + lo["end_stock_t"]
    assert t_hist > 0
    assert abs(t_hist - t_opt) / t_hist <= 0.02, f"historical={t_hist:.1f} t optimized={t_opt:.1f} t"


def test_in_window_difference_is_only_end_stock(replay):
    """Routing never creates glass: Δ collected-in-window == −Δ end stock (rounding only)."""
    hist, opt, _ = replay
    lh, lo = simulate_daily.mass_ledger(hist), simulate_daily.mass_ledger(opt)
    d_collected = float(opt["tonnage_t"].sum()) - float(hist["tonnage_t"].sum())
    d_end_stock = lh["end_stock_t"] - lo["end_stock_t"]
    assert d_collected == pytest.approx(d_end_stock, abs=0.5)


@pytest.mark.parametrize("side", ["hist", "opt"])
def test_ledger_closes_per_side(replay, side):
    """collected + end_stock == produced, exactly per side, and produced is the world total."""
    hist, opt, produced = replay
    frame = hist if side == "hist" else opt
    ledger = simulate_daily.mass_ledger(frame)
    assert ledger["produced_t"] == pytest.approx(produced, rel=1e-12)
    assert ledger["collected_t"] + ledger["end_stock_t"] == pytest.approx(ledger["produced_t"], abs=1e-6)
    # CSV daily tonnage is rounded to 3 decimals per day only
    assert float(frame["tonnage_t"].sum()) == pytest.approx(ledger["collected_t"], abs=0.2)
    assert ledger["end_stock_t"] >= 0.0


def test_status_quo_reproduces_measured_in_window_mass(replay):
    """Replaying the real visit dates against r_c = Σlevel/ΣΔt returns the measured glass (readings 2…n)."""
    hist, _, _ = replay
    readings = pd.read_csv(ROOT / "data/processed/cleaned_readings.csv").sort_values("date")
    in_window = readings.groupby(["Location_id", "material_type"])["fill_level_numeric"].apply(
        lambda s: float(s.iloc[1:].sum())
    )
    cfg = load_config(ROOT / "prezero_config.json")
    measured_t = float(in_window.sum()) / 100.0 * cfg.container_volume_m3 * 400.0 / 1000.0
    assert simulate_daily.mass_ledger(hist)["collected_t"] == pytest.approx(measured_t, abs=0.01)
