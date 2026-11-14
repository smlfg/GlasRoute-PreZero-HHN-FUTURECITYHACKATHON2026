"""Visualizations."""

from __future__ import annotations

import pandas as pd
import folium
import matplotlib

from pathlib import Path

from prezero.routing import HEILBRONN_DEPOT

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot_trends(df: pd.DataFrame, output_path: str) -> None:
    """Plot seasonal/material trends."""
    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    if "fill_level_numeric" not in data:
        data["fill_level_numeric"] = data["fill_level_perc"].map(_numeric_level)
    monthly = (
        data.dropna(subset=["date", "material_type", "fill_level_numeric"])
        .assign(month=lambda frame: frame["date"].dt.to_period("M").astype(str))
        .groupby(["month", "material_type"], as_index=False)["fill_level_numeric"]
        .mean()
    )
    figure, axis = plt.subplots(figsize=(10, 5))
    for material, group in monthly.groupby("material_type"):
        axis.plot(group["month"], group["fill_level_numeric"], marker="o", label=material)
    axis.set_title("Monatliche durchschnittliche Füllstände")
    axis.set_xlabel("Monat")
    axis.set_ylabel("Füllstand (%)")
    axis.set_ylim(0, 115)
    axis.tick_params(axis="x", rotation=45)
    axis.legend(title="Material")
    figure.tight_layout()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(destination, dpi=150)
    plt.close(figure)


def plot_route(route: pd.DataFrame, output_path: str) -> None:
    """Render route map."""
    points = route.dropna(subset=["lat", "lon"]).copy()
    center = [
        float(points["lat"].mean()) if not points.empty else HEILBRONN_DEPOT[0],
        float(points["lon"].mean()) if not points.empty else HEILBRONN_DEPOT[1],
    ]
    map_view = folium.Map(location=center, zoom_start=13)
    path = [[HEILBRONN_DEPOT[0], HEILBRONN_DEPOT[1]]]
    for _, stop in points.sort_values("route_order").iterrows():
        score = float(stop["score"])
        source = str(stop.get("source", "simulated"))
        score_color = _score_color(score)
        source_color = "green" if source.startswith("real") else "blue"
        folium.CircleMarker(
            location=[float(stop["lat"]), float(stop["lon"])],
            radius=7,
            color=source_color,
            weight=3,
            fill=True,
            fill_color=score_color,
            fill_opacity=0.85,
            tooltip=f"{stop['Location_id']} · score {score:.2f}",
            popup=f"Material: {stop['material_type']}<br>Quelle: {source}",
        ).add_to(map_view)
        path.append([float(stop["lat"]), float(stop["lon"])])
    folium.PolyLine(path, color="purple", weight=4, opacity=0.75).add_to(map_view)
    folium.Marker(
        HEILBRONN_DEPOT,
        tooltip="Depot Heilbronn",
        icon=folium.Icon(color="black", icon="home"),
    ).add_to(map_view)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    map_view.save(destination)


def _numeric_level(value: object) -> float | None:
    if isinstance(value, str) and value.strip().lower() == "overfull":
        return 110.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_color(score: float) -> str:
    if score >= 0.7:
        return "red"
    if score >= 0.4:
        return "orange"
    return "green"
