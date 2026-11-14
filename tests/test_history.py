import json

import pandas as pd
import pytest

from prezero.history import historical_days, observed_visits
from prezero.routing import OperationalConfig


def test_duplicate_records_and_colocated_containers():
    raw = pd.DataFrame({
        "date": ["2026-01-01"] * 4, "Location_id": ["a", "a", "a", "b"],
        "material_type": ["green", "green", "white", "green"],
        "fill_level_perc": ["50", "50", "overfull", "80"],
    })
    geo = pd.DataFrame({
        "Location_id": ["a", "b"], "lat": [49.14] * 2, "lon": [9.21] * 2,
        "source": ["osm_assigned"] * 2, "confidence": ["simulated_mapping"] * 2,
    })
    row = historical_days(raw, geo, OperationalConfig()).iloc[0]
    assert (row.measurement_records, row.containers_visited, row.location_ids, row.modeled_sites) == (4, 3, 2, 1)
    assert (row.overfull_observations, row.estimated_mass_kg, row.unserved_bins) == (1, 2400, 0)
    assert row.estimated_volume_m3 == 6
    assert json.loads(row.material_breakdown)["green"]["containers"] == 2
    assert row.modeled_vehicle_days == row.modeled_rounds == 1
    with pytest.raises(ValueError, match="mapped point"):
        historical_days(raw, geo.iloc[:1], OperationalConfig())
    raw.loc[0, "fill_level_perc"] = "90"
    with pytest.raises(ValueError, match="Conflicting"):
        observed_visits(raw)
