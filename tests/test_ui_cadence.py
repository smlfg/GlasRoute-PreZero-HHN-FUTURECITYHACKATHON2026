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


def test_prepare_keeps_the_file_values():
    data = ui_cadence.load_scenario_data(FIXTURE_DIR)
    work = ui_cadence._prepare_containers(data.containers)
    assert list(work["recommendation"]) == ["gleich", "länger", "kürzer", "länger"]
    assert work["rhythm_weeks_new"].tolist() == [1.0, 4.0, 1.0, 3.0]


# --- tab 1: Wochenplan ------------------------------------------------------------------


def test_week_plan_has_key_sentence_and_one_card_per_area():
    html = _sections()["plan"]
    assert ui_cadence.KEY_SENTENCE in html
    assert html.count("cadence-area-card") == 2  # areas 0 and 1 (CSS class counted once per card tag)
    assert "Gebiet 1 (Mo)" in html and "Gebiet 2 (Di)" in html
    assert "<table" not in html  # the long container table is gone


def test_week_plan_recommendation_sentences():
    html = _sections()["plan"]
    assert "Standort L1…" in html or "Standort L1" in html
    assert "alle 4 Wochen statt alle 2 Wochen – war im Schnitt nur 22 % voll" in html
    assert "jede Woche statt alle 2 Wochen – lief 3× über" in html
    assert "bekommen einen längeren Rhythmus" in html and "bekommen einen kürzeren Rhythmus" in html


def test_week_plan_missing_columns_say_daten_folgen(tmp_path: Path):
    shutil.copytree(FIXTURE_DIR, tmp_path / "s")
    c = pd.read_csv(tmp_path / "s" / "containers.csv").drop(columns=["recommendation", "rhythm_weeks_new"])
    c.to_csv(tmp_path / "s" / "containers.csv", index=False)
    html = _sections(tmp_path / "s")["plan"]
    assert "Daten folgen" in html and "rhythm_weeks_new" in html
    assert "cadence-area-card" not in html


def test_plan_without_data_shows_hint(tmp_path: Path):
    assert "Szenariodaten fehlen (scripts/run_scenarios.py ausführen)" in _sections(tmp_path / "nope")["plan"]


# --- tab 2: Wirkung ---------------------------------------------------------------------


def test_impact_shows_today_to_new_and_marks_worse_red():
    html = _sections()["impact"]
    assert "67,0 % → 60,0 %" in html  # fill goes DOWN
    assert "impact-bad" in html  # ... and is shown red
    assert "40 → 15" in html  # overflows down: good (green)
    assert "Ø Füllgrad bei Leerung" in html and "Überläufe" in html
    assert "Leerungen" in html and "Stunden" in html and "Kosten" in html


def test_impact_falls_back_to_f_fixed_areas(tmp_path: Path):
    shutil.copytree(FIXTURE_DIR, tmp_path / "s")
    summary = json.loads((tmp_path / "s" / "summary.json").read_text(encoding="utf-8"))
    for sc in summary["scenarios"]:
        if sc["id"] == "h_area_week_rhythm":
            sc["id"] = "f_fixed_areas"
    (tmp_path / "s" / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    html = _sections(tmp_path / "s")["impact"]
    assert "f_fixed_areas" not in html or "67,0 %" in html
    assert "noch nicht vor" in html


def test_impact_without_data_shows_hint(tmp_path: Path):
    assert "Szenariodaten fehlen" in _sections(tmp_path / "nope")["impact"]


# --- tab 2 ----------------------------------------------------------------------------------


def test_detail_sawtooth_from_readings_and_explanation():
    html = _sections()["detail"]
    assert "saw-chart" in html and "cadence-explain" in html
    rows = _payload(html)
    assert len(rows) == 4
    by = {(r["location_id"], r["material"]): r for r in rows}
    assert by[("L1", "white")]["history"]
    assert by[("L1", "brown")]["explanation"] == (
        "Takt heute 2 Wochen → neu 4 Wochen, wird nach jeder Messung neu berechnet."
    )


def test_detail_without_data_shows_hint(tmp_path: Path):
    assert "Szenariodaten fehlen" in _sections(tmp_path / "nope")["detail"]


def test_route_is_a_collapsible_extra_in_the_outlook():
    html = _sections(route_html="<div>MAP</div>", route_metrics={"num_stops": 3})["scenarios"]
    assert "<summary>Karte und Route (zusätzlich)</summary>" in html and "MAP" in html


# --- tab 4 ----------------------------------------------------------------------------------


def test_scenarios_one_table_per_time_model_real_first_with_caveats():
    html = _sections()["scenarios"]
    assert '<details class="cadence-all">' in html  # collapsed by default
    assert "<details class=\"cadence-all\" open" not in html
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
    assert produced in sections["scenarios"] and produced in sections["impact"]
    for scenario in summary["scenarios"]:
        assert f'data-scenario="{scenario["id"]}"' in sections["scenarios"]
