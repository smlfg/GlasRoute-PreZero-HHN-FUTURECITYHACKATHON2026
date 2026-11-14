"""Visualizations for fill-level trends and collection routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import folium
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

MATERIAL_COLORS = {
    "white": "#4a5568",
    "green": "#2e8b57",
    "brown": "#8b4513",
}


def _score_color(score: float) -> str:
    if score >= 0.85:
        return "#b91c1c"  # dark red
    if score >= 0.70:
        return "#ea580c"  # orange-red (critical)
    if score >= 0.45:
        return "#d97706"  # amber
    return "#16a34a"  # green


def _is_simulated(source: str, confidence: str) -> bool:
    return source == "synthetic_placeholder" or confidence == "synthetic"


def plot_trends(df: pd.DataFrame, output_path: str | Path = "trends.png") -> Path:
    """Plot monthly average fill levels per glass material and save as PNG."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"])
    work["month"] = work["date"].dt.to_period("M").dt.to_timestamp()

    monthly = (
        work.groupby(["month", "material_type"], as_index=False)["fill_level_numeric"]
        .mean()
        .sort_values("month")
    )

    fig, ax = plt.subplots(figsize=(9, 4.8))
    for material, group in monthly.groupby("material_type", sort=True):
        color = MATERIAL_COLORS.get(str(material).lower(), "#2563eb")
        ax.plot(
            group["month"],
            group["fill_level_numeric"],
            marker="o",
            linewidth=2.0,
            label=str(material),
            color=color,
        )

    ax.axhline(100.0, color="#dc2626", linestyle="--", linewidth=1.0, alpha=0.6, label="100% full")
    ax.set_title("Monthly Average Container Fill Level by Material")
    ax.set_xlabel("Month")
    ax.set_ylabel("Average Fill Level (%)")
    ax.set_ylim(0, 115)
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(title="Material", frameon=True)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def plot_route(
    route: dict[str, Any] | str | Path,
    output_path: str | Path | None = None,
    scored: pd.DataFrame | None = None,
    locations: pd.DataFrame | None = None,
) -> Path:
    """Render an interactive Folium route map colored by score and site provenance."""
    if isinstance(route, (str, Path)):
        route_data = json.loads(Path(route).read_text(encoding="utf-8"))
    else:
        route_data = route

    route_date = route_data.get("date") or "route"
    out = Path(output_path) if output_path is not None else Path(f"map_{route_date}.html")
    out.parent.mkdir(parents=True, exist_ok=True)

    depot = route_data.get("depot", {"lat": 49.1427, "lon": 9.2109})
    depot_coords = [float(depot["lat"]), float(depot["lon"])]
    stops = route_data.get("stops", [])

    fmap = folium.Map(location=depot_coords, zoom_start=12)

    folium.Marker(
        location=depot_coords,
        popup="<b>Depot Heilbronn</b>",
        tooltip="Depot Heilbronn",
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(fmap)

    stop_ids = {s["Location_id"] for s in stops}

    # Optional context layer of non-selected containers colored by score & site origin.
    if scored is not None and locations is not None and not scored.empty:
        loc_scores = (
            scored.sort_values(["Location_id", "score"], ascending=[True, False])
            .groupby("Location_id", as_index=False)
            .first()
            .merge(locations[["Location_id", "lat", "lon", "source", "confidence"]], on="Location_id")
        )
        for _, row in loc_scores.iterrows():
            if row["Location_id"] in stop_ids:
                continue
            simulated = _is_simulated(str(row["source"]), str(row["confidence"]))
            color = _score_color(float(row["score"]))
            folium.CircleMarker(
                location=[float(row["lat"]), float(row["lon"])],
                radius=4,
                color=color,
                weight=1.5,
                dash_array="3, 3" if simulated else None,
                fill=True,
                fill_color=color,
                fill_opacity=0.25 if simulated else 0.6,
                tooltip=(
                    f"{row['Location_id']} | score={row['score']:.2f} | "
                    f"{'simulated' if simulated else row['source']}"
                ),
            ).add_to(fmap)

    if stops:
        line_coords = [depot_coords] + [[float(s["lat"]), float(s["lon"])] for s in stops] + [depot_coords]
        folium.PolyLine(
            locations=line_coords,
            color="#1d4ed8",
            weight=3.5,
            opacity=0.85,
            tooltip=route_data.get("comparison", "Planned route"),
        ).add_to(fmap)

    for stop in stops:
        simulated = _is_simulated(str(stop.get("source", "")), str(stop.get("confidence", "")))
        color = _score_color(float(stop["score"]))
        site_kind = "Simulated (synthetic)" if simulated else f"Real/OSM ({stop.get('source', 'unknown')})"
        popup_html = (
            f"<b>Stop #{stop['order']}</b><br>"
            f"ID: {stop['Location_id']}<br>"
            f"Material: {stop.get('primary_material', '-')}<br>"
            f"Score: {stop['score']:.3f}<br>"
            f"Last fill: {stop.get('last_fill_level', '-')}%<br>"
            f"Site: {site_kind}<br>"
            f"Cumulative: {stop.get('cumulative_km', '-')} km"
        )
        folium.CircleMarker(
            location=[float(stop["lat"]), float(stop["lon"])],
            radius=8,
            color="#111827" if not simulated else "#4b5563",
            weight=2,
            dash_array="4, 4" if simulated else None,
            fill=True,
            fill_color=color,
            fill_opacity=0.45 if simulated else 0.9,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"#{stop['order']} ({stop['score']:.2f}) - {'SIM' if simulated else 'REAL'}",
        ).add_to(fmap)

    legend_html = f"""
    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999;
                background: white; padding: 10px 14px; border-radius: 6px;
                border: 1px solid #ccc; font-size: 12px; line-height: 1.4;">
      <b>GlasRoute – {route_date}</b><br>
      {route_data.get('comparison', '')}<br>
      <span style="color:#b91c1c;">&#9679;</span> Score &ge; 0.85 &nbsp;
      <span style="color:#ea580c;">&#9679;</span> &ge; 0.70 (critical) &nbsp;
      <span style="color:#d97706;">&#9679;</span> &ge; 0.45 &nbsp;
      <span style="color:#16a34a;">&#9679;</span> &lt; 0.45<br>
      Solid border = real/OSM site &middot; Dashed/translucent = simulated site
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))
    fmap.save(str(out))
    return out
