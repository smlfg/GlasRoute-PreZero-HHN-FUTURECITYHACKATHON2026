import pandas as pd
import pytest
from prezero.replay import simulate
from prezero.routing import OperationalConfig


def sample():
    raw = pd.DataFrame(
        dict(
            Location_id=["a"] * 3,
            material_type=["green"] * 3,
            date=["2026-01-01", "2026-01-03", "2026-01-05"],
            fill_level_perc=["30", "80", "60"],
        )
    )
    geo = pd.DataFrame(
        dict(
            Location_id=["a"],
            lat=[49.14],
            lon=[9.21],
            source=["osm_assigned"],
            confidence=["simulated_mapping"],
        )
    )
    return raw, geo


def test_threshold_reset_backlog_conservation_and_no_future_leakage():
    raw, geo = sample()
    cfg = OperationalConfig()
    daily, r = simulate(raw, geo, cfg, cold_rate=40.0)
    assert list(daily.optimized_emptyings) == [1, 0, 1, 0, 1]
    assert list(daily.optimized_ending_kg) == [0, 400, 0, 400, 0]
    # Same geography and actual operating dates, paired ledgers route identical loads identically.
    assert list(daily.optimized_km) == list(daily.historical_km)
    assert list(daily.optimized_vehicles_needed) == [1, 0, 1, 0, 1]
    for s in ["optimized", "historical"]:
        b = r[s]["inventory"]
        assert b["admitted_kg"] + b["generated_kg"] == pytest.approx(
            b["ending_kg"] + b["collected_kg"] + b["spill_kg"]
        )
    raw.loc[2, "fill_level_perc"] = "10"
    other, _ = simulate(raw, geo, cfg, cold_rate=40.0)
    pd.testing.assert_frame_equal(daily.iloc[:-1], other.iloc[:-1])
    assert daily.optimized_collected_kg.equals(other.optimized_collected_kg)
    higher, _ = simulate(raw, geo, cfg, cold_rate=40.0, threshold=90)
    assert higher.optimized_emptyings.iloc[2] == 0
    assert higher.optimized_due_backlog.iloc[3] == 1
    assert higher.optimized_spill_kg.iloc[-1] > 0


def test_fleet_carries_due_work_through_end():
    raw, geo = sample()
    # Separate births, one short shift. Both bins become due together on final day.
    raw = pd.concat([raw.iloc[[0, 2]], raw.iloc[[1]].assign(Location_id="b")])
    geo = pd.concat([geo, geo.assign(Location_id="b", lon=9.22)])
    cfg = OperationalConfig(max_shift_hours=0.16)
    daily, r = simulate(raw, geo, cfg, cold_rate=50.0, fleet=1)
    assert r["optimized"]["peak"] == 1
    assert r["optimized"]["due_backlog"] == 1
    assert daily.optimized_ending_kg.iloc[-1] >= 800
