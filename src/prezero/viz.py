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
    "paper": "#2563eb",
    "bio": "#7c3aed",
    "gastro": "#db2777",
    "plastik": "#0891b2",
    "glass_white": "#4a5568",
    "glass_green": "#2e8b57",
    "glass_brown": "#8b4513",
}

STREAM_LABELS = {
    "glass": "Glas",
    "paper": "Papier",
    "bio": "Bio",
    "gastro": "Gastronomie",
    "plastik": "Plastik",
}


def _material_sort_key_for_viz(material: str) -> int:
    """Stable visual ordering for heatmap material groups."""
    known = {"glass_white": 0, "glass_green": 1, "glass_brown": 2}
    return known.get(material, 3)


FORECAST_STATUS_COLORS = {
    "green": "#16a34a",
    "yellow": "#eab308",
    "red": "#dc2626",
    "black": "#111827",
}

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_ATTR = "© OpenStreetMap contributors, ODbL"


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
    map_date: str | None = None,
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
    material_names = sorted(display_materials.unique().tolist(), key=_material_sort_key_for_viz)
    if stored_shares is not None:
        overfull_shares = [float(stored_shares.get(material, 0.0)) for material in material_names]
    else:
        overfull_shares = []
        for material in material_names:
            material_rows = matrix.index[display_materials == material]
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
                        str(location_id).split(" · ", 1)[0],
                        material.removeprefix("glass_"),
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
                    "ID: %{customdata[0]}<br>Glas: %{customdata[2]}<br>"
                    "Füllstand: %{customdata[3]}<br>%{customdata[4]}<extra>"
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
    html_doc = fig.to_html(include_plotlyjs="inline", full_html=True, div_id="heatmap-plot")
    target_map = f"map_{map_date}.html" if map_date else "map_2026-04-15.html"
    labels_json = json.dumps(labels)
    click_script = f"""
    <script>
      document.addEventListener("DOMContentLoaded", function() {{
        var plot = document.getElementById("heatmap-plot");
        var labels = {labels_json};
        var targetMap = "{target_map}";
        function currentWeekLabel() {{
          try {{
            var slider = (plot.layout && plot.layout.sliders && plot.layout.sliders[0]) || null;
            var idx = slider ? (slider.active || 0) : 0;
            return labels[idx] || labels[0] || "";
          }} catch (e) {{ return labels[0] || ""; }}
        }}
        if (!plot) return;
        plot.on("plotly_click", function(event) {{
          var point = event.points && event.points[0];
          if (!point || !point.customdata) return;
          var loc = String(point.customdata[0]);
          var mat = String(point.customdata[1] || "").toLowerCase().replace(/^glass_/, "");
          var week = currentWeekLabel();
          var hash = "#loc=" + encodeURIComponent(loc) + "&mat=" + encodeURIComponent(mat);
          var targetHref = targetMap + hash; // map_2026-04-15.html#loc= fallback target
          if (window.parent && window.parent !== window) {{
            try {{ window.parent.postMessage({{type: "heatmap-select", loc: loc, mat: mat, week: week, target: targetHref}}, "*"); }} catch (e) {{}}
          }} else {{
            window.location.href = targetHref;
          }}
        }});
        plot.on("plotly_sliderchange", function(evt) {{
          var idx = (evt && typeof evt.slider === "object" && typeof evt.slider.active === "number") ? evt.slider.active : (evt && evt.active);
          var week = labels[idx] || currentWeekLabel();
          try {{ if (window.parent && window.parent !== window) window.parent.postMessage({{type: "heatmap-week", week: week, label: week}}, "*"); }} catch (e) {{}}
        }});
        window.addEventListener("message", function(evt) {{
          var d = evt.data || {{}};
          if (d.type !== "set-week") return;
          var week = d.week || d.label;
          var idx = labels.indexOf(week);
          if (idx < 0 || !window.Plotly) return;
          try {{
            Plotly.relayout(plot, {{"sliders[0].active": idx}});
            var steps = (plot.layout.sliders[0].steps || []);
            if (steps[idx]) Plotly.restyle(plot, steps[idx].args[0], steps[idx].args[1] ? undefined : undefined);
          }} catch (e) {{}}
        }});
      }});
    </script>
    """
    out.write_text(html_doc.replace("</body>", click_script + "</body>"), encoding="utf-8")
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

        for row in layer_data.sort_values("forecast_pct", ascending=True, kind="mergesort").itertuples(index=False):
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
    labels_json = json.dumps([label for label, _ in layer_refs])
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
                var labels = {labels_json};
                function showForecastLayer(label, notify) {{
                  if (!forecastLayers[label]) return;
                  Object.keys(forecastLayers).forEach(function(key) {{
                    var layer = forecastLayers[key];
                    if (forecastMap.hasLayer(layer)) {{
                      forecastMap.removeLayer(layer);
                    }}
                  }});
                  forecastMap.addLayer(forecastLayers[label]);
                  if (selector.value !== label) selector.value = label;
                  if (notify && window.parent && window.parent !== window) {{
                    try {{ window.parent.postMessage({{type: "map-week", week: label, label: label}}, "*"); }} catch (e) {{}}
                  }}
                }}
                selector.addEventListener("change", function() {{
                  showForecastLayer(selector.value, true);
                }});
                window.addEventListener("message", function(evt) {{
                  var d = evt.data || {{}};
                  if (d.type !== "set-week") return;
                  var w = String(d.week || d.label || "");
                  if (forecastLayers[w]) {{ showForecastLayer(w, false); return; }}
                  var m = w.match(/KW\\s*0?(\\d+)/i);
                  if (m) {{
                    var n = m[1];
                    for (var i = 0; i < labels.length; i++) {{
                      if (labels[i].indexOf(n) !== -1) {{ showForecastLayer(labels[i], false); return; }}
                    }}
                  }}
                }});
                showForecastLayer(selector.value, false);
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
    container_keys: pd.DataFrame | None = None,
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
        popup="<b>Betriebshof</b>",
        tooltip="Betriebshof",
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
    ).add_to(fmap)
    disposal = route_data.get("disposal_depot")
    if disposal:
        folium.Marker(
            location=[float(disposal["lat"]), float(disposal["lon"])],
            popup="<b>Glas-Entsorgungsplatz</b>",
            tooltip="Glas-Entsorgungsplatz",
            icon=folium.Icon(color="green", icon="recycle", prefix="fa"),
        ).add_to(fmap)

    # Optional context layer of non-selected containers colored by score & site origin.
    if scored is not None and locations is not None and not scored.empty:
        pair_frame = (
            container_keys[["Location_id", "material_type"]].drop_duplicates()
            if container_keys is not None
            else scored[["Location_id", "material_type"]].drop_duplicates()
        )
        loc_scores = pair_frame.merge(
            scored,
            on=["Location_id", "material_type"],
            how="left",
        ).merge(
            locations[["Location_id", "lat", "lon", "source", "confidence"]],
            on="Location_id",
        )
        loc_scores["score"] = loc_scores["score"].fillna(0.0)
        container_markers: dict[str, tuple[str, str]] = {}
        for _, row in loc_scores.iterrows():
            simulated = _is_simulated(str(row["source"]), str(row["confidence"]))
            color = _score_color(float(row["score"]))
            material = str(row.get("material_type", "unknown")).strip().lower()
            container_key = f"{row['Location_id']}|{material}"
            marker = folium.CircleMarker(
                location=[float(row["lat"]), float(row["lon"])],
                radius=4,
                color=color,
                weight=1.5,
                dash_array="3, 3" if simulated else None,
                fill=True,
                fill_color=color,
                fill_opacity=0.25 if simulated else 0.6,
                popup=folium.Popup(
                    (
                        f"<b>ID:</b> {row['Location_id']}<br>"
                        f"<b>Material:</b> {material}<br>"
                        f"<b>Site:</b> "
                        f"{'Zuordnung simuliert' if simulated else row['source']}"
                    ),
                    max_width=280,
                ),
                tooltip=(
                    f"{row['Location_id']} / {material} | score={row['score']:.2f} | "
                    f"{'simulated' if simulated else row['source']}"
                ),
            )
            marker.add_to(fmap)
            marker.options["container_key"] = container_key
            container_markers[container_key] = (marker.get_name(), "simulated" if simulated else "real")
    else:
        container_markers = {}

    if stops:
        prev = depot_coords
        prev_veh = None
        for stop in stops + [None]:
            veh = None if stop is None else stop.get("vehicle", 1)
            if stop is not None and veh != prev_veh and prev_veh is not None:
                folium.PolyLine([prev, depot_coords], color="#1d4ed8", weight=3.5, opacity=0.85).add_to(fmap)
                prev = depot_coords
            cur = depot_coords if stop is None else [float(stop["lat"]), float(stop["lon"])]
            to_unload = stop is not None and stop.get("stop_type") == "unload"
            from_unload = prev == [float(disposal["lat"]), float(disposal["lon"])] if disposal else False
            folium.PolyLine(
                locations=[prev, cur],
                color="#16a34a" if (to_unload or from_unload) else "#1d4ed8",
                weight=3.5,
                opacity=0.85,
                dash_array="8, 8" if to_unload else None,
                tooltip=route_data.get("comparison", "Planned route"),
            ).add_to(fmap)
            prev, prev_veh = cur, veh

    stop_markers: list[dict[str, Any]] = []
    for stop in stops:
        simulated = _is_simulated(str(stop.get("source", "")), str(stop.get("confidence", "")))
        color = _score_color(float(stop["score"]))
        site_kind = "Simulated (synthetic)" if simulated else f"Real/OSM ({stop.get('source', 'unknown')})"
        mat_raw = str(stop.get("primary_material", "-")).lower()
        mat_label = {"white": "Weißglas", "green": "Grünglas", "brown": "Braunglas", "unload": "Entladung"}.get(mat_raw, stop.get("primary_material", "-"))
        loc_str = str(stop.get("Location_id", "-"))
        loc_display = "Entsorgungshof (angenommen)" if loc_str == "disposal_depot" else (f"Standort #{stop['order']}" if stop.get("order") is not None else (f"{loc_str[:8]}..." if len(loc_str) > 12 else loc_str))
        popup_html = (
            f"<b>Stopp #{stop['order']}</b><br>"
            f"Standort: {loc_display}<br>"
            f"Glasart: {mat_label}<br>"
            f"Dringlichkeit: {float(stop['score']):.2f}<br>"
            f"Füllstand letzter Besuch: {stop.get('last_fill_level', '-')}%<br>"
            f"Ortsquelle: {site_kind}<br>"
            f"Strecke gesamt: {stop.get('cumulative_km', '-')} km"
        )
        stop_marker = folium.CircleMarker(
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
        )
        stop_marker.add_to(fmap)
        folium.Marker(
            location=[float(stop["lat"]), float(stop["lon"])],
            icon=folium.DivIcon(
                html=f'<div style="font:bold 11px sans-serif;color:#fff;text-align:center;'
                f'margin:-7px 0 0 -7px;width:14px;">{stop["order"]}</div>'
            ),
        ).add_to(fmap)
        if str(stop.get("stop_type", "collection")) == "collection":
            stop_markers.append(
                {
                    "marker": stop_marker.get_name(),
                    "loc": str(stop.get("Location_id", "")).strip(),
                    "mat": str(stop.get("primary_material", "")).strip().lower(),
                    "order": stop.get("order"),
                }
            )

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
    _add_container_hash_handler(fmap, container_markers, stop_markers=stop_markers)
    fmap.save(str(out))
    return out


def _add_container_hash_handler(
    fmap: folium.Map,
    container_markers: dict[str, tuple[str, str]],
    stop_markers: list[dict[str, Any]] | None = None,
) -> None:
    """Make heatmap links focus markers and emit click events for Copilot explain."""
    map_name = fmap.get_name()
    marker_lookup = json.dumps(
        {
            key: {
                "marker": marker,
                "site": site,
                "loc": key.rsplit("|", 1)[0],
                "mat": key.rsplit("|", 1)[1] if "|" in key else "",
            }
            for key, (marker, site) in container_markers.items()
        }
    )
    stop_lookup = json.dumps(stop_markers or [])
    fmap.get_root().html.add_child(
        folium.Element(
            f"""
            <script>
              document.addEventListener("DOMContentLoaded", function() {{
                var containerMarkers = {marker_lookup};
                var stopMarkers = {stop_lookup};
                var containerMap = {map_name};
                var notice = document.createElement("div");
                notice.style.cssText =
                  "position:fixed;top:10px;left:50%;transform:translateX(-50%);" +
                  "z-index:9999;background:#fff3cd;padding:8px 12px;border:1px solid #e0b100;" +
                  "border-radius:5px;font:13px sans-serif;display:none;";
                document.body.appendChild(notice);
                function showNotice(message) {{
                  notice.textContent = message;
                  notice.style.display = "block";
                  window.setTimeout(function() {{ notice.style.display = "none"; }}, 3500);
                }}
                function notifyParentExplain(loc, mat, order) {{
                  if (!loc) return;
                  if (window.parent && window.parent !== window) {{
                    try {{
                      window.parent.postMessage(
                        {{
                          type: "copilot-explain",
                          loc: String(loc),
                          mat: String(mat || ""),
                          order: order === undefined ? null : order
                        }},
                        "*"
                      );
                    }} catch (e) {{}}
                  }}
                }}
                Object.keys(containerMarkers).forEach(function(key) {{
                  var entry = containerMarkers[key];
                  var marker = window[entry.marker];
                  if (marker && marker.on) {{
                    marker.on("click", function() {{
                      notifyParentExplain(entry.loc, entry.mat, null);
                    }});
                  }}
                }});
                stopMarkers.forEach(function(entry) {{
                  var marker = window[entry.marker];
                  if (marker && marker.on) {{
                    marker.on("click", function() {{
                      notifyParentExplain(entry.loc, entry.mat, entry.order);
                    }});
                  }}
                }});
                function focusFrom(locationId, material) {{
                  if (!locationId || !material) return;
                  var matNorm = String(material).toLowerCase().replace(/^glass_/, "");
                  var key = locationId + "|" + matNorm;
                  var target = containerMarkers[key];
                  if (!target) {{
                    showNotice("Container " + locationId + " / " + matNorm + " nicht gefunden.");
                    return;
                  }}
                  var marker = window[target.marker];
                  if (!marker || !containerMap) {{
                    showNotice("Marker für " + locationId + " / " + matNorm + " nicht verfügbar.");
                    return;
                  }}
                  containerMap.setView(marker.getLatLng(), 17);
                  if (marker.openPopup) marker.openPopup();
                  if (marker.setStyle) {{
                    marker.setStyle({{weight: 5, radius: 8}});
                    window.setTimeout(function() {{ marker.setStyle({{weight: 1.5, radius: 4}}); }}, 3500);
                  }}
                  if (target.site === "simulated") {{
                    showNotice("Standortzuordnung simuliert.");
                  }}
                  notifyParentExplain(locationId, matNorm, null);
                }}
                function focusFromHash() {{
                  var hash = new URLSearchParams(window.location.hash.slice(1));
                  focusFrom(hash.get("loc"), hash.get("mat"));
                }}
                focusFromHash();
                window.addEventListener("hashchange", focusFromHash);
                window.addEventListener("message", function(evt) {{
                  var d = evt.data || {{}};
                  if (d.type === "focus-container") focusFrom(d.loc, d.mat);
                }});
              }});
            </script>
            """
        )
    )


from prezero.ui import build_ui, compute_data_check, compute_upload_check  # noqa: E402, F401
