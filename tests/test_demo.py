from pathlib import Path

import pandas as pd
import pytest

from prezero.demo import (
    FEATURED_DATES,
    build_demo_playback_dataset,
    build_demo_section_html,
)
from prezero.locations import load_locations
from prezero.routing import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def demo_data():
    readings = pd.read_csv(ROOT / "data/processed/cleaned_readings.csv")
    locations = load_locations(ROOT / "data/external/locations.csv")
    cfg = load_config(ROOT / "prezero_config.json")
    return build_demo_playback_dataset(readings, locations, cfg)


def test_demo_playback_dataset_structure(demo_data):
    """Verify that playback data contains depots, featured dates, routes, and complete ledger."""
    assert "depots" in demo_data
    assert "yard" in demo_data["depots"]
    assert "disposal" in demo_data["depots"]

    yard = demo_data["depots"]["yard"]
    assert 49.0 <= yard[0] <= 49.3 and 9.1 <= yard[1] <= 9.3

    assert "2026-04-15" in demo_data["featured_dates"]
    assert len(demo_data["featured_dates"]) >= 5

    assert "featured_routes" in demo_data
    assert "2026-04-15" in demo_data["featured_routes"]
    pitch_day = demo_data["featured_routes"]["2026-04-15"]
    assert len(pitch_day["historical_stops"]) > 0
    assert len(pitch_day["optimized_stops"]) > 0

    assert "ledger" in demo_data
    assert len(demo_data["ledger"]["dates"]) == 349
    assert len(demo_data["ledger"]["historical"]) == 349
    assert len(demo_data["ledger"]["optimized"]) == 349


def test_demo_html_renders_required_ux_elements(demo_data):
    """Verify all UX requirements: A/B panels, honesty box, scrubber, KPIs, deltas, truck loads."""
    html_out = build_demo_section_html(demo_data)

    # 1. Day selector & time scrubber
    assert 'id="demo-date-slider"' in html_out
    assert 'id="demo-current-date-label"' in html_out
    assert 'id="demo-play-btn"' in html_out
    assert 'id="demo-step-slider"' in html_out
    assert "16×" in html_out
    assert "06:00" in html_out

    # 2. Split-screen layout
    assert "demo-panel-left" in html_out
    assert "demo-panel-right" in html_out
    assert "Heute / Status Quo" in html_out
    assert "Mit GlasRoute" in html_out

    # 3. Maps and animation stages
    assert 'id="demo-svg-hist"' in html_out
    assert 'id="demo-svg-opt"' in html_out
    assert "Orte simuliert (OSM)" in html_out

    # 4. Bin fill and vehicle load meters
    assert 'id="hist-meter-1"' in html_out
    assert 'id="opt-meter-1"' in html_out
    assert "LKW-Ladevolumen" in html_out

    # 5. Delta summary cards
    assert 'id="delta-km"' in html_out
    assert 'id="delta-veh"' in html_out
    assert 'id="delta-stops"' in html_out
    assert 'id="delta-fill"' in html_out
    assert 'id="delta-shift"' in html_out

    # 6. Hero message & honesty notice
    assert 'id="demo-hero-summary"' in html_out
    assert "Simulierte Orte, echte Besuchstage" in html_out
    assert "Tage und Füllstände echt" in html_out

    # 7. Comparison strip and period toggle
    assert 'id="ab-toggle-day"' in html_out
    assert 'id="ab-toggle-period"' in html_out
    assert "card-finish" in html_out
    assert "card-unload" in html_out
    assert "card-overflow" in html_out


def test_numbers_in_strip_equal_daily_ledger(demo_data):
    """Acceptance: numbers in the strip equal the daily ledger for that day.

    Both replay sides are derived from the same logic as scripts/simulate_daily.py
    (world model, MODEL_SPEC.md), so the strip must match the ledger on every day
    and the ledger must match data/outputs/*_daily.csv.
    """
    dates_data = demo_data["dates_data"]
    hist_ledger = {r["date"]: r for r in demo_data["ledger"]["historical"]}
    opt_ledger = {r["date"]: r for r in demo_data["ledger"]["optimized"]}

    for d_str, day_data in dates_data.items():
        h_d, o_d = day_data["hist"], day_data["opt"]
        hl, ol = hist_ledger[d_str], opt_ledger[d_str]

        assert h_d["n_emptyings"] == hl["n_emptyings"]
        assert h_d["vehicles_needed"] == hl["vehicles_needed"]
        assert h_d["est_km"] == round(float(hl["est_km"]), 1)
        assert h_d["overflow_bin_days"] == hl["n_containers_overfull_at_visit"]

        assert o_d["n_emptyings"] == ol["n_emptyings"]
        assert o_d["vehicles_needed"] == ol["vehicles_needed"]
        assert o_d["est_km"] == round(float(ol["est_km"]), 1)
        assert o_d["overflow_bin_days"] == ol["n_containers_overfull_at_visit"]
        assert o_d["overflow_unserved_days"] == ol["n_overflows_simulated"]


def test_demo_ledger_equals_daily_csv(demo_data):
    """The demo ledger is the committed daily CSV (same logic, no second implementation)."""
    for key, name in (("historical", "historical_daily.csv"), ("optimized", "optimized_daily.csv")):
        csv = pd.read_csv(ROOT / "data/outputs" / name)
        led = pd.DataFrame(demo_data["ledger"][key])
        assert list(led["date"]) == list(csv["date"])
        for col in ("n_emptyings", "vehicles_needed", "n_containers_overfull_at_visit", "n_overflows_simulated"):
            assert list(led[col]) == list(csv[col]), col
        for col in ("est_km", "tonnage_t", "shift_hours", "avg_fill_at_emptying_pct"):
            assert led[col].astype(float).round(2).tolist() == csv[col].astype(float).round(2).tolist(), col


def test_demo_day_is_consistent_with_ledger_and_mass_balance(demo_data):
    """Demo day 2026-04-15: both sides present and consistent with the ledger.

    The earlier version of this test asserted a clear optimized-side advantage (fewer
    km, earlier finish, ...). That advantage came from the old, buggy simulation (phantom
    mass from a random timer reset). With the corrected world model (MODEL_SPEC.md) the
    timer is NOT better on every day or in total, so we assert consistency, not a win.
    """
    day_item = demo_data["dates_data"]["2026-04-15"]
    h, o = day_item["hist"], day_item["opt"]
    hl = {r["date"]: r for r in demo_data["ledger"]["historical"]}["2026-04-15"]
    ol = {r["date"]: r for r in demo_data["ledger"]["optimized"]}["2026-04-15"]

    # both sides present with real routes
    assert h["n_emptyings"] > 0 and o["n_emptyings"] > 0
    assert len(h["vehicles"]) == h["vehicles_needed"] > 0
    assert len(o["vehicles"]) == o["vehicles_needed"] > 0
    featured = demo_data["featured_routes"]["2026-04-15"]
    assert featured["historical_stops"] and featured["optimized_stops"]

    # strip == ledger, incl. tonnage and fill
    for strip, led in ((h, hl), (o, ol)):
        assert strip["n_emptyings"] == led["n_emptyings"]
        assert strip["tonnage_t"] == round(float(led["tonnage_t"]), 1)
        assert strip["avg_fill_at_emptying_pct"] == round(float(led["avg_fill_at_emptying_pct"]), 1)
        assert strip["shift_hours"] == round(float(led["shift_hours"]), 1)

    # mass balance over the whole replay: collected tonnage equal on both sides is not
    # required (timer leaves glass in containers), but produced = collected + end stock.
    from scripts.simulate_daily import mass_ledger

    for key in ("historical", "optimized"):
        df = pd.DataFrame(demo_data["ledger"][key])
        assert df["tonnage_t"].sum() > 0
    readings = pd.read_csv(ROOT / "data/processed/cleaned_readings.csv")
    locations = load_locations(ROOT / "data/external/locations.csv")
    from scripts.simulate_daily import build_historical_daily, simulate_optimized_daily

    cfg = load_config(ROOT / "prezero_config.json")
    for df in (build_historical_daily(readings, locations, cfg), simulate_optimized_daily(readings, locations, cfg)):
        led = mass_ledger(df)
        assert led["produced_t"] == pytest.approx(led["collected_t"] + led["end_stock_t"], rel=1e-9)
