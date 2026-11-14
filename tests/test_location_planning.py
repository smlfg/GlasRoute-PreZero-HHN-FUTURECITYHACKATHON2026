"""Tests for the Standortplanung what-if module."""

from __future__ import annotations

import pandas as pd
import pytest

from prezero import location_planning
from prezero.location_planning import (
    LocationPlanningConfig,
    _adoption_share,
    plan_new_locations,
)
from prezero.routing import OperationalConfig


def _sample_scored() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3", "L4"],
            "material_type": ["white", "green", "brown", "white"],
            "last_fill_level": [90.0, 60.0, 110.0, 40.0],
            "est_fill_level": [95.0, 65.0, 110.0, 45.0],
            "avg_daily_increase": [2.0, 1.0, 3.0, 0.5],
            "overfull_rate": [0.0, 0.0, 1.0, 0.0],
            "score": [0.85, 0.55, 0.92, 0.35],
            "critical": [True, False, True, False],
        }
    )


def _sample_locations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3", "L4"],
            "lat": [49.14, 49.15, 49.16, 49.18],
            "lon": [9.21, 9.22, 9.23, 9.25],
            "source": ["osm_assigned"] * 4,
            "confidence": ["simulated_mapping"] * 4,
        }
    )


def test_adoption_share_is_monotonic() -> None:
    cfg = LocationPlanningConfig(adoption_weeks=8.0, logistic_steepness=1.0)
    shares = [_adoption_share(w, cfg.adoption_weeks, cfg.logistic_steepness) for w in range(13)]
    assert shares[0] == 0.0
    assert all(shares[i] <= shares[i + 1] for i in range(len(shares) - 1))
    assert shares[-1] > 0.95


def test_adoption_share_reaches_full_at_configured_weeks() -> None:
    cfg = LocationPlanningConfig(adoption_weeks=4.0, logistic_steepness=2.0)
    assert _adoption_share(4, cfg.adoption_weeks, cfg.logistic_steepness) > 0.95


def test_plan_new_locations_returns_expected_keys() -> None:
    result = plan_new_locations(_sample_scored(), _sample_locations())
    assert result["simulated"] is True
    assert "new_sites" in result
    assert "timeline" in result
    assert "config" in result
    assert "demand_conserved" in result
    assert len(result["timeline"]) == 13


def test_plan_new_locations_limits_to_five_sites() -> None:
    result = plan_new_locations(_sample_scored(), _sample_locations())
    assert len(result["new_sites"]) <= 5


def test_plan_new_locations_demands_are_conserved() -> None:
    cfg = OperationalConfig(
        location_planning_radius_m=2000.0,
        location_planning_adoption_weeks=8.0,
        location_planning_logistic_steepness=1.0,
    )
    result = plan_new_locations(_sample_scored(), _sample_locations(), cfg)
    assert result["demand_conserved"] is True
    assert result["total_transferred_demand_pp_day"] <= result["total_existing_demand_pp_day"] + 1e-6


def test_timeline_new_container_fill_rises() -> None:
    result = plan_new_locations(_sample_scored(), _sample_locations())
    fills = [t["new_container_fill_pct"] for t in result["timeline"]]
    assert fills[0] == 0.0
    assert all(fills[i] <= fills[i + 1] for i in range(len(fills) - 1))


def test_timeline_neighbor_drop_is_non_negative() -> None:
    result = plan_new_locations(_sample_scored(), _sample_locations())
    drops = [t["avg_neighbor_drop_pct"] for t in result["timeline"]]
    assert all(d >= 0.0 for d in drops)


def test_timeline_overflow_counts_are_non_negative() -> None:
    result = plan_new_locations(_sample_scored(), _sample_locations())
    for t in result["timeline"]:
        assert t["overflow_count_before"] >= 0
        assert t["overflow_count_after"] >= 0


def test_plan_new_locations_with_empty_input() -> None:
    empty_scored = pd.DataFrame(columns=["Location_id", "material_type", "est_fill_level", "avg_daily_increase", "overfull_rate"])
    empty_locs = pd.DataFrame(columns=["Location_id", "lat", "lon"])
    result = plan_new_locations(empty_scored, empty_locs)
    assert result["new_sites"] == []
    assert result["demand_conserved"] is True
    assert all(t["new_container_fill_pct"] == 0.0 for t in result["timeline"])


def test_location_planning_config_from_operational_config() -> None:
    op_cfg = OperationalConfig(
        location_planning_radius_m=750.0,
        location_planning_adoption_weeks=6.0,
        location_planning_logistic_steepness=2.0,
        road_detour_factor=1.5,
    )
    cfg = LocationPlanningConfig.from_operational_config(op_cfg)
    assert cfg.radius_m == 750.0
    assert cfg.adoption_weeks == 6.0
    assert cfg.logistic_steepness == 2.0
    assert cfg.road_detour_factor == 1.5


def test_new_sites_respect_minimum_separation() -> None:
    # Create a cluster and a remote point so we get >1 site with enough radius.
    scored = pd.DataFrame(
        {
            "Location_id": ["L1", "L2"],
            "material_type": ["white", "green"],
            "est_fill_level": [100.0, 100.0],
            "avg_daily_increase": [5.0, 5.0],
            "overfull_rate": [1.0, 1.0],
        }
    )
    locs = pd.DataFrame(
        {
            "Location_id": ["L1", "L2"],
            "lat": [49.14, 49.20],
            "lon": [9.21, 9.27],
            "source": ["osm_assigned"] * 2,
            "confidence": ["simulated_mapping"] * 2,
        }
    )
    cfg = OperationalConfig(location_planning_radius_m=2000.0)
    result = plan_new_locations(scored, locs, cfg)
    sites = result["new_sites"]
    for i in range(len(sites)):
        for j in range(i + 1, len(sites)):
            d = location_planning._haversine_m(
                sites[i]["lat"], sites[i]["lon"], sites[j]["lat"], sites[j]["lon"]
            )
            assert d >= location_planning.MIN_SITE_SEPARATION_M
