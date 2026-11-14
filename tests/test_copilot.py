"""Tests for the deterministic GlasRoute Copilot MVP and optional Ollama adapter."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from click.testing import CliRunner
import pandas as pd
import pytest

from prezero import routing, scoring
from prezero.cli import cli
from prezero.copilot import (
    ALLOWED_TOOLS,
    WHAT_IF_ALLOWLIST,
    CopilotLookupError,
    CopilotValidationError,
    ask_copilot,
    dispatch_tool_call,
    explain_container,
    format_copilot_output,
    get_tour_overview,
    simulate_what_if,
)


def _stage_copilot_inputs(tmp_path: Path) -> dict[str, Path]:
    """Create deterministic multi-container test inputs (including multi-material L1)."""
    readings_path = tmp_path / "cleaned_readings.csv"
    scored_path = tmp_path / "scored_2026-04-15.csv"
    locations_path = tmp_path / "locations.csv"
    route_path = tmp_path / "route_2026-04-15.json"

    readings_df = pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L1", "L1", "L2", "L3", "L3", "L4"],
            "material_type": ["white", "white", "brown", "brown", "green", "white", "white", "brown"],
            "date": [
                "2026-03-01",
                "2026-04-10",
                "2026-03-01",
                "2026-04-10",
                "2026-04-12",
                "2026-03-15",
                "2026-04-11",
                "2026-04-05",
            ],
            "fill_level_perc": ["100", "overfull", "20", "30", "overfull", "overfull", "95", "40"],
            "fill_level_numeric": [100.0, 110.0, 20.0, 30.0, 110.0, 110.0, 95.0, 40.0],
            "is_overfull": [False, True, False, False, True, True, False, False],
        }
    )
    readings_df.to_csv(readings_path, index=False)

    scored_df = pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3", "L1", "L4"],
            "material_type": ["white", "green", "white", "brown", "brown"],
            "last_date": ["2026-04-10", "2026-04-12", "2026-04-11", "2026-04-10", "2026-04-05"],
            "last_fill_level": [110.0, 110.0, 95.0, 30.0, 40.0],
            "days_since_last": [5, 3, 4, 5, 10],
            "overfull_rate": [0.5, 1.0, 0.5, 0.0, 0.0],
            "avg_daily_increase": [0.25, 0.0, 0.0, 0.25, 0.0],
            "season_factor": [1.0, 1.0, 1.0, 1.0, 1.0],
            "reading_count": [2, 1, 2, 2, 1],
        }
    )
    scored_df = scoring.score_containers(scored_df)
    scored_df.to_csv(scored_path, index=False)

    locations_df = pd.DataFrame(
        {
            "Location_id": ["L1", "L2", "L3", "L4"],
            "lat": [49.1450, 49.1550, 49.1700, 49.1900],
            "lon": [9.2120, 9.2220, 9.2400, 9.2550],
            "source": ["osm_assigned", "osm_assigned", "synthetic_placeholder", "osm_assigned"],
            "confidence": ["simulated_mapping", "simulated_mapping", "synthetic", "simulated_mapping"],
            "match_reason": ["osm test 1", "osm test 2", "synthetic seed 2026", "osm test 4"],
        }
    )
    locations_df.to_csv(locations_path, index=False)

    route_data = routing.build_route(
        scored_df,
        locations_df,
        depot=routing.DEFAULT_DEPOT,
        max_stops=25,
        date="2026-04-15",
        output_dir=tmp_path,
    )
    assert route_path.is_file()
    assert route_data["num_stops"] == 3

    return {
        "readings_path": readings_path,
        "scored_path": scored_path,
        "locations_path": locations_path,
        "route_path": route_path,
    }


def test_explain_container_requires_material_or_composite_key(tmp_path: Path) -> None:
    paths = _stage_copilot_inputs(tmp_path)
    with pytest.raises(CopilotValidationError) as exc_info:
        explain_container(
            "L1",
            date="2026-04-15",
            scored_path=paths["scored_path"],
            route_path=paths["route_path"],
            locations_path=paths["locations_path"],
        )
    msg = str(exc_info.value).lower()
    assert "material" in msg
    assert "white" in msg and "green" in msg and "brown" in msg


def test_explain_container_distinguishes_materials_at_same_location(tmp_path: Path) -> None:
    paths = _stage_copilot_inputs(tmp_path)

    white_res = explain_container(
        "L1",
        "white",
        "2026-04-15",
        scored_path=paths["scored_path"],
        route_path=paths["route_path"],
        locations_path=paths["locations_path"],
    )
    assert white_res["container_key"] == "L1:white"
    assert white_res["Location_id"] == "L1"
    assert white_res["material_type"] == "white"
    assert white_res["metrics"]["last_fill_level"] == pytest.approx(110.0)
    assert white_res["metrics"]["critical"] is True
    # Timer replaces the old weighted factors.
    sb = white_res["score_breakdown"]
    assert "Timer" in sb["formula"]
    assert sb["due_level_pct"] == pytest.approx(80.0)
    assert "status" in sb and "due_date" in sb and "est_fill_level" in sb
    assert white_res["in_planned_tour"] is True
    assert white_res["stop_order"] == 1
    assert len(white_res["site_containers"]) == 2
    assert {c["material_type"] for c in white_res["site_containers"]} == {"white", "brown"}
    assert white_res["location_provenance"]["source"] == "osm_assigned"
    assert white_res["location_provenance"]["confidence"] == "simulated_mapping"
    assert str(paths["scored_path"]) in white_res["sources"]

    # Composite key and German material alias resolve to the same authoritative record.
    alias_res = explain_container(
        container_key="L1:Weißglas",
        date="2026-04-15",
        scored_path=paths["scored_path"],
        route_path=paths["route_path"],
        locations_path=paths["locations_path"],
    )
    assert alias_res["container_key"] == "L1:white"
    assert alias_res["metrics"]["score"] == pytest.approx(white_res["metrics"]["score"])

    # Brown bin at the same location L1 is NOT critical and NOT collected on the tour.
    brown_res = explain_container(
        "L1",
        "brown",
        "2026-04-15",
        scored_path=paths["scored_path"],
        route_path=paths["route_path"],
        locations_path=paths["locations_path"],
    )
    assert brown_res["container_key"] == "L1:brown"
    assert brown_res["metrics"]["last_fill_level"] == pytest.approx(30.0)
    assert brown_res["metrics"]["critical"] is False
    assert brown_res["in_planned_tour"] is False
    assert brown_res["stop_order"] is None
    assert brown_res["metrics"]["score"] < white_res["metrics"]["score"]

    # Non-existent material at an existing location lists available materials.
    with pytest.raises(CopilotLookupError) as exc_info:
        explain_container(
            "L1",
            "green",
            "2026-04-15",
            scored_path=paths["scored_path"],
            route_path=paths["route_path"],
            locations_path=paths["locations_path"],
        )
    assert "white" in str(exc_info.value) and "brown" in str(exc_info.value)


def test_get_tour_overview_returns_authoritative_data_and_sources(tmp_path: Path) -> None:
    paths = _stage_copilot_inputs(tmp_path)
    route_payload = json.loads(paths["route_path"].read_text(encoding="utf-8"))

    overview = get_tour_overview(
        "2026-04-15",
        route_path=paths["route_path"],
        scored_path=paths["scored_path"],
        locations_path=paths["locations_path"],
    )
    assert overview["date"] == "2026-04-15"
    assert overview["num_stops"] == route_payload["num_stops"] == 3
    assert overview["total_critical_locations"] == 3
    assert overview["total_critical_pairs"] == 3
    assert overview["planned_km"] == pytest.approx(route_payload["planned_km"])
    assert overview["full_round_km"] == pytest.approx(route_payload["full_round_km"])
    assert overview["saved_km"] == pytest.approx(route_payload["saved_km"])
    assert overview["saved_pct"] == pytest.approx(route_payload["saved_pct"])
    assert overview["vehicles_needed"] == route_payload["vehicles_needed"]
    assert overview["rounds"] == route_payload["rounds"]
    assert overview["shift_hours"] == pytest.approx(route_payload["shift_hours"])
    assert overview["t_collected"] == pytest.approx(route_payload["t_collected"])
    assert len(overview["top_stops"]) == 3
    assert overview["top_stops"][0]["container_key"] == "L1:white"
    assert "approval.py" in overview["approval_hint"] or "approve" in overview["approval_hint"]
    assert str(paths["route_path"]) in overview["sources"]
    assert str(paths["scored_path"]) in overview["sources"]


def test_simulate_what_if_enforces_allowlist_and_bounds(tmp_path: Path) -> None:
    paths = _stage_copilot_inputs(tmp_path)

    for invalid_overrides in (
        {"hallucinated_param": 42},
        {"critical_threshold": 0.5},
        {"max_shift_hours": 0},
        {"max_shift_hours": 30.0},
        {"max_stops": -5},
        {"max_stops": 2.5},
        {"max_stops": True},
        {"vehicle_max_weight_kg": 100.0},
    ):
        with pytest.raises(CopilotValidationError):
            simulate_what_if(
                "2026-04-15",
                invalid_overrides,
                scored_path=paths["scored_path"],
                route_path=paths["route_path"],
                locations_path=paths["locations_path"],
            )

    assert "max_shift_hours" in WHAT_IF_ALLOWLIST
    assert "max_stops" in WHAT_IF_ALLOWLIST
    assert "vehicle_max_weight_kg" in WHAT_IF_ALLOWLIST


def test_simulate_what_if_compares_against_baseline_without_overwriting_route_file(
    tmp_path: Path,
) -> None:
    paths = _stage_copilot_inputs(tmp_path)
    before_bytes = paths["route_path"].read_bytes()

    sim = simulate_what_if(
        "2026-04-15",
        {"max_shift_hours": 0.25, "max_stops": 2},
        scored_path=paths["scored_path"],
        route_path=paths["route_path"],
        locations_path=paths["locations_path"],
    )

    assert paths["route_path"].read_bytes() == before_bytes
    assert sim["baseline"]["num_stops"] == 3
    assert sim["simulation"]["num_stops"] == 2
    assert sim["delta"]["num_stops_delta"] == -1
    assert sim["delta"]["unserved_critical_locations_delta"] == 1
    assert sim["delta"]["planned_km_delta"] == pytest.approx(
        round(sim["simulation"]["planned_km"] - sim["baseline"]["planned_km"], 2)
    )
    assert "vehicles_needed_delta" in sim["delta"]
    assert "shift_hours_delta" in sim["delta"]
    assert "t_collected_delta" in sim["delta"]
    assert sim["delta"]["added_stops"] == []
    assert sim["delta"]["dropped_stops"] == ["L3"]
    assert str(paths["route_path"]) in sim["sources"]
    assert str(paths["scored_path"]) in sim["sources"]


def test_approve_tour_is_forbidden_as_chat_tool(tmp_path: Path) -> None:
    assert ALLOWED_TOOLS == ("get_tour_overview", "explain_container", "simulate_what_if")

    for forbidden in ("approve_tour", "approve_route", "approve", "reject_route"):
        with pytest.raises(CopilotValidationError) as exc_info:
            dispatch_tool_call(forbidden, {"date": "2026-04-15"})
        assert "approval.py" in str(exc_info.value)


def test_format_copilot_output_includes_sources_and_baseline_comparison(tmp_path: Path) -> None:
    paths = _stage_copilot_inputs(tmp_path)

    overview = get_tour_overview(
        "2026-04-15",
        route_path=paths["route_path"],
        scored_path=paths["scored_path"],
        locations_path=paths["locations_path"],
    )
    overview_text = format_copilot_output(overview)
    assert "3" in overview_text
    assert "Freigabe" in overview_text
    assert "Quellen:" in overview_text

    explain = explain_container(
        "L1",
        "white",
        "2026-04-15",
        scored_path=paths["scored_path"],
        route_path=paths["route_path"],
        locations_path=paths["locations_path"],
    )
    explain_text = format_copilot_output(explain)
    assert "L1:white" in explain_text
    assert "110" in explain_text
    assert "Quellen:" in explain_text

    sim = simulate_what_if(
        "2026-04-15",
        {"max_stops": 2},
        scored_path=paths["scored_path"],
        route_path=paths["route_path"],
        locations_path=paths["locations_path"],
    )
    sim_text = format_copilot_output(sim)
    assert "Baseline" in sim_text
    assert "What-If" in sim_text
    assert "Delta" in sim_text
    assert "Freigabe" in sim_text
    assert "Quellen:" in sim_text


def test_ollama_adapter_uses_authoritative_tool_output_and_handles_offline_fallback(
    tmp_path: Path,
) -> None:
    paths = _stage_copilot_inputs(tmp_path)

    mock_ollama_payload = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "explain_container",
                        "arguments": {
                            "location_id": "L1",
                            "material": "white",
                            "date": "2026-04-15",
                        },
                    }
                }
            ],
        }
    }

    class _MockResponse:
        def __enter__(self) -> _MockResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(mock_ollama_payload).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=_MockResponse()) as mock_urlopen:
        res = ask_copilot(
            "Warum ist L1 weiß auf der Route?",
            date="2026-04-15",
            use_llm=True,
            route_path=paths["route_path"],
            scored_path=paths["scored_path"],
            locations_path=paths["locations_path"],
        )
    assert mock_urlopen.call_count == 1
    assert res["mode"] == "ollama_tool_router"
    assert res["tool_name"] == "explain_container"
    assert res["tool_result"]["container_key"] == "L1:white"
    assert res["tool_result"]["metrics"]["last_fill_level"] == pytest.approx(110.0)
    assert str(paths["scored_path"]) in res["sources"]

    # Offline fallback when Ollama is unreachable
    with patch("urllib.request.urlopen", side_effect=URLError("connection refused")):
        fallback = ask_copilot(
            "Was passiert bei max_stops=2?",
            date="2026-04-15",
            use_llm=True,
            route_path=paths["route_path"],
            scored_path=paths["scored_path"],
            locations_path=paths["locations_path"],
        )
    assert fallback["mode"] == "deterministic_fallback"
    assert fallback["tool_name"] == "simulate_what_if"
    assert fallback["tool_result"]["simulation"]["num_stops"] == 2
    assert "Baseline" in fallback["formatted_output"]
    assert "Quellen:" in fallback["formatted_output"]


def test_cli_copilot_subcommands(tmp_path: Path) -> None:
    paths = _stage_copilot_inputs(tmp_path)
    runner = CliRunner()

    r_overview = runner.invoke(
        cli,
        [
            "copilot",
            "overview",
            "--date",
            "2026-04-15",
            "--route",
            str(paths["route_path"]),
            "--scored",
            str(paths["scored_path"]),
            "--locations",
            str(paths["locations_path"]),
        ],
    )
    assert r_overview.exit_code == 0, r_overview.output
    assert "Quellen:" in r_overview.output

    r_explain = runner.invoke(
        cli,
        [
            "copilot",
            "explain",
            "--location",
            "L1",
            "--material",
            "white",
            "--date",
            "2026-04-15",
            "--route",
            str(paths["route_path"]),
            "--scored",
            str(paths["scored_path"]),
            "--locations",
            str(paths["locations_path"]),
        ],
    )
    assert r_explain.exit_code == 0, r_explain.output
    assert "L1:white" in r_explain.output
    assert "Quellen:" in r_explain.output

    r_what_if = runner.invoke(
        cli,
        [
            "copilot",
            "what-if",
            "--date",
            "2026-04-15",
            "--set",
            "max_stops=2",
            "--route",
            str(paths["route_path"]),
            "--scored",
            str(paths["scored_path"]),
            "--locations",
            str(paths["locations_path"]),
        ],
    )
    assert r_what_if.exit_code == 0, r_what_if.output
    assert "Baseline" in r_what_if.output
    assert "What-If" in r_what_if.output
    assert "Quellen:" in r_what_if.output

    r_ask = runner.invoke(
        cli,
        [
            "copilot",
            "ask",
            "Wie sieht die Tour aus?",
            "--date",
            "2026-04-15",
            "--no-llm",
            "--route",
            str(paths["route_path"]),
            "--scored",
            str(paths["scored_path"]),
            "--locations",
            str(paths["locations_path"]),
        ],
    )
    assert r_ask.exit_code == 0, r_ask.output
    assert "Quellen:" in r_ask.output


def test_what_if_shift_limit_bounds_each_vehicle_not_the_sum(tmp_path: Path) -> None:
    """Regression: 'shift 6 h -> 8.83 h' came from summing vehicle-hours, not one shift."""
    paths = _stage_copilot_inputs(tmp_path)
    sim = simulate_what_if(
        "2026-04-15",
        {"max_shift_hours": 0.25},
        scored_path=paths["scored_path"],
        route_path=paths["route_path"],
        locations_path=paths["locations_path"],
    )
    s = sim["simulation"]
    # Each vehicle respects the cap (a lone first stop may exceed a tiny cap; 0.25 h here).
    assert s["max_vehicle_shift_hours"] <= s["shift_hours"]
    assert s["vehicles_needed"] >= 1
    text = format_copilot_output(sim)
    assert "Fahrzeugstunden gesamt" in text
    assert "Längste Einzelschicht" in text


def test_route_reports_longest_single_shift_within_limit() -> None:
    import pandas as pd

    from prezero import routing

    scored = pd.DataFrame(
        {
            "Location_id": [f"L{i}" for i in range(12)],
            "material_type": ["white"] * 12,
            "score": [0.9] * 12,
            "critical": [True] * 12,
            "last_fill_level": [100.0] * 12,
        }
    )
    locs = pd.DataFrame(
        {
            "Location_id": [f"L{i}" for i in range(12)],
            "lat": [49.10 + 0.01 * i for i in range(12)],
            "lon": [9.15 + 0.01 * i for i in range(12)],
            "source": ["osm_assigned"] * 12,
            "confidence": ["simulated_mapping"] * 12,
        }
    )
    cfg = routing.OperationalConfig(max_shift_hours=1.0)
    route = routing.build_route(scored, locs, config=cfg)
    assert route["vehicles_needed"] >= 2
    assert route["max_vehicle_shift_hours"] <= 1.0 + 1e-9
    assert route["shift_hours"] == pytest.approx(sum(route["shift_hours_per_vehicle"]), abs=0.02)
    assert route["max_shift_hours_limit"] == 1.0


def test_precompute_what_if_presets_and_explain_stop(tmp_path: Path) -> None:
    import json

    import pandas as pd

    from prezero.copilot import explain_stop, precompute_what_if_presets

    paths = _stage_copilot_inputs(tmp_path)
    route = json.loads(paths["route_path"].read_text(encoding="utf-8"))
    scored = pd.read_csv(paths["scored_path"], dtype={"Location_id": str})
    locs = pd.read_csv(paths["locations_path"], dtype={"Location_id": str})
    before = paths["route_path"].read_bytes()

    presets = precompute_what_if_presets(route, scored, locs)
    assert [p["id"] for p in presets] == ["shift_6h", "truck_8t", "plus_vehicle", "all_critical"]
    for p in presets:
        assert {"baseline", "simulation", "delta"} <= set(p)
    plus = presets[2]
    assert plus["simulation"]["vehicles_needed"] <= plus["baseline"]["vehicles_needed"] + 1
    assert presets[3]["simulation"]["unserved_critical_locations"] == 0
    assert paths["route_path"].read_bytes() == before

    stop = next(s for s in route["stops"] if s.get("stop_type", "collection") == "collection")
    exp = explain_stop(stop, scored, locs, "2026-04-15", max_stops=route.get("max_stops"))
    assert exp["containers"], exp
    c = exp["containers"][0]
    # Score is the estimated level now scaled to 110 % = 1.0; the timer explains it.
    assert c["score"] == pytest.approx(min(1.0, c["est_fill_level"] / 110.0), abs=0.002)
    assert "status" in c and "due_date" in c
