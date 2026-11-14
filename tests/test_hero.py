"""Hero KPIs must match Pitch/NOTES.md for the demo date (2026-04-15)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from prezero import hero
from prezero.ui import build_ui, compute_benchmark_summary

ROOT = Path(__file__).resolve().parents[1]
DEMO_DATE = "2026-04-15"

# Pitch/NOTES.md (verify_pitch_numbers.py EXPECTED_ROUTE + hero narrative).
PITCH_HERO = {
    "today_overfull": 328,
    "in_tour_overfull": 20,
    "planned_km": 249.9,
    "status_quo_km": 1202.24,
    "vehicles": 4,
    "shift_hours": 7.58,
    "tons": 142.82,
}


def _load_demo_snapshot_from_built_ui() -> dict | None:
    ui_path = ROOT / f"ui_{DEMO_DATE}.html"
    if not ui_path.is_file():
        return None
    text = ui_path.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="date-snapshots-payload" type="application/json">(.*?)</script>',
        text,
        flags=re.S,
    )
    if not match:
        return None
    snapshots = json.loads(match.group(1).replace("<\\/", "</"))
    return snapshots.get(DEMO_DATE)


@pytest.mark.skipif(
    not (ROOT / "route_2026-04-15.json").is_file(),
    reason="Demo route artefact missing",
)
def test_hero_metrics_match_pitch_notes_for_demo_date(tmp_path: Path) -> None:
    route_path = ROOT / "route_2026-04-15.json"
    scored_path = ROOT / "data/processed/scored_2026-04-15.csv"
    locs_path = ROOT / "data/external/locations.csv"
    readings_path = ROOT / "data/processed/cleaned_readings.csv"
    if not all(p.is_file() for p in (scored_path, locs_path, readings_path)):
        pytest.skip("processed pipeline CSVs missing for live snapshot")
    route_data = json.loads(route_path.read_text(encoding="utf-8"))
    bench_csv = ROOT / "benchmark_results.csv"
    out = build_ui(
        date=DEMO_DATE,
        readings_df=pd.read_csv(readings_path),
        scored_df=pd.read_csv(scored_path),
        locations_df=pd.read_csv(locs_path),
        route_data=route_data,
        output_path=tmp_path / "ui.html",
        benchmark_rows=pd.read_csv(bench_csv) if bench_csv.is_file() else None,
    )
    match = re.search(
        r'<script id="date-snapshots-payload" type="application/json">(.*?)</script>',
        out.read_text(encoding="utf-8"),
        flags=re.S,
    )
    assert match is not None
    snap = json.loads(match.group(1).replace("<\\/", "</"))[DEMO_DATE]

    metrics = hero.compute_hero_metrics(snap, status_quo_km=snap.get("status_quo_km"))

    assert metrics["today_overfull"] == PITCH_HERO["today_overfull"]
    assert metrics["in_tour_overfull"] == PITCH_HERO["in_tour_overfull"]
    assert abs(metrics["planned_km"] - PITCH_HERO["planned_km"]) < 0.01
    assert abs(metrics["status_quo_km"] - PITCH_HERO["status_quo_km"]) < 0.01
    assert metrics["vehicles"] == PITCH_HERO["vehicles"]
    assert abs(metrics["shift_hours"] - PITCH_HERO["shift_hours"]) < 0.01
    assert abs(metrics["tons"] - PITCH_HERO["tons"]) < 0.01


def test_dispatcher_hero_is_first_visible_dispatcher_content(tmp_path: Path) -> None:
  """Hero mount sits directly under the header, before location banner and KPI grid."""
  from tests.test_ui import (  # noqa: PLC0415 — shared fixtures
      _sample_locations,
      _sample_readings,
      _sample_route,
      _sample_scored,
  )

  out = build_ui(
      date=DEMO_DATE,
      readings_df=_sample_readings(),
      scored_df=_sample_scored(),
      locations_df=_sample_locations(),
      route_data=_sample_route(),
      output_path=tmp_path / "ui.html",
  )
  html = out.read_text(encoding="utf-8")
  header_end = html.index("</header>")
  hero_pos = html.index('id="dispatcher-hero-mount"')
  dispatcher_pos = html.index('id="role-dispatcher"')
  assert header_end < hero_pos < dispatcher_pos
  assert "Heute drohen" in html
  assert "Wir leeren, was voll wird" in html
  assert "hero-chain" in html