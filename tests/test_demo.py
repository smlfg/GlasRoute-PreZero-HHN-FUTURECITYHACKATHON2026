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
    """Acceptance: numbers in the strip equal the daily ledger for that day (test)."""
    dates_data = demo_data["dates_data"]
    hist_ledger = {r["date"]: r for r in demo_data["ledger"]["historical"]}
    opt_ledger = {r["date"]: r for r in demo_data["ledger"]["optimized"]}

    # Verify on demo day 2026-04-15
    day_item = dates_data["2026-04-15"]
    h_strip = day_item["hist"]
    o_strip = day_item["opt"]

    h_row = hist_ledger["2026-04-15"]
    o_row = opt_ledger["2026-04-15"]

    assert h_strip["n_emptyings"] == h_row["n_emptyings"] == 51
    assert h_strip["vehicles_needed"] == h_row["vehicles_needed"] == 2
    assert h_strip["est_km"] == round(float(h_row["est_km"]), 1) == 100.3
    assert h_strip["avg_fill_at_emptying_pct"] == round(float(h_row["avg_fill_at_emptying_pct"]), 1) == 90.2
    assert h_strip["overflow_bin_days"] == h_row["n_containers_overfull_at_visit"] == 11

    assert o_strip["n_emptyings"] == o_row["n_emptyings"] == 29
    assert o_strip["vehicles_needed"] == o_row["vehicles_needed"] == 1
    assert o_strip["est_km"] == round(float(o_row["est_km"]), 1) == 82.7
    assert o_strip["avg_fill_at_emptying_pct"] == round(float(o_row["avg_fill_at_emptying_pct"]), 1) == 81.1
    assert o_strip["overflow_bin_days"] == o_row["n_containers_overfull_at_visit"] == 0

    # Verify across all 349 days that strip numbers never diverge from ledger
    for d_str, day_data in dates_data.items():
        h_d = day_data["hist"]
        o_d = day_data["opt"]
        hl = hist_ledger[d_str]
        ol = opt_ledger[d_str]

        assert h_d["n_emptyings"] == hl["n_emptyings"]
        assert h_d["vehicles_needed"] == hl["vehicles_needed"]
        assert h_d["est_km"] == round(float(hl["est_km"]), 1)

        assert o_d["n_emptyings"] == ol["n_emptyings"]
        assert o_d["vehicles_needed"] == ol["vehicles_needed"]
        assert o_d["est_km"] == round(float(ol["est_km"]), 1)


def test_chosen_demo_day_has_clear_advantage(demo_data):
    """Verify that chosen demo day 2026-04-15 demonstrates clear wins across dimensions."""
    day_item = demo_data["dates_data"]["2026-04-15"]
    h = day_item["hist"]
    o = day_item["opt"]

    # 1. Fewer vehicles
    assert o["vehicles_needed"] < h["vehicles_needed"]
    assert o["vehicles_needed"] == 1
    assert h["vehicles_needed"] == 2

    # 2. Earlier finish time
    assert o["finish_time"] < h["finish_time"]
    assert o["finish_time"] == "12:23"
    assert h["finish_time"] == "13:40"

    # 3. Fewer rounds
    assert o["rounds"] < h["rounds"]
    assert o["rounds"] == 3
    assert h["rounds"] == 6

    # 4. Fewer kilometers
    assert o["est_km"] < h["est_km"]
    assert o["est_km"] == 82.7
    assert h["est_km"] == 100.3

    # 5. Overflows eliminated
    assert o["overflow_bin_days"] == 0
    assert h["overflow_bin_days"] == 11

    # 6. Higher percentage of full unloads at disposal depot
    assert o["share_unloads_ge_90"] == 100.0
    assert h["share_unloads_ge_90"] == 75.0
