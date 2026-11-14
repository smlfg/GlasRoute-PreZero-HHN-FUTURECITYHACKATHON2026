"""Full tours per vehicle: Betriebshof -> Stopps/Entladen -> Betriebshof, with km and time per leg.

Pure view over ``route_data`` from ``routing.build_route``; no routing logic is duplicated.
"""

from __future__ import annotations

import csv
import html
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

from prezero import routing

YARD_START = "Start Betriebshof"
YARD_END = "Ende Betriebshof"
UNLOAD_LABEL = "Entladen am Glas-Entsorgungsplatz"
ASSUMED_NOTE = "angenommen (Koordinaten von PreZero nicht geliefert)"

TOUR_CSV_COLUMNS = [
    "vehicle", "seq", "row_type", "label", "location_id", "lat", "lon",
    "load_t", "leg_km", "leg_min", "cumulative_km", "note",
]


def locations_assumed(cfg: routing.OperationalConfig) -> dict[str, bool]:
    """True while yard/disposal still equal the built-in placeholder defaults."""
    d = routing.OperationalConfig()
    return {
        "yard": tuple(cfg.yard_depot) == tuple(d.yard_depot),
        "disposal": tuple(cfg.disposal_depot) == tuple(d.disposal_depot),
    }


def build_tours(route_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return one tour per vehicle with explicit yard start/end rows."""
    cfg = routing.OperationalConfig.from_dict(route_data.get("assumptions") or {})
    assumed = locations_assumed(cfg)
    yard = (float(cfg.yard_depot[0]), float(cfg.yard_depot[1]))
    by_vehicle: dict[int, list[Mapping[str, Any]]] = {}
    for s in sorted(route_data.get("stops") or [], key=lambda s: int(s["order"])):
        by_vehicle.setdefault(int(s.get("vehicle", 1)), []).append(s)

    tours: list[dict[str, Any]] = []
    for veh, stops in sorted(by_vehicle.items()):
        rows: list[dict[str, Any]] = [{
            "row_type": "start", "label": YARD_START, "location_id": "yard",
            "lat": yard[0], "lon": yard[1], "load_t": 0.0, "leg_km": 0.0, "leg_min": 0.0,
            "note": ASSUMED_NOTE if assumed["yard"] else "",
        }]
        last = yard
        for s in stops:
            km = float(s.get("leg_km", 0.0))
            drive = routing.drive_time_min(km, cfg)
            if s.get("stop_type") == "unload":
                rows.append({
                    "row_type": "unload",
                    "label": f"Entladen ({float(s.get('unloaded_kg', 0.0)) / 1000:.1f} t geladen)",
                    "location_id": "disposal_depot", "lat": float(s["lat"]), "lon": float(s["lon"]),
                    "load_t": float(s.get("unloaded_kg", 0.0)) / 1000.0,
                    "leg_km": km, "leg_min": drive + float(cfg.unload_time_min),
                    "note": (ASSUMED_NOTE if assumed["disposal"] else "") or UNLOAD_LABEL,
                })
            else:
                service = float(cfg.stop_setup_min) + int(s.get("critical_bins", 1)) * float(cfg.lift_time_per_bin_min)
                rows.append({
                    "row_type": "collection", "label": str(s["Location_id"]),
                    "location_id": str(s["Location_id"]), "lat": float(s["lat"]), "lon": float(s["lon"]),
                    "load_t": float(s.get("load_kg", 0.0)) / 1000.0,
                    "leg_km": km, "leg_min": drive + service, "note": "",
                })
            last = (float(s["lat"]), float(s["lon"]))
        back = routing.road_distance_km(last[0], last[1], yard[0], yard[1], cfg)
        rows.append({
            "row_type": "end", "label": YARD_END, "location_id": "yard",
            "lat": yard[0], "lon": yard[1], "load_t": 0.0,
            "leg_km": back, "leg_min": routing.drive_time_min(back, cfg),
            "note": ASSUMED_NOTE if assumed["yard"] else "",
        })
        cum = 0.0
        for i, r in enumerate(rows, 1):
            cum += r["leg_km"]
            r.update(vehicle=veh, seq=i, cumulative_km=round(cum, 3))
            r["leg_km"] = round(r["leg_km"], 3)
            r["leg_min"] = round(r["leg_min"], 1)
            r["load_t"] = round(r["load_t"], 2)
        tours.append({"vehicle": veh, "rows": rows, "total_km": round(cum, 3),
                      "total_min": round(sum(r["leg_min"] for r in rows), 1)})
    return tours


def export_tour_csv(route_data: Mapping[str, Any], output_path: str | Path) -> Path:
    """Driver export: all rows incl. Start/Entladen/Ende Betriebshof."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=TOUR_CSV_COLUMNS)
        w.writeheader()
        for tour in build_tours(route_data):
            w.writerows({k: r.get(k, "") for k in TOUR_CSV_COLUMNS} for r in tour["rows"])
    return path


def tour_html(route_data: Mapping[str, Any]) -> str:
    """Printable stop list (Fahrer + Disponentin) as an HTML fragment."""
    from html import escape

    out: list[str] = []
    for t in build_tours(route_data):
        out.append(f"<h3>Fahrzeug {t['vehicle']} &ndash; {t['total_km']:.1f} km, {t['total_min']:.0f} min</h3>")
        out.append("<table><tr><th>#</th><th>Halt</th><th>km</th><th>min</th><th>Hinweis</th></tr>")
        for r in t["rows"]:
            out.append(
                f"<tr class='{r['row_type']}'><td>{r['seq']}</td><td>{escape(r['label'])}</td>"
                f"<td>{r['leg_km']:.1f}</td><td>{r['leg_min']:.0f}</td><td>{escape(r['note'])}</td></tr>"
            )
        out.append("</table>")
    return "\n".join(out)


def interleave(route_data: Mapping[str, Any]) -> list[tuple[int | None, dict[str, Any]]]:
    """Stops in driving order with synthetic yard rows (stop_type depot_start/depot_end).

    Returns ``(index into route_data["stops"], row)``; the index is ``None`` for yard rows.
    """
    stops = list(route_data.get("stops") or [])
    tours = {t["vehicle"]: t for t in build_tours(route_data)}
    ordered = sorted(range(len(stops)), key=lambda i: int(stops[i]["order"]))
    out: list[tuple[int | None, dict[str, Any]]] = []
    cum = 0.0
    seen: set[int] = set()
    last_veh: int | None = None

    def yard(kind: str, veh: int, tour_row: Mapping[str, Any], cumulative: float) -> dict[str, Any]:
        return {
            "stop_type": kind, "Location_id": "yard", "vehicle": veh,
            "label": tour_row["label"], "note": tour_row["note"],
            "lat": tour_row["lat"], "lon": tour_row["lon"],
            "leg_km": tour_row["leg_km"], "leg_min": tour_row["leg_min"],
            "cumulative_km": round(cumulative, 3),
        }

    for i in ordered:
        veh = int(stops[i].get("vehicle", 1))
        if veh != last_veh:
            if last_veh is not None:
                end = tours[last_veh]["rows"][-1]
                cum += end["leg_km"]
                out.append((None, yard("depot_end", last_veh, end, cum)))
            out.append((None, yard("depot_start", veh, tours[veh]["rows"][0], cum)))
            last_veh = veh
        out.append((i, dict(stops[i])))
        cum = float(stops[i].get("cumulative_km", cum))
    if last_veh is not None:
        end = tours[last_veh]["rows"][-1]
        out.append((None, yard("depot_end", last_veh, end, cum + end["leg_km"])))
    return out


# ---------------------------------------------------------------------------
# Driver-device exports: GPX route and Google Maps deep-links.
# ---------------------------------------------------------------------------

GOOGLE_MAPS_MAX_WAYPOINTS = 9  # documented limit for Maps URLs on desktop


def _xml_escape(text: str) -> str:
    """Escape text for XML element content / attributes."""
    return html.escape(str(text), quote=True)


def build_gpx(route_data: Mapping[str, Any]) -> str:
    """Return a GPX 1.1 document with one ordered route per vehicle.

    Each route contains the Betriebshof start, every collection/unload stop,
    and the Betriebshof end as routepoints (`<rtept>`). Waypoints (`<wpt>`)
    are also emitted for compatibility with Garmin/OsmAnd imports.
    """
    tours = build_tours(route_data)
    date = str(route_data.get("date") or "")
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        '<gpx version="1.1" creator="GlasRoute" xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 '
        'http://www.topografix.com/GPX/1/1/gpx.xsd">',
    ]
    if date:
        lines.append(f"  <metadata><name>{_xml_escape(date)}</name></metadata>")

    waypoints = []
    routes = []
    for tour in tours:
        veh = tour["vehicle"]
        routes.append(f'  <rte><name>{_xml_escape(f"Tour {date} Fahrzeug {veh}")}</name>')
        for r in tour["rows"]:
            lat = float(r["lat"])
            lon = float(r["lon"])
            label = str(r["label"])
            note = str(r.get("note", ""))
            routes.append(f'    <rtept lat="{lat:.6f}" lon="{lon:.6f}">')
            routes.append(f"      <name>{_xml_escape(label)}</name>")
            if note:
                routes.append(f"      <desc>{_xml_escape(note)}</desc>")
            routes.append("    </rtept>")
            # Also emit as waypoint so devices/apps that prefer waypoints still see every stop.
            waypoints.append(f'  <wpt lat="{lat:.6f}" lon="{lon:.6f}">')
            waypoints.append(f"    <name>{_xml_escape(label)}</name>")
            if note:
                waypoints.append(f"    <desc>{_xml_escape(note)}</desc>")
            waypoints.append("  </wpt>")
        routes.append("  </rte>")

    lines.extend(waypoints)
    lines.extend(routes)
    lines.append("</gpx>")
    return "\n".join(lines)


def build_google_maps_legs(
    route_data: Mapping[str, Any],
    max_waypoints: int = GOOGLE_MAPS_MAX_WAYPOINTS,
) -> dict[int, list[str]]:
    """Return per-vehicle Google Maps direction URLs, split into legs if needed.

    Google Maps URLs support at most ``max_waypoints`` intermediate waypoints
    between origin and destination. If a tour has more points, it is split into
    consecutive legs where the last point of leg *n* is the first point of
    leg *n+1*.
    """
    if max_waypoints < 0:
        raise ValueError("max_waypoints must be nonnegative")
    tours = build_tours(route_data)
    result: dict[int, list[str]] = {}
    for tour in tours:
        points = [
            {"lat": float(r["lat"]), "lon": float(r["lon"]), "label": str(r["label"])}
            for r in tour["rows"]
        ]
        n = len(points)
        legs: list[str] = []
        if n == 0:
            result[tour["vehicle"]] = legs
            continue

        def coord(p: dict[str, Any]) -> str:
            return f"{p['lat']:.6f},{p['lon']:.6f}"

        start = 0
        while start < n - 1:
            # origin + max_waypoints intermediates + destination
            end = min(start + max_waypoints + 1, n - 1)
            origin = coord(points[start])
            destination = coord(points[end])
            waypoints = "|".join(coord(points[i]) for i in range(start + 1, end))
            url = f"https://www.google.com/maps/dir/?api=1&origin={quote(origin, safe=',')}&destination={quote(destination, safe=',')}"
            if waypoints:
                url += f"&waypoints={quote(waypoints, safe=',|')}"
            legs.append(url)
            start = end
        result[tour["vehicle"]] = legs
    return result
