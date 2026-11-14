"""Forecast layers built on scored_<date>.csv (no new model, no ML)."""

from __future__ import annotations

import pandas as pd
import pytest

from prezero.forecast import (
    FORECAST_OFFSETS,
    count_critical,
    forecast_from_scored,
    format_forecast_line,
)


def scored_fixture() -> pd.DataFrame:
    """Scored rows as the pipeline writes them."""
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L2", "L2", "L3"],
            "material_type": ["white", "white", "green", "green", "brown"],
            "last_date": [
                "2026-04-01",
                "2026-04-06",
                "2026-04-01",
                "2026-04-06",
                "2026-04-06",
            ],
            "last_fill_level": [40.0, 90.0, 40.0, 45.0, 110.0],
            "days_since_last": [14, 9, 14, 9, 9],
            "overfull_rate": [0.0, 0.0, 0.0, 0.0, 1.0],
            "avg_daily_increase": [10.0, 10.0, 1.0, 1.0, 0.0],
            "season_factor": [1.0, 1.0, 1.0, 1.0, 1.0],
            "reading_count": [2, 2, 2, 2, 1],
            "score": [1.0, 1.0, 0.5, 0.5, 1.0],
            "critical": [True, True, False, False, True],
        }
    )


def test_forecast_is_capped_at_110() -> None:
    result = forecast_from_scored(scored_fixture(), "2026-04-15")
    assert not result.empty
    assert result["forecast_pct"].max() <= 110.0
    assert (result["forecast_pct"] >= 0).all()


def test_later_date_forecast_is_not_lower_than_earlier() -> None:
    result = forecast_from_scored(scored_fixture(), "2026-04-15")
    by_horizon = {
        offset: result[result["offset_days"] == offset].set_index(
            ["Location_id", "material_type"]
        )["forecast_pct"]
        for offset in FORECAST_OFFSETS
    }
    for earlier, later in zip(FORECAST_OFFSETS, FORECAST_OFFSETS[1:]):
        first = by_horizon[earlier]
        second = by_horizon[later]
        assert (second >= first).all(), f"{later} day forecast below {earlier} day forecast"


def test_status_mapping_boundaries() -> None:
    result = forecast_from_scored(scored_fixture(), "2026-04-15", offsets=(0,))
    statuses = dict(
        zip(
            zip(result["Location_id"], result["material_type"]),
            result["status"],
        )
    )
    # Measure-and-empty: level now = rate x days since the emptying visit (season 1.0 in April).
    # L1 white: 10 %/d x 9 d = 90 % -> red ; L2 green: 1 %/d x 9 d = 9 % -> green ;
    # L3 brown: found at 110 % but emptied, rate 0 -> 0 % -> green.
    assert statuses[("L1", "white")] == "red"
    assert statuses[("L2", "green")] == "green"
    assert statuses[("L3", "brown")] == "green"


@pytest.mark.parametrize(
    ("fill", "status"),
    [(49.9, "green"), (50.0, "yellow"), (80.0, "yellow"), (80.1, "red"), (110.0, "black")],
)
def test_status_thresholds(fill: float, status: str) -> None:
    from prezero.forecast import _status

    assert _status(fill) == status


def test_forecast_line_format() -> None:
    result = forecast_from_scored(scored_fixture(), "2026-04-15")
    line = format_forecast_line(7, result[result["offset_days"] == 7])
    assert line.startswith("+7 Tage: ")
    assert "rot" in line and "schwarz" in line
    today = format_forecast_line(0, result[result["offset_days"] == 0])
    assert today.startswith("Heute: ")


def test_critical_count_matches_statuses() -> None:
    result = forecast_from_scored(scored_fixture(), "2026-04-15")
    frame = result[result["offset_days"] == 7]
    expected = int(frame["status"].isin(["red", "black"]).sum())
    assert count_critical(frame) == expected


def test_all_offsets_are_produced() -> None:
    result = forecast_from_scored(scored_fixture(), "2026-04-15")
    assert sorted(result["offset_days"].unique()) == list(FORECAST_OFFSETS)
    # 5 scored rows x 4 horizons
    assert len(result) == 20
