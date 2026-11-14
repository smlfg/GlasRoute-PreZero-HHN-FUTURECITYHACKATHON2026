from __future__ import annotations

import pandas as pd
import pytest

from prezero.forecast import forecast_fill
from prezero.model import build_model


def _model() -> list:
    readings = pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L2", "L2", "L3"],
            "material_type": ["white", "white", "green", "green", "brown"],
            "date": ["2026-04-01", "2026-04-06", "2026-04-01", "2026-04-06", "2026-04-06"],
            "fill_level_perc": [40, 90, 40, 45, 110],
        }
    )
    locations = pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3"],
            "lat": [49.1, 49.2, 49.3],
            "lon": [9.1, 9.2, 9.3],
            "source": ["prezero", "osm_assigned", "synthetic"],
        }
    )
    return build_model(readings, locations)


def test_forecast_is_capped_and_status_mapping_is_correct() -> None:
    """Measure-and-empty: each container refills from ~0 % after its last visit (2026-04-06)."""
    result = forecast_fill(_model(), "2026-04-20")
    assert result["forecast_pct"].max() <= 110.0
    statuses = dict(zip(result["location_id"], result["status"]))
    # L1: 90 %/5 d = 18 %/d x 14 d -> capped 110 (black); L2: 45 %/5 d = 9 %/d x 14 d -> 110 (black);
    # L3: single visit, no rate -> 0 % (green).
    assert statuses == {"L1": "black", "L2": "black", "L3": "green"}


def test_later_forecast_is_not_lower() -> None:
    earlier = forecast_fill(_model(), "2026-04-10").set_index("location_id")
    later = forecast_fill(_model(), "2026-04-20").set_index("location_id")
    assert (later["forecast_pct"] >= earlier["forecast_pct"]).all()


def test_forecast_on_visit_day_is_empty() -> None:
    """The level found at a visit (here 90 %) is emptied; on that day the forecast is ~0 %."""
    result = forecast_fill(_model(), "2026-04-06")
    assert result.loc[result["location_id"] == "L1", "forecast_pct"].item() == pytest.approx(0.0)
    assert result.loc[result["location_id"] == "L1", "status"].item() == "green"
