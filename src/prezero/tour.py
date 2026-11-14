"""Full tours per vehicle: Betriebshof -> Stopps/Entladen -> Betriebshof, with km and time per leg.

Pure view over ``route_data`` from ``routing.build_route``; no routing logic is duplicated.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping

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
