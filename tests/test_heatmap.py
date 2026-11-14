from __future__ import annotations

from pathlib import Path

import pandas as pd

from prezero import features, scoring
from prezero.heatmap import build_heatmap_matrix
from prezero.model import build_model
from prezero.viz import plot_heatmap, plot_route

ROOT = Path(__file__).resolve().parent.parent


def _model() -> list:
    readings = pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L2"],
            "material_type": ["white", "white", "green"],
            "date": ["2025-10-17", "2025-10-24", "2025-10-20"],
            "fill_level_perc": [40, 90, 110],
        }
    )
    locations = pd.DataFrame(
        {
            "Location_id": ["L1", "L2"],
            "lat": [49.1, 49.2],
            "lon": [9.1, 9.2],
            "source": ["osm_assigned", "synthetic"],
        }
    )
    return build_model(readings, locations)


def test_matrix_has_values_and_prediction_mask() -> None:
    matrix = build_heatmap_matrix(_model(), "2025-10-17", "2025-10-31")
    assert len(matrix) == 2
    assert matrix.shape[1] == len(matrix.attrs["week_labels"])
    assert matrix.min().min() >= 0
    assert matrix.max().max() <= 110
    assert matrix.attrs["predicted"].shape == matrix.shape
    assert matrix.attrs["predicted"].to_numpy().dtype == bool


def test_heatmap_is_offline_and_slider_matches_weeks(tmp_path: Path) -> None:
    matrix = build_heatmap_matrix(_model(), "2025-10-17", "2025-10-31")
    out = plot_heatmap(matrix, tmp_path / "heatmap.html")
    html = out.read_text(encoding="utf-8")
    assert out.is_file()
    assert "plotly" in html.lower()
    assert html.count('"steps":') >= 1
    assert all(
        label.replace("/", r"\u002f") in html
        for label in matrix.attrs["week_labels"]
    )
    assert "<script src=" not in html
    assert "plotly_click" in html
    assert "map_2026-04-15.html#loc=" in html


def test_real_dataset_has_all_1338_material_containers() -> None:
    readings = pd.read_csv(
        ROOT / "data" / "processed" / "cleaned_readings.csv",
        parse_dates=["date"],
        dtype={"Location_id": str, "material_type": str},
    )
    locations = pd.read_csv(ROOT / "data" / "external" / "locations.csv", dtype={"Location_id": str})
    matrix = build_heatmap_matrix(
        build_model(readings, locations),
        "2025-10-17",
        "2026-09-30",
    )
    assert len(matrix) == 1338
    assert matrix.min().min() >= 0
    assert matrix.max().max() <= 110
    assert matrix.attrs["predicted"].shape == matrix.shape
    assert matrix.attrs["predicted"].map(lambda value: isinstance(value, bool)).all().all()


def test_raw_material_series_keep_brown_and_green() -> None:
    readings = pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L1"],
            "material_type": ["white", "green", "brown"],
            "date": ["2025-10-17", "2025-10-17", "2025-10-17"],
            "fill_level_perc": [40, 60, 80],
        }
    )
    locations = pd.DataFrame({"Location_id": ["L1"], "lat": [49.1], "lon": [9.1]})
    matrix = build_heatmap_matrix(
        readings,
        "2025-10-17",
        "2025-10-17",
        locations=locations,
    )
    assert len(matrix) == 1
    assert set(matrix.attrs["series_materials"]) == {"glass_white", "glass_green", "glass_brown"}


def test_heatmap_and_map_have_identical_material_container_keys(tmp_path: Path) -> None:
    readings = pd.read_csv(
        ROOT / "data" / "processed" / "cleaned_readings.csv",
        parse_dates=["date"],
        dtype={"Location_id": str, "material_type": str},
    )
    locations = pd.read_csv(ROOT / "data" / "external" / "locations.csv", dtype={"Location_id": str})
    matrix = build_heatmap_matrix(
        readings,
        "2025-10-17",
        "2026-09-30",
        locations=locations,
    )
    scored = scoring.score_containers(features.build_features(readings, "2026-04-15"))
    map_path = plot_route(
        {"date": "2026-04-15", "stops": []},
        tmp_path / "map_2026-04-15.html",
        scored=scored,
        locations=locations,
        container_keys=readings[["Location_id", "material_type"]],
    )
    html = map_path.read_text(encoding="utf-8")
    heatmap_keys = {
        f"{str(key).split(' · ', 1)[0]}|{str(material).removeprefix('glass_')}"
        for key, material in matrix.attrs["series_materials"].items()
    }
    assert len(heatmap_keys) == 1338
    assert html.count('"container_key":') == len(heatmap_keys)
    assert all(f'"container_key": "{key}"' in html for key in heatmap_keys)
