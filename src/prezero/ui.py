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

from prezero import approval, forecast


def _safe_json_for_html(payload: Any) -> str:
    """Serialize JSON safely for embedding inside an inline HTML <script> tag."""
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def _wrap_srcdoc_iframe(inner_html: str, height_px: int = 560, title: str = "Map") -> str:
    """Wrap a standalone Folium HTML document into an isolated iframe."""
    escaped = html.escape(inner_html, quote=True)
    return (
        f'<iframe class="map-frame" title="{html.escape(title, quote=True)}" '
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
        "t_collected": route_dict.get("t_collected"),
        "comparison": route_dict.get("comparison"),
        "stops": route_dict.get("stops", []),
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
              <div class="value">{item['critical']} kritisch</div>
              <div class="sub">
                Rot (&gt;80%): {item['red']} · Schwarz (&ge;110%): {item['black']} ·
                Gelb: {item['yellow']} · Grün: {item['green']}
              </div>
            </div>
            """
        )
    return "\n".join(cards)


def _build_route_section_html(route_map_html: str, route_bundle: dict[str, Any]) -> str:
    metrics = route_bundle["metrics"]
    stops = metrics.get("stops", [])

    kpi_cards = "\n".join(
        [
            f'<div class="card"><div class="label">Geplante Tour ({metrics.get("num_stops", 0)} Stopps)</div><div class="value">{_format_num(metrics.get("planned_km"), " km")}</div><div class="sub">Volle Runde ({_format_num(metrics.get("total_active_locations"))} Standorte): {_format_num(metrics.get("full_round_km"), " km")}</div></div>',
            f'<div class="card"><div class="label">Bedarfs-Ersparnis</div><div class="value">{_format_num(metrics.get("saved_km"), " km")}</div><div class="sub">{_format_num(metrics.get("saved_pct"), " %")} gegenüber voller Runde</div></div>',
            f'<div class="card"><div class="label">Fahrzeuge &amp; Runden</div><div class="value">{_format_num(metrics.get("vehicles_needed"))} Fahrzeuge</div><div class="sub">Runden: {_format_num(metrics.get("rounds"))} · Schicht: {_format_num(metrics.get("shift_hours"), " h")}</div></div>',
            f'<div class="card"><div class="label">Sammelmenge &amp; Kritisch</div><div class="value">{_format_num(metrics.get("t_collected"), " t")}</div><div class="sub">Kritische Standorte: {_format_num(metrics.get("total_critical_locations"))}</div></div>',
        ]
    )

    stop_rows: list[str] = []
    for stop in stops:
        stop_type = str(stop.get("stop_type", "collection"))
        stop_rows.append(
            f"""
            <tr>
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

    route_iframe = _wrap_srcdoc_iframe(route_map_html, height_px=500, title="Bestehende Route")
    route_date = html.escape(str(metrics.get("date") or "unbekannt"))
    comparison_text = html.escape(str(metrics.get("comparison") or "-"))

    return f"""
      <div class="section-head">
        <h2>Bestehende Route ({route_date})</h2>
        <p class="muted">{comparison_text}</p>
      </div>
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

      <div class="map-wrap">{route_iframe}</div>

      <h3>Stopp-Liste in Fahrreihenfolge</h3>
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


def build_ui(
    date: str,
    readings_df: pd.DataFrame,
    scored_df: pd.DataFrame,
    locations_df: pd.DataFrame,
    route_data: Mapping[str, Any] | str | Path,
    output_path: str | Path | None = None,
    trends_path: str | Path | None = None,
) -> Path:
    """Build the self-contained 4-view local HTML UI (Views 3, 4, 2, 1) from verifiable data."""
    out = Path(output_path) if output_path is not None else Path(f"ui_{date}.html")
    out.parent.mkdir(parents=True, exist_ok=True)

    forecast_map_html, forecast_summaries = render_forecast_timeline_map_html(
        scored_df, locations_df, date
    )
    route_map_html, route_bundle = render_route_view_data(route_data, scored_df, locations_df)
    data_check = compute_data_check(readings_df)
    upload_check = compute_upload_check(readings_df)
    trends_uri = _trends_data_uri(readings_df, trends_path)

    forecast_cards_html = _build_forecast_cards_html(forecast_summaries)
    forecast_iframe = _wrap_srcdoc_iframe(forecast_map_html, height_px=560, title="Forecast-Timeline")
    route_section_html = _build_route_section_html(route_map_html, route_bundle)
    datacheck_section_html = _build_datacheck_section_html(data_check, trends_uri)
    upload_section_html = _build_upload_section_html(upload_check)

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

  <nav class="tabs" role="tablist">
    <button type="button" class="tab-btn active" data-target="view-forecast">1. Forecast-Timeline</button>
    <button type="button" class="tab-btn" data-target="view-route">2. Bestehende Route</button>
    <button type="button" class="tab-btn" data-target="view-datacheck">3. Datencheck</button>
    <button type="button" class="tab-btn" data-target="view-upload">4. Upload</button>
  </nav>

  <main>
    <section id="view-forecast" class="view-panel active">
      <div class="section-head">
        <h2>Forecast-Timeline (+0 / +7 / +14 / +21 Tage)</h2>
        <p class="muted">Formel: last_fill_level + avg_daily_increase &times; Tage &times; Saisonfaktor, begrenzt auf 110 %.</p>
      </div>
      <div class="kpi-grid">{forecast_cards_html}</div>
      <div class="map-wrap">{forecast_iframe}</div>
    </section>

    <section id="view-route" class="view-panel">
      {route_section_html}
    </section>

    <section id="view-datacheck" class="view-panel">
      {datacheck_section_html}
    </section>

    <section id="view-upload" class="view-panel">
      {upload_section_html}
    </section>
  </main>

  <script id="proposal-payload" type="application/json">{proposal_json}</script>
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
