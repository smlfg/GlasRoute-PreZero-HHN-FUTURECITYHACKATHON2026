"""Tests for visualization outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from prezero.viz import plot_route, plot_trends


def test_plot_trends_writes_png(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "Location_id": ["L1", "L1", "L2", "L2"],
            "material_type": ["white", "white", "brown", "brown"],
            "date": ["2026-01-10", "2026-04-10", "2026-01-10", "2026-04-10"],
            "fill_level_numeric": [80.0, 95.0, 40.0, 55.0],
        }
    )
    out = plot_trends(df, tmp_path / "trends.png")
    assert out.is_file()
    assert out.stat().st_size > 1000


def test_plot_route_writes_folium_html_with_real_and_simulated(tmp_path: Path) -> None:
    route = {
        "date": "2026-04-15",
        "depot": {"lat": 49.1427, "lon": 9.2109},
        "comparison": "5.2 km planned (2 stops) vs. 12.0 km full round (2 stops)",
        "stops": [
            {
                "order": 1,
                "Location_id": "L1",
                "lat": 49.145,
                "lon": 9.212,
                "score": 0.92,
                "primary_material": "white",
                "last_fill_level": 110.0,
                "source": "osm_heuristic",
                "confidence": "low",
                "cumulative_km": 0.3,
            },
            {
                "order": 2,
                "Location_id": "L2",
                "lat": 49.160,
                "lon": 9.225,
                "score": 0.75,
                "primary_material": "green",
                "last_fill_level": 90.0,
                "source": "synthetic_placeholder",
                "confidence": "synthetic",
                "cumulative_km": 2.2,
            },
        ],
    }
    out = plot_route(route, tmp_path / "map_2026-04-15.html")
    html = out.read_text(encoding="utf-8")
    assert out.is_file()
    assert "Simulated (synthetic)" in html
    assert "Real/OSM" in html
