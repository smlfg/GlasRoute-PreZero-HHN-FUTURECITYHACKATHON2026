"""Tests for synthetic waste streams (WasteStream, config, generator, CSVs, CLI paths)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from prezero.cli import (
    STREAMS,
    _stream_cleaned_path,
    _stream_heatmap_path,
    _stream_map_path,
    _stream_raw_path,
    _stream_route_path,
    _stream_scored_path,
    _stream_trends_path,
    _stream_ui_path,
)
from prezero.model import (
    BIO,
    GASTRONOMIE,
    GLASS_BROWN,
    GLASS_GREEN,
    GLASS_WHITE,
    PAPER,
    PLASTIK,
    WASTE_STREAMS,
    Container,
    Measurement,
    WasteStream,
    stream_for_material,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import generate_synthetic_streams as gen  # noqa: E402

SYNTHETIC_STREAMS: dict[str, WasteStream] = {
    "paper": PAPER,
    "bio": BIO,
    "gastro": GASTRONOMIE,
    "plastik": PLASTIK,
}


def test_waste_stream_definitions_and_lookup() -> None:
    for ws in (GLASS_WHITE, GLASS_GREEN, GLASS_BROWN):
        assert ws.synthetic is False
        assert ws.density_kg_per_m3 == pytest.approx(400.0)
        assert ws.container_volume_m3 == pytest.approx(2.5)

    for key, ws in SYNTHETIC_STREAMS.items():
        assert ws.name == key
        assert ws.synthetic is True
        assert ws.display_name
        assert stream_for_material(key) is ws
        assert stream_for_material(key.upper()) is ws
        assert key in WASTE_STREAMS

    # Unknown material falls back to GLASS_WHITE.
    assert stream_for_material("unknown_material") is GLASS_WHITE


def test_config_streams_match_model_constants() -> None:
    config = json.loads((ROOT / "prezero_config.json").read_text(encoding="utf-8"))
    streams_cfg = config["streams"]

    for key, ws in SYNTHETIC_STREAMS.items():
        cfg = streams_cfg[key]
        assert cfg["synthetic"] is True
        assert cfg["materials"] == [key]
        assert cfg["density_kg_per_m3"] == pytest.approx(ws.density_kg_per_m3)
        assert cfg["container_volume_m3"] == pytest.approx(ws.container_volume_m3)
        assert cfg["fill_speed"] == pytest.approx(ws.fill_speed)
        for month in range(1, 13):
            assert cfg["season_factor"][str(month)] == pytest.approx(
                ws.season_factor_for_month(month)
            )


def test_container_adopts_stream_volume_and_density() -> None:
    m = Measurement(location_id="L1", timestamp=pd.Timestamp("2026-04-10"), fill_pct=50.0)
    bio_container = Container(
        location_id="L1",
        site_id="site_001",
        waste_stream=BIO,
        measurements=[m],
        reference_date=pd.Timestamp("2026-04-15"),
    )
    assert bio_container.volume_m3 == pytest.approx(2.4)
    assert bio_container.expected_mass_kg(100.0) == pytest.approx(2.4 * 600.0)

    paper_container = Container(
        location_id="L1",
        site_id="site_001",
        waste_stream=PAPER,
        measurements=[m],
        reference_date=pd.Timestamp("2026-04-15"),
    )
    assert paper_container.volume_m3 == pytest.approx(3.0)
    assert paper_container.expected_mass_kg(100.0) == pytest.approx(3.0 * 80.0)


def test_synthetic_generator_is_deterministic_and_valid() -> None:
    config = gen.load_config()["streams"]["gastro"]
    locs = ["LOC_001", "LOC_002", "LOC_003"]

    df1 = gen.generate_stream("gastro", config, locs, seed=2026)
    df2 = gen.generate_stream("gastro", config, locs, seed=2026)

    assert list(df1.columns) == ["Location_id", "material_type", "date", "fill_level_perc"]
    pd.testing.assert_frame_equal(df1, df2)
    assert set(df1["Location_id"].unique()) == set(locs)
    assert set(df1["material_type"].unique()) == {"gastro"}
    assert df1["date"].min() >= gen.START_DATE.isoformat()
    assert df1["date"].max() <= gen.END_DATE.isoformat()


def test_synthetic_csv_files_exist_and_match_schema() -> None:
    for key in ("paper", "bio", "gastro", "plastik"):
        csv_path = ROOT / "data" / "synthetic" / f"{key}_fill_levels.csv"
        assert csv_path.exists(), f"Missing synthetic CSV: {csv_path}"
        df = pd.read_csv(csv_path, dtype={"Location_id": str, "material_type": str})
        assert list(df.columns) == ["Location_id", "material_type", "date", "fill_level_perc"]
        assert len(df) > 0
        assert df["Location_id"].nunique() == 449
        assert set(df["material_type"].unique()) == {key}


def test_cli_stream_path_helpers() -> None:
    assert STREAMS == ("glass", "paper", "bio", "gastro", "plastik")
    assert _stream_raw_path("glass") == "data/raw/glass_fill_levels_anonymized_f.csv"
    assert _stream_cleaned_path("glass") == "data/processed/cleaned_readings.csv"
    assert _stream_scored_path("glass", "2026-04-15") == "data/processed/scored_2026-04-15.csv"
    assert _stream_route_path("glass", "2026-04-15") == "route_2026-04-15.json"
    assert _stream_ui_path("glass", "2026-04-15") == "ui_2026-04-15.html"
    assert _stream_map_path("glass", "2026-04-15") == "map_2026-04-15.html"
    assert _stream_heatmap_path("glass") == "heatmap.html"
    assert _stream_trends_path("glass") == "trends.png"

    for stream in ("paper", "bio", "gastro", "plastik"):
        assert _stream_raw_path(stream) == f"data/synthetic/{stream}_fill_levels.csv"
        assert _stream_cleaned_path(stream) == f"data/processed/{stream}_cleaned_readings.csv"
        assert (
            _stream_scored_path(stream, "2026-04-15")
            == f"data/processed/{stream}_scored_2026-04-15.csv"
        )
        assert _stream_route_path(stream, "2026-04-15") == f"{stream}_route_2026-04-15.json"
        assert _stream_ui_path(stream, "2026-04-15") == f"{stream}_ui_2026-04-15.html"
        assert _stream_map_path(stream, "2026-04-15") == f"{stream}_map_2026-04-15.html"
        assert _stream_heatmap_path(stream) == f"{stream}_heatmap.html"
        assert _stream_trends_path(stream) == f"{stream}_trends.png"
