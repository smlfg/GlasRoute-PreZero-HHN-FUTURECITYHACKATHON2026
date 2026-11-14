from __future__ import annotations

from pathlib import Path

import pandas as pd

from prezero.heatmap import build_heatmap_matrix
from prezero.model import build_model
from prezero.viz import plot_heatmap

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


def test_real_dataset_has_all_449_containers() -> None:
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
    assert len(matrix) == 449
    assert matrix.min().min() >= 0
    assert matrix.max().max() <= 110
    assert matrix.attrs["predicted"].shape == matrix.shape
    assert matrix.attrs["predicted"].map(lambda value: isinstance(value, bool)).all().all()
