"""Tests for container criticality scoring."""

from __future__ import annotations

import pandas as pd
import pytest

from prezero.scoring import CRITICAL_THRESHOLD, score_containers


def _features_sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["A", "B", "C", "D"],
            "material_type": ["white", "brown", "white", "green"],
            "last_fill_level": [110.0, 110.0, 0.0, 95.0],
            "overfull_rate": [1.0, 1.0, 0.0, 0.2],
            "season_factor": [1.0, 1.0, 0.5, 1.0],
        }
    )


def test_score_is_normalized_between_zero_and_one() -> None:
    scored = score_containers(_features_sample())
    assert (scored["score"] >= 0.0).all()
    assert (scored["score"] <= 1.0).all()
    top = scored.loc[scored["Location_id"] == "A", "score"].iloc[0]
    assert top == pytest.approx(1.0)


def test_white_glass_weighted_higher_than_brown() -> None:
    scored = score_containers(_features_sample())
    score_white = scored.loc[scored["Location_id"] == "A", "score"].iloc[0]
    score_brown = scored.loc[scored["Location_id"] == "B", "score"].iloc[0]
    assert score_white > score_brown


def test_critical_flag_matches_threshold() -> None:
    scored = score_containers(_features_sample())
    for _, row in scored.iterrows():
        assert bool(row["critical"]) == (row["score"] >= CRITICAL_THRESHOLD)
    assert not bool(scored.loc[scored["Location_id"] == "C", "critical"].iloc[0])
