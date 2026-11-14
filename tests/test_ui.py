"""Tests for the 4-view local web UI built strictly from verifiable data."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
import pandas as pd
import pytest

from prezero import viz
from prezero.cli import cli
from prezero.ui import (
    build_ui,
    compute_data_check,
    compute_upload_check,
    render_forecast_timeline_map_html,
)


def _sample_readings() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L1", "L2", "L2", "L2", "L3"],
            "material_type": ["white", "white", "white", "green", "green", "green", "brown"],
            "date": [
                "2026-01-01",
                "2026-01-06",
                "2026-04-12",  # > 90-day gap and > 50 pp jump
                "2026-04-01",
                "2026-04-06",
                "2026-04-11",
                "2026-04-06",
            ],
            "fill_level_perc": ["10", "20", "90", "30", "45", "60", "overfull"],
            "fill_level_numeric": [10.0, 20.0, 90.0, 30.0, 45.0, 60.0, 110.0],
            "is_overfull": [False, False, False, False, False, False, True],
        }
    )


def _sample_scored() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3"],
            "material_type": ["white", "green", "brown"],
            "last_date": ["2026-04-12", "2026-04-11", "2026-04-06"],
            "last_fill_level": [90.0, 60.0, 110.0],
            "days_since_last": [3, 4, 9],
            "overfull_rate": [0.0, 0.0, 1.0],
            "avg_daily_increase": [2.0, 3.0, 0.0],
            "season_factor": [1.0, 1.0, 1.0],
            "reading_count": [3, 3, 1],
            "score": [0.85, 0.55, 0.92],
            "critical": [True, False, True],
        }
    )


def _sample_locations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3"],
            "lat": [49.14, 49.15, 49.16],
            "lon": [9.21, 9.22, 9.23],
            "source": ["osm_assigned", "synthetic_placeholder", "osm_assigned"],
            "confidence": ["simulated_mapping", "synthetic", "simulated_mapping"],
        }
    )


def _sample_route() -> dict:
    return {
        "date": "2026-04-15",
        "depot": {"lat": 49.1427, "lon": 9.2109},
        "num_stops": 2,
        "total_critical_locations": 2,
        "total_active_locations": 3,
        "vehicles_needed": 1,
        "rounds": 1,
        "shift_hours": 1.25,
        "t_collected": 2.0,
        "planned_km": 4.2,
        "full_round_km": 7.5,
        "saved_km": 3.3,
        "saved_pct": 44.0,
        "comparison": "4.2 km planned (2 stops) vs. 7.5 km full round (3 stops)",
        "stops": [
            {
                "order": 1,
                "stop_type": "collection",
                "Location_id": "L1",
                "lat": 49.14,
                "lon": 9.21,
                "score": 0.85,
                "primary_material": "white",
                "last_fill_level": 90.0,
                "source": "osm_assigned",
                "confidence": "simulated_mapping",
                "leg_km": 1.2,
                "cumulative_km": 1.2,
            },
            {
                "order": 2,
                "stop_type": "collection",
                "Location_id": "L3",
                "lat": 49.16,
                "lon": 9.23,
                "score": 0.92,
                "primary_material": "brown",
                "last_fill_level": 110.0,
                "source": "osm_assigned",
                "confidence": "simulated_mapping",
                "leg_km": 1.8,
                "cumulative_km": 3.0,
            },
        ],
    }


def test_compute_upload_check_matches_dataframe() -> None:
    df = _sample_readings()
    check = compute_upload_check(df)
    assert check["row_count"] == 7
    assert check["container_count"] == 3
    assert check["series_count"] == 3
    assert check["date_min"] == "2026-01-01"
    assert check["date_max"] == "2026-04-12"
    assert check["measurement_days"] == 6
    assert check["missing_values"] == 0
    assert check["overfull_count"] == 1


def test_compute_data_check_returns_exact_computed_metrics() -> None:
    df = _sample_readings()
    check = compute_data_check(df)
    assert check["total_series"] == 3
    assert check["evaluable_series"] == 2
    assert check["total_transitions"] == 4
    assert check["jumps_gt_50_total"] == 1
    assert check["jumps_gt_50_pct"] == pytest.approx(25.0)
    assert check["series_with_gap_gt_90d"] == 1
    assert check["overfull_total"] == 1

    for row in check["series"]:
        if row["regularity_score"] is not None:
            assert 0.0 <= row["regularity_score"] <= 1.0

    by_id = {row["Location_id"]: row for row in check["series"]}
    # L2 has constant +3.0 pp/day intervals -> regularity_score == 1.0
    assert by_id["L2"]["regularity_score"] == pytest.approx(1.0)
    assert by_id["L1"]["jumps_gt_50"] == 1
    assert by_id["L1"]["gaps_gt_90d"] == 1

    mat_means = {row["material_type"]: row["mean_fill_pct"] for row in check["material_summary"]}
    assert mat_means["white"] == pytest.approx(40.0)
    assert mat_means["green"] == pytest.approx(45.0)
    assert mat_means["brown"] == pytest.approx(110.0)


def test_forecast_timeline_map_has_no_route_polyline() -> None:
    map_html, summaries = render_forecast_timeline_map_html(
        _sample_scored(), _sample_locations(), "2026-04-15"
    )
    assert len(summaries) == 4
    assert "forecast-week-selector" in map_html
    assert "L.polyline" not in map_html
    assert "Letzte Leerung" not in map_html
    assert "tile.openstreetmap.org" in map_html


def test_build_ui_has_all_four_views_and_no_unbacked_claims(tmp_path: Path) -> None:
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui_2026-04-15.html",
    )
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert "tile.openstreetmap.org" in html

    # All 4 views present (ordered Forecast -> Route -> Datacheck -> Upload)
    for view_id in ("view-forecast", "view-route", "view-datacheck", "view-upload"):
        assert f'id="{view_id}"' in html

    # Forecast timeline horizons
    for label in ("Heute", "+7 Tage", "+14 Tage", "+21 Tage"):
        assert label in html

    # Separate route view with Freigeben action and verifiable route numbers
    assert 'id="approve-route-btn"' in html
    assert "Freigeben" in html
    assert "4.2 km" in html
    assert "44.0 %" in html

    # Datacheck & Upload computed metrics
    assert "Regularity Score" in html
    assert 'id="csv-dropzone"' in html
    assert "2026-01-01 bis 2026-04-12" in html

    # Re-exported cleanly from prezero.viz
    assert viz.build_ui is build_ui

    # Strictly NO unbacked events or emptying dates
    for forbidden in ("Weindorf", "Nachweihnachtsspitze", "Letzte Leerung", "last_emptying_date"):
        assert forbidden not in html


def test_cli_ui_command_generates_html(tmp_path: Path) -> None:
    readings_path = tmp_path / "cleaned.csv"
    locs_path = tmp_path / "locations.csv"
    scored_path = tmp_path / "scored.csv"
    route_path = tmp_path / "route.json"
    out_dir = tmp_path / "out"

    _sample_readings().to_csv(readings_path, index=False)
    _sample_locations().to_csv(locs_path, index=False)
    _sample_scored().to_csv(scored_path, index=False)
    route_path.write_text(json.dumps(_sample_route()), encoding="utf-8")

    runner = CliRunner()
    res = runner.invoke(
        cli,
        [
            "ui",
            "--date",
            "2026-04-15",
            "--readings",
            str(readings_path),
            "--scored",
            str(scored_path),
            "--locations",
            str(locs_path),
            "--route",
            str(route_path),
            "--output-dir",
            str(out_dir),
        ],
    )
    assert res.exit_code == 0, res.output
    assert (out_dir / "ui_2026-04-15.html").is_file()


def test_build_ui_heatmap_tab_jumps_to_route_map(tmp_path: Path) -> None:
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui.html",
        heatmap_src="heatmap.html",
    )
    html = out.read_text(encoding="utf-8")
    assert 'id="view-heatmap"' in html
    assert 'id="heatmap-frame"' in html
    assert 'src="heatmap.html"' in html
    # Click wiring: heatmap message -> route tab -> focus marker in the route map.
    assert 'id="route-map-frame"' in html
    assert '"heatmap-select"' in html
    assert 'activateTab("view-route")' in html
    assert "focus-container" in html


def test_build_ui_without_heatmap_shows_hint(tmp_path: Path) -> None:
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui.html",
    )
    assert "Keine Heatmap erzeugt" in out.read_text(encoding="utf-8")


def _benchmark_rows() -> list[dict]:
    rows = []
    for date in ("2026-04-15", "2026-07-15"):
        for seed in (7, 42):
            for variant, km in (
                ("B0 status quo", 200.0),
                ("B1 status quo optimized", 150.0),
                ("B2 demand-driven NN", 100.0),
                ("B3 demand-driven + 2-opt", 92.0),
                ("B4 demand-driven + solver", 90.0),
            ):
                rows.append({"variant": variant, "date": date, "seed": seed, "km": km,
                             "stops": 10, "h": 5.0, "rounds": 2, "vehicles": 2, "t": 8.0})
    return rows


def test_benchmark_summary_splits_routing_and_demand_effect() -> None:
    from prezero.ui import compute_benchmark_summary

    s = compute_benchmark_summary(_benchmark_rows(), "2026-04-15", 42)
    assert s is not None
    assert s["effects"]["demand_pct"] == 33.3  # 150 -> 100
    assert s["effects"]["routing_pct"] == 10.0  # 100 -> best 90
    assert s["effects"]["overall_vs_b1_pct"] == 40.0  # 150 -> 90
    assert s["effects"]["overall_vs_b0_pct"] == 55.0  # 200 -> 90
    assert [v["code"] for v in s["variants"]] == ["B0", "B1", "B2", "B4"]
    assert s["cases"] == 4


def test_build_ui_has_benchmark_tab(tmp_path: Path) -> None:
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui.html",
        benchmark_rows=_benchmark_rows(),
    )
    html = out.read_text(encoding="utf-8")
    assert 'id="view-benchmark"' in html
    assert "Routing-Effekt" in html and "Bedarfs-Effekt" in html
    assert "33.3 %" in html and "10.0 %" in html


def test_build_ui_has_what_if_and_explain_hooks(tmp_path: Path) -> None:
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui.html",
    )
    html = out.read_text(encoding="utf-8")
    assert 'id="insights-payload"' in html
    assert 'id="explain-panel"' in html
    assert "Fahrzeugstunden gesamt" in html
    assert "· Schicht:" not in html  # old misleading label (sum shown as one shift)


def test_build_ui_inline_scripts_are_valid_js(tmp_path: Path) -> None:
    """Guard against Python-escaping bugs that break the whole page script."""
    import re
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        import pytest

        pytest.skip("node not installed")
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui.html",
    )
    html = out.read_text(encoding="utf-8")
    outer = html.split("</iframe>")[-1]  # skip srcdoc maps, check the page's own scripts
    for i, body in enumerate(re.findall(r"<script>(.*?)</script>", outer, flags=re.S)):
        js = tmp_path / f"s{i}.js"
        js.write_text(body, encoding="utf-8")
        res = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr


def test_build_ui_labels_units_and_simulated_mapping(tmp_path: Path) -> None:
    locs = _sample_locations().copy()
    locs["confidence"] = "simulated_mapping"
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=locs,
        route_data=_sample_route(),
        output_path=tmp_path / "ui.html",
    )
    html = out.read_text(encoding="utf-8")
    assert "Ortsdaten erfunden, nicht von PreZero" in html
    assert "kritische Container" in html
    assert "kritischen Standorten in dieser Tour" in html


def test_benchmark_summary_marks_nn_fallback() -> None:
    from prezero.ui import _build_benchmark_section_html, compute_benchmark_summary

    rows = _benchmark_rows()
    for r in rows:
        r["nn_kept"] = r["variant"].startswith("B4") and r["seed"] == 42 and r["date"] == "2026-04-15"
    s = compute_benchmark_summary(rows, "2026-04-15", 42)
    assert s is not None
    assert s["nn_kept_counts"]["B4"] == 1
    assert next(v for v in s["variants"] if v["code"] == "B4")["nn_kept"] is True
    html = _build_benchmark_section_html(s)
    assert "NN-Reihenfolge behalten" in html
    assert "in 1 von 4 Fällen" in html


def test_ui_copilot_overview_explain_whatif_ask_and_shift_limit(tmp_path: Path) -> None:
    import re
    import shutil
    import subprocess

    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui.html",
    )
    html_text = out.read_text(encoding="utf-8")

    # 1. Overview box appears at the top of the route tab (before KPI cards & approval box).
    route_start = html_text.index('id="view-route"')
    overview_pos = html_text.index('id="copilot-overview-box"', route_start)
    kpi_pos = html_text.index('class="kpi-grid"', route_start)
    approve_pos = html_text.index('id="approve-route-btn"', route_start)
    assert overview_pos < kpi_pos < approve_pos
    assert 'id="copilot-overview-text"' in html_text
    assert "Stopps geplant:" in html_text

    # 2. Parse precomputed insights payload.
    payload_match = re.search(
        r'<script id="insights-payload" type="application/json">(.*?)</script>',
        html_text,
        flags=re.S,
    )
    assert payload_match is not None
    insights = json.loads(payload_match.group(1).replace("<\\/", "</"))
    assert "Stopps geplant:" in insights["overview_text"]
    assert "Quellen:" in insights["overview_text"]

    # Explain for every (Location_id, material) in scored data, Top-20 rows, stop rows, and map clicks.
    container_explains = insights["container_explains"]
    for key in ("L1:white", "L2:green", "L3:brown"):
        assert key in container_explains
        assert key in container_explains[key]["formatted"]
        assert "Quellen:" in container_explains[key]["formatted"]
    assert 'class="top20-row" data-loc="L1" data-mat="white"' in html_text
    assert 'id="top20-explain-panel"' in html_text
    assert 'data-loc="L1" data-mat="white"' in html_text
    assert "copilot-explain" in html_text  # inside #route-map-frame srcdoc & outer script

    # 3. What-if presets (shift_6h, truck_8t, plus_vehicle, stops_20, all_critical) and shift limit guard.
    presets = insights["presets"]
    assert [p["id"] for p in presets] == [
        "shift_6h",
        "truck_8t",
        "plus_vehicle",
        "stops_20",
        "all_critical",
    ]
    for idx, preset in enumerate(presets):
        assert f'data-preset="{idx}"' in html_text
        base = preset["baseline"]
        sim = preset["simulation"]
        assert base["max_vehicle_shift_hours"] <= base["max_shift_hours_limit"] + 1e-9
        assert sim["max_vehicle_shift_hours"] <= sim["max_shift_hours_limit"] + 1e-9
        assert sim["num_stops"] >= 1

    # 4. Ask box with input + 5 fixed precomputed (--no-llm) questions, no live server calls.
    assert 'id="copilot-ask-input"' in html_text
    assert 'id="copilot-ask-datalist"' in html_text
    assert 'id="copilot-ask-output"' in html_text
    ask_examples = insights["ask_examples"]
    assert len(ask_examples) == 5
    for idx, example in enumerate(ask_examples):
        assert f'data-ask-idx="{idx}"' in html_text
        assert example["mode"] == "deterministic_fallback"
        assert example["answer"].strip()
        assert "Quellen:" in example["answer"]
    outer = html_text.split("</iframe>")[-1]
    assert "fetch(" not in outer
    assert "11434" not in outer

    # 5. Approval controls remain intact in view-route.
    assert 'id="dispatcher-name-input"' in html_text
    assert 'id="approve-route-btn"' in html_text
    assert 'id="approval-status-badge"' in html_text
    assert 'id="approval-record-preview"' in html_text

    # 6. Verify both map iframe script and main page script parse cleanly in Node (when available).
    node = shutil.which("node")
    if node is not None:
        import html as html_lib

        srcdoc_match = re.search(r'id="route-map-frame"[^>]*srcdoc="(.*?)"', html_text, flags=re.S)
        assert srcdoc_match is not None
        route_map_doc = html_lib.unescape(srcdoc_match.group(1))
        for idx, script_body in enumerate(re.findall(r"<script[^>]*>(.*?)</script>", route_map_doc, flags=re.S)):
            if not script_body.strip():
                continue
            js_file = tmp_path / f"map_{idx}.js"
            js_file.write_text(script_body, encoding="utf-8")
            check = subprocess.run([node, "--check", str(js_file)], capture_output=True, text=True)
            assert check.returncode == 0, check.stderr


def test_build_ui_explains_measure_and_empty(tmp_path: Path) -> None:
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui.html",
    )
    html = out.read_text(encoding="utf-8")
    assert "schätzt den Füllstand und leert" in html
    assert "Füllstand jetzt (geschätzt)" in html
    assert "last_fill_level + avg_daily_increase" not in html  # old continuous-sensor formula
