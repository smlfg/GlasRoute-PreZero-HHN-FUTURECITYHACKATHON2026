"""Tests for the cadence UI - pure rendering of the scenario engine output.

Fixture: ``tests/fixtures/ui_cadence/`` in exactly the engine's format. One test
renders against the real committed outputs in ``data/outputs/scenarios/``.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from prezero import ui_cadence

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "ui_cadence"
REAL_DIR = ROOT / "data" / "outputs" / "scenarios"

READINGS = pd.DataFrame(
    {
        "Location_id": ["L1", "L1", "L1", "L2", "L2"],
        "material_type": ["white", "white", "white", "brown", "brown"],
        "date": ["2026-01-01", "2026-01-11", "2026-01-21", "2026-01-01", "2026-01-11"],
        "fill_level_numeric": [0.0, 40.0, 60.0, 0.0, 10.0],
    }
)


def _sections(directory: Path = FIXTURE_DIR, readings=READINGS, **kw) -> dict[str, str]:
    return ui_cadence.build_cadence_sections(readings, "2026-04-15", scenario_dir=directory, **kw)


def _payload(html: str) -> list[dict]:
    m = re.search(r'<script id="cadence-detail-payload" type="application/json">(.*?)</script>', html, re.S)
    assert m
    return json.loads(m.group(1))


# --- reading ------------------------------------------------------------------------------


def test_load_reads_the_engine_files():
    data = ui_cadence.load_scenario_data(FIXTURE_DIR)
    assert data.available and data.missing == []
    assert data.produced_t == 100.0
    assert data.period["days"] == 349
    assert ("e_mentor", "real") in data.daily
    assert data.km_decomposition is not None


def test_missing_files_are_reported(tmp_path: Path):
    shutil.copytree(FIXTURE_DIR, tmp_path / "s")
    (tmp_path / "s" / "containers.csv").unlink()
    data = ui_cadence.load_scenario_data(tmp_path / "s")
    assert not data.available and "containers.csv" in data.missing
    assert not ui_cadence.load_scenario_data(tmp_path / "nope").available


def test_prepare_status_rules():
    data = ui_cadence.load_scenario_data(FIXTURE_DIR)
    work = ui_cadence._prepare_containers(data.containers, 349)
    status = dict(zip(work["location_id"] + work["material"], work["status"]))
    assert status["L1white"] == "ok"
    assert status["L1brown"] == "yellow"  # skip_14d = 1
    assert status["L2brown"] == "red"  # overflow > 0
    # Takt heute = period / emptyings, Takt neu = cadence_days_T
    assert work.loc[0, "current_cadence_days"] == pytest.approx(349 / 9)
    assert work.loc[0, "proposed_cadence_days"] == 5.0


# --- tab 1 ----------------------------------------------------------------------------------


def test_list_has_kpis_short_lists_histogram_and_collapsed_full_list():
    html = _sections()["list"]
    assert "100,0 t" in html  # produced_t
    assert "Läuft über – Takt zu lang" in html and "Zu oft geleert – Takt zu kurz" in html
    assert "<svg" in html and "cadence-histogram" in html
    assert re.search(r"<details class=\"cadence-all\">\s*<summary>Alle 4 Container anzeigen", html)
    assert "cadence-search" in html
    assert "%/Tag" in html and "5,0 %/Tag" in html


def test_list_kpi_counts_and_best_scenario():
    data = ui_cadence.load_scenario_data(FIXTURE_DIR)
    work = ui_cadence._prepare_containers(data.containers, 349)
    kpis = ui_cadence.compute_header_kpis(work, data.summary)
    assert kpis["containers_with_overflow"] == 2
    assert kpis["too_often_emptied"] == 2  # L1 brown (skipped) and L3 green (45 %)
    html = _sections()["list"]
    assert "Mentor-Takt" in html  # cheapest scenario (real) named
    assert ">-30<" in html or "-30" in html


def test_list_without_data_shows_hint_and_no_numbers(tmp_path: Path):
    html = _sections(tmp_path / "nope")["list"]
    assert "Szenariodaten fehlen (scripts/run_scenarios.py ausführen)" in html
    assert "%/Tag" not in html


# --- tab 2 ----------------------------------------------------------------------------------


def test_detail_sawtooth_from_readings_and_explanation():
    html = _sections()["detail"]
    assert "saw-chart" in html and "cadence-explain" in html
    rows = _payload(html)
    assert len(rows) == 4
    by = {(r["location_id"], r["material"]): r for r in rows}
    assert by[("L1", "white")]["history"]
    assert "übersprungen" in by[("L1", "brown")]["explanation"]
    assert "Überlauf" in by[("L2", "brown")]["explanation"]


def test_detail_without_data_shows_hint(tmp_path: Path):
    assert "Szenariodaten fehlen" in _sections(tmp_path / "nope")["detail"]


# --- tab 3 ----------------------------------------------------------------------------------


def test_week_view_has_daily_sums_and_areas():
    html = _sections()["week"]
    assert "Diese Woche" in html and "Gebiet 1" in html and "Gebiet 2" in html
    assert "70" in html  # 7 days x 10 emptyings
    assert "<details" not in html


def test_week_view_route_is_collapsible():
    html = _sections(route_html="<div>MAP</div>", route_metrics={"num_stops": 3})["week"]
    assert "<summary>Karte und Route (zusätzlich)</summary>" in html and "MAP" in html


# --- tab 4 ----------------------------------------------------------------------------------


def test_scenarios_one_table_per_time_model_real_first_with_caveats():
    html = _sections()["scenarios"]
    assert html.index('data-time-model="real"') < html.index('data-time-model="km"')
    assert "Gleiche Glasmenge: 100,00 t in jedem Szenario" in html
    assert "Standorte simuliert: 3 IDs auf 3 OSM-Punkten" in html
    assert "Mehrkammer vs. ein LKW je Farbe unbekannt" in html
    assert "Farbtrennung" in html and "Woher kommen die Mehr-km" in html
    assert "günstigste" in html and "wenigste Überläufe" in html


def test_scenarios_missing_is_visible_hint(tmp_path: Path):
    html = _sections(tmp_path / "nope")["scenarios"]
    assert "Szenariodaten fehlen" in html


def test_no_use_of_the_deleted_cadence_module():
    assert not (ROOT / "src" / "prezero" / "cadence.py").exists()
    for name in ("ui.py", "ui_cadence.py", "ui_cadence_assets.py", "ui_cadence_js.py"):
        text = (ROOT / "src" / "prezero" / name).read_text(encoding="utf-8")
        assert not re.search(r"prezero\.cadence|import cadence|from prezero import .*\bcadence\b", text)


# --- real committed outputs ---------------------------------------------------------------


@pytest.mark.skipif(not (REAL_DIR / "summary.json").is_file(), reason="no committed outputs")
def test_renders_against_real_outputs():
    summary = json.loads((REAL_DIR / "summary.json").read_text(encoding="utf-8"))
    sections = ui_cadence.build_cadence_sections(None, "2026-04-15", scenario_dir=REAL_DIR)
    assert "Szenariodaten fehlen" not in "".join(sections.values())
    produced = ui_cadence._de(summary["produced_t"], 2)
    assert produced in sections["scenarios"]
    for scenario in summary["scenarios"]:
        assert f'data-scenario="{scenario["id"]}"' in sections["scenarios"]
    assert ui_cadence._de(summary["produced_t"], 1) in sections["list"]
