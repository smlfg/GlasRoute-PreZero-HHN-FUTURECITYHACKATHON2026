"""Today-First hero block for the dispatcher view.

All numbers are taken from the verified pipeline snapshot; no UUIDs are shown.
"""

from __future__ import annotations

import html
from typing import Any, Mapping


def _pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _num(value: float | int | None, digits: int = 1) -> str:
    if value is None:
        return "-"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _int(value: Any) -> str:
    if value is None:
        return "-"
    return f"{int(value):,}".replace(",", ".")


def _build_process_chain(current_step: str = "Auswahl") -> str:
    steps = [
        ("Daten", "Daten"),
        ("Prognose", "Prognose"),
        ("Auswahl", "Auswahl"),
        ("Tour", "Tour"),
        ("Freigabe", "Freigabe"),
    ]
    items: list[str] = []
    for idx, (key, label) in enumerate(steps, start=1):
        active = key == current_step
        cls = "hero-chain-step hero-chain-active" if active else "hero-chain-step"
        items.append(
            f'<div class="{cls}"><span class="hero-chain-num">{idx}</span>'
            f'<span class="hero-chain-label">{html.escape(label)}</span></div>'
        )
    return '<div class="hero-chain">' + "".join(items) + "</div>"


def _excluded_reason(snapshot: Mapping[str, Any], row: Mapping[str, Any] | None = None) -> str:
    metrics = snapshot.get("metrics", {})
    num_stops = int(metrics.get("num_stops") or 0)
    max_stops = metrics.get("max_stops")
    if max_stops is not None and num_stops >= int(max_stops):
        return f"Kapazität voll (Stopplimit {max_stops})"
    max_shift = float(metrics.get("max_vehicle_shift_hours") or 0.0)
    shift_cap = float(metrics.get("max_shift_hours_limit") or 8.0)
    if max_shift >= shift_cap - 0.05:
        return f"Schicht voll ({_num(max_shift, 2)} h)"
    if row and str(row.get("excluded_reason", "")).strip():
        return str(row["excluded_reason"])
    return "Kapazität / Schicht voll"


def compute_hero_metrics(
    snapshot: Mapping[str, Any],
    status_quo_km: float | None = None,
) -> dict[str, Any]:
    """Derive hero KPIs from a pipeline snapshot (full container set, not UI top-15)."""
    metrics = snapshot.get("metrics", {})
    hero_data = snapshot.get("hero") or {}

    today_overfull = int(snapshot.get("today_overfull_containers") or 0)
    in_tour_overfull = int(hero_data.get("in_tour_overfull_count") or 0)
    excluded = list(hero_data.get("excluded_overflow") or [])

    planned_km = float(metrics.get("planned_km") or 0.0)
    status_km = float(metrics.get("full_round_km") or 0.0)
    if status_km <= 0 and status_quo_km is not None:
        status_km = float(status_quo_km)

    return {
        "today_overfull": today_overfull,
        "in_tour_overfull": in_tour_overfull,
        "planned_km": round(planned_km, 2),
        "status_quo_km": round(status_km, 2),
        "vehicles": int(metrics.get("vehicles_needed") or 0),
        "shift_hours": round(float(metrics.get("max_vehicle_shift_hours") or 0.0), 2),
        "tons": round(float(metrics.get("t_collected") or 0.0), 2),
        "excluded_overflow": excluded,
        "process_step": str(hero_data.get("process_step") or "Auswahl"),
    }


def build_hero_html(snapshot: Mapping[str, Any], status_quo_km: float | None = None) -> str:
    """Render the value-proposition hero above the dispatcher view."""
    date_de = html.escape(str(snapshot.get("date_de", "")))
    stand_de = html.escape(str(snapshot.get("stand_de", "")))
    hm = compute_hero_metrics(snapshot, status_quo_km=status_quo_km)

    today_overfull = hm["today_overfull"]
    in_tour_overfull = hm["in_tour_overfull"]
    excluded = hm["excluded_overflow"]

    planned_km = hm["planned_km"]
    status_km = hm["status_quo_km"]
    vehicles = hm["vehicles"]
    longest_shift = hm["shift_hours"]
    tons = hm["tons"]
    chain_step = hm["process_step"]

    excluded_rows = "".join(
        f"<tr><td>{html.escape(str(r.get('site_title', '-')))}</td>"
        f"<td>{html.escape(str(r.get('mat_label', '-')))}</td>"
        f"<td>{_num(r.get('today_pct'), 0)} %</td>"
        f"<td>{html.escape(_excluded_reason(snapshot, r))}</td></tr>"
        for r in excluded[:15]
    )
    excluded_section = ""
    if excluded:
        excluded_section = f"""
        <div class="hero-excluded">
          <strong>Heute überlaufend, aber nicht in dieser Tour:</strong>
          <div class="table-wrap" style="margin-top:8px;margin-bottom:0;">
            <table>
              <thead><tr><th>Standort</th><th>Glasart</th><th>Füllstand heute</th><th>Grund</th></tr></thead>
              <tbody>{excluded_rows}</tbody>
            </table>
          </div>
        </div>
        """

    return f"""
    <div class="hero-block">
      <p class="hero-eyebrow">GlasRoute &middot; {stand_de}</p>
      <h2 class="hero-headline">Heute drohen <strong>{_int(today_overfull)} Container</strong> bis {date_de} überzulaufen</h2>
      <p class="hero-sub">
        <strong>{_int(in_tour_overfull)} davon</strong> in der heutigen Tour &middot;
        <strong>{_num(planned_km, 1)} km</strong> statt {_num(status_km, 1)} km (Status quo) &middot;
        passt in <strong>{_int(vehicles)} LKW</strong> &middot; <strong>{_num(longest_shift, 2)} h</strong> Schicht &middot; <strong>{_num(tons, 2)} t</strong>
      </p>
      <p class="hero-sentence">
        Wir leeren, was voll wird, nicht was im Plan steht – unter Kapazität und Arbeitszeit.
      </p>
      {_build_process_chain(chain_step)}
      {excluded_section}
    </div>
    """
