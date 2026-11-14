"""Visualizations for fill-level trends, forecasts, and collection routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import folium
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

MATERIAL_COLORS = {
    "white": "#4a5568",
    "green": "#2e8b57",
    "brown": "#8b4513",
}

FORECAST_STATUS_COLORS = {
    "green": "#16a34a",
    "yellow": "#eab308",
    "red": "#dc2626",
    "black": "#111827",
}

TILE_URL = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
TILE_ATTR = "© OpenStreetMap contributors © CARTO"


def _heatmap_status(value: float) -> str:
    if value >= 110:
        return "black"
    if value > 80:
        return "red"
    if value >= 50:
        return "yellow"
    return "green"


def plot_heatmap(
    matrix: pd.DataFrame,
    output_path: str | Path = "heatmap.html",
    selected_week: str | None = None,
) -> Path:
    """Write an offline Plotly container tileboard with a week slider."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    labels = list(matrix.attrs.get("week_labels", matrix.columns))
    predicted = matrix.attrs.get("predicted")
    if predicted is None:
        predicted = pd.DataFrame(False, index=matrix.index, columns=matrix.columns)
    materials = matrix.attrs.get("materials", pd.Series("unknown", index=matrix.index))
    display_matrix = matrix.attrs.get("series_values", matrix)
    display_predicted = matrix.attrs.get("series_predicted", predicted)
    display_materials = matrix.attrs.get("series_materials", materials)
    selected_index = labels.index(selected_week) if selected_week in labels else 0

    colorscale = [
        [0.0, "#16a34a"],
        [49.999 / 110, "#16a34a"],
        [50 / 110, "#eab308"],
        [80 / 110, "#eab308"],
        [80.001 / 110, "#dc2626"],
        [109.999 / 110, "#dc2626"],
        [1.0, "#111827"],
    ]

    stored_shares = matrix.attrs.get("overfull_shares")
    if stored_shares is not None:
        overfull_shares = [float(stored_shares.get(material, 0.0)) for material in ("glass_white", "glass_green", "glass_brown")]
    else:
        overfull_shares = []
        for material in ("glass_white", "glass_green", "glass_brown"):
            material_rows = matrix.index[materials == material]
            measured = matrix.loc[material_rows].where(~predicted.loc[material_rows])
            overfull_shares.append(
                float((measured >= 110).sum().sum() / measured.notna().sum().sum())
                if measured.notna().sum().sum()
                else 0.0
            )

    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.88, 0.12],
        specs=[[{"type": "scatter"}, {"type": "bar"}]],
        horizontal_spacing=0.08,
    )
    material_names = ("glass_white", "glass_green", "glass_brown")
    material_labels = {"glass_white": "Weißglas", "glass_green": "Grünglas", "glass_brown": "Braunglas"}
    grid_columns = 25
    group_sizes = [int((display_materials == material).sum()) for material in material_names]
    band_height = max(1, max((size + grid_columns - 1) // grid_columns for size in group_sizes)) + 1
    y_ticks = [index * band_height + (size / grid_columns) / 2 for index, size in enumerate(group_sizes)]
    y_ticktext = [f"{material_labels[material]} ({size})" for material, size in zip(material_names, group_sizes)]

    def rgba(hex_color: str, alpha: float) -> str:
        return f"rgba({int(hex_color[1:3], 16)},{int(hex_color[3:5], 16)},{int(hex_color[5:7], 16)},{alpha})"

    trace_count = 0
    for index, label in enumerate(labels):
        x_values: list[int] = []
        y_values: list[int] = []
        colors: list[str] = []
        hover_data: list[list[str]] = []
        for group, material in enumerate(material_names):
            ids = list(display_matrix.index[display_materials == material])
            ids.sort(key=lambda location_id: float(display_matrix.loc[location_id, label]), reverse=True)
            for position, location_id in enumerate(ids):
                value = float(display_matrix.loc[location_id, label])
                is_predicted = bool(display_predicted.loc[location_id, label])
                status_color = FORECAST_STATUS_COLORS[_heatmap_status(value)]
                x_values.append(position % grid_columns)
                y_values.append(group * band_height + position // grid_columns)
                colors.append(rgba(status_color, 0.45 if is_predicted else 0.95))
                hover_data.append(
                    [
                        str(location_id),
                        material_labels[material],
                        f"{value:.1f}%",
                        "prognostiziert" if is_predicted else "gemessen",
                    ]
                )
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="markers",
                marker={"symbol": "square", "size": 15, "color": colors, "line": {"color": "white", "width": 1}},
                customdata=hover_data,
                hovertemplate=(
                    "ID: %{customdata[0]}<br>Glas: %{customdata[1]}<br>"
                    "Füllstand: %{customdata[2]}<br>%{customdata[3]}<extra>"
                    + label
                    + "</extra>"
                ),
                name=label,
                visible=index == selected_index,
                showlegend=False,
            ),
            row=1,
            col=1,
        )
        trace_count += 1
    fig.add_trace(
        go.Bar(
            x=[f"{material.removeprefix('glass_')}" for material in ("glass_white", "glass_green", "glass_brown")],
            y=overfull_shares,
            marker_color=["#4a5568", "#2e8b57", "#8b4513"],
            hovertemplate="%{x}: %{y:.1%} übervoll<extra></extra>",
            name="Übervoll",
        ),
        row=1,
        col=2,
    )

    def header(index: int) -> str:
        values_at_week = display_matrix.iloc[:, index]
        predicted_at_week = display_predicted.iloc[:, index]
        statuses = values_at_week.map(_heatmap_status)
        red = int((statuses == "red").sum())
        black = int((statuses == "black").sum())
        measured_count = int((~predicted_at_week).sum())
        return (
            f"{labels[index]}: {red} rot, {black} schwarz, "
            f"{measured_count} gemessen / {len(display_matrix) - measured_count} prognostiziert"
        )

    static_trace_count = 1
    for status, label in (
        ("green", "Grün <50%"),
        ("yellow", "Gelb 50–80%"),
        ("red", "Rot >80%"),
        ("black", "Schwarz =110%"),
    ):
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={"symbol": "square", "size": 13, "color": FORECAST_STATUS_COLORS[status]},
                name=label,
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )
        static_trace_count += 1
    for opacity, label in ((0.95, "Gemessen"), (0.45, "Prognostiziert")):
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={"symbol": "square", "size": 13, "color": "#64748b", "opacity": opacity},
                name=label,
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )
        static_trace_count += 1

    steps = []
    for index in range(len(labels)):
        visibility = [False] * (trace_count + static_trace_count)
        visibility[index] = True
        visibility[trace_count:] = [True] * static_trace_count
        steps.append(
            {
                "label": labels[index],
                "method": "update",
                "args": [
                    {
                        "visible": visibility,
                    },
                    {
                        "title.text": header(index),
                        "xaxis.ticktext": [f"{labels[index]} – {len(matrix)} Standorte / {len(display_matrix)} Serien"],
                    },
                ],
            }
        )
    fig.update_layout(
        title=header(selected_index),
        template="plotly_white",
        height=650,
        xaxis={
            "title": "Container je Glasfarbe (sortiert nach Füllstand)",
            "tickmode": "array",
            "tickvals": list(range(grid_columns)),
            "showticklabels": False,
            "range": [-1, grid_columns],
        },
        yaxis={"title": "Containergruppe", "tickmode": "array", "tickvals": y_ticks, "ticktext": y_ticktext, "autorange": "reversed"},
        xaxis2={"title": "Glasfarbe", "tickangle": -45},
        yaxis2={"title": "Anteil übervoll", "tickformat": ".0%"},
        sliders=[
            {
                "active": selected_index,
                "currentvalue": {"prefix": "Ausgewählte Woche: "},
                "pad": {"t": 30},
                "steps": steps,
            }
        ],
    )
    fig.write_html(str(out), include_plotlyjs="inline", full_html=True)
    return out


def _score_color(score: float) -> str:
    if score >= 0.85:
        return "#b91c1c"  # dark red
    if score >= 0.70:
        return "#ea580c"  # orange-red (critical)
    if score >= 0.45:
        return "#d97706"  # amber
    return "#16a34a"  # green


def _is_simulated(source: str, confidence: str) -> bool:
    """True when a coordinate is a placeholder rather than a real place.

    A real place stays solid even when the *assignment* to an anonymised ID is
    only heuristic (OSM sites). Only synthetic placeholders are drawn dashed.
    """
    if source in {"synthetic_placeholder", "synthetic"} or confidence == "synthetic":
        return True
    if source == "osm_assigned" and confidence == "simulated_mapping":
        # A real OSM site whose ID assignment is simulated: real place.
        return False
    return False


def _forecast_material_label(material: str) -> str:
    return material.removeprefix("glass_")


def plot_forecast_map(
    df: pd.DataFrame,
    week: int,
    output_path: str | Path | None = None,
) -> Path:
    """Write a Folium forecast map, optionally containing several week layers."""
    out = Path(output_path) if output_path is not None else Path(f"forecast_{week:02d}.html")
    out.parent.mkdir(parents=True, exist_ok=True)

    work = df.copy()
    if "week" not in work.columns:
        work["week"] = week
    weeks = sorted(int(value) for value in work["week"].dropna().unique())
    if not weeks:
        weeks = [week]
    center = [float(work["lat"].mean()), float(work["lon"].mean())] if not work.empty else [49.1427, 9.2109]
    fmap = folium.Map(location=center, zoom_start=12, tiles=None)
    folium.TileLayer(
        tiles=TILE_URL,
        name="OpenStreetMap",
        control=False,
        attr=TILE_ATTR,
    ).add_to(fmap)

    layer_refs: list[tuple[str, str]] = []
    for index, current_week in enumerate(weeks):
        layer_data = work[work["week"] == current_week]
        critical_count = int(layer_data["status"].isin(["red", "black"]).sum())
        layer = folium.FeatureGroup(
            name=f"KW {current_week:02d} ({critical_count} kritisch)",
            show=index == 0,
        )
        for row in layer_data.itertuples(index=False):
            status = str(row.status)
            color = FORECAST_STATUS_COLORS[status]
            simulated = str(row.source) in {"synthetic", "synthetic_placeholder"}
            last_date = pd.Timestamp(row.last_date).strftime("%Y-%m-%d") if pd.notna(row.last_date) else "-"
            popup = (
                f"<b>ID:</b> {row.location_id}<br>"
                f"<b>Glasfarbe:</b> {_forecast_material_label(str(row.material))}<br>"
                f"<b>Letzte Messung:</b> {float(row.last_fill):.1f}% ({last_date})<br>"
                f"<b>Prognose:</b> {float(row.forecast_pct):.1f}%<br>"
                f"<b>Quelle:</b> {row.source}"
            )
            folium.CircleMarker(
                location=[float(row.lat), float(row.lon)],
                radius=7,
                color=color,
                weight=2,
                dash_array="5, 5" if simulated else None,
                fill=True,
                fill_color=color,
                fill_opacity=0.8 if not simulated else 0.15,
                popup=folium.Popup(popup, max_width=280),
            ).add_to(layer)
        layer.add_to(fmap)
        layer_refs.append((f"KW {current_week:02d}", layer.get_name()))

    _add_forecast_selector(fmap, layer_refs)
    first_data = work[work["week"] == weeks[0]]
    first_critical = int(first_data["status"].isin(["red", "black"]).sum())
    legend_html = f"""
    <div style="position: fixed; top: 10px; left: 50px; z-index: 9999;
                background: white; padding: 8px 12px; border-radius: 6px;
                border: 1px solid #ccc; font-size: 14px;">
      <b>KW {weeks[0]:02d} – {first_critical} Container voraussichtlich kritisch</b>
    </div>
    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999;
                background: white; padding: 10px 14px; border-radius: 6px;
                border: 1px solid #ccc; font-size: 12px; line-height: 1.6;">
      <b>Prognose</b><br>
      <span style="color:#16a34a;">&#9679;</span> Grün &lt; 50&nbsp;&nbsp;
      <span style="color:#eab308;">&#9679;</span> Gelb 50–80<br>
      <span style="color:#dc2626;">&#9679;</span> Rot &gt; 80&nbsp;&nbsp;
      <span style="color:#111827;">&#9679;</span> Schwarz &ge; 110<br>
      Durchgezogen = real/OSM &middot; Gestrichelt = simuliert
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))
    fmap.save(str(out))
    return out


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


def add_forecast_layers(
    fmap: folium.Map,
    forecast: pd.DataFrame,
    locations: pd.DataFrame,
    route_data: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Add +0/+7/+14/+21 forecast layers to an existing map.

    Each layer holds one circle marker per container, coloured by forecast
    status: green < 50, yellow 50-80, red > 80, black >= 110. Real OSM sites
    are solid, placeholders dashed. The planned route is drawn on the
    "Heute" layer. Returns one summary dict per layer.
    """
    work = forecast.copy()
    if work.empty:
        return []

    merged = work.merge(
        locations[["Location_id", "lat", "lon", "source", "confidence"]],
        on="Location_id",
        how="left",
    )

    route_layer = folium.FeatureGroup(name="Route (Heute)", show=True)
    if route_data:
        depot = route_data.get("depot", {"lat": 49.1427, "lon": 9.2109})
        stops = route_data.get("stops", [])
        if stops:
            line = (
                [[float(depot["lat"]), float(depot["lon"])]]
                + [[float(s["lat"]), float(s["lon"])] for s in stops]
                + [[float(depot["lat"]), float(depot["lon"])]]
            )
            folium.PolyLine(
                locations=line,
                color="#1d4ed8",
                weight=4,
                opacity=0.9,
                tooltip=route_data.get("comparison", "Geplante Route"),
            ).add_to(route_layer)
    route_layer.add_to(fmap)

    summaries: list[dict[str, Any]] = []
    layer_refs: list[tuple[str, str]] = []
    offsets = sorted(int(value) for value in merged["offset_days"].dropna().unique())
    for index, offset in enumerate(offsets):
        layer_data = merged[merged["offset_days"] == offset]
        label = "Heute" if offset == 0 else f"+{offset} Tage"
        critical = int(layer_data["status"].isin(["red", "black"]).sum())
        layer = folium.FeatureGroup(name=f"{label}: {critical} kritisch", show=index == 0)

        for row in layer_data.itertuples(index=False):
            status = str(row.status)
            color = FORECAST_STATUS_COLORS.get(status, "#64748b")
            simulated = _is_simulated(str(row.source), str(row.confidence))
            last_date = (
                pd.Timestamp(row.last_date).strftime("%Y-%m-%d")
                if pd.notna(row.last_date)
                else "-"
            )
            material = _forecast_material_label(str(row.material_type))
            popup = (
                f"<b>ID:</b> {row.Location_id}<br>"
                f"<b>Glasfarbe:</b> {material}<br>"
                f"<b>Letzte Messung:</b> {float(row.last_fill_level):.1f}% ({last_date})<br>"
                f"<b>Prognose ({label}):</b> {float(row.forecast_pct):.1f}%<br>"
                f"<b>Status:</b> {status}<br>"
                f"<b>Quelle:</b> {row.source}"
            )
            folium.CircleMarker(
                location=[float(row.lat), float(row.lon)],
                radius=6,
                color=color,
                weight=2,
                dash_array="5, 5" if simulated else None,
                fill=True,
                fill_color=color,
                fill_opacity=0.15 if simulated else 0.85,
                popup=folium.Popup(popup, max_width=280),
                tooltip=f"{row.Location_id} | {float(row.forecast_pct):.0f}% ({status})",
            ).add_to(layer)
        layer.add_to(fmap)
        layer_refs.append((label, layer.get_name()))

        counts = layer_data["status"].value_counts()
        summaries.append(
            {
                "offset_days": offset,
                "label": label,
                "critical": critical,
                "red": int(counts.get("red", 0)),
                "black": int(counts.get("black", 0)),
            }
        )

    folium.LayerControl(collapsed=False).add_to(fmap)
    _add_forecast_selector(fmap, layer_refs)
    _add_forecast_header(fmap, summaries)
    return summaries


def _add_forecast_selector(fmap: folium.Map, layer_refs: list[tuple[str, str]]) -> None:
    """Add an exclusive client-side selector for forecast horizons."""
    if not layer_refs:
        return
    map_name = fmap.get_name()
    options = "".join(
        f'<option value="{label}">{label}</option>' for label, _ in layer_refs
    )
    layers = ", ".join(f'"{label}": {layer_name}' for label, layer_name in layer_refs)
    fmap.get_root().html.add_child(
        folium.Element(
            f"""
            <div style="position: fixed; top: 10px; right: 10px; z-index: 9999;
                        background: white; padding: 8px 10px; border-radius: 6px;
                        border: 1px solid #ccc; font-size: 13px;">
              <label for="forecast-week-selector"><b>Forecast:</b></label>
              <select id="forecast-week-selector">{options}</select>
            </div>
            <script>
              document.addEventListener("DOMContentLoaded", function() {{
                var forecastMap = {map_name};
                var forecastLayers = {{{layers}}};
                var selector = document.getElementById("forecast-week-selector");
                function showForecastLayer(label) {{
                  Object.keys(forecastLayers).forEach(function(key) {{
                    var layer = forecastLayers[key];
                    if (forecastMap.hasLayer(layer)) {{
                      forecastMap.removeLayer(layer);
                    }}
                  }});
                  forecastMap.addLayer(forecastLayers[label]);
                }}
                selector.addEventListener("change", function() {{
                  showForecastLayer(selector.value);
                }});
                showForecastLayer(selector.value);
              }});
            </script>
            """
        )
    )


def _add_forecast_header(fmap: folium.Map, summaries: list[dict[str, Any]]) -> None:
    """Render one header line per layer with the critical count."""
    rows = "".join(
        f"<div><b>{item['label']}:</b> {item['critical']} Container voraussichtlich kritisch</div>"
        for item in summaries
    )
    fmap.get_root().html.add_child(
        folium.Element(
            f"""
            <div id="forecast-header" style="position: fixed; top: 10px; left: 50px; z-index: 9999;
                        background: white; padding: 8px 12px; border-radius: 6px;
                        border: 1px solid #ccc; font-size: 13px; line-height: 1.5;">
              {rows}
              <div style="font-size: 11px; color: #555;">Orange = geplante Route (Heute) &middot;
                Standorte: OSM-Punkte, ID-Zuordnung simuliert</div>
            </div>
            """
        )
    )


def plot_route(
    route: dict[str, Any] | str | Path,
    output_path: str | Path | None = None,
    scored: pd.DataFrame | None = None,
    locations: pd.DataFrame | None = None,
    forecast: pd.DataFrame | None = None,
) -> Path:
    """Render an interactive Folium route map colored by score and site provenance.

    When ``forecast`` is given, +0/+7/+14/+21 day forecast layers are added to
    the same map, so the demo needs a single file.
    """
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

    fmap = folium.Map(location=depot_coords, zoom_start=12, tiles=None)
    folium.TileLayer(
        tiles=TILE_URL,
        name="OpenStreetMap",
        control=False,
        attr=TILE_ATTR,
    ).add_to(fmap)

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

    if forecast is not None and not forecast.empty and locations is not None:
        add_forecast_layers(fmap, forecast, locations, route_data)

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


from prezero.ui import build_ui, compute_data_check, compute_upload_check  # noqa: E402, F401
