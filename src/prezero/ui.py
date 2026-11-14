"""Self-contained 4-view local web UI built solely from verifiable pipeline data."""

from __future__ import annotations

import base64
import html
import json
import statistics
import tempfile
from pathlib import Path
from typing import Any, Mapping

import folium
import pandas as pd
import plotly.graph_objects as go

from prezero import approval, forecast


def _safe_json_for_html(payload: Any) -> str:
    """Serialize JSON safely for embedding inside an inline HTML <script> tag."""
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def _wrap_srcdoc_iframe(
    inner_html: str, height_px: int = 560, title: str = "Map", frame_id: str | None = None
) -> str:
    """Wrap a standalone Folium HTML document into an isolated iframe."""
    escaped = html.escape(inner_html, quote=True)
    id_attr = f' id="{html.escape(frame_id, quote=True)}"' if frame_id else ""
    return (
        f'<iframe class="map-frame"{id_attr} title="{html.escape(title, quote=True)}" '
        f'style="width:100%;height:{height_px}px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;" '
        f'srcdoc="{escaped}"></iframe>'
    )


def render_forecast_timeline_map_html(
    scored_df: pd.DataFrame,
    locations_df: pd.DataFrame,
    base_date: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Render standalone Forecast-Timeline map (+0/+7/+14/+21 days) with no route line."""
    from prezero import viz

    forecast_df = forecast.forecast_from_scored(scored_df, base_date)
    if forecast_df.empty:
        fmap = folium.Map(location=[49.1427, 9.2109], zoom_start=12, tiles=None)
        folium.TileLayer(
            tiles=viz.TILE_URL,
            name="OpenStreetMap",
            control=False,
            attr=viz.TILE_ATTR,
        ).add_to(fmap)
        return fmap.get_root().render(), []

    merged = forecast_df.merge(
        locations_df[["Location_id", "lat", "lon", "source", "confidence"]],
        on="Location_id",
        how="left",
    )
    valid_coords = merged.dropna(subset=["lat", "lon"])
    center = (
        [float(valid_coords["lat"].mean()), float(valid_coords["lon"].mean())]
        if not valid_coords.empty
        else [49.1427, 9.2109]
    )

    fmap = folium.Map(location=center, zoom_start=12, tiles=None)
    folium.TileLayer(
        tiles=viz.TILE_URL,
        name="OpenStreetMap",
        control=False,
        attr=viz.TILE_ATTR,
    ).add_to(fmap)

    summaries: list[dict[str, Any]] = []
    layer_refs: list[tuple[str, str]] = []
    offsets = sorted(int(value) for value in merged["offset_days"].dropna().unique())

    for index, offset in enumerate(offsets):
        layer_data = merged[merged["offset_days"] == offset]
        label = "Heute" if offset == 0 else f"+{offset} Tage"
        if "target_date" in layer_data.columns and not layer_data["target_date"].dropna().empty:
            target_date_str = str(layer_data["target_date"].dropna().iloc[0])
        else:
            target_date_str = (pd.Timestamp(base_date) + pd.Timedelta(days=offset)).date().isoformat()
        kw = int(pd.Timestamp(target_date_str).isocalendar().week)

        critical = int(layer_data["status"].isin(["red", "black"]).sum())
        layer = folium.FeatureGroup(name=f"{label}: {critical} kritisch", show=index == 0)

        for row in layer_data.sort_values("forecast_pct", ascending=True, kind="mergesort").itertuples(index=False):
            if pd.isna(row.lat) or pd.isna(row.lon):
                continue
            status = str(row.status)
            color = viz.FORECAST_STATUS_COLORS.get(status, "#64748b")
            source_str = str(row.source) if pd.notna(row.source) else "unknown"
            conf_str = str(row.confidence) if pd.notna(row.confidence) else "unknown"
            simulated = viz._is_simulated(source_str, conf_str)
            last_date = (
                pd.Timestamp(row.last_date).strftime("%Y-%m-%d")
                if pd.notna(row.last_date)
                else "-"
            )
            material = viz._forecast_material_label(str(row.material_type))
            popup = (
                f"<b>ID:</b> {html.escape(str(row.Location_id))}<br>"
                f"<b>Glasfarbe:</b> {html.escape(material)}<br>"
                f"<b>Letzte Messung:</b> {float(row.last_fill_level):.1f}% ({last_date})<br>"
                f"<b>Täglicher Anstieg:</b> {float(row.avg_daily_increase):.2f}%/Tag<br>"
                f"<b>Prognose ({html.escape(label)} / {html.escape(target_date_str)}):</b> "
                f"{float(row.forecast_pct):.1f}%<br>"
                f"<b>Status:</b> {html.escape(status)}<br>"
                f"<b>Quelle:</b> {html.escape(source_str)} ({html.escape(conf_str)})"
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
                popup=folium.Popup(popup, max_width=300),
                tooltip=f"{row.Location_id} | {float(row.forecast_pct):.0f}% ({status})",
            ).add_to(layer)

        layer.add_to(fmap)
        layer_refs.append((label, layer.get_name()))

        counts = layer_data["status"].value_counts()
        summaries.append(
            {
                "offset_days": offset,
                "label": label,
                "target_date": target_date_str,
                "kw": kw,
                "total": int(len(layer_data)),
                "critical": critical,
                "red": int(counts.get("red", 0)),
                "black": int(counts.get("black", 0)),
                "yellow": int(counts.get("yellow", 0)),
                "green": int(counts.get("green", 0)),
            }
        )

    viz._add_forecast_selector(fmap, layer_refs)
    legend_html = """
    <div style="position: fixed; bottom: 16px; left: 16px; z-index: 9999;
                background: white; padding: 10px 14px; border-radius: 6px;
                border: 1px solid #cbd5e1; font-size: 12px; line-height: 1.5;">
      <b>Prognose-Skala (Cap 110 %)</b><br>
      <span style="color:#16a34a;">&#9679;</span> Grün &lt; 50 % &nbsp;
      <span style="color:#eab308;">&#9679;</span> Gelb 50–80 % &nbsp;
      <span style="color:#dc2626;">&#9679;</span> Rot &gt; 80 % &nbsp;
      <span style="color:#111827;">&#9679;</span> Schwarz &ge; 110 %<br>
      Durchgezogen = real/OSM &middot; Gestrichelt = simuliert
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))
    return fmap.get_root().render(), summaries


def render_route_view_data(
    route_data: Mapping[str, Any] | str | Path,
    scored_df: pd.DataFrame | None = None,
    locations_df: pd.DataFrame | None = None,
    container_keys: pd.DataFrame | None = None,
) -> tuple[str, dict[str, Any]]:
    """Render the existing route map and extract verifiable metrics + approval proposal."""
    from prezero import viz

    if isinstance(route_data, (str, Path)):
        route_dict: dict[str, Any] = json.loads(Path(route_data).read_text(encoding="utf-8"))
    else:
        route_dict = dict(route_data)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_map_path = Path(tmp_dir) / "route_view.html"
        viz.plot_route(
            route_dict,
            output_path=tmp_map_path,
            scored=scored_df,
            locations=locations_df,
            forecast=None,
            container_keys=container_keys,
        )
        route_map_html = tmp_map_path.read_text(encoding="utf-8")

    proposal_payload = approval.propose_route(route_dict)
    metrics = {
        "date": route_dict.get("date"),
        "num_stops": route_dict.get("num_stops"),
        "total_critical_locations": route_dict.get("total_critical_locations"),
        "total_active_locations": route_dict.get("total_active_locations"),
        "planned_km": route_dict.get("planned_km", route_dict.get("km")),
        "full_round_km": route_dict.get("full_round_km"),
        "saved_km": route_dict.get("saved_km"),
        "saved_pct": route_dict.get("saved_pct"),
        "vehicles_needed": route_dict.get("vehicles_needed"),
        "rounds": route_dict.get("rounds"),
        "rounds_per_vehicle": route_dict.get("rounds_per_vehicle"),
        "shift_hours": route_dict.get("shift_hours"),
        "max_vehicle_shift_hours": route_dict.get(
            "max_vehicle_shift_hours", max(route_dict.get("shift_hours_per_vehicle") or [0.0])
        ),
        "max_shift_hours_limit": (route_dict.get("assumptions") or {}).get("max_shift_hours"),
        "t_collected": route_dict.get("t_collected"),
        "comparison": route_dict.get("comparison"),
        "stops": route_dict.get("stops", []),
        "max_stops": route_dict.get("max_stops"),
    }
    return route_map_html, {"proposal": proposal_payload, "metrics": metrics}


def _extract_numeric_fill(df: pd.DataFrame) -> pd.Series:
    """Return numeric fill level series from fill_level_numeric or fill_level_perc."""
    if "fill_level_numeric" in df.columns:
        return pd.to_numeric(df["fill_level_numeric"], errors="coerce")
    if "fill_level_perc" in df.columns:
        raw = df["fill_level_perc"].astype(str).str.strip().str.lower()
        numeric = pd.to_numeric(df["fill_level_perc"], errors="coerce")
        return numeric.where(raw != "overfull", 110.0)
    return pd.Series(dtype=float, index=df.index)


def compute_upload_check(readings_df: pd.DataFrame) -> dict[str, Any]:
    """Compute exact dataset summary counts directly from readings_df."""
    if readings_df.empty:
        return {
            "row_count": 0,
            "container_count": 0,
            "series_count": 0,
            "date_min": "-",
            "date_max": "-",
            "measurement_days": 0,
            "missing_values": 0,
            "overfull_count": 0,
        }

    work = readings_df.copy()
    numeric_fill = _extract_numeric_fill(work)
    work["fill_level_numeric"] = numeric_fill

    parsed_dates = (
        pd.to_datetime(work["date"], errors="coerce")
        if "date" in work.columns
        else pd.Series(pd.NaT, index=work.index)
    )
    valid_dates = parsed_dates.dropna()

    req_cols = [c for c in ("Location_id", "material_type", "date", "fill_level_numeric") if c in work.columns]
    missing_values = int(work[req_cols].isna().sum().sum()) if req_cols else 0
    if "date" in work.columns:
        # Count unparseable non-null date strings too.
        missing_values += int((parsed_dates.isna() & work["date"].notna()).sum())

    container_count = (
        int(work["Location_id"].dropna().astype(str).nunique())
        if "Location_id" in work.columns
        else 0
    )
    if "Location_id" in work.columns and "material_type" in work.columns:
        valid_pairs = work.dropna(subset=["Location_id", "material_type"])
        series_count = int(valid_pairs.groupby(["Location_id", "material_type"]).ngroups)
    else:
        series_count = 0

    return {
        "row_count": int(len(work)),
        "container_count": container_count,
        "series_count": series_count,
        "date_min": valid_dates.min().strftime("%Y-%m-%d") if not valid_dates.empty else "-",
        "date_max": valid_dates.max().strftime("%Y-%m-%d") if not valid_dates.empty else "-",
        "measurement_days": int(valid_dates.dt.date.nunique()) if not valid_dates.empty else 0,
        "missing_values": missing_values,
        "overfull_count": int((numeric_fill >= 110.0).sum()),
    }


def compute_data_check(readings_df: pd.DataFrame) -> dict[str, Any]:
    """Compute regularity scores, transitions (>50 pp / >90d gaps), and trends from readings_df."""
    work = readings_df.copy()
    work["fill_level_numeric"] = _extract_numeric_fill(work)
    if "date" in work.columns:
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["Location_id", "material_type", "date", "fill_level_numeric"])

    if work.empty:
        return {
            "total_series": 0,
            "evaluable_series": 0,
            "mean_regularity": None,
            "median_regularity": None,
            "total_transitions": 0,
            "jumps_gt_50_total": 0,
            "jumps_gt_50_pct": 0.0,
            "series_with_gap_gt_90d": 0,
            "overfull_total": 0,
            "material_summary": [],
            "monthly_averages": [],
            "outlier_series": [],
            "top_regular_series": [],
            "series": [],
        }

    work = work.sort_values(["Location_id", "material_type", "date"]).reset_index(drop=True)
    series_rows: list[dict[str, Any]] = []

    for (loc_id, material), group in work.groupby(["Location_id", "material_type"], sort=True):
        dates = group["date"].to_list()
        levels = group["fill_level_numeric"].to_numpy(dtype=float)

        dt_days = [
            float((dates[i] - dates[i - 1]).total_seconds() / 86400.0)
            for i in range(1, len(dates))
        ]
        deltas = [float(levels[i] - levels[i - 1]) for i in range(1, len(levels))]
        rates = [
            delta / dt
            for dt, delta in zip(dt_days, deltas)
            if dt > 0.0 and delta >= 0.0
        ]

        regularity_score: float | None = None
        if len(rates) >= 2:
            mean_rate = statistics.mean(rates)
            if mean_rate > 0.0:
                std_rate = statistics.pstdev(rates)
                cv = std_rate / mean_rate
                regularity_score = round(1.0 / (1.0 + cv), 3)

        jumps_gt_50 = sum(1 for delta in deltas if delta > 50.0)
        gaps_gt_90d = sum(1 for dt in dt_days if dt > 90.0)
        max_gap_days = int(round(max(dt_days))) if dt_days else 0
        overfull_count = int((levels >= 110.0).sum())

        series_rows.append(
            {
                "Location_id": str(loc_id),
                "material_type": str(material),
                "reading_count": int(len(group)),
                "transitions": len(deltas),
                "regularity_score": regularity_score,
                "jumps_gt_50": jumps_gt_50,
                "gaps_gt_90d": gaps_gt_90d,
                "max_gap_days": max_gap_days,
                "overfull_count": overfull_count,
                "last_fill_level": round(float(levels[-1]), 1),
            }
        )

    scores = [row["regularity_score"] for row in series_rows if row["regularity_score"] is not None]
    total_transitions = sum(int(row["transitions"]) for row in series_rows)
    jumps_gt_50_total = sum(int(row["jumps_gt_50"]) for row in series_rows)

    work["month"] = work["date"].dt.strftime("%Y-%m")
    mat_grp = (
        work.assign(_overfull=work["fill_level_numeric"] >= 110.0)
        .groupby("material_type", as_index=False)
        .agg(
            reading_count=("fill_level_numeric", "count"),
            mean_fill_pct=("fill_level_numeric", "mean"),
            overfull_count=("_overfull", "sum"),
        )
        .sort_values("material_type")
    )
    material_summary = [
        {
            "material_type": str(r.material_type),
            "reading_count": int(r.reading_count),
            "mean_fill_pct": round(float(r.mean_fill_pct), 1),
            "overfull_count": int(r.overfull_count),
        }
        for r in mat_grp.itertuples(index=False)
    ]

    monthly_grp = (
        work.groupby(["month", "material_type"], as_index=False)
        .agg(
            mean_fill_pct=("fill_level_numeric", "mean"),
            reading_count=("fill_level_numeric", "count"),
        )
        .sort_values(["month", "material_type"])
    )
    monthly_averages = [
        {
            "month": str(r.month),
            "material_type": str(r.material_type),
            "mean_fill_pct": round(float(r.mean_fill_pct), 1),
            "reading_count": int(r.reading_count),
        }
        for r in monthly_grp.itertuples(index=False)
    ]

    outlier_series = sorted(
        (
            row
            for row in series_rows
            if row["jumps_gt_50"] > 0 or row["gaps_gt_90d"] > 0 or row["overfull_count"] > 0
        ),
        key=lambda r: (-r["jumps_gt_50"], -r["gaps_gt_90d"], -r["overfull_count"], r["Location_id"]),
    )[:30]
    top_regular_series = sorted(
        (row for row in series_rows if row["regularity_score"] is not None),
        key=lambda r: (-float(r["regularity_score"]), -r["reading_count"], r["Location_id"]),
    )[:30]

    return {
        "total_series": len(series_rows),
        "evaluable_series": len(scores),
        "mean_regularity": round(statistics.mean(scores), 3) if scores else None,
        "median_regularity": round(statistics.median(scores), 3) if scores else None,
        "total_transitions": total_transitions,
        "jumps_gt_50_total": jumps_gt_50_total,
        "jumps_gt_50_pct": (
            round(100.0 * jumps_gt_50_total / total_transitions, 1)
            if total_transitions > 0
            else 0.0
        ),
        "series_with_gap_gt_90d": sum(1 for row in series_rows if row["gaps_gt_90d"] > 0),
        "overfull_total": sum(int(row["overfull_count"]) for row in series_rows),
        "material_summary": material_summary,
        "monthly_averages": monthly_averages,
        "outlier_series": outlier_series,
        "top_regular_series": top_regular_series,
        "series": series_rows,
    }


def _trends_data_uri(readings_df: pd.DataFrame, trends_path: str | Path | None) -> str:
    """Return a base64 PNG data URI for trends.png."""
    from prezero import viz

    if trends_path is not None and Path(trends_path).is_file():
        png_bytes = Path(trends_path).read_bytes()
    else:
        work = readings_df.copy()
        if "fill_level_numeric" not in work.columns:
            work["fill_level_numeric"] = _extract_numeric_fill(work)
        work = work.dropna(subset=["date", "material_type", "fill_level_numeric"])
        with tempfile.TemporaryDirectory() as tmp_dir:
            generated = viz.plot_trends(work, Path(tmp_dir) / "trends.png")
            png_bytes = generated.read_bytes()
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _format_num(value: Any, suffix: str = "") -> str:
    if value is None:
        return "-"
    return f"{html.escape(str(value))}{suffix}"


def _build_forecast_cards_html(summaries: list[dict[str, Any]]) -> str:
    if not summaries:
        return '<div class="card"><div class="label">Hinweis</div><div class="value">Keine Prognosedaten</div></div>'
    cards: list[str] = []
    for item in summaries:
        cards.append(
            f"""
            <div class="card">
              <div class="label">{html.escape(item['label'])} (KW {item['kw']:02d} · {html.escape(item['target_date'])})</div>
              <div class="value">{item['critical']} kritische Container</div>
              <div class="sub">
                Rot (&gt;80%): {item['red']} · Schwarz (&ge;110%): {item['black']} ·
                Gelb: {item['yellow']} · Grün: {item['green']}<br>
                Container = Standort-ID &times; Glasfarbe (nicht physische Standorte)
              </div>
            </div>
            """
        )
    return "\n".join(cards)


def _build_route_section_html(
    route_map_html: str,
    route_bundle: dict[str, Any],
    what_if_html: str = "",
) -> str:
    metrics = route_bundle["metrics"]
    stops = metrics.get("stops", [])

    kpi_cards = "\n".join(
        [
            f'<div class="card"><div class="label">Geplante Tour ({metrics.get("num_stops", 0)} Stopps)</div><div class="value">{_format_num(metrics.get("planned_km"), " km")}</div><div class="sub">Volle Runde ({_format_num(metrics.get("total_active_locations"))} physische Standorte, alle Behälter, gleiche Regeln 11 t / 8 h / Entladung): {_format_num(metrics.get("full_round_km"), " km")}</div></div>',
            f'<div class="card"><div class="label">Weniger km als Status quo (diese Tour)</div><div class="value">{_format_num(metrics.get("saved_km"), " km")}</div><div class="sub">{_format_num(metrics.get("saved_pct"), " %")} gegenüber &bdquo;alles leeren&ldquo;. Achtung: Die Tour deckt nur {_format_num(metrics.get("num_stops"))} von {_format_num(metrics.get("total_critical_locations"))} kritischen Standorten. Pitch-Zahl (alle kritischen): Tab &bdquo;Fairer Vergleich&ldquo;</div></div>',
            f'<div class="card"><div class="label">Fahrzeuge &amp; Runden</div><div class="value">{_format_num(metrics.get("vehicles_needed"))} Fahrzeuge</div><div class="sub">Runden: {_format_num(metrics.get("rounds"))} · Fahrzeugstunden gesamt: {_format_num(metrics.get("shift_hours"), " h")} · längste Schicht: {_format_num(metrics.get("max_vehicle_shift_hours"), " h")} (Limit {_format_num(metrics.get("max_shift_hours_limit"), " h")})</div></div>',
            f'<div class="card"><div class="label">Sammelmenge &amp; Kritisch</div><div class="value">{_format_num(metrics.get("t_collected"), " t")}</div><div class="sub">Kritische physische Standorte gesamt: {_format_num(metrics.get("total_critical_locations"))}</div></div>',
        ]
    )

    stop_rows: list[str] = []
    for stop_idx, stop in enumerate(stops):
        stop_type = str(stop.get("stop_type", "collection"))
        row_attr = (
            f' class="stop-row" data-stop-idx="{stop_idx}" title="Klick: Warum dieser Stopp?"'
            if stop_type == "collection"
            else ""
        )
        stop_rows.append(
            f"""
            <tr{row_attr}>
              <td>{html.escape(str(stop.get('order', '-')))}</td>
              <td>{html.escape(stop_type)}</td>
              <td><code>{html.escape(str(stop.get('Location_id', '-')))}</code></td>
              <td>{html.escape(str(stop.get('primary_material', '-')))}</td>
              <td>{_format_num(stop.get('last_fill_level'), '%')}</td>
              <td>{_format_num(stop.get('score'))}</td>
              <td>{html.escape(str(stop.get('source', '-')))} ({html.escape(str(stop.get('confidence', '-')))})</td>
              <td>{_format_num(stop.get('leg_km'), ' km')}</td>
              <td>{_format_num(stop.get('cumulative_km'), ' km')}</td>
            </tr>
            """
        )

    route_iframe = _wrap_srcdoc_iframe(
        route_map_html, height_px=500, title="Bestehende Route", frame_id="route-map-frame"
    )
    route_date = html.escape(str(metrics.get("date") or "unbekannt"))
    served = int(metrics.get("num_stops") or 0)
    total_crit = int(metrics.get("total_critical_locations") or 0)
    open_crit = max(0, total_crit - served)
    coverage_html = (
        f'<div class="coverage-hint"><strong>{served} von {total_crit} kritischen Standorten in dieser Tour</strong>'
        + (
            f" &middot; {open_crit} bleiben offen (Stopp-Limit {html.escape(str(metrics.get('max_stops')))}). "
            "What-if &bdquo;Alle kritischen&ldquo; zeigt den Aufwand für alle."
            if open_crit
            else " &middot; alle kritischen Standorte werden angefahren."
        )
        + "</div>"
    )
    comparison_text = html.escape(str(metrics.get("comparison") or "-"))

    return f"""
      <div class="section-head">
        <h2>Bestehende Route ({route_date})</h2>
        <p class="muted">{comparison_text}</p>
      </div>
      {coverage_html}
      <div class="kpi-grid">{kpi_cards}</div>

      <div class="approval-box">
        <div>
          <strong>Human-in-the-Loop Freigabe:</strong> Nichts wird automatisch versendet, bevor die Disponentin freigibt.
        </div>
        <div class="approval-controls">
          <label for="dispatcher-name-input">Freigegeben durch:</label>
          <input id="dispatcher-name-input" type="text" value="dispatcher" />
          <button id="approve-route-btn" type="button">Freigeben</button>
          <span id="approval-status-badge" class="badge pending">Status: Vorgeschlagen</span>
        </div>
        <pre id="approval-record-preview" class="json-preview"></pre>
      </div>

      {what_if_html}

      <div class="map-wrap">{route_iframe}</div>

      <h3>Stopp-Liste in Fahrreihenfolge</h3>
      <p class="muted">Klick auf einen Stopp zeigt, warum er in der Tour ist (Score-Zerlegung aller Container am Standort).</p>
      <div id="explain-panel" class="explain-panel" hidden></div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Typ</th>
              <th>Location_id</th>
              <th>Material</th>
              <th>Letzte Messung</th>
              <th>Score</th>
              <th>Ortsquelle</th>
              <th>Etappe</th>
              <th>Kumulativ</th>
            </tr>
          </thead>
          <tbody>
            {''.join(stop_rows) if stop_rows else '<tr><td colspan="9">Keine Stopps in route_data</td></tr>'}
          </tbody>
        </table>
      </div>
    """


def _build_datacheck_section_html(data_check: dict[str, Any], trends_uri: str) -> str:
    mean_reg = "-" if data_check["mean_regularity"] is None else f"{data_check['mean_regularity']:.3f}"
    med_reg = "-" if data_check["median_regularity"] is None else f"{data_check['median_regularity']:.3f}"

    kpi_cards = "\n".join(
        [
            f'<div class="card"><div class="label">Regularity Score (Mittel / Median)</div><div class="value">{mean_reg} / {med_reg}</div><div class="sub">Auswertbare Serien: {data_check["evaluable_series"]} von {data_check["total_series"]}</div></div>',
            f'<div class="card"><div class="label">Stufensprünge (&gt; 50 pp)</div><div class="value">{data_check["jumps_gt_50_total"]} ({data_check["jumps_gt_50_pct"]:.1f}%)</div><div class="sub">Übergänge gesamt: {data_check["total_transitions"]}</div></div>',
            f'<div class="card"><div class="label">Messlücken (&gt; 90 Tage)</div><div class="value">{data_check["series_with_gap_gt_90d"]} Serien</div><div class="sub">Serien mit mindestens einer &gt;90-Tage-Lücke</div></div>',
            f'<div class="card"><div class="label">Überfüllungen (&ge; 110 %)</div><div class="value">{data_check["overfull_total"]}</div><div class="sub">Direkt aus cleaned_readings gezählt</div></div>',
        ]
    )

    mat_rows = "".join(
        f"<tr><td>{html.escape(r['material_type'])}</td><td>{r['reading_count']}</td><td>{r['mean_fill_pct']:.1f}%</td><td>{r['overfull_count']}</td></tr>"
        for r in data_check["material_summary"]
    )
    outlier_rows = "".join(
        (
            f"<tr><td><code>{html.escape(r['Location_id'])}</code></td>"
            f"<td>{html.escape(r['material_type'])}</td>"
            f"<td>{r['reading_count']}</td>"
            f"<td>{'-' if r['regularity_score'] is None else f'{r['regularity_score']:.3f}'}</td>"
            f"<td>{r['jumps_gt_50']}</td>"
            f"<td>{r['gaps_gt_90d']} (max {r['max_gap_days']} d)</td>"
            f"<td>{r['overfull_count']}</td></tr>"
        )
        for r in data_check["outlier_series"]
    )

    return f"""
      <div class="section-head">
        <h2>Datencheck: Berechnete Kennzahlen zur Prognostizierbarkeit</h2>
        <p class="muted">Alle Kennzahlen werden direkt aus den geladenen Messwerten berechnet.</p>
      </div>
      <div class="kpi-grid">{kpi_cards}</div>

      <div class="two-col">
        <div>
          <h3>Monatstrend pro Glasfarbe</h3>
          <img class="trend-img" src="{trends_uri}" alt="Monthly Average Container Fill Level by Material" />
        </div>
        <div>
          <h3>Mittelwerte nach Glasfarbe</h3>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>Glasfarbe</th><th>Messungen</th><th>Ø Füllstand</th><th>Overfull (&ge;110%)</th></tr>
              </thead>
              <tbody>{mat_rows or '<tr><td colspan="4">Keine Daten</td></tr>'}</tbody>
            </table>
          </div>
        </div>
      </div>

      <h3>Container-Serien mit Sprüngen (&gt; 50 pp), Lücken (&gt; 90 d) oder Überfüllungen (Top 30)</h3>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Location_id</th>
              <th>Material</th>
              <th>Messungen</th>
              <th>Regularity Score</th>
              <th>Sprünge &gt; 50 pp</th>
              <th>Lücken &gt; 90 d</th>
              <th>Overfull</th>
            </tr>
          </thead>
          <tbody>{outlier_rows or '<tr><td colspan="7">Keine Auffälligkeiten</td></tr>'}</tbody>
        </table>
      </div>
    """


BENCHMARK_VARIANT_LABELS: dict[str, str] = {
    "B0": "B0 Status quo (Listenreihenfolge, alle Standorte)",
    "B1": "B1 Status quo optimiert (Nearest Neighbor, alle Standorte)",
    "B2": "B2 Bedarfsgesteuert (nur kritische, Nearest Neighbor)",
    "B3": "B3 Bedarfsgesteuert + 2-opt",
    "B4": "B4 Bedarfsgesteuert + OR-Tools-Solver",
}


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value) if value is not None and not pd.isna(value) else False


def _pct_saving(before: float, after: float) -> float:
    return round((before - after) / before * 100.0, 1) if before > 0 else 0.0


def compute_benchmark_summary(
    rows: list[Mapping[str, Any]] | pd.DataFrame | None,
    date: str = "2026-04-15",
    seed: int = 42,
) -> dict[str, Any] | None:
    """Summarize benchmark_results.csv rows into B0/B1/B2/B4 KPIs and routing vs. demand effect."""
    if rows is None:
        return None
    frame = rows.copy() if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows))
    if frame.empty or not {"variant", "date", "seed", "km"}.issubset(frame.columns):
        return None
    frame["code"] = frame["variant"].astype(str).str.slice(0, 2)
    frame["date"] = frame["date"].astype(str)

    def effects(case: pd.DataFrame) -> dict[str, float] | None:
        km = case.set_index("code")["km"].astype(float)
        if not {"B0", "B1", "B2"}.issubset(km.index):
            return None
        best = float(km[[c for c in ("B2", "B3", "B4") if c in km.index]].min())
        return {
            "routing_pct": _pct_saving(float(km["B2"]), best),
            "demand_pct": _pct_saving(float(km["B1"]), float(km["B2"])),
            "overall_vs_b1_pct": _pct_saving(float(km["B1"]), best),
            "overall_vs_b0_pct": _pct_saving(float(km["B0"]), best),
            "best_km": round(best, 2),
        }

    case = frame[(frame["date"] == date) & (frame["seed"].astype(int) == int(seed))]
    if case.empty:
        date = str(frame["date"].iloc[0])
        seed = int(frame["seed"].iloc[0])
        case = frame[(frame["date"] == date) & (frame["seed"].astype(int) == seed)]
    main = effects(case)
    if main is None:
        return None

    variants = []
    for code in ("B0", "B1", "B2", "B4"):
        sub = case[case["code"] == code]
        if sub.empty:
            continue
        r = sub.iloc[0]
        variants.append(
            {
                "code": code,
                "label": BENCHMARK_VARIANT_LABELS[code],
                "variant": str(r["variant"]),
                "stops": int(r.get("stops", 0)),
                "km": round(float(r["km"]), 2),
                "h": round(float(r.get("h", 0.0)), 2),
                "rounds": int(r.get("rounds", r.get("vehicles", 0))),
                "t": round(float(r.get("t", 0.0)), 2),
                "nn_kept": _as_bool(r.get("nn_kept", False)),
            }
        )

    per_case = [
        e for e in (effects(g) for _, g in frame.groupby(["date", "seed"])) if e is not None
    ]
    robustness = {}
    for key in ("routing_pct", "demand_pct", "overall_vs_b1_pct"):
        values = [e[key] for e in per_case]
        robustness[key] = {
            "min": round(min(values), 1),
            "max": round(max(values), 1),
            "mean": round(sum(values) / len(values), 1),
        }

    nn_kept_counts: dict[str, int] = {}
    if "nn_kept" in frame.columns:
        flags = frame["nn_kept"].map(_as_bool)
        for code in ("B3", "B4"):
            nn_kept_counts[code] = int(flags[frame["code"] == code].sum())

    return {
        "date": date,
        "seed": int(seed),
        "variants": variants,
        "nn_kept_counts": nn_kept_counts,
        "effects": main,
        "robustness": robustness,
        "cases": len(per_case),
        "dates": sorted(frame["date"].unique().tolist()),
        "seeds": sorted(int(s) for s in frame["seed"].unique()),
    }


def _build_benchmark_section_html(summary: dict[str, Any] | None) -> str:
    head = """
      <div class="section-head">
        <h2>Fairer Vergleich: Routing-Effekt vs. Bedarfs-Effekt</h2>
        <p class="muted">Alle Varianten mit denselben Regeln: 11 t pro Runde, Entladung am Wertstoffhof, max. 8 h pro Runde, Start/Ende Betriebshof.
        Ein Stopp = ein physischer Standort (alle Glasfarben dort zusammen).</p>
      </div>
    """
    if not summary:
        return head + '<div class="card"><div class="label">Hinweis</div><div class="value">Kein Benchmark vorhanden</div><div class="sub">python scripts/benchmark.py erzeugt benchmark_results.csv.</div></div>'
    e = summary["effects"]
    rb = summary["robustness"]
    cards = "\n".join(
        [
            f'<div class="card"><div class="label">Bedarfs-Effekt (B1 &rarr; B2)</div><div class="value">{e["demand_pct"]:.1f} %</div><div class="sub">nur kritische Standorte statt alle &middot; Spanne {rb["demand_pct"]["min"]:.1f}&ndash;{rb["demand_pct"]["max"]:.1f} %</div></div>',
            f'<div class="card"><div class="label">Routing-Effekt (B2 &rarr; beste)</div><div class="value">{e["routing_pct"]:.1f} %</div><div class="sub">gleiche Stopps, bessere Reihenfolge &middot; Spanne {rb["routing_pct"]["min"]:.1f}&ndash;{rb["routing_pct"]["max"]:.1f} %</div></div>',
            f'<div class="card"><div class="label">Gesamt vs. optimierter Status quo (B1)</div><div class="value">{e["overall_vs_b1_pct"]:.1f} %</div><div class="sub">{e["best_km"]:.2f} km statt B1 &middot; Spanne {rb["overall_vs_b1_pct"]["min"]:.1f}&ndash;{rb["overall_vs_b1_pct"]["max"]:.1f} %</div></div>',
            f'<div class="card"><div class="label">Gesamt vs. Papierliste (B0)</div><div class="value">{e["overall_vs_b0_pct"]:.1f} %</div><div class="sub">obere Schranke, B0 ist nicht optimiert</div></div>',
        ]
    )
    kept = summary.get("nn_kept_counts") or {}
    nn_note = (
        f"OR-Tools (B4) war in {kept.get('B4', 0)} von {summary['cases']} Fällen schlechter als Nearest Neighbor, "
        f"2-opt (B3) in {kept.get('B3', 0)}; dann gilt die NN-Reihenfolge (Routing-Effekt dort 0 %)."
        if kept
        else ""
    )
    rows = "".join(
        f"<tr><td>{html.escape(v['label'])}"
        + (" <em>(Solver schlechter als NN, NN-Reihenfolge behalten)</em>" if v.get("nn_kept") else "")
        + f"</td><td>{v['stops']}</td><td>{v['km']:.2f} km</td>"
        f"<td>{v['h']:.2f} h</td><td>{v['rounds']}</td><td>{v['t']:.2f} t</td></tr>"
        for v in summary["variants"]
    )
    return head + f"""
      <div class="kpi-grid">{cards}</div>
      <h3>Stichtag {html.escape(summary['date'])} (Zuordnungs-Seed {summary['seed']})</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Variante</th><th>Stopps (Standorte)</th><th>Strecke</th><th>Fahrzeugstunden</th><th>Runden (&le; 11 t, &le; 8 h)</th><th>Menge</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
      <p class="muted">Spannen über {summary['cases']} Fälle: Stichtage {html.escape(', '.join(summary['dates']))} &times; Seeds {html.escape(', '.join(map(str, summary['seeds'])))}.
      Jede Runde braucht ein Fahrzeug für bis zu 8 h. Quelle: scripts/benchmark.py &rarr; benchmark_results.csv.
      {nn_note}</p>
    """


WHAT_IF_ROWS: tuple[tuple[str, str, str], ...] = (
    ("num_stops", "Stopps (Standorte)", ""),
    ("unserved_critical_locations", "Kritische Standorte nicht in Tour", ""),
    ("planned_km", "Strecke", " km"),
    ("vehicles_needed", "Fahrzeuge", ""),
    ("rounds", "Runden", ""),
    ("shift_hours", "Fahrzeugstunden gesamt", " h"),
    ("max_vehicle_shift_hours", "Längste Einzelschicht", " h"),
    ("t_collected", "Sammelmenge", " t"),
)


def compute_route_insights(
    route_data: Mapping[str, Any] | str | Path,
    scored_df: pd.DataFrame,
    locations_df: pd.DataFrame,
    date: str,
) -> dict[str, Any]:
    """Precompute what-if presets and per-stop explanations for the static website."""
    from prezero import copilot

    route_dict = (
        json.loads(Path(route_data).read_text(encoding="utf-8"))
        if isinstance(route_data, (str, Path))
        else dict(route_data)
    )
    try:
        presets = copilot.precompute_what_if_presets(route_dict, scored_df, locations_df)
    except Exception:  # noqa: BLE001 - UI must still render with partial inputs
        presets = []
    explains: dict[str, Any] = {}
    for idx, stop in enumerate(route_dict.get("stops", [])):
        if str(stop.get("stop_type", "collection")) != "collection":
            continue
        try:
            explains[str(idx)] = copilot.explain_stop(
                stop, scored_df, locations_df, date, max_stops=route_dict.get("max_stops")
            )
        except Exception:  # noqa: BLE001
            continue
    return {"presets": presets, "explains": explains}


def _build_what_if_html(presets: list[dict[str, Any]]) -> str:
    if not presets:
        return ""
    buttons = "".join(
        f'<button type="button" class="whatif-btn" data-preset="{i}" title="{html.escape(p["description"], quote=True)}">{html.escape(p["label"])}</button>'
        for i, p in enumerate(presets)
    )
    return f"""
      <div class="whatif-box">
        <strong>What-if (vorberechnet, ändert die Tour nicht):</strong>
        <div class="whatif-controls">{buttons}</div>
        <div id="whatif-result" class="muted">Szenario wählen: Baseline vs. Simulation.</div>
      </div>
    """


def _build_location_banner_html(locations_df: pd.DataFrame) -> str:
    """Page-wide notice that the ID-to-site mapping is simulated (counted from locations.csv)."""
    if locations_df is None or locations_df.empty or "confidence" not in locations_df.columns:
        return ""
    total = int(len(locations_df))
    conf = locations_df["confidence"].astype(str)
    simulated = int((conf != "high").sum())
    if simulated == 0:
        return ""
    points = (
        int(locations_df[["lat", "lon"]].round(6).drop_duplicates().shape[0])
        if {"lat", "lon"}.issubset(locations_df.columns)
        else 0
    )
    return (
        '<div class="location-banner"><strong>Standort-Zuordnung simuliert:</strong> '
        f"{simulated} von {total} Standort-IDs liegen auf {points} echten OSM-Glascontainer-Punkten in Heilbronn. "
        "Welche anonymisierte PreZero-ID zu welchem Punkt gehört, ist simuliert (mehrere IDs teilen sich einen Punkt). "
        "Mit der echten Zuordnungstabelle von PreZero entfällt das ohne Codeänderung.</div>"
    )


def _build_heatmap_section_html(heatmap_src: str | None) -> str:
    head = """
      <div class="section-head">
        <h2>Heatmap: Füllstand je Container und Woche</h2>
        <p class="muted">Ein Kästchen = ein Container (Standort &times; Glasfarbe). Wochen-Slider unten.
        Klick auf ein Kästchen springt in den Tab &bdquo;Route &amp; Freigabe&ldquo; und zeigt den Container auf der Karte.</p>
      </div>
    """
    if not heatmap_src:
        return head + '<div class="card"><div class="label">Hinweis</div><div class="value">Keine Heatmap erzeugt</div><div class="sub">prezero run bzw. prezero ui erzeugt sie automatisch.</div></div>'
    # Linked (not srcdoc) because the offline Plotly heatmap is >10 MB.
    return head + (
        f'<iframe class="map-frame" id="heatmap-frame" title="Heatmap" src="{html.escape(heatmap_src, quote=True)}" '
        'style="width:100%;height:760px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;"></iframe>'
    )


def _build_upload_section_html(upload_check: dict[str, Any]) -> str:
    return f"""
      <div class="section-head">
        <h2>CSV Upload &amp; Datensatzprüfung</h2>
        <p class="muted">Vorbelegt mit den geladenen Demo-Messdaten; per Drag &amp; Drop kann eine andere CSV lokal im Browser geprüft werden.</p>
      </div>

      <div id="csv-dropzone" class="dropzone">
        <p><strong>CSV-Datei hierher ziehen</strong> oder manuell auswählen:</p>
        <input id="csv-file-input" type="file" accept=".csv,text/csv" />
        <div id="upload-file-label" class="sub">Aktuell angezeigt: Vorgeladener Datensatz</div>
      </div>

      <div id="upload-check-results" class="kpi-grid">
        <div class="card"><div class="label">Container / Standorte</div><div class="value" id="uc-containers">{upload_check['container_count']}</div><div class="sub">Serien: <span id="uc-series">{upload_check['series_count']}</span> · Zeilen: <span id="uc-rows">{upload_check['row_count']}</span></div></div>
        <div class="card"><div class="label">Zeitraum</div><div class="value" id="uc-period">{html.escape(upload_check['date_min'])} bis {html.escape(upload_check['date_max'])}</div><div class="sub">Messtage: <span id="uc-days">{upload_check['measurement_days']}</span></div></div>
        <div class="card"><div class="label">Fehlende / ungültige Werte</div><div class="value" id="uc-missing">{upload_check['missing_values']}</div><div class="sub">Pflichtspalten: Location_id, material_type, date, fill</div></div>
        <div class="card"><div class="label">Overfull-Ereignisse</div><div class="value" id="uc-overfull">{upload_check['overfull_count']}</div><div class="sub">Als &ge; 110 % kodiert</div></div>
      </div>
    """


MATERIAL_LABELS = {"white": "Weißglas", "green": "Grünglas", "brown": "Braunglas"}
MATERIAL_COLORS = {"white": "#64748b", "green": "#2e8b57", "brown": "#8b4513"}


def _measurement_analysis_frame(readings_df: pd.DataFrame) -> pd.DataFrame:
    """Normalize the raw measurement columns used by the real-data dashboard."""
    required = {"Location_id", "material_type", "date"}
    if not required.issubset(readings_df.columns):
        return pd.DataFrame(columns=["Location_id", "material_type", "date", "fill_level_numeric"])
    work = readings_df.copy()
    work["fill_level_numeric"] = _extract_numeric_fill(work)
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["material_type"] = work["material_type"].astype(str).str.strip().str.lower()
    return work.dropna(subset=["Location_id", "material_type", "date", "fill_level_numeric"]).sort_values(
        ["Location_id", "material_type", "date"]
    )


def _forecast_backtest(work: pd.DataFrame, horizon: int) -> list[dict[str, Any]]:
    """Backtest the existing positive-growth forecast against later real readings."""
    rows: list[dict[str, Any]] = []
    for (location_id, material), group in work.groupby(["Location_id", "material_type"], sort=True):
        group = group.sort_values("date")
        dates = group["date"].tolist()
        levels = group["fill_level_numeric"].astype(float).tolist()
        for index in range(1, len(group)):
            origin_date = dates[index]
            prior_dates = dates[: index + 1]
            prior_levels = levels[: index + 1]
            rates = [
                (prior_levels[pos] - prior_levels[pos - 1])
                / (prior_dates[pos] - prior_dates[pos - 1]).days
                for pos in range(1, len(prior_levels))
                if (prior_dates[pos] - prior_dates[pos - 1]).days > 0
                and prior_levels[pos] >= prior_levels[pos - 1]
            ]
            if not rates:
                continue
            target = origin_date + pd.Timedelta(days=horizon)
            future = group[group["date"] >= target]
            if future.empty:
                continue
            actual_row = future.iloc[0]
            if actual_row["date"] > target + pd.Timedelta(days=7):
                continue
            forecast_value = min(110.0, levels[index] + statistics.mean(rates) * horizon)
            actual_value = float(actual_row["fill_level_numeric"])
            rows.append(
                {
                    "Location_id": str(location_id),
                    "material_type": str(material),
                    "horizon": horizon,
                    "forecast": forecast_value,
                    "actual": actual_value,
                    "error_pct": abs(forecast_value - actual_value) / max(abs(actual_value), 1.0) * 100.0,
                }
            )
    return rows


def compute_measurement_analysis(readings_df: pd.DataFrame) -> dict[str, Any]:
    """Compute all real-measurement series used by the first dashboard tab."""
    work = _measurement_analysis_frame(readings_df)
    materials = ("white", "green", "brown")
    if work.empty:
        return {
            "container_count": 0,
            "distribution": [],
            "weekly_overfull": [],
            "weekly_fill": [],
            "top_overfull": [],
            "intervals": [],
            "forecast_errors": [],
        }

    bins = list(range(0, 111, 10))
    distribution: list[dict[str, Any]] = []
    for material in materials:
        subset = work[work["material_type"] == material]
        counts = subset["fill_level_numeric"].clip(upper=110).round().apply(lambda value: min(110, int(value // 10 * 10)))
        for level in bins:
            distribution.append(
                {
                    "material_type": material,
                    "level": level,
                    "count": int((counts == level).sum()),
                }
            )

    work["week"] = work["date"].dt.to_period("W-MON").apply(lambda period: period.start_time)
    weekly = (
        work.assign(_overfull=work["fill_level_numeric"] >= 110.0)
        .groupby("week", as_index=False)
        .agg(overfull_rate=("_overfull", "mean"))
        .sort_values("week")
    )
    weekly_overfull = [
        {"week": row.week.strftime("%Y-%m-%d"), "overfull_rate": float(row.overfull_rate * 100.0)}
        for row in weekly.itertuples(index=False)
    ]
    rate_rows: list[dict[str, Any]] = []
    for (_, material), group in work.groupby(["Location_id", "material_type"], sort=True):
        group = group.sort_values("date")
        days = group["date"].diff().dt.total_seconds() / 86400.0
        deltas = group["fill_level_numeric"].diff()
        rates = (deltas / days * 7.0).where((days > 0) & (deltas >= 0))
        rate_rows.extend(
            {"week": date.to_period("W-MON").start_time, "material_type": material, "fill_rate": rate}
            for date, rate in zip(group["date"].iloc[1:], rates.iloc[1:])
            if pd.notna(rate)
        )
    weekly_fill_frame = (
        pd.DataFrame(rate_rows)
        .groupby(["week", "material_type"], as_index=False)["fill_rate"]
        .mean()
        .sort_values(["week", "material_type"])
        if rate_rows
        else pd.DataFrame(columns=["week", "material_type", "fill_rate"])
    )
    weekly_fill = [
        {
            "week": row.week.strftime("%Y-%m-%d"),
            "material_type": str(row.material_type),
            "fill_rate": float(row.fill_rate),
        }
        for row in weekly_fill_frame.itertuples(index=False)
    ]

    series = (
        work.assign(_overfull=work["fill_level_numeric"] >= 110.0)
        .groupby(["Location_id", "material_type"], as_index=False)
        .agg(overfull_count=("_overfull", "sum"), measurement_count=("fill_level_numeric", "count"))
    )
    series["overfull_rate"] = series["overfull_count"] / series["measurement_count"] * 100.0
    top_overfull = [
        {
            "Location_id": str(row.Location_id),
            "material_type": str(row.material_type),
            "overfull_count": int(row.overfull_count),
            "measurement_count": int(row.measurement_count),
            "overfull_rate": float(row.overfull_rate),
        }
        for row in series.sort_values(
            ["overfull_count", "overfull_rate", "measurement_count", "Location_id"],
            ascending=[False, False, False, True],
        ).head(20).itertuples(index=False)
    ]

    intervals: list[dict[str, Any]] = []
    for (location_id, material), group in work.groupby(["Location_id", "material_type"], sort=True):
        gaps = group["date"].diff().dt.days.dropna()
        intervals.extend(
            {
                "Location_id": str(location_id),
                "material_type": str(material),
                "interval_days": int(value),
            }
            for value in gaps[gaps > 0]
        )

    forecast_errors: list[dict[str, Any]] = []
    for horizon in (7, 14):
        forecast_errors.extend(_forecast_backtest(work, horizon))

    return {
        "container_count": int(series.shape[0]),
        "distribution": distribution,
        "weekly_overfull": weekly_overfull,
        "weekly_fill": weekly_fill,
        "top_overfull": top_overfull,
        "intervals": intervals,
        "forecast_errors": forecast_errors,
    }


def _plotly_html(fig: go.Figure, include_plotlyjs: bool = False) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=include_plotlyjs, config={"displayModeBar": False})


def _build_data_section_html(analysis: dict[str, Any]) -> str:
    """Render the real-measurement dashboard without any map or location data."""
    distribution = analysis["distribution"]
    fig_distribution = go.Figure()
    for material in ("white", "green", "brown"):
        rows = [row for row in distribution if row["material_type"] == material]
        fig_distribution.add_bar(
            x=[f"{row['level']}%" if row["level"] < 110 else "110%+" for row in rows],
            y=[row["count"] for row in rows],
            name=MATERIAL_LABELS[material],
            marker_color=MATERIAL_COLORS[material],
        )
    fig_distribution.update_layout(barmode="group", title="Füllstandverteilung je Material", yaxis_title="Messungen", xaxis_title="Füllstand")

    weekly_overfull = analysis["weekly_overfull"]
    fig_overfull = go.Figure(
        go.Scatter(
            x=[row["week"] for row in weekly_overfull],
            y=[row["overfull_rate"] for row in weekly_overfull],
            mode="lines+markers",
            name="Übervoll",
            line={"color": "#dc2626"},
        )
    )
    fig_overfull.update_layout(title="Übervoll-Anteil pro Kalenderwoche", yaxis_title="Anteil (%)", xaxis_title="Kalenderwoche")

    weekly_fill = analysis["weekly_fill"]
    fig_fill = go.Figure()
    for material in ("white", "green", "brown"):
        rows = [row for row in weekly_fill if row["material_type"] == material]
        fig_fill.add_trace(
            go.Scatter(
                x=[row["week"] for row in rows],
                y=[row["fill_rate"] for row in rows],
                mode="lines+markers",
                name=MATERIAL_LABELS[material],
                line={"color": MATERIAL_COLORS[material]},
            )
        )
    fig_fill.update_layout(title="Wöchentliche Füllrate nach Material", yaxis_title="Füllrate (% pro Woche)", xaxis_title="Kalenderwoche")

    intervals = analysis["intervals"]
    fig_intervals = go.Figure()
    for material in ("white", "green", "brown"):
        values = [row["interval_days"] for row in intervals if row["material_type"] == material]
        fig_intervals.add_trace(
            go.Box(y=values, name=MATERIAL_LABELS[material], marker_color=MATERIAL_COLORS[material], boxmean=True)
        )
    fig_intervals.update_layout(title="Messintervall je Container", yaxis_title="Tage zwischen Scans")

    errors = analysis["forecast_errors"]
    error_summary = []
    for horizon in (7, 14):
        values = [row["error_pct"] for row in errors if row["horizon"] == horizon]
        error_summary.append((horizon, statistics.mean(values) if values else None, len(values)))
    fig_errors = go.Figure(
        go.Bar(
            x=[f"+{horizon} Tage" for horizon, _, _ in error_summary],
            y=[value or 0 for _, value, _ in error_summary],
            text=[f"{value:.1f}%" if value is not None else "n/a" for _, value, _ in error_summary],
            textposition="auto",
            marker_color=["#2563eb", "#7c3aed"],
        )
    )
    fig_errors.update_layout(title="Forecast vs. tatsächliche Messung", yaxis_title="Mittlerer Fehler (%)")

    top_rows = "".join(
        f"<tr><td><code>{html.escape(row['Location_id'])}</code></td><td>{html.escape(MATERIAL_LABELS.get(row['material_type'], row['material_type']))}</td><td>{row['overfull_count']}</td><td>{row['measurement_count']}</td><td>{row['overfull_rate']:.1f}%</td></tr>"
        for row in analysis["top_overfull"]
    )
    interval_values = [row["interval_days"] for row in intervals]
    median_interval = statistics.median(interval_values) if interval_values else None
    error_cards = "".join(
        f'<div class="card"><div class="label">Forecast +{horizon} Tage</div><div class="value">{"-" if value is None else f"{value:.1f}%"} Fehler</div><div class="sub">{count} vergleichbare reale Messungen</div></div>'
        for horizon, value, count in error_summary
    )
    charts = [
        _plotly_html(fig_distribution, include_plotlyjs=True),
        _plotly_html(fig_overfull),
        _plotly_html(fig_fill),
        _plotly_html(fig_intervals),
        _plotly_html(fig_errors),
    ]
    return f"""
      <div class="section-head">
        <h2>Daten: Reale Messungen</h2>
        <p class="muted">Echte PreZero-Messdaten · {analysis['container_count']:,} Container · Füllstand 110 % = übervoll</p>
      </div>
      <div class="two-col">
        <div>{charts[0]}</div>
        <div>{charts[1]}</div>
        <div>{charts[2]}</div>
        <div>{charts[3]}<p class="muted">Median des Scanintervalls: {"-" if median_interval is None else f"{median_interval:.1f} Tage"}.</p></div>
      </div>
      <div class="section-head"><h3>Top 20 Container nach Übervoll-Häufigkeit</h3></div>
      <div class="table-wrap">
        <table><thead><tr><th>Container</th><th>Material</th><th>Übervoll</th><th>Messungen</th><th>Anteil</th></tr></thead>
        <tbody>{top_rows or '<tr><td colspan="5">Keine Daten</td></tr>'}</tbody></table>
      </div>
      <div class="section-head"><h3>Vorhersagbarkeit: Forecast gegen reale Folgemessung</h3>
        <p class="muted">Historisches Backtesting: positive mittlere Steigung bis zum Prognosezeitpunkt; verglichen mit der ersten realen Messung am Zieltag (+/- 7 Tage).</p>
      </div>
      <div class="kpi-grid">{error_cards}</div>
      <div>{charts[4]}</div>
    """


def build_ui(
    date: str,
    readings_df: pd.DataFrame,
    scored_df: pd.DataFrame,
    locations_df: pd.DataFrame,
    route_data: Mapping[str, Any] | str | Path,
    output_path: str | Path | None = None,
    trends_path: str | Path | None = None,
    heatmap_src: str | None = None,
    benchmark_rows: list[Mapping[str, Any]] | pd.DataFrame | None = None,
) -> Path:
    """Build the single self-contained website ui_<date>.html from verifiable data."""
    out = Path(output_path) if output_path is not None else Path(f"ui_{date}.html")
    out.parent.mkdir(parents=True, exist_ok=True)

    forecast_map_html, forecast_summaries = render_forecast_timeline_map_html(
        scored_df, locations_df, date
    )
    container_keys = (
        readings_df[["Location_id", "material_type"]]
        if {"Location_id", "material_type"}.issubset(readings_df.columns)
        else None
    )
    route_map_html, route_bundle = render_route_view_data(
        route_data, scored_df, locations_df, container_keys=container_keys
    )
    data_check = compute_data_check(readings_df)
    measurement_analysis = compute_measurement_analysis(readings_df)
    upload_check = compute_upload_check(readings_df)
    trends_uri = _trends_data_uri(readings_df, trends_path)

    forecast_cards_html = _build_forecast_cards_html(forecast_summaries)
    forecast_iframe = _wrap_srcdoc_iframe(forecast_map_html, height_px=560, title="Forecast-Timeline")
    insights = compute_route_insights(route_data, scored_df, locations_df, date)
    route_section_html = _build_route_section_html(
        route_map_html, route_bundle, _build_what_if_html(insights["presets"])
    )
    insights_json = _safe_json_for_html(
        {"presets": insights["presets"], "explains": insights["explains"], "rows": WHAT_IF_ROWS}
    )
    datacheck_section_html = _build_datacheck_section_html(data_check, trends_uri)
    upload_section_html = _build_upload_section_html(upload_check)
    heatmap_section_html = _build_heatmap_section_html(heatmap_src)
    location_banner_html = _build_location_banner_html(locations_df)
    benchmark_section_html = _build_benchmark_section_html(compute_benchmark_summary(benchmark_rows, date))
    data_section_html = _build_data_section_html(measurement_analysis)

    proposal_json = _safe_json_for_html(route_bundle["proposal"])
    approval_filename = f"approval_{date}.json"

    document_html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GlasRoute UI – {html.escape(date)}</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --surface: #ffffff;
      --border: #cbd5e1;
      --text: #0f172a;
      --muted: #475569;
      --accent: #1d4ed8;
      --accent-soft: #eff6ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }}
    header {{
      background: #0f172a;
      color: #ffffff;
      padding: 14px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    header h1 {{
      margin: 0;
      font-size: 18px;
    }}
    header .meta {{
      font-size: 12px;
      color: #cbd5e1;
    }}
    nav.tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 12px 20px;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
    }}
    nav.tabs button {{
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--text);
      padding: 8px 14px;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 600;
      font-size: 13px;
    }}
    nav.tabs button.active {{
      background: var(--accent);
      color: #ffffff;
      border-color: var(--accent);
    }}
    main {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 18px 20px 40px;
    }}
    .view-panel {{ display: none; }}
    .view-panel.active {{ display: block; }}
    .section-head h2 {{ margin: 0 0 4px; font-size: 18px; }}
    .muted {{ margin: 0 0 14px; color: var(--muted); font-size: 13px; }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
    }}
    .card .label {{ font-size: 12px; color: var(--muted); margin-bottom: 4px; }}
    .card .value {{ font-size: 20px; font-weight: 700; }}
    .card .sub {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
    .map-wrap {{ margin-bottom: 18px; }}
    .location-banner {{ background: #fef3c7; border-bottom: 1px solid #f59e0b; color: #78350f; padding: 8px 20px; font-size: 13px; }}
    .coverage-hint {{ background: #fff7ed; border: 1px solid #fdba74; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px; font-size: 13px; }}
    .map-banner {{
      display: inline-block;
      margin: 4px 0 14px;
      padding: 5px 9px;
      border-radius: 5px;
      background: #fef3c7;
      color: #92400e;
      font-size: 12px;
      font-weight: 600;
    }}
    .two-col {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
      gap: 16px;
      margin-bottom: 18px;
    }}
    .trend-img {{
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #ffffff;
    }}
    .table-wrap {{
      overflow-x: auto;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-bottom: 18px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{
      padding: 8px 10px;
      border-bottom: 1px solid #e2e8f0;
      text-align: left;
      white-space: nowrap;
    }}
    th {{ background: #f1f5f9; font-weight: 600; }}
    .approval-box {{
      background: var(--accent-soft);
      border: 1px solid #93c5fd;
      border-radius: 8px;
      padding: 12px 14px;
      margin-bottom: 16px;
    }}
    .approval-controls {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin-top: 8px;
    }}
    .approval-controls input {{
      padding: 6px 10px;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 13px;
    }}
    .approval-controls button {{
      background: #16a34a;
      color: #ffffff;
      border: none;
      padding: 8px 14px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
    }}
    .badge {{
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
    }}
    .badge.pending {{ background: #fef3c7; color: #92400e; }}
    .badge.approved {{ background: #dcfce7; color: #166534; }}
    .json-preview {{
      display: none;
      margin-top: 10px;
      background: #0f172a;
      color: #e2e8f0;
      padding: 10px;
      border-radius: 6px;
      font-size: 12px;
      max-height: 220px;
      overflow: auto;
    }}
    .whatif-box {{ background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; margin-bottom: 16px; }}
    .whatif-controls {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }}
    .whatif-btn {{ border: 1px solid var(--accent); background: var(--accent-soft); color: var(--accent); padding: 6px 12px; border-radius: 6px; font-weight: 600; cursor: pointer; }}
    .whatif-btn.active {{ background: var(--accent); color: #fff; }}
    .delta-better {{ color: #166534; font-weight: 600; }} .delta-worse {{ color: #b91c1c; font-weight: 600; }}
    tr.stop-row {{ cursor: pointer; }} tr.stop-row:hover, tr.stop-row.selected {{ background: var(--accent-soft); }}
    .explain-panel {{ background: #fff; border: 1px solid #93c5fd; border-radius: 8px; padding: 12px 14px; margin-bottom: 12px; font-size: 13px; }}
    .dropzone {{
      border: 2px dashed #94a3b8;
      border-radius: 8px;
      background: var(--surface);
      padding: 20px;
      text-align: center;
      margin-bottom: 16px;
    }}
    .dropzone.dragover {{
      border-color: var(--accent);
      background: var(--accent-soft);
    }}
  </style>
</head>
<body>
  <header>
    <h1>GlasRoute – PreZero Demo UI ({html.escape(date)})</h1>
    <div class="meta">Nur nachweisbare Pipeline-Daten · {upload_check['container_count']} Standorte · {upload_check['row_count']} Messungen</div>
  </header>

  {location_banner_html}

  <nav class="tabs" role="tablist">
    <button type="button" class="tab-btn active" data-target="view-data">1. Daten</button>
    <button type="button" class="tab-btn" data-target="view-forecast">2. Forecast-Timeline</button>
    <button type="button" class="tab-btn" data-target="view-heatmap">3. Heatmap</button>
    <button type="button" class="tab-btn" data-target="view-route">4. Route &amp; Freigabe</button>
    <button type="button" class="tab-btn" data-target="view-benchmark">5. Fairer Vergleich</button>
    <button type="button" class="tab-btn" data-target="view-datacheck">6. Datencheck</button>
    <button type="button" class="tab-btn" data-target="view-upload">7. Upload</button>
  </nav>

  <main>
    <section id="view-data" class="view-panel active">
      {data_section_html}
    </section>

    <section id="view-forecast" class="view-panel">
      <div class="section-head">
        <h2>Forecast-Timeline (+0 / +7 / +14 / +21 Tage)</h2>
        <p class="muted">Formel: last_fill_level + avg_daily_increase &times; Tage &times; Saisonfaktor, begrenzt auf 110 %.</p>
      </div>
      <div class="kpi-grid">{forecast_cards_html}</div>
      <div class="map-wrap">{forecast_iframe}</div>
    </section>

    <section id="view-heatmap" class="view-panel">
      {heatmap_section_html}
    </section>

    <section id="view-route" class="view-panel">
      {route_section_html}
    </section>

    <section id="view-benchmark" class="view-panel">
      {benchmark_section_html}
    </section>

    <section id="view-datacheck" class="view-panel">
      {datacheck_section_html}
    </section>

    <section id="view-upload" class="view-panel">
      {upload_section_html}
    </section>
  </main>

  <script id="proposal-payload" type="application/json">{proposal_json}</script>
  <script id="insights-payload" type="application/json">{insights_json}</script>
  <script>
    (function() {{
      var buttons = document.querySelectorAll(".tab-btn");
      var panels = document.querySelectorAll(".view-panel");

      function activateTab(targetId) {{
        buttons.forEach(function(btn) {{
          btn.classList.toggle("active", btn.getAttribute("data-target") === targetId);
        }});
        panels.forEach(function(panel) {{
          var active = panel.id === targetId;
          panel.classList.toggle("active", active);
          if (active) {{
            var frames = panel.querySelectorAll("iframe");
            frames.forEach(function(frame) {{
              try {{
                if (frame.contentWindow) {{
                  frame.contentWindow.dispatchEvent(new Event("resize"));
                }}
              }} catch (err) {{}}
            }});
          }}
        }});
      }}

      buttons.forEach(function(btn) {{
        btn.addEventListener("click", function() {{
          activateTab(btn.getAttribute("data-target"));
        }});
      }});

      var insights = JSON.parse(document.getElementById("insights-payload").textContent);
      function esc(s) {{ return String(s).replace(/[&<>"']/g, function(c) {{ return {{"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}}[c]; }}); }}
      function fmt(v, suf) {{ return (v === null || v === undefined) ? "-" : (String(v) + (suf || "")); }}
      // Lower is better for every what-if metric except stops and tonnes collected.
      var higherIsBetter = {{ num_stops: true, t_collected: true }};
      document.querySelectorAll(".whatif-btn").forEach(function(btn) {{
        btn.addEventListener("click", function() {{
          document.querySelectorAll(".whatif-btn").forEach(function(b) {{ b.classList.toggle("active", b === btn); }});
          var p = insights.presets[Number(btn.getAttribute("data-preset"))];
          var rows = insights.rows.map(function(r) {{
            var key = r[0], b = p.baseline[key], s = p.simulation[key];
            var d = Math.round((Number(s) - Number(b)) * 100) / 100;
            var cls = d === 0 ? "" : ((d > 0) === !!higherIsBetter[key] ? "delta-better" : "delta-worse");
            return "<tr><td>" + esc(r[1]) + "</td><td>" + fmt(b, r[2]) + "</td><td>" + fmt(s, r[2]) +
              "</td><td class='" + cls + "'>" + (d > 0 ? "+" : "") + d + esc(r[2]) + "</td></tr>";
          }}).join("");
          var ov = Object.keys(p.overrides).map(function(k) {{ return k + " = " + p.overrides[k]; }}).join(", ");
          document.getElementById("whatif-result").innerHTML =
            "<p><b>" + esc(p.label) + ":</b> " + esc(p.description) + " <code>" + esc(ov) + "</code></p>" +
            "<div class='table-wrap'><table><thead><tr><th>Kennzahl</th><th>Baseline</th><th>Simulation</th><th>Delta</th></tr></thead><tbody>" +
            rows + "</tbody></table></div>";
        }});
      }});
      document.querySelectorAll("tr.stop-row").forEach(function(row) {{
        row.addEventListener("click", function() {{
          document.querySelectorAll("tr.stop-row").forEach(function(r) {{ r.classList.toggle("selected", r === row); }});
          var e = insights.explains[row.getAttribute("data-stop-idx")];
          var panel = document.getElementById("explain-panel");
          if (!e) {{ panel.hidden = false; panel.textContent = "Keine Erklärung verfügbar."; return; }}
          var rows = e.containers.map(function(c) {{
            return "<tr><td><code>" + esc(c.Location_id).slice(0, 8) + "…</code></td><td>" + esc(c.material_type) +
              "</td><td>" + c.last_fill_level + " %</td><td>" + c.level_component + "</td><td>" + c.overfull_component +
              "</td><td>" + c.season_component + "</td><td><b>" + c.score + "</b></td><td>" + (c.critical ? "ja" : "nein") + "</td></tr>";
          }}).join("");
          panel.hidden = false;
          panel.innerHTML = "<b>Stopp #" + esc(e.order) + " – warum?</b> " + esc(e.reason) +
            "<br><span class='muted'>" + esc(e.formula) + " · kritisch ab " + e.critical_threshold +
            " · Ortsquelle " + esc(e.source) + " (" + esc(e.confidence) + ")</span>" +
            "<div class='table-wrap'><table><thead><tr><th>ID</th><th>Glas</th><th>Füllstand</th><th>0,5·Füllstand</th>" +
            "<th>0,3·Überlauf</th><th>0,2·Mat·Saison</th><th>Score</th><th>kritisch</th></tr></thead><tbody>" + rows + "</tbody></table></div>";
          panel.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
        }});
      }});

      // Heatmap click -> jump to the route map tab and focus the container marker.
      window.addEventListener("message", function(evt) {{
        var d = evt.data || {{}};
        if (d.type !== "heatmap-select" || !d.loc) return;
        activateTab("view-route");
        var routeFrame = document.getElementById("route-map-frame");
        if (!routeFrame || !routeFrame.contentWindow) return;
        var msg = {{ type: "focus-container", loc: String(d.loc), mat: String(d.mat || "") }};
        // Give the hidden map one tick to resize before focusing.
        setTimeout(function() {{ routeFrame.contentWindow.postMessage(msg, "*"); }}, 150);
      }});

      var approveBtn = document.getElementById("approve-route-btn");
      var nameInput = document.getElementById("dispatcher-name-input");
      var badge = document.getElementById("approval-status-badge");
      var preview = document.getElementById("approval-record-preview");
      var proposalRaw = document.getElementById("proposal-payload").textContent;

      if (approveBtn) {{
        approveBtn.addEventListener("click", function() {{
          var approver = (nameInput.value || "").trim() || "dispatcher";
          var record = JSON.parse(proposalRaw);
          record.status = "approved";
          record.approved = true;
          record.approved_by = approver;
          record.approved_at = new Date().toISOString().replace(/\\.\\d{{3}}Z$/, "+00:00");

          badge.textContent = "Freigegeben durch " + approver;
          badge.classList.remove("pending");
          badge.classList.add("approved");

          var text = JSON.stringify(record, null, 2);
          preview.textContent = text;
          preview.style.display = "block";

          var blob = new Blob([text], {{ type: "application/json" }});
          var url = URL.createObjectURL(blob);
          var link = document.createElement("a");
          link.href = url;
          link.download = {json.dumps(approval_filename)};
          document.body.appendChild(link);
          link.click();
          link.remove();
          URL.revokeObjectURL(url);
        }});
      }}

      function parseCsvLine(line, delimiter) {{
        var cells = [];
        var cur = "";
        var inQuotes = false;
        for (var i = 0; i < line.length; i++) {{
          var ch = line[i];
          if (ch === '"') {{
            inQuotes = !inQuotes;
          }} else if (ch === delimiter && !inQuotes) {{
            cells.push(cur.trim());
            cur = "";
          }} else {{
            cur += ch;
          }}
        }}
        cells.push(cur.trim());
        return cells;
      }}

      function inspectCsvText(text, filename) {{
        var lines = text.split(/\\r?\\n/).filter(function(l) {{ return l.trim().length > 0; }});
        if (lines.length < 2) {{
          document.getElementById("upload-file-label").textContent = filename + " enthält keine Datenzeilen.";
          return;
        }}
        var delimiter = lines[0].indexOf(";") !== -1 && lines[0].indexOf(",") === -1 ? ";" : ",";
        var headers = parseCsvLine(lines[0], delimiter);
        var idxLoc = headers.indexOf("Location_id");
        var idxMat = headers.indexOf("material_type");
        var idxDate = headers.indexOf("date");
        var idxNum = headers.indexOf("fill_level_numeric");
        var idxPerc = headers.indexOf("fill_level_perc");

        var locs = new Set();
        var series = new Set();
        var dates = new Set();
        var minDate = null;
        var maxDate = null;
        var missing = 0;
        var overfull = 0;
        var rows = lines.length - 1;

        for (var i = 1; i < lines.length; i++) {{
          var cols = parseCsvLine(lines[i], delimiter);
          var loc = idxLoc >= 0 ? (cols[idxLoc] || "") : "";
          var mat = idxMat >= 0 ? (cols[idxMat] || "") : "";
          var dt = idxDate >= 0 ? (cols[idxDate] || "").slice(0, 10) : "";
          var rawFill = idxNum >= 0 ? (cols[idxNum] || "") : (idxPerc >= 0 ? (cols[idxPerc] || "") : "");

          if (!loc) missing++; else locs.add(loc);
          if (!mat) missing++;
          if (loc && mat) series.add(loc + "|" + mat);
          if (!dt || !/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(dt)) {{
            missing++;
          }} else {{
            dates.add(dt);
            if (!minDate || dt < minDate) minDate = dt;
            if (!maxDate || dt > maxDate) maxDate = dt;
          }}
          var lowered = rawFill.toLowerCase();
          var num = lowered === "overfull" ? 110 : parseFloat(rawFill);
          if (isNaN(num)) {{
            missing++;
          }} else if (num >= 110) {{
            overfull++;
          }}
        }}

        document.getElementById("upload-file-label").textContent = "Geprüfte Datei: " + filename;
        document.getElementById("uc-containers").textContent = String(locs.size);
        document.getElementById("uc-series").textContent = String(series.size);
        document.getElementById("uc-rows").textContent = String(rows);
        document.getElementById("uc-period").textContent = (minDate || "-") + " bis " + (maxDate || "-");
        document.getElementById("uc-days").textContent = String(dates.size);
        document.getElementById("uc-missing").textContent = String(missing);
        document.getElementById("uc-overfull").textContent = String(overfull);
      }}

      var dropzone = document.getElementById("csv-dropzone");
      var fileInput = document.getElementById("csv-file-input");

      function handleFile(file) {{
        if (!file) return;
        var reader = new FileReader();
        reader.onload = function(evt) {{
          inspectCsvText(String(evt.target.result || ""), file.name);
        }};
        reader.readAsText(file);
      }}

      if (fileInput) {{
        fileInput.addEventListener("change", function() {{
          if (fileInput.files && fileInput.files[0]) handleFile(fileInput.files[0]);
        }});
      }}
      if (dropzone) {{
        dropzone.addEventListener("dragover", function(evt) {{
          evt.preventDefault();
          dropzone.classList.add("dragover");
        }});
        dropzone.addEventListener("dragleave", function() {{
          dropzone.classList.remove("dragover");
        }});
        dropzone.addEventListener("drop", function(evt) {{
          evt.preventDefault();
          dropzone.classList.remove("dragover");
          if (evt.dataTransfer && evt.dataTransfer.files && evt.dataTransfer.files[0]) {{
            handleFile(evt.dataTransfer.files[0]);
          }}
        }});
      }}
    }})();
  </script>
</body>
</html>
"""
    out.write_text(document_html, encoding="utf-8")
    return out
