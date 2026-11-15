"""Tests for the cadence UI — pure presentation of the model lane's output.

The UI must read the scenario output (``summary.json``, ``containers.csv``) and
show no substitute numbers when it is missing. The tests use a small fixture
in exactly the agreed format.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from prezero import ui_cadence

# --- fixtures in the agreed format --------------------------------------------------------

FIXTURE_SUMMARY = {
    "generated_at": "2026-11-15T14:00:00+01:00",
    "period": {"start": "2025-10-17", "end": "2026-09-30", "days": 349},
    "produced_t": 7613.95,
    "scenarios": [
        {
            "id": "d_status_quo",
            "label": "Status quo (reale Leerungstage)",
            "time_model": "real",
            "collected_t": 7613.95,
            "end_stock_t": 0.0,
            "produced_t": 7613.95,
            "mass_balance_ok": True,
            "avg_fill_at_emptying_pct": 66.0,
            "overflow_events": 1858,
            "emptyings": 9918,
            "emptyings_saved_vs_status_quo": 0,
            "stops": 7499,
            "vehicle_days": 326,
            "hours": 1753.15,
            "km": 24640.27,
            "cost_eur": 291217.78,
            "cost_breakdown": {
                "vehicle_days_eur": 163000.0,
                "crew_eur": 112201.6,
                "km_eur": 16016.18,
            },
            "flags": {"cheapest": False, "fewest_overflows": False},
            "source": "scripts/run_scenarios.py",
        },
        {
            "id": "b_min_km",
            "label": "Minimum km (spät leeren)",
            "time_model": "real",
            "collected_t": 7613.95,
            "end_stock_t": 0.0,
            "produced_t": 7613.95,
            "mass_balance_ok": True,
            "avg_fill_at_emptying_pct": 97.6,
            "overflow_events": 9,
            "emptyings": 7907,
            "emptyings_saved_vs_status_quo": 2011,
            "stops": 6200,
            "vehicle_days": 306,
            "hours": 1572.4,
            "km": 23078.0,
            "cost_eur": 268633.0,
            "cost_breakdown": {
                "vehicle_days_eur": 153000.0,
                "crew_eur": 100634.0,
                "km_eur": 14999.0,
            },
            "flags": {"cheapest": True, "fewest_overflows": False},
            "truck_mode": "standard",
            "extra_emptyings_co": 0,
            "source": "scripts/run_scenarios.py",
        },
    ],
}

FIXTURE_CONTAINERS = pd.DataFrame(
    {
        "location_id": ["L1", "L2", "L3"],
        "material": ["white", "brown", "green"],
        "lat": [49.1427, 49.1936, 49.15],
        "lon": [9.2109, 9.2111, 9.22],
        "area": ["urban", "rural", "urban"],
        "rate_pct_per_day": [5.0, 0.67, 2.5],
        "rate_kg_per_day": [50.0, 6.7, 25.0],
        "cadence_days_T": [4.0, 14.0, 8.0],
        "emptyings_status_quo": [9.0, 7.0, 12.0],
        "emptyings_mentor": [12.0, 23.0, 15.0],
        "avg_fill_status_quo_pct": [80.0, 21.8, 55.0],
        "avg_fill_mentor_pct": [45.0, 34.8, 40.0],
        "overflow_events_status_quo": [0.0, 3.0, 1.0],
        "skip_14d": [0.0, 12.0, 2.0],
    }
)

FIXTURE_READINGS = pd.DataFrame(
    {
        "Location_id": ["L1", "L1", "L1", "L2", "L2"],
        "material_type": ["white", "white", "white", "brown", "brown"],
        "date": ["2026-01-01", "2026-01-11", "2026-01-21", "2026-01-01", "2026-01-11"],
        "fill_level_numeric": [0.0, 40.0, 60.0, 0.0, 10.0],
    }
)


@pytest.fixture()
def scenario_dir(tmp_path: Path) -> Path:
    """A small scenario directory in exactly the agreed format."""
    directory = tmp_path / "scenarios"
    directory.mkdir()
    (directory / "summary.json").write_text(
        json.dumps(FIXTURE_SUMMARY, ensure_ascii=False), encoding="utf-8"
    )
    FIXTURE_CONTAINERS.to_csv(directory / "containers.csv", index=False)
    for scenario in FIXTURE_SUMMARY["scenarios"]:
        daily = pd.DataFrame(
            {
                "date": ["2025-10-17", "2025-10-18"],
                "n_emptyings": [23, 0],
                "n_overflow_events": [2, 0],
                "avg_fill_at_emptying_pct": [66.0, 0.0],
                "tonnage_t": [15.5, 0.0],
                "stops": [5, 0],
                "vehicles_needed": [1, 0],
                "shift_hours": [3.82, 0.0],
                "km": [51.63, 0.0],
                "cost_eur": [1200.0, 0.0],
            }
        )
        daily.to_csv(
            directory / f"{scenario['id']}__{scenario['time_model']}_daily.csv", index=False
        )
    return directory


# --- reading ------------------------------------------------------------------------------


def test_load_scenario_data_reads_the_contract_files(scenario_dir: Path):
    data = ui_cadence.load_scenario_data(scenario_dir)
    assert data.available
    assert data.missing == []
    assert data.produced_t == 7613.95
    assert data.period["days"] == 349
    assert len(data.scenarios) == 2
    assert data.scenario("b_min_km", "real")["emptyings_saved_vs_status_quo"] == 2011
    assert ("d_status_quo", "real") in data.daily


def test_missing_files_are_reported(scenario_dir: Path):
    (scenario_dir / "containers.csv").unlink()
    data = ui_cadence.load_scenario_data(scenario_dir)
    assert not data.available
    assert "containers.csv" in data.missing


def test_missing_directory_is_reported(tmp_path: Path):
    data = ui_cadence.load_scenario_data(tmp_path / "nope")
    assert not data.available
    assert "summary.json" in data.missing


# --- View 1: container list ---------------------------------------------------------------


def test_container_list_shows_the_values_of_the_containers_file(scenario_dir: Path):
    sections = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=scenario_dir
    )
    html = sections["list"]
    # The fill rate and the cadence come from containers.csv.
    assert "5,0 %/Tag" in html
    assert "14 Tage" in html
    assert "8 Tage" in html
    assert "Land (Flein, Lauffen)" in html


def test_container_list_has_the_required_columns(scenario_dir: Path):
    html = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=scenario_dir
    )["list"]
    for header in ("Füllrate", "Takt heute", "Takt neu", "Status"):
        assert header in html


def test_container_list_kpis_come_from_the_files(scenario_dir: Path):
    data = ui_cadence.load_scenario_data(scenario_dir)
    kpis = ui_cadence.compute_header_kpis(data.containers, data.summary)
    # Weighted by the emptyings of the status quo:
    # (80*9 + 21.8*7 + 55*12) / (9+7+12) = 1478.6 / 28 = 52.8
    assert kpis["avg_fill_at_emptying_pct"] == pytest.approx(52.8, abs=0.1)
    assert kpis["overflow_events"] == 4  # 0 + 3 + 1
    assert kpis["emptyings_saved"] == 2011
    assert kpis["emptyings_saved_source"] == "Minimum km (spät leeren)"
    assert kpis["containers"] == 3


def test_container_list_has_approval_button_per_row_and_bulk_button(scenario_dir: Path):
    html = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=scenario_dir
    )["list"]
    assert html.count("cadence-approve-btn") == 3
    assert "cadence-approve-all-btn" in html
    assert "Alle Taktänderungen übernehmen" in html


def test_container_list_uses_german_number_format(scenario_dir: Path):
    html = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=scenario_dir
    )["list"]
    assert "5,0 %/Tag" in html
    assert "5.0 %/Tag" not in html


def test_container_list_labels_assumptions(scenario_dir: Path):
    html = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=scenario_dir
    )["list"]
    assert "Annahme" in html


def test_container_list_without_data_shows_the_hint_and_no_numbers(tmp_path: Path):
    html = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=tmp_path / "nope"
    )["list"]
    assert "Szenariodaten fehlen" in html
    assert "summary.json" in html
    # No substitute numbers.
    assert "%/Tag" not in html


# --- View 2: container detail ------------------------------------------------------------


def test_container_detail_has_sawtooth_and_explanation(scenario_dir: Path):
    html = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=scenario_dir
    )["detail"]
    assert "saw-chart" in html
    assert "cadence-explain" in html
    payload = re.search(
        r'<script id="cadence-detail-payload" type="application/json">(.*?)</script>', html, re.S
    )
    assert payload is not None
    rows = json.loads(payload.group(1))
    assert len(rows) == 3
    assert rows[0]["explanation"]
    # The sawtooth comes from the measurements.
    assert rows[0]["history"]


def test_container_detail_explanation_is_plain_german_with_takt(scenario_dir: Path):
    html = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=scenario_dir
    )["detail"]
    payload = re.search(
        r'<script id="cadence-detail-payload" type="application/json">(.*?)</script>', html, re.S
    )
    rows = json.loads(payload.group(1))
    yellow = [r for r in rows if r["status"] == "yellow"]
    assert yellow, "L2 should be yellow (skipped often in the mentor cadence)"
    assert "übersprungen" in yellow[0]["explanation"]
    assert "Takt" in yellow[0]["explanation"]


def test_container_detail_without_data_shows_the_hint(tmp_path: Path):
    html = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=tmp_path / "nope"
    )["detail"]
    assert "Szenariodaten fehlen" in html


# --- View 3: diese Woche -----------------------------------------------------------------


def test_week_view_groups_by_area(scenario_dir: Path):
    html = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=scenario_dir
    )["week"]
    assert "Diese Woche" in html
    assert "Stadt (Heilbronn)" in html or "Land (Flein, Lauffen)" in html


def test_week_view_hides_map_in_a_collapsible(scenario_dir: Path):
    html = ui_cadence.build_week_view_html(
        ui_cadence._prepare_containers(FIXTURE_CONTAINERS),
        "2026-04-15",
        route_html="<div>MAP</div>",
        route_metrics={"num_stops": 3},
    )
    assert "<details" in html
    assert "<summary>Karte und Route (zusätzlich)</summary>" in html
    assert "MAP" in html


def test_week_view_without_route_has_no_details_element(scenario_dir: Path):
    html = ui_cadence.build_week_view_html(
        ui_cadence._prepare_containers(FIXTURE_CONTAINERS), "2026-04-15"
    )
    assert "<details" not in html


# --- scenario grid ------------------------------------------------------------------------


def test_scenario_grid_renders_the_summary(scenario_dir: Path):
    html = ui_cadence.build_scenario_grid_html(FIXTURE_SUMMARY)
    assert "Status quo" in html
    assert "66,0 %" in html
    assert "1.858" in html
    assert "349" in html
    assert "7.613,95 t" in html


def test_scenario_grid_missing_is_a_visible_hint():
    html = ui_cadence.build_scenario_grid_html(None)
    assert "Szenariodaten fehlen" in html


# --- integration ---------------------------------------------------------------------------


def test_build_cadence_sections_returns_the_three_views(scenario_dir: Path):
    sections = ui_cadence.build_cadence_sections(
        FIXTURE_READINGS, "2026-04-15", scenario_dir=scenario_dir
    )
    assert set(sections) == {"list", "detail", "week", "scenarios"}
    assert "view-cadence" in sections["list"]
    assert "view-cadence-detail" in sections["detail"]
    assert "view-cadence-week" in sections["week"]
