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

    # Strictly NO unbacked emptying dates
    for forbidden in ("Letzte Leerung", "last_emptying_date"):
        assert forbidden not in html

    # Documented calendar events, behavior grouping ('Combine'), and driver driving-order list
    for expected in (
        "Weihnachten",
        "Nachweihnachtsspitze",
        "Osterferien",
        "Sommerferien",
        "Heilbronner Weindorf",
        "Gleiches Verhalten",
        "Hochlast",
        "Mittellast",
        "Niedriglast",
        "Selten gemessen",
        "Stoppliste für den Fahrer (in Fahrreihenfolge",
        'id="download-stops-csv-btn"',
        'id="print-route-stops-btn"',
        'id="driver-download-stops-csv-btn"',
    ):
        assert expected in html


def test_build_ui_driver_has_gpx_maps_legs_and_qr(tmp_path: Path) -> None:
    import json as _json
    from bs4 import BeautifulSoup

    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui_exports.html",
    )
    html = out.read_text(encoding="utf-8")

    # UI controls exist.
    assert 'id="driver-download-gpx-btn"' in html
    assert "GPX herunterladen" in html
    assert 'id="driver-maps-legs"' in html
    assert 'id="driver-qr-code"' in html
    assert "QR-Code" in html

    # Snapshot payload carries GPX and per-vehicle Maps legs.
    match = __import__("re").search(
        r'<script id="date-snapshots-payload" type="application/json">(.*?)</script>',
        html,
        flags=__import__("re").S,
    )
    assert match is not None
    snapshots = _json.loads(match.group(1).replace("<\\/", "</"))
    snap = snapshots["2026-04-15"]
    assert "gpx_xml" in snap
    assert "<gpx" in snap["gpx_xml"] and "</gpx>" in snap["gpx_xml"]
    assert "Start Betriebshof" in snap["gpx_xml"]
    assert "maps_legs" in snap
    assert isinstance(snap["maps_legs"], dict)
    assert any(snap["maps_legs"].get(v) for v in snap["maps_legs"])
    first_leg = next(u for urls in snap["maps_legs"].values() for u in urls)
    assert first_leg.startswith("https://www.google.com/maps/dir/?api=1")
    assert "origin=" in first_leg and "destination=" in first_leg

    # Driver panel stays free of charts/images and keeps the offline QR script inline.
    soup = BeautifulSoup(html, "html.parser")
    driver = soup.find(id="role-driver")
    assert driver is not None
    assert driver.find("iframe") is None
    assert driver.find("canvas") is None


def test_build_ui_role_start_screen_supports_approval_and_round_trip_export(tmp_path: Path) -> None:
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui.html",
    )
    html = out.read_text(encoding="utf-8")
    for role in ("Fahrer", "Disponentin", "Analyse"):
        assert role in html
    assert 'id="start-screen"' in html
    assert 'id="role-driver"' in html
    assert 'id="role-dispatcher"' in html
    assert 'id="role-approve-route-btn"' in html
    assert 'id="export-tour-btn"' in html
    assert "fill_level_perc" in html and "fill_level_numeric" in html
    assert "is_overfull" in html
    assert "glasroute-approved-" in html
    assert "window.print()" in html


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


def test_build_ui_has_location_planning_tab(tmp_path: Path) -> None:
    route = dict(_sample_route())
    route["assumptions"] = {
        "density_kg_per_m3": 400.0,
        "container_volume_m3": 2.5,
        "vehicle_max_weight_kg": 11000.0,
        "vehicle_max_volume_m3": 26.0,
        "road_detour_factor": 1.35,
        "avg_speed_kmh": 25.0,
        "yard_depot": [49.1427, 9.2109],
        "disposal_depot": [49.178, 9.2085],
        "max_shift_hours": 8.0,
        "stop_setup_min": 2.0,
        "lift_time_per_bin_min": 3.0,
        "unload_time_min": 20.0,
        "location_planning_radius_m": 500.0,
        "location_planning_adoption_weeks": 8.0,
        "location_planning_logistic_steepness": 1.0,
    }
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=route,
        output_path=tmp_path / "ui.html",
    )
    html = out.read_text(encoding="utf-8")
    assert 'data-target="view-location-planning"' in html
    assert 'id="view-location-planning"' in html
    assert "Standortplanung" in html
    assert "simulierten Koordinaten" in html
    assert "Adoptions-Timeline" in html


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

    # 1. Copilot gets its own tab (view-copilot), while view-route stays focused on KPIs, approval, map & stops.
    assert 'data-target="view-copilot"' in html_text
    route_start = html_text.index('id="view-route"')
    copilot_start = html_text.index('id="view-copilot"')
    copilot_end = html_text.index('id="view-variables"', copilot_start)
    assert route_start < copilot_start < copilot_end
    route_html = html_text[route_start:copilot_start]
    copilot_html = html_text[copilot_start:copilot_end]

    assert 'id="copilot-overview-box"' not in route_html
    assert 'class="whatif-box"' not in route_html
    assert 'id="copilot-ask-box"' not in route_html
    assert 'id="route-map-frame"' in route_html
    kpi_pos = route_html.index('class="kpi-grid"')
    approve_pos = route_html.index('id="approve-route-btn"')
    map_pos = route_html.index('id="route-map-frame"')
    assert kpi_pos < approve_pos < map_pos

    overview_pos = copilot_html.index('id="copilot-overview-box"')
    whatif_pos = copilot_html.index('class="whatif-box"')
    ask_pos = copilot_html.index('id="copilot-ask-box"')
    explain_box_pos = copilot_html.index('id="copilot-explain-panel"')
    assert overview_pos < whatif_pos < ask_pos < explain_box_pos
    assert 'id="copilot-container-select"' in copilot_html
    assert 'id="copilot-overview-text"' in copilot_html
    assert "Stopps geplant:" in copilot_html

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


def test_build_ui_has_variables_tab_for_spec_3_and_4(tmp_path: Path) -> None:
    from prezero.routing import OperationalConfig

    route = dict(_sample_route())
    route["assumptions"] = OperationalConfig(density_green_kg_per_m3=450.0).to_dict()
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=route,
        output_path=tmp_path / "ui.html",
    )
    html = out.read_text(encoding="utf-8")
    assert 'id="view-variables"' in html
    for needle in ("vehicle_max_volume_m3", "road_detour_factor", "max_shift_hours", "disposal_depot", "yard_depot"):
        assert needle in html
    assert "grün 450" in html and "weiß 400" in html
    assert "Flotteneinsatz" in html


def test_ui_visible_text_no_technical_leakage(tmp_path: Path) -> None:
    """Audit test against Nielsen heuristic #2: No UUID, snake_case, True/False, or raw English enums in visible text."""
    from bs4 import BeautifulSoup
    import re

    readings = _sample_readings().copy()
    scored = _sample_scored().copy()
    locs = _sample_locations().copy()
    route = dict(_sample_route())

    uuid_loc = "b3ebe810-724a-454e-83c5-68467048b3ec"
    route["stops"] = [
        {
            "order": 1,
            "stop_type": "collection",
            "Location_id": uuid_loc,
            "lat": 49.1339,
            "lon": 9.2111,
            "primary_material": "white",
            "est_fill_level": 90.0,
            "last_fill_level": 100.0,
            "score": 0.8333,
            "source": "osm_assigned",
            "confidence": "simulated_mapping",
            "leg_km": 1.318,
            "cumulative_km": 1.318,
        },
        {
            "order": 2,
            "stop_type": "unload",
            "Location_id": "disposal_depot",
            "lat": 49.178,
            "lon": 9.2085,
            "primary_material": "unload",
            "est_fill_level": 0.0,
            "last_fill_level": 0.0,
            "score": 0.0,
            "source": "config",
            "confidence": "high",
            "leg_km": 7.874,
            "cumulative_km": 9.192,
        },
    ]

    out = build_ui(
        date="2026-04-15",
        readings_df=readings,
        scored_df=scored,
        locations_df=locs,
        route_data=route,
        output_path=tmp_path / "ui_audit.html",
    )
    assert out.is_file()

    soup = BeautifulSoup(out.read_text(encoding="utf-8"), "html.parser")
    for tag in soup(["script", "style", "svg"]):
        tag.decompose()

    # 1. Driver & Dispatcher tour: no raw or shortened UUID, no disposal_depot, no English color enum, no True/False
    driver_panel = soup.find(id="role-driver")
    assert driver_panel is not None
    driver_text = driver_panel.get_text()
    assert re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", driver_text) is None
    assert re.search(r"\b[0-9a-f]{8}\.{3}", driver_text) is None
    assert "disposal_depot" not in driver_text
    assert "Wertstoffhof" not in driver_text
    assert "white" not in driver_text.split()
    assert "True" not in driver_text.split()
    assert "False" not in driver_text.split()
    assert "Weißglas" in driver_text
    assert "Standort #1" in driver_text

    # 2. Route view (view-route) table
    route_panel = soup.find(id="view-route")
    assert route_panel is not None
    route_table = route_panel.find("table")
    assert route_table is not None
    table_text = route_table.get_text()
    assert re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", table_text) is None
    assert re.search(r"\b[0-9a-f]{8}\.{3}", table_text) is None
    assert "disposal_depot" not in table_text
    assert "Wertstoffhof" not in table_text
    assert "collection" not in table_text.split()
    assert "Leerung" in table_text
    assert "Entladung" in table_text
    assert "white" not in table_text.split()
    assert "Weißglas" in table_text
    assert "osm_assigned" not in table_text
    assert "simulated_mapping" not in table_text
    assert "OSM-Standort" in table_text
    assert "simulierte Zuordnung" in table_text
    assert "0.8333" not in table_text
    assert "0,83" in table_text
    assert "Standort #1" in table_text

    # 3. Copilot view
    copilot_panel = soup.find(id="view-copilot")
    assert copilot_panel is not None
    copilot_text = copilot_panel.get_text()
    assert "--no-llm" not in copilot_text
    assert "explain_container" not in copilot_text
    assert "max_shift_hours=" not in copilot_text
    assert "vehicle_max_weight_kg=" not in copilot_text
    assert "max_stops=" not in copilot_text
    assert "b3ebe810" not in copilot_text
    assert re.search(r"\b[0-9a-f]{8}\.{3}", copilot_text) is None
    assert "Wertstoffhof" not in copilot_text

    # Check dropdown options and question buttons
    copilot_select = soup.find(id="copilot-container-select")
    if copilot_select:
        for opt in copilot_select.find_all("option"):
            opt_text = opt.get_text()
            assert re.search(r"\b[0-9a-f]{8}\.{3}", opt_text) is None
            assert "Standort" in opt_text or "Häufig" in opt_text

    # Check ask buttons & placeholder
    ask_input = soup.find(id="copilot-ask-input")
    if ask_input:
        placeholder = ask_input.get("placeholder", "")
        assert "b3ebe810" not in placeholder
        assert re.search(r"\b[0-9a-f]{8}\b", placeholder) is None

    # 4. Datacheck view
    datacheck_panel = soup.find(id="view-datacheck")
    assert datacheck_panel is not None
    datacheck_text = datacheck_panel.get_text()
    assert "Overfull" not in datacheck_text
    assert "Überfüllt" in datacheck_text

    # 5. No raw boolean literals across visible text, no Wertstoffhof, no bestätigt (except unbestätigt)
    all_text = soup.get_text()
    words = set(all_text.split())
    assert "True" not in words
    assert "False" not in words
    assert "Wertstoffhof" not in all_text
    assert re.search(r"\bbestätigt\b", all_text) is None
    assert "angenommen" in all_text


def test_compute_measurement_analysis_includes_behavior_groups() -> None:
    from prezero.ui import compute_measurement_analysis

    analysis = compute_measurement_analysis(_sample_readings())
    assert analysis["container_count"] > 0
    assert "behavior_groups" in analysis
    assert "behavior_points" in analysis
    assert len(analysis["behavior_groups"]) == 4
    assert [g["group"] for g in analysis["behavior_groups"]] == [
        "Hochlast",
        "Mittellast",
        "Niedriglast",
        "Selten gemessen",
    ]
    assert sum(g["container_count"] for g in analysis["behavior_groups"]) == analysis["container_count"]
    assert len(analysis["behavior_points"]) == analysis["container_count"]


def test_build_ui_shows_timer_and_backtest(tmp_path: Path) -> None:
    import json as _json

    route = dict(_sample_route())
    route["stops"] = [dict(s) for s in route["stops"]]
    for s in route["stops"]:
        if s.get("stop_type", "collection") == "collection":
            s["days_until_due"] = -9
            s["due_date"] = "2026-04-06"
    summary = _json.loads(
        """{"predicted_visits": 10, "methods": {"model": "Timer-Modell", "mean_past": "Durchschnitt bisher"},
        "overall": {"model": {"mae_pp": 19.9, "within_20pp_pct": 63.7, "full_precision_pct": 75.0, "full_recall_pct": 59.4},
                    "mean_past": {"mae_pp": 22.3, "within_20pp_pct": 55.5, "full_precision_pct": 64.9, "full_recall_pct": 60.8}},
        "rhythm": {"visits": 100, "found_below_50_pct": 30.1, "found_overfull_pct": 11.2,
                   "by_material": {"brown": {"ideal_days_median": 95.4, "actual_days_median": 42.0, "too_often_pct": 89.1, "too_rarely_pct": 2.1}}}}"""
    )
    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=route,
        output_path=tmp_path / "ui.html",
        backtest_summary=summary,
    )
    html = out.read_text(encoding="utf-8")
    assert "überfällig seit 9 d (2026-04-06)" in html
    assert "Ist der Füllstand vorhersagbar?" in html and "19,9 pp" in html
    assert "Braunglas" in html and "95 Tage" in html and "89,1 %" in html
    assert "Saisonfaktor)" not in html


def test_ui_plan_documents_today_first_user_stories() -> None:
    plan_path = Path(__file__).resolve().parents[1] / "docs" / "UI_PLAN.md"
    assert plan_path.exists()
    content = plan_path.read_text(encoding="utf-8")
    for token in ("Disponentin", "Fahrer", "Analyse / Management", "Stand DD.MM.YYYY", "KW+1", "KW+3", "+ 21 Tage"):
        assert token in content, f"missing {token} in docs/UI_PLAN.md"


def test_ui_today_first_date_picker_stand_labels_and_snapshots(tmp_path: Path) -> None:
    import json as _json
    from bs4 import BeautifulSoup

    out = build_ui(
        date=None,
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=_sample_route(),
        output_path=tmp_path / "ui_auto.html",
    )
    html_text = out.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_text, "html.parser")

    # Default resolves to last data day of _sample_readings() -> 2026-04-12
    assert soup.find(id="header-date-iso").get_text(strip=True) == "2026-04-12"
    stand_badge = soup.find(id="current-stand-badge")
    assert stand_badge is not None and stand_badge.get_text(strip=True) == "Stand 12.04.2026"

    picker = soup.find(id="global-date-picker")
    assert picker is not None
    selected_opt = picker.find("option", selected=True)
    assert selected_opt is not None and selected_opt.get("value") == "2026-04-12"
    assert "Letzter Datentag" in selected_opt.get_text()
    assert len(picker.find_all("option")) >= 3

    snapshots = _json.loads(soup.find(id="date-snapshots-payload").string)
    assert "2026-04-12" in snapshots
    snap = snapshots["2026-04-12"]
    assert snap["stand_de"] == "Stand 12.04.2026"
    assert [h["title"] for h in snap["horizons"]] == ["Heute (+0 Tage)", "KW+1 (+7 Tage)", "KW+2 (+14 Tage)", "KW+3 (+21 Tage)"]
    assert len(snap["variants"]) >= 1

    # Landing view is Disponentin; Analyse workspace starts hidden
    dispatcher = soup.find(id="role-dispatcher")
    driver = soup.find(id="role-driver")
    assert dispatcher is not None and "active" in (dispatcher.get("class") or [])
    assert driver is not None and "active" not in (driver.get("class") or [])
    analysis_nav = soup.find("nav", class_="analysis-workspace")
    assert analysis_nav is not None and "active" not in (analysis_nav.get("class") or [])

    # Disponentin has 3-week horizon cards (no KW+4), Today/+7 tables, variant modifier and approval button
    horizon_text = soup.find(id="dispatcher-horizon-3w").get_text()
    assert "KW+1" in horizon_text and "KW+2" in horizon_text and "KW+3" in horizon_text
    assert "KW+4" not in horizon_text
    assert soup.find(id="dispatcher-today-full-table") is not None
    assert soup.find(id="dispatcher-week-full-table") is not None
    assert soup.find(id="dispatcher-tour-variant-select") is not None
    assert soup.find(id="role-approve-route-btn") is not None


def test_dispatcher_and_driver_views_have_no_data_outside_0_to_21_days(tmp_path: Path) -> None:
    import re
    from datetime import date as _date, timedelta
    from bs4 import BeautifulSoup

    base = _date.fromisoformat("2026-04-15")
    horizon_max = base + timedelta(days=21)

    route = dict(_sample_route())
    route["stops"] = [dict(s) for s in route["stops"]]
    # Inject an overdue past due_date and a far-future >21d due_date to ensure both are masked in operational views
    for idx, s in enumerate(route["stops"]):
        if s.get("stop_type", "collection") == "collection":
            if idx == 0:
                s["days_until_due"] = -14
                s["due_date"] = "2026-04-01"
            else:
                s["days_until_due"] = 45
                s["due_date"] = "2026-05-30"

    out = build_ui(
        date="2026-04-15",
        readings_df=_sample_readings(),
        scored_df=_sample_scored(),
        locations_df=_sample_locations(),
        route_data=route,
        output_path=tmp_path / "ui_window.html",
    )
    soup = BeautifulSoup(out.read_text(encoding="utf-8"), "html.parser")

    for section_id in ("role-dispatcher", "role-driver"):
        section = soup.find(id=section_id)
        assert section is not None
        for tag in section.find_all(["script", "style", "svg"]):
            tag.decompose()
        visible = section.get_text(" ", strip=True)
        assert "Stand 15.04.2026" in visible
        for iso in re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", visible):
            parsed = _date.fromisoformat(iso)
            assert base <= parsed <= horizon_max, f"{section_id} leaked out-of-window ISO date {iso}"
        for de_str in re.findall(r"\b(\d{2}\.\d{2}\.\d{4})\b", visible):
            day, mon, yr = map(int, de_str.split("."))
            parsed = _date(yr, mon, day)
            assert base <= parsed <= horizon_max, f"{section_id} leaked out-of-window DE date {de_str}"

    # Driver view must contain no charts and no historical tables
    driver = soup.find(id="role-driver")
    assert driver.find("iframe") is None
    assert driver.find("svg") is None
    assert driver.find("img") is None
    assert driver.find("canvas") is None
    assert not driver.find_all(class_="js-plotly-plot")
    assert "Weihnachten" not in driver.get_text()
    assert "Saisonalität" not in driver.get_text()

