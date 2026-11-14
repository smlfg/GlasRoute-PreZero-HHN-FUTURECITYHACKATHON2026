"""Tests for feature engineering."""

from __future__ import annotations

import pandas as pd
import pytest

from prezero.features import build_features, get_season_factor


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L1", "L1", "L2"],
            "material_type": ["white", "white", "white", "white", "brown"],
            "date": pd.to_datetime(
                ["2026-04-01", "2026-04-06", "2026-04-10", "2026-04-20", "2026-04-05"]
            ),
            "fill_level_numeric": [20.0, 70.0, 110.0, 10.0, 40.0],
        }
    )


def test_build_features_filters_after_target_date() -> None:
    df = _sample_df()
    feat = build_features(df, "2026-04-15")
    l1 = feat[(feat["Location_id"] == "L1") & (feat["material_type"] == "white")].iloc[0]
    # 2026-04-20 reading must be excluded; last reading is 2026-04-10 at 110.0.
    assert l1["last_fill_level"] == pytest.approx(110.0)
    assert l1["days_since_last"] == 5
    assert l1["reading_count"] == 3


def test_build_features_metrics_overfull_and_daily_increase() -> None:
    """Measure-and-empty: each visit empties the container, so rate = level found / days since visit."""
    df = _sample_df()
    feat = build_features(df, "2026-04-15")
    l1 = feat[(feat["Location_id"] == "L1") & (feat["material_type"] == "white")].iloc[0]
    # 1 of 3 readings <= 2026-04-15 is 110.0; rates after emptying: 70/5=14, 110/4=27.5.
    assert l1["overfull_rate"] == pytest.approx(1 / 3)
    assert l1["avg_daily_increase"] == pytest.approx(20.75)
    assert l1["rate_source"] == "history"
    # Emptied on 2026-04-10 at 110 %: now 5 days x 20.75 %/day = 103.75 %, not 110 % + growth.
    assert l1["est_fill_level"] == pytest.approx(103.8, abs=0.05)
    l2 = feat[(feat["Location_id"] == "L2") & (feat["material_type"] == "brown")].iloc[0]
    assert l2["overfull_rate"] == pytest.approx(0.0)
    # Single visit: no interval, so the median rate of all known containers is used.
    assert l2["rate_source"] == "material_median"
    assert l2["avg_daily_increase"] == pytest.approx(20.75)
    assert l2["est_fill_level"] == pytest.approx(110.0)  # 10 days x 20.75, capped


def test_container_emptied_at_visit_restarts_near_zero() -> None:
    df = pd.DataFrame(
        {
            "Location_id": ["L1", "L1"],
            "material_type": ["green", "green"],
            "date": pd.to_datetime(["2026-03-01", "2026-03-31"]),
            "fill_level_numeric": [110.0, 60.0],
        }
    )
    feat = build_features(df, "2026-03-31").iloc[0]
    assert feat["last_fill_level"] == pytest.approx(60.0)  # found at the visit ...
    assert feat["est_fill_level"] == pytest.approx(0.0)  # ... and emptied the same day
    assert feat["avg_daily_increase"] == pytest.approx(2.0)  # 60 % in 30 days


def test_season_factor_high_in_jan_apr() -> None:
    assert get_season_factor("2026-01-15") > get_season_factor("2026-07-15")
    assert get_season_factor("2026-04-15") == pytest.approx(1.0)
    feat = build_features(_sample_df(), "2026-04-15")
    assert (feat["season_factor"] == 1.0).all()
