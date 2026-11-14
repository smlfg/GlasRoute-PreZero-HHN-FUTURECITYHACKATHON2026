"""Backtest walks forward without look-ahead and scores the timer model against baselines."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

_SPEC = importlib.util.spec_from_file_location(
    "backtest", Path(__file__).resolve().parents[1] / "scripts" / "backtest.py"
)
backtest = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(backtest)


def _readings() -> pd.DataFrame:
    # Fills 2 %/day; emptied at each visit. Visits every 20 days -> always found at 40 %,
    # then a 40-day gap -> found at 80 %.
    return pd.DataFrame(
        {
            "Location_id": ["L1"] * 4,
            "material_type": ["white"] * 4,
            "date": pd.to_datetime(["2026-01-01", "2026-01-21", "2026-02-10", "2026-03-22"]),
            "fill_level_numeric": [30.0, 40.0, 40.0, 80.0],
        }
    )


def test_walk_forward_uses_only_earlier_visits() -> None:
    res = backtest.walk_forward(_readings())
    # Visits 0 and 1 cannot be predicted (need one earlier interval): 2 predictions.
    assert list(res["date"]) == ["2026-02-10", "2026-03-22"]
    first, second = res.iloc[0], res.iloc[1]
    assert first["model"] == pytest.approx(40.0)  # 2 %/day x 20 days
    assert second["model"] == pytest.approx(80.0)  # same rate x 40 days, future value not used
    assert second["mean_past"] == pytest.approx((30 + 40 + 40) / 3)
    assert second["last_value"] == pytest.approx(40.0)


def test_summary_reports_model_and_baselines() -> None:
    summary = backtest.summarize(backtest.walk_forward(_readings()))
    assert summary["overall"]["model"]["mae_pp"] == pytest.approx(0.0)
    assert summary["overall"]["mean_past"]["mae_pp"] > 0
    assert set(summary["overall"]) == set(backtest.METHODS)


def test_rhythm_flags_container_emptied_too_often() -> None:
    # Fills 1 %/day -> ideal 80 days; emptied every 20 days -> too often.
    readings = pd.DataFrame(
        {
            "Location_id": ["B"] * 4,
            "material_type": ["brown"] * 4,
            "date": pd.to_datetime(["2026-01-01", "2026-01-21", "2026-02-10", "2026-03-02"]),
            "fill_level_numeric": [20.0, 20.0, 20.0, 20.0],
        }
    )
    rh = backtest.rhythm_analysis(readings)
    brown = rh["by_material"]["brown"]
    assert brown["ideal_days_median"] == pytest.approx(80.0)
    assert brown["actual_days_median"] == pytest.approx(20.0)
    assert brown["too_often_pct"] == pytest.approx(100.0)
    assert rh["found_below_50_pct"] == pytest.approx(100.0)
