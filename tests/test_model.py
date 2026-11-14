"""Tests for the GlasRoute domain model."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from prezero.model import (
    GLASS_WHITE,
    Container,
    Depot,
    Measurement,
    ShiftConfig,
    Vehicle,
    WasteStream,
    build_model,
)

ROOT = Path(__file__).resolve().parent.parent
READINGS_PATH = ROOT / "data" / "processed" / "cleaned_readings.csv"
LOCATIONS_PATH = ROOT / "data" / "external" / "locations.csv"


def test_build_model_produces_449_containers_with_measurements_and_waste_stream() -> None:
    readings_df = pd.read_csv(
        READINGS_PATH,
        parse_dates=["date"],
        dtype={"Location_id": str, "material_type": str},
    )
    locations_df = pd.read_csv(LOCATIONS_PATH, dtype={"Location_id": str})

    sites = build_model(readings_df, locations_df)
    assert sites

    containers = [container for site in sites for container in site.containers]
    assert len(containers) == 449
    assert len({c.location_id for c in containers}) == 449

    valid_names = {"glass_white", "glass_green", "glass_brown"}
    for container in containers:
        assert len(container.measurements) >= 1
        assert isinstance(container.waste_stream, WasteStream)
        assert container.waste_stream.name in valid_names
        assert container.expected_mass_kg(100) == pytest.approx(2.5 * 400.0)


def test_container_and_measurement_helpers() -> None:
    m1 = Measurement(location_id="L1", timestamp="2026-04-01", fill_pct=50.0)
    m2 = Measurement(location_id="L1", timestamp="2026-04-06", fill_pct=110.0)

    assert m1.estimated is True
    assert m1.is_overfull is False
    assert m2.is_overfull is True

    container = Container(
        location_id="L1",
        site_id="site_001",
        waste_stream=GLASS_WHITE,
        measurements=[m2, m1],
        reference_date=pd.Timestamp("2026-04-15"),
    )
    assert container.last_fill() == pytest.approx(110.0)
    assert container.days_since_last() == 9
    assert container.avg_daily_increase() == pytest.approx(12.0)
    assert container.overfull_rate() == pytest.approx(0.5)
    assert container.expected_mass_kg(100) == pytest.approx(2.5 * 400.0)


def test_operational_dataclasses_defaults() -> None:
    vehicle = Vehicle()
    depot = Depot()
    shift = ShiftConfig()

    assert vehicle.max_weight_kg == pytest.approx(11000.0)
    assert vehicle.max_volume_m3 == pytest.approx(26.0)
    assert vehicle.avg_speed_kmh == pytest.approx(25.0)
    assert depot.yard_depot == (49.1427, 9.2109)
    assert depot.disposal_depot == (49.1780, 9.2085)
    assert depot.unload_time_min == pytest.approx(20.0)
    assert shift.max_shift_hours == pytest.approx(8.0)
    assert shift.stop_setup_min == pytest.approx(2.0)
    assert shift.lift_time_per_bin_min == pytest.approx(3.0)
    assert shift.road_detour_factor == pytest.approx(1.35)
    assert GLASS_WHITE.season_factor_for_month(3) > GLASS_WHITE.season_factor_for_month(7)
