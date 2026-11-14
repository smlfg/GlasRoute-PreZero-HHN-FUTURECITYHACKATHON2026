"""Location resolution, source-labelling and graceful-fetch tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from prezero import locations as module
from prezero.locations import (
    COLUMNS,
    HEILBRONN_BBOX,
    assign_osm_sites,
    complete_locations,
    load_locations,
    location_stats,
    match_osm_locations,
    material_sets,
    materials_from_tags,
    resolve_locations,
    synthetic_locations,
    write_sanity_map,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_locations as fetch  # noqa: E402


def raw_fixture() -> pd.DataFrame:
    return pd.DataFrame([
        ("A", "brown"), ("A", "green"), ("A", "white"),
        ("B", "white"), ("C", "green"),
    ], columns=["Location_id", "material_type"])


def candidate(candidate_id: str, tags: str, lat: float = 49.14) -> dict[str, object]:
    return {
        "osm_id": candidate_id, "lat": lat, "lon": 9.2,
        "material_tags": tags, "source": "openstreetmap", "address": "",
    }


def test_material_sets() -> None:
    sets = material_sets(raw_fixture())
    assert sets == {"A": frozenset({"brown", "green", "white"}), "B": frozenset({"white"}), "C": frozenset({"green"})}


def test_materials_from_colour_and_general_tags() -> None:
    colours, general, _ = materials_from_tags({"recycling:glass_bottles:colour": "clear;green"})
    assert colours == frozenset({"white", "green"})
    assert not general
    colours, general, _ = materials_from_tags({"recycling:glass": "yes", "recycling:glass_brown": "no"})
    assert colours == module.MATERIALS
    assert general


def test_matching_is_material_aware_unique_and_honest() -> None:
    candidates = pd.DataFrame([
        candidate("node/all", "recycling:glass_brown;recycling:glass_green;recycling:glass_white"),
        candidate("node/white", "recycling:glass_white"),
        candidate("node/green", "recycling:glass_green"),
    ])
    result = match_osm_locations(raw_fixture(), candidates).set_index("Location_id")
    assert set(result["confidence"]) == {"low"}
    assert set(result["source"]) == {"osm_heuristic"}
    assert result["lon"].nunique() == 1  # fixture values; IDs below prove one-to-one assignment
    reasons = " ".join(result["match_reason"])
    assert all(f"OSM=node/{name}" in reasons for name in ("all", "white", "green"))
    assert result["match_reason"].str.contains("UNVERIFIED").all()


def test_general_glass_beats_superset_for_single_colour() -> None:
    raw = pd.DataFrame([("B", "white")], columns=["Location_id", "material_type"])
    candidates = pd.DataFrame([
        candidate("node/all", "recycling:glass_brown;recycling:glass_green;recycling:glass_white"),
        candidate("node/general", "recycling:glass"),
    ])
    result = match_osm_locations(raw, candidates).iloc[0]
    assert "OSM=node/general" in result["match_reason"]
    assert "general_glass_tag" in result["match_reason"]


def test_synthetic_fallback_is_reproducible_and_labelled() -> None:
    first = synthetic_locations(["B", "A", "A"])
    second = synthetic_locations(["A", "B"])
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == 2
    assert set(first["source"]) == {"synthetic_placeholder"}
    assert set(first["confidence"]) == {"synthetic"}
    south, west, north, east = HEILBRONN_BBOX
    assert first["lat"].between(south, north).all()
    assert first["lon"].between(west, east).all()


def test_direct_provider_overrides_baseline_and_missing_ids_fall_back() -> None:
    raw = raw_fixture()
    baseline = synthetic_locations(raw["Location_id"].unique())
    baseline.loc[baseline["Location_id"] == "B", ["source", "confidence", "match_reason"]] = [
        "osm_heuristic", "low", "UNVERIFIED baseline"
    ]
    provider = pd.DataFrame([{"Location_id": "A", "lat": 49.2, "lon": 9.3}])
    result = complete_locations(raw, baseline=baseline, provider=provider).set_index("Location_id")
    assert (result.loc["A", "source"], result.loc["A", "confidence"]) == ("prezero_supplied", "high")
    assert result.loc["A", "lat"] == 49.2
    assert result.loc["B", "source"] == "osm_heuristic"
    assert result.loc["C", "confidence"] == "synthetic"


def test_resolve_explicit_real_path_has_priority(tmp_path: Path) -> None:
    synthetic = tmp_path / "base.csv"
    synthetic_locations(["A", "B", "C"]).to_csv(synthetic, index=False)
    real = tmp_path / "real.csv"
    pd.DataFrame([
        {"Location_id": "B", "lat": 49.21, "lon": 9.31},
        {"Location_id": "outside", "lat": 1, "lon": 1},
    ]).to_csv(real, index=False)
    result = resolve_locations(raw_fixture(), real_path=real, synthetic_path=synthetic).set_index("Location_id")
    assert set(result.index) == {"A", "B", "C"}
    assert result.loc["B", "confidence"] == "high"
    assert result.loc["B", "source"] == "prezero_supplied"
    assert "outside" not in result.index


def test_load_locations_minimal_provider_csv(tmp_path: Path) -> None:
    path = tmp_path / "provided.csv"
    pd.DataFrame([{"Location_id": "A", "lat": 49.1, "lon": 9.2}]).to_csv(path, index=False)
    result = load_locations(path).iloc[0]
    assert result["source"] == "prezero_supplied"
    assert result["confidence"] == "high"
    assert result["match_reason"]


def test_load_locations_rejects_duplicate_and_bad_coordinates(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.csv"
    pd.DataFrame([
        {"Location_id": "A", "lat": 49.1, "lon": 9.2},
        {"Location_id": "A", "lat": 49.2, "lon": 9.3},
    ]).to_csv(duplicate, index=False)
    with pytest.raises(ValueError, match="Duplicate"):
        load_locations(duplicate)
    invalid = tmp_path / "invalid.csv"
    pd.DataFrame([{"Location_id": "A", "lat": 91, "lon": 9.2}]).to_csv(invalid, index=False)
    with pytest.raises(ValueError, match="WGS84"):
        load_locations(invalid)


def test_overpass_parser_handles_node_center_address_and_non_glass() -> None:
    payload = json.dumps({"elements": [
        {"type": "node", "id": 1, "lat": 49.1, "lon": 9.2, "tags": {
            "amenity": "recycling", "recycling:glass_bottles:colour": "clear;green",
            "addr:street": "Testweg", "addr:housenumber": "4",
        }},
        {"type": "way", "id": 2, "center": {"lat": 49.2, "lon": 9.3}, "tags": {
            "amenity": "recycling", "recycling:glass": "yes",
        }},
        {"type": "node", "id": 3, "lat": 49.2, "lon": 9.3, "tags": {"amenity": "recycling"}},
    ]}).encode()
    result = fetch.parse_overpass_payload(payload).set_index("osm_id")
    assert set(result.index) == {"node/1", "way/2"}
    assert result.loc["node/1", "address"] == "Testweg 4"
    assert "clear|green" in result.loc["node/1", "material_tags"]
    assert result.loc["way/2", "lat"] == 49.2


def test_timeout_retries_then_full_synthetic_resolution() -> None:
    calls: list[tuple[int, int]] = []

    def timeout(*args: object) -> bytes:
        calls.append((args[-2], args[-1]))
        raise TimeoutError("simulated read timeout")

    candidates, payload, errors = fetch.fetch_real_candidates(
        mirrors=("https://one.example/api",), transport=timeout, sleep=lambda _: None,
    )
    assert candidates.empty
    assert payload is None
    assert len(errors) == 2
    assert calls == [(10, 90), (10, 90)]
    result = assign_osm_sites(raw_fixture(), candidates)
    assert len(result) == 3
    assert set(result["confidence"]) == {"synthetic"}


def test_http_client_error_does_not_retry() -> None:
    calls = 0

    def unavailable(*args: object) -> bytes:
        nonlocal calls
        calls += 1
        raise fetch.OverpassError("rate limited", status=429)

    candidates, payload, errors = fetch.fetch_real_candidates(
        mirrors=("https://one.example/api",), transport=unavailable,
    )
    assert candidates.empty
    assert payload is None
    assert calls == 2
    assert "rate limited" in errors[0]


def test_cli_fetch_failure_still_writes_all_outputs(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.csv"
    raw_fixture().to_csv(raw_path, index=False)

    def unavailable(*args: object) -> bytes:
        raise TimeoutError("offline")

    stats = fetch.main([
        "--raw", str(raw_path), "--output", str(tmp_path / "attempt.csv"),
        "--raw-output", str(tmp_path / "raw.json"),
        "--matched-output", str(tmp_path / "matched.csv"),
        "--locations-output", str(tmp_path / "locations.csv"),
        "--map-output", str(tmp_path / "map.html"),
    ], transport=unavailable)
    assert stats == {"total": 0, "provider_direct": 0, "osm_assigned": 0, "synthetic": 0}
    assert (tmp_path / "attempt.csv").is_file()
    assert not (tmp_path / "locations.csv").exists()
    assert not (tmp_path / "map.html").exists()


def test_osm_path_assigns_all_ids_simulated_and_preserves_prezero_priority() -> None:
    candidates = pd.DataFrame([
        candidate("node/one", "recycling:glass_bottles"),
        candidate("node/two", "recycling:glass"),
    ])
    assigned = assign_osm_sites(raw_fixture(), candidates)
    assert len(assigned) == 3
    assert set(assigned["source"]) == {"osm_assigned"}
    assert set(assigned["confidence"]) == {"simulated_mapping"}
    assert set(assigned["match_reason"]) == {"real OSM site, ID assignment simulated"}

    provider = pd.DataFrame([{"Location_id": "A", "lat": 49.2, "lon": 9.3}])
    resolved = complete_locations(raw_fixture(), baseline=assigned, provider=provider).set_index("Location_id")
    assert resolved.loc["A", "source"] == "prezero_supplied"
    assert resolved.loc["B", "source"] == "osm_assigned"
    assert resolved.loc["C", "source"] == "osm_assigned"

    query = fetch.overpass_query(6)
    assert '[timeout:90]' in query
    assert '["admin_level"]="6"' in query
    assert '"recycling:glass_bottles"="yes"' in query
    assert '"recycling:glass"="yes"' in query


def test_full_raw_dataset_has_exactly_449_ids() -> None:
    raw = pd.read_csv(ROOT / "data/raw/glass_fill_levels_anonymized_f.csv")
    result = complete_locations(raw)
    assert raw["Location_id"].nunique() == 449
    assert len(result) == 449
    assert result["Location_id"].is_unique
    assert set(result["Location_id"]) == set(raw["Location_id"])
    assert list(result.columns) == COLUMNS
    assert location_stats(result)["synthetic"] == 449


def test_sanity_map_contains_every_source(tmp_path: Path) -> None:
    output = tmp_path / "sanity.html"
    result = complete_locations(raw_fixture())
    result.loc[0, ["source", "confidence", "match_reason"]] = ["prezero_supplied", "high", "direct"]
    result.loc[1, ["source", "confidence", "match_reason"]] = ["osm_assigned", "simulated_mapping", "real OSM site, ID assignment simulated"]
    write_sanity_map(result, output)
    html = output.read_text(encoding="utf-8")
    assert output.stat().st_size > 1000
    assert "OpenStreetMap" in html
    assert all(location_id in html for location_id in ("A", "B", "C"))
