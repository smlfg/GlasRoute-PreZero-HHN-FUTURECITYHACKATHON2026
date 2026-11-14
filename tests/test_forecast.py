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
    result = forecast_fill(_model(), "2026-04-20")
    assert result["forecast_pct"].max() <= 110.0
    statuses = dict(zip(result["location_id"], result["status"]))
    assert statuses == {"L1": "black", "L2": "yellow", "L3": "black"}


def test_later_forecast_is_not_lower() -> None:
    earlier = forecast_fill(_model(), "2026-04-10").set_index("location_id")
    later = forecast_fill(_model(), "2026-04-20").set_index("location_id")
    assert (later["forecast_pct"] >= earlier["forecast_pct"]).all()


@pytest.mark.parametrize(
    ("fill", "status"),
    [(49.9, "green"), (50.0, "yellow"), (80.0, "yellow"), (80.1, "red"), (110.0, "black")],
)
def test_status_boundaries(fill: float, status: str) -> None:
    model = _model()
    model[0].containers[0].measurements[-1] = model[0].containers[0].measurements[-1].__class__(
        location_id="L1", timestamp="2026-04-06", fill_pct=fill
    )
    result = forecast_fill(model, "2026-04-06")
    assert result.loc[result["location_id"] == "L1", "status"].item() == status
