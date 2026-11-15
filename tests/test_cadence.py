"""Tests for the cadence model (Erzeuger-Verbraucher pro Container).

The test is the specification: every number must come from the readings.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from prezero.cadence import (
    AREA_RURAL,
    AREA_URBAN,
    DEFAULT_EMPTY_AT_PCT,
    CadenceParams,
    assign_area,
    build_container_cadences,
    classify_status,
    explain_cadence_change,
    fill_rate_pct_per_day,
    ideal_cadence_days,
    observed_cadence_days,
)


def _readings(rows: list[tuple[str, str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Location_id": loc,
                "material_type": mat,
                "date": date,
                "fill_level_numeric": level,
                "fill_level_perc": str(level),
                "is_overfull": level >= 110.0,
            }
            for loc, mat, date, level in rows
        ]
    )


# --- ideal cadence ----------------------------------------------------------------------


def test_ideal_cadence_is_capacity_minus_buffer_divided_by_rate():
    # (100 - 80) / 2.0 = 10 days
    assert ideal_cadence_days(2.0, 80.0) == pytest.approx(10.0)
    # (100 - 70) / 2.0 = 15 days
    assert ideal_cadence_days(2.0, 70.0) == pytest.approx(15.0)


def test_ideal_cadence_none_without_rate():
    assert ideal_cadence_days(0.0, 80.0) is None
    assert ideal_cadence_days(-1.0, 80.0) is None


def test_cadence_is_clamped_to_the_allowed_band():
    params = CadenceParams(min_cadence_days=3.0, max_cadence_days=14.0)
    assert params.clamped_cadence(1.0) == 3.0
    assert params.clamped_cadence(40.0) == 14.0
    assert params.clamped_cadence(7.0) == 7.0


# --- fill rate ---------------------------------------------------------------------------


def test_fill_rate_uses_quotient_of_sums():
    dates = pd.to_datetime(["2026-01-01", "2026-01-11", "2026-01-21"])
    # (40 + 60) / 20 days = 5 %/day
    assert fill_rate_pct_per_day(dates, [0.0, 40.0, 60.0]) == pytest.approx(5.0)


def test_fill_rate_needs_two_visits():
    assert fill_rate_pct_per_day(pd.to_datetime(["2026-01-01"]), [40.0]) is None


def test_observed_cadence_is_mean_gap_between_visits():
    dates = pd.to_datetime(["2026-01-01", "2026-01-11", "2026-01-26"])
    assert observed_cadence_days(dates) == pytest.approx(12.5)


# --- status rules ------------------------------------------------------------------------


def test_yellow_when_last_three_visits_were_below_30_percent():
    params = CadenceParams()
    levels = [10.0, 12.0, 15.0, 20.0]
    assert classify_status(levels, 1.0, 3, params) == "yellow"


def test_not_yellow_when_a_recent_visit_was_above_30_percent():
    params = CadenceParams()
    assert classify_status([10.0, 12.0, 15.0, 55.0], 1.0, 1, params) != "yellow"


def test_red_when_overflow_risk_before_next_visit():
    params = CadenceParams()
    # 80 % found, 15 %/day -> overflow (110 %) in 2 days, next visit in 5 days.
    assert classify_status([80.0], 15.0, 5, params) == "red"


def test_ok_when_no_rule_triggers():
    params = CadenceParams()
    assert classify_status([95.0, 99.0], 5.0, 1, params) == "ok"


# --- areas -------------------------------------------------------------------------------


def test_area_assignment_is_urban_near_the_city_centre():
    assert assign_area(49.1427, 9.2109) == AREA_URBAN


def test_area_assignment_is_rural_far_from_the_city_centre():
    # Flein / Lauffen are north of the city centre (Flein: d = 0.051).
    assert assign_area(49.1936, 9.2111) == AREA_RURAL
    assert assign_area(49.2286, 9.2726) == AREA_RURAL


# --- container table ---------------------------------------------------------------------


def test_build_container_cadences_computes_rate_and_cadence():
    readings = _readings(
        [
            ("L1", "white", "2026-01-01", 0.0),
            ("L1", "white", "2026-01-11", 40.0),
            ("L1", "white", "2026-01-21", 60.0),
        ]
    )
    params = CadenceParams(empty_at_pct=80.0)
    table = build_container_cadences(readings, params, reference_date="2026-01-21")
    assert len(table) == 1
    row = table.iloc[0]
    # rate = (40 + 60) / 20 days = 5 %/day
    assert row["rate_pct_per_day"] == pytest.approx(5.0)
    # T = (100 - 80) / 5 = 4 days
    assert row["cadence_days_T"] == pytest.approx(4.0)
    assert row["visits"] == 3
    assert row["location_id"] == "L1"


def test_build_container_cadences_uses_coordinates_for_the_area():
    readings = _readings(
        [
            ("L1", "white", "2026-01-01", 0.0),
            ("L1", "white", "2026-01-11", 40.0),
        ]
    )
    locations = pd.DataFrame(
        {"Location_id": ["L1"], "lat": [49.1427], "lon": [9.2109]}
    )
    table = build_container_cadences(
        readings, CadenceParams(), locations_df=locations, reference_date="2026-01-11"
    )
    assert table.iloc[0]["area"] == AREA_URBAN
    assert table.iloc[0]["lat"] == pytest.approx(49.1427)


def test_build_container_cadences_empty_input_returns_empty_table():
    table = build_container_cadences(pd.DataFrame(), CadenceParams())
    assert table.empty
    assert "cadence_days_T" in table.columns


def test_kg_per_day_follows_from_rate_volume_and_density():
    readings = _readings(
        [
            ("L1", "white", "2026-01-01", 0.0),
            ("L1", "white", "2026-01-11", 40.0),
        ]
    )
    params = CadenceParams(container_volume_m3=2.5, density_kg_per_m3=400.0)
    table = build_container_cadences(readings, params, reference_date="2026-01-11")
    # 4 %/day -> 4/100 * 2.5 m³ * 400 kg/m³ = 40 kg/day
    assert table.iloc[0]["rate_kg_per_day"] == pytest.approx(40.0)


# --- explanations ------------------------------------------------------------------------


def test_explain_cadence_change_yellow_mentions_visits_and_takt():
    row = {
        "status": "yellow",
        "current_cadence_days": 7.0,
        "proposed_cadence_days": 14.0,
        "visits": 5,
        "rate_pct_per_day": 1.4,
    }
    text = explain_cadence_change(row)
    assert "3 Leerungen unter 30 %" in text
    assert "7 → 14 Tage" in text


def test_explain_cadence_change_red_mentions_overflow():
    row = {
        "status": "red",
        "current_cadence_days": 7.0,
        "proposed_cadence_days": 5.0,
        "visits": 5,
        "rate_pct_per_day": 15.0,
    }
    text = explain_cadence_change(row)
    assert "über" in text
    assert "Takt 7 → 5 Tage" in text


def test_explain_cadence_change_ok_mentions_rate_and_threshold():
    row = {
        "status": "ok",
        "current_cadence_days": 10.0,
        "proposed_cadence_days": 10.0,
        "visits": 5,
        "rate_pct_per_day": 2.0,
        "empty_at_pct": 80.0,
    }
    text = explain_cadence_change(row)
    assert "2,0 % pro Tag" in text
    assert "80 % geleert" in text
