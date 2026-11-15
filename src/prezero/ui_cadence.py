"""The GlasRoute UI around the container (producer-consumer cadence).

**This module computes nothing.** Every number comes from the scenario output
of the model lane (W3):

* ``data/outputs/scenarios/summary.json``            — the main table
* ``data/outputs/scenarios/<id>__<time_model>_daily.csv`` — the daily course
* ``data/outputs/scenarios/containers.csv``           — the cadence per container

If a file is missing, the view says so ("Szenariodaten fehlen") and shows no
substitute numbers.

The surface is built around the **container**, not around the map:

1. **Container list** — the start view. Header KPIs, one row per container with
   fill rate, current cadence, proposed cadence, next due date and status. The
   dispatcher approves a cadence change per row or for all rows at once.
2. **Container detail** — the sawtooth of all measurements (the fill rises and
   resets at every emptying) plus one plain-German sentence that explains the
   cadence change.
3. **Diese Woche** — the containers due this week, grouped by area. Map and
   route are only a collapsible extra.

Everything is generated statically (no server, no live computation in the
browser). Assumptions are labelled "Annahme".
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

#: Default location of the scenario output (owned by the model lane).
DEFAULT_SCENARIO_DIR = Path("data/outputs/scenarios")

#: Label of the material types (German).
MATERIAL_LABELS: dict[str, str] = {
    "white": "Weißglas",
    "green": "Grünglas",
    "brown": "Braunglas",
}

#: Label of the areas.
AREA_LABELS: dict[str, str] = {
    "urban": "Stadt (Heilbronn)",
    "rural": "Land (Flein, Lauffen)",
}

#: Status labels and the row class behind them.
STATUS_LABELS: dict[str, str] = {
    "red": "Kritisch",
    "yellow": "Zu oft geleert",
    "ok": "Im Takt",
}

#: Fill level at which a container is emptied (the "Puffer"), in percent.
DEFAULT_EMPTY_AT_PCT = 80.0

#: Longest allowed cadence in days (Annahme) — used for the boundary note.
DEFAULT_MAX_CADENCE_DAYS = 14.0

#: Minimum allowed cadence in days (Annahme).
DEFAULT_MIN_CADENCE_DAYS = 3.0

#: A container found below this level was emptied too early (yellow).
LOW_FILL_PCT = 30.0

#: Overflow threshold (110 % = "overfull" in the data).
MAX_FILL_PCT = 110.0

#: Hint shown when the scenario output is missing.
MISSING_HINT = "Szenariodaten fehlen"


def _esc(value: Any) -> str:
    return html.escape(str(value))


def _de(value: Any, digits: int = 1) -> str:
    """German number format (decimal comma, thousands point)."""
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number != number or number in (float("inf"), float("-inf")):
        return "-"
    return f"{number:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _date_de(value: Any) -> str:
    """ISO date -> German date (TT.MM.JJJJ)."""
    if value is None:
        return "–"
    try:
        stamp = pd.Timestamp(value)
    except (ValueError, TypeError):
        return str(value)
    if pd.isna(stamp):
        return "–"
    return stamp.strftime("%d.%m.%Y")


def _material_label(material: str) -> str:
    return MATERIAL_LABELS.get(str(material).lower(), str(material).title())


def _area_label(area: str) -> str:
    return AREA_LABELS.get(str(area), str(area).title())


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(str(status), "Im Takt")


def _site_title(location_id: str, material: str) -> str:
    """Human-readable title of a container (the ID stays the technical key)."""
    return f"{_material_label(material)} · Standort {str(location_id)[:8]}"


# --- reading the model lane's output -------------------------------------------------------


class ScenarioData:
    """The scenario output of the model lane — read, never computed.

    ``available`` is False when the files are missing; the views then say so
    instead of showing substitute numbers.
    """

    def __init__(self, scenario_dir: str | Path = DEFAULT_SCENARIO_DIR) -> None:
        self.dir = Path(scenario_dir)
        self.summary: dict[str, Any] | None = None
        self.containers: pd.DataFrame | None = None
        self.daily: dict[tuple[str, str], pd.DataFrame] = {}
        self.missing: list[str] = []

        summary_path = self.dir / "summary.json"
        containers_path = self.dir / "containers.csv"
        if summary_path.is_file():
            try:
                self.summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.missing.append("summary.json")
        else:
            self.missing.append("summary.json")

        if containers_path.is_file():
            try:
                self.containers = pd.read_csv(containers_path, dtype={"location_id": str})
            except (OSError, ValueError):
                self.missing.append("containers.csv")
        else:
            self.missing.append("containers.csv")

        # The daily courses of the scenarios named in the summary.
        if self.summary:
            for scenario in self.summary.get("scenarios", []):
                scenario_id = str(scenario.get("id", ""))
                time_model = str(scenario.get("time_model", "real"))
                path = self.dir / f"{scenario_id}__{time_model}_daily.csv"
                if path.is_file():
                    try:
                        self.daily[(scenario_id, time_model)] = pd.read_csv(path)
                    except (OSError, ValueError):
                        self.missing.append(path.name)
                else:
                    self.missing.append(path.name)

    @property
    def available(self) -> bool:
        """True when the summary and the container table could be read."""
        return self.summary is not None and self.containers is not None

    @property
    def scenarios(self) -> list[dict[str, Any]]:
        return list(self.summary.get("scenarios", [])) if self.summary else []

    def scenario(self, scenario_id: str, time_model: str = "real") -> dict[str, Any] | None:
        """One scenario row of the summary."""
        for scenario in self.scenarios:
            if (
                str(scenario.get("id")) == scenario_id
                and str(scenario.get("time_model", "real")) == time_model
            ):
                return scenario
        return None

    @property
    def period(self) -> dict[str, Any]:
        return dict(self.summary.get("period", {})) if self.summary else {}

    @property
    def produced_t(self) -> float:
        return float(self.summary.get("produced_t", 0.0)) if self.summary else 0.0


def _missing_block(what: str, missing: Sequence[str]) -> str:
    """Visible hint that the scenario data is missing — no substitute numbers."""
    listed = ", ".join(sorted(set(missing))) if missing else "unbekannt"
    return f"""
    <div class="cadence-missing" role="alert">
      <strong>{_esc(MISSING_HINT)}</strong>
      <p class="muted">
        {_esc(what)} braucht die Ausgabe des Modell-Lanes
        (<code>data/outputs/scenarios/</code>). Es fehlt: {_esc(listed)}.
        Es werden bewusst keine Ersatzzahlen gezeigt.
      </p>
    </div>
    """


# --- container table ----------------------------------------------------------------------


def _prepare_containers(containers: pd.DataFrame) -> pd.DataFrame:
    """Add the derived columns the views need (reading, not computing a model)."""
    work = containers.copy()
    work["location_id"] = work["location_id"].astype(str)
    work["material"] = work["material"].astype(str).str.lower()

    if "area" not in work.columns:
        work["area"] = "urban"
    work["area"] = work["area"].astype(str).str.strip().str.lower().replace("", "urban")

    numeric_columns = (
        "rate_pct_per_day",
        "cadence_days_T",
        "emptyings_status_quo",
        "emptyings_mentor",
        "avg_fill_status_quo_pct",
        "avg_fill_mentor_pct",
        "overflow_events_status_quo",
        "skip_14d",
    )
    for column in numeric_columns:
        if column not in work.columns:
            work[column] = 0.0
        work[column] = pd.to_numeric(work[column], errors="coerce").astype(float).fillna(0.0)

    # The cadence realised today: the period divided by the number of emptyings
    # of the status quo — a read of two given numbers, not a model of its own.
    period_days = _period_days()
    emptyings = work["emptyings_status_quo"].replace(0.0, float("nan"))
    with np.errstate(divide="ignore", invalid="ignore"):
        current = period_days / emptyings
    work["current_cadence_days"] = current.astype(float)

    # The proposed cadence is the cadence of the model lane (a read).
    work["proposed_cadence_days"] = work["cadence_days_T"].astype(float)

    # Status from the data of the model lane:
    # * yellow — emptied too early: it was found below LOW_FILL_PCT in the
    #   status quo (the mentor cadence skipped it often),
    # * red   — overflow events in the status quo,
    # * ok    — everything else.
    work["status"] = "ok"
    too_early = work["avg_fill_status_quo_pct"] < LOW_FILL_PCT
    work.loc[too_early, "status"] = "yellow"
    work.loc[work["overflow_events_status_quo"] > 0, "status"] = "red"

    return work


def _period_days() -> float:
    """Days of the replay period — set by :func:`load_scenario_data`."""
    return _PERIOD_DAYS[0]


_PERIOD_DAYS: list[float] = [349.0]


def _days_until_next_emptying(work: pd.DataFrame) -> pd.Series:
    """Days until the next emptying, read off the period, the emptyings and the cadence.

    The contract carries the cadence and the number of emptyings of the status
    quo over the period. The next emptying follows from them: the share of the
    period already used, plus one more cadence.
    """
    period_days = _period_days()
    emptyings = work["emptyings_status_quo"].replace(0.0, float("nan"))
    used = period_days / emptyings
    remainder = (period_days - used).fillna(0.0).clip(lower=0.0)
    cadence = work["cadence_days_T"].replace(0.0, float("nan"))
    steps = (remainder / cadence).fillna(0.0)
    return (steps.apply(lambda s: int(s) + 1) * cadence).fillna(0.0)


def load_scenario_data(scenario_dir: str | Path = DEFAULT_SCENARIO_DIR) -> ScenarioData:
    """Read the scenario output of the model lane."""
    data = ScenarioData(scenario_dir)
    period = data.period
    if period.get("days"):
        _PERIOD_DAYS[0] = float(period["days"])
    return data


# --- View 1: container list ---------------------------------------------------------------


def compute_header_kpis(
    containers: pd.DataFrame,
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Header KPIs of the container list — all read from the model lane's output."""
    if containers is None or containers.empty:
        return {
            "avg_fill_at_emptying_pct": 0.0,
            "overflow_events": 0,
            "emptyings_saved": 0,
            "containers": 0,
            "cadence_change_needed": 0,
            "emptyings_saved_source": "",
            "emptyings_status_quo_total": 0,
        }

    # Ø fill at emptying: weighted by the emptyings of the status quo.
    fills = pd.to_numeric(containers["avg_fill_status_quo_pct"], errors="coerce").fillna(0.0)
    emptyings = pd.to_numeric(
        containers["emptyings_status_quo"], errors="coerce"
    ).fillna(0.0)
    total_emptyings = float(emptyings.sum())
    avg_fill = (
        float((fills * emptyings).sum() / total_emptyings) if total_emptyings else 0.0
    )

    overflow_events = int(
        pd.to_numeric(
            containers["overflow_events_status_quo"], errors="coerce"
        ).fillna(0.0).sum()
    )

    # Cadence change needed: the proposed cadence differs from the current one.
    current = pd.to_numeric(containers["current_cadence_days"], errors="coerce")
    proposed = pd.to_numeric(containers["proposed_cadence_days"], errors="coerce")
    change_needed = int(
        ((proposed - current).abs() >= 1.0).sum()
    )

    # Emptyings saved: from the summary (the comparison of the scenarios).
    emptyings_saved = 0
    source = ""
    if summary:
        scenarios = [
            s
            for s in summary.get("scenarios", [])
            if str(s.get("time_model", "real")) == "real"
        ]
        candidates = [s for s in scenarios if s.get("id") != "d_status_quo"]
        if candidates:
            best = max(
                candidates, key=lambda s: s.get("emptyings_saved_vs_status_quo", 0)
            )
            emptyings_saved = int(best.get("emptyings_saved_vs_status_quo", 0))
            source = str(best.get("label", best.get("id", "")))

    return {
        "avg_fill_at_emptying_pct": round(avg_fill, 1),
        "overflow_events": overflow_events,
        "emptyings_saved": emptyings_saved,
        "containers": int(len(containers)),
        "cadence_change_needed": change_needed,
        "emptyings_saved_source": source,
        "emptyings_status_quo_total": int(total_emptyings),
    }


def _sort_table(table: pd.DataFrame) -> pd.DataFrame:
    """Default sort: "cadence change needed" — the biggest deviation first."""
    work = table.copy()
    current = pd.to_numeric(work["current_cadence_days"], errors="coerce")
    proposed = pd.to_numeric(work["proposed_cadence_days"], errors="coerce")
    work["delta"] = proposed - current
    work["_rank"] = work["status"].map({"red": 0, "yellow": 1}).fillna(2)
    work = work.sort_values(
        ["_rank", "delta"], ascending=[True, False], na_position="last"
    )
    return work.drop(columns=["_rank"])


def _render_container_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    """One table row per container."""
    out: list[str] = []
    for row in rows:
        status = str(row.get("status", "ok"))
        current = row.get("current_cadence_days")
        proposed = row.get("proposed_cadence_days")
        rate = row.get("rate_pct_per_day")
        location = str(row.get("location_id", ""))
        material = str(row.get("material", ""))

        current_txt = (
            f"{_de(current, 0)} Tage" if current is not None and current == current else "–"
        )
        proposed_txt = f"{_de(proposed, 0)} Tage"

        change_txt = ""
        note = ""
        if current is not None and current == current:
            delta = float(proposed) - float(current)
            if abs(delta) >= 1.0:
                sign = "+" if delta > 0 else "−"
                change_txt = f"{sign}{_de(abs(delta), 0)}"
            if float(proposed) >= DEFAULT_MAX_CADENCE_DAYS - 0.5:
                note = "am längsten erlaubten Takt"

        approve_btn = (
            '<button type="button" class="cadence-approve-btn" '
            f'data-location="{_esc(location)}" data-material="{_esc(material)}" '
            'title="Taktänderung freigeben">Freigeben</button>'
        )
        note_html = f'<span class="cadence-note">{_esc(note)}</span>' if note else ""

        out.append(
            f'<tr class="cadence-row status-{_esc(status)}" '
            f'data-location="{_esc(location)}" data-material="{_esc(material)}" '
            f'data-status="{_esc(status)}">'
            f'<td class="cadence-site"><a href="#cadence-detail" class="cadence-detail-link" '
            f'data-location="{_esc(location)}" data-material="{_esc(material)}">'
            f"{_esc(_site_title(location, material))}</a>"
            f'<span class="cadence-id">{_esc(location[:8])}</span></td>'
            f'<td>{_esc(_area_label(str(row.get("area", "urban"))))}</td>'
            f'<td class="num">{_de(rate, 1)} %/Tag</td>'
            f"<td class=\"num\">{_esc(current_txt)}</td>"
            f"<td class=\"num\">{_esc(proposed_txt)}{note_html}</td>"
            f'<td class="num">{_esc(change_txt)}</td>'
            f'<td class="num">{_de(row.get("emptyings_status_quo"), 0)}</td>'
            f'<td><span class="status-pill status-{_esc(status)}">'
            f"{_esc(_status_label(status))}</span></td>"
            f"<td>{approve_btn}</td>"
            "</tr>"
        )
    return "".join(out)


def build_container_list_html(
    containers: pd.DataFrame | None,
    summary: Mapping[str, Any] | None,
    reference_date: str,
    missing: Sequence[str] = (),
) -> str:
    """View 1 — the container list (the start view)."""
    if containers is None or containers.empty:
        return _missing_block("Die Container-Liste", missing)

    kpis = compute_header_kpis(containers, summary)
    ordered = _sort_table(containers)
    rows = ordered.to_dict(orient="records")

    status_counts = ordered["status"].value_counts().to_dict()

    saved_sub = "bei gleichem Tonnage (Szenariovergleich)"
    if kpis.get("emptyings_saved_source"):
        saved_sub = f"bei gleichem Tonnage · {_esc(kpis['emptyings_saved_source'])}"

    kpi_cards = f"""
      <div class="card kpi-cadence">
        <div class="label">Ø Füllstand bei Leerung</div>
        <div class="value">{_de(kpis['avg_fill_at_emptying_pct'], 1)} %</div>
        <div class="sub">gewichtet nach {_de(kpis['emptyings_status_quo_total'], 0)} Leerungen</div>
      </div>
      <div class="card kpi-cadence">
        <div class="label">Überläufe</div>
        <div class="value">{_de(kpis['overflow_events'], 0)}</div>
        <div class="sub">Überlauf-Ereignisse im Status quo</div>
      </div>
      <div class="card kpi-cadence">
        <div class="label">Eingesparte Leerungen</div>
        <div class="value">{_de(kpis['emptyings_saved'], 0)}</div>
        <div class="sub">{_esc(saved_sub)}</div>
      </div>
      <div class="card kpi-cadence">
        <div class="label">Taktänderung nötig</div>
        <div class="value">{_de(kpis['cadence_change_needed'], 0)}</div>
        <div class="sub">von {_de(kpis['containers'], 0)} Containern</div>
      </div>
    """

    filter_buttons = "".join(
        f'<button type="button" class="cadence-filter-btn{" active" if key == "all" else ""}" '
        f'data-filter="{_esc(key)}">{_esc(label)}</button>'
        for key, label in (
            ("all", f"Alle ({_de(kpis['containers'], 0)})"),
            ("red", f"Kritisch ({_de(status_counts.get('red', 0), 0)})"),
            ("yellow", f"Zu oft geleert ({_de(status_counts.get('yellow', 0), 0)})"),
            ("ok", f"Im Takt ({_de(status_counts.get('ok', 0), 0)})"),
        )
    )

    return f"""
    <section id="view-cadence" class="view-panel cadence-view active">
      <div class="section-head">
        <h2>Container &amp; Takt</h2>
        <p class="muted">
          Jeder Container ist ein Erzeuger-Verbraucher-System: Er füllt sich mit
          <b>r</b> % pro Tag und wird alle <b>T</b> Tage geleert.
          <b>T = (Kapazität − Puffer) / r</b>, nach jeder Messung neu berechnet.
          Die Route ist nur eine nachgelagerte Bündelung.
          Stand {_esc(_date_de(reference_date))}.
        </p>
      </div>

      <div class="kpi-grid cadence-kpi-grid">{kpi_cards}</div>

      <div class="cadence-toolbar">
        <div class="cadence-filters" role="group" aria-label="Container filtern">
          {filter_buttons}
        </div>
        <div class="cadence-toolbar-actions">
          <button type="button" class="primary-btn" id="cadence-approve-all-btn">
            Alle Taktänderungen übernehmen
          </button>
          <span id="cadence-approval-status" class="badge pending" role="status">
            Status: Vorschlag
          </span>
        </div>
      </div>

      <div class="table-scroll">
        <table class="cadence-table" id="cadence-table">
          <caption class="sr-only">
            Container mit Füllrate, aktuellem Takt, vorgeschlagenem Takt und Status
          </caption>
          <thead>
            <tr>
              <th scope="col">Container / Standort</th>
              <th scope="col">Gebiet</th>
              <th scope="col">Füllrate</th>
              <th scope="col">Takt heute</th>
              <th scope="col">Takt neu</th>
              <th scope="col">Änderung</th>
              <th scope="col">Leerungen (Status quo)</th>
              <th scope="col">Status</th>
              <th scope="col"><span class="sr-only">Freigabe</span></th>
            </tr>
          </thead>
          <tbody id="cadence-table-body">{_render_container_rows(rows)}</tbody>
        </table>
      </div>

      <p class="muted">
        Sortierung: erst kritisch, dann die größte Taktänderung.
        <b>Gelb</b> = im Mentor-Takt oft übersprungen (zu selten geleert).
        <b>Rot</b> = im Status quo mit Überlauf-Ereignissen.
        Annahme: Puffer {_de(DEFAULT_EMPTY_AT_PCT, 0)} %,
        Takt zwischen {_de(DEFAULT_MIN_CADENCE_DAYS, 0)} und
        {_de(DEFAULT_MAX_CADENCE_DAYS, 0)} Tagen.
      </p>
    </section>
    """


# --- View 2: container detail ------------------------------------------------------------


def _measurement_history(
    readings_df: pd.DataFrame | None, location_id: str, material: str
) -> list[tuple[pd.Timestamp, float]]:
    """The measured fill levels of one container (the sawtooth's data).

    Read from the cleaned readings of the pipeline — the measurement series
    itself, not a model of it.
    """
    if readings_df is None or readings_df.empty:
        return []
    work = readings_df
    work = work[
        (work["Location_id"].astype(str) == str(location_id))
        & (work["material_type"].astype(str).str.lower() == str(material).lower())
    ]
    if work.empty:
        return []
    work = work.sort_values("date")
    return [
        (pd.Timestamp(row.date).normalize(), float(row.fill_level_numeric))
        for row in work.itertuples(index=False)
    ]


def _sawtooth_svg(history: Sequence[Any], width: int = 900, height: int = 260) -> str:
    """Sawtooth chart of all measurements: the fill rises, resets at every emptying.

    ``history`` may be a sequence of ``(Timestamp, level)`` tuples or of
    ``[iso_date, level]`` lists (the JSON form of the payload).
    """
    if not history:
        return '<div class="empty-note">Keine Messungen für diesen Container.</div>'

    points: list[tuple[pd.Timestamp, float]] = []
    for entry in history:
        ts, level = entry[0], entry[1]
        if isinstance(ts, str):
            ts = pd.Timestamp(ts)
        points.append((pd.Timestamp(ts).normalize(), float(level)))

    first = points[0][0]
    last = points[-1][0]
    span_days = max(1, int((last - first).days))

    pad_left, pad_right, pad_top, pad_bottom = 46, 16, 16, 34
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    def x_of(ts: pd.Timestamp) -> float:
        return pad_left + (pd.Timestamp(ts) - first).days / span_days * plot_w

    def y_of(level: float) -> float:
        clamped = max(0.0, min(110.0, float(level)))
        return pad_top + (1 - clamped / 110.0) * plot_h

    paths: list[str] = []
    dots: list[str] = []
    for i, (ts, level) in enumerate(points):
        x = x_of(ts)
        y = y_of(level)
        if i == 0:
            paths.append(f"M {x:.1f} {y:.1f}")
            paths.append(f"L {x:.1f} {pad_top + plot_h:.1f}")
        else:
            px = x_of(points[i - 1][0])
            py = y_of(points[i - 1][1])
            paths.append(f"M {px:.1f} {pad_top + plot_h:.1f}")
            paths.append(f"L {px:.1f} {py:.1f}")
            paths.append(f"L {x:.1f} {y:.1f}")
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" class="saw-dot"/>')

    grid = []
    for level in (0.0, 50.0, 80.0, 110.0):
        y = y_of(level)
        grid.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{width - pad_right}" y2="{y:.1f}" class="saw-grid"/>'
            f'<text x="{pad_left - 6}" y="{y + 4:.1f}" class="saw-axis" text-anchor="end">{_de(level, 0)} %</text>'
        )

    return f"""
      <svg class="saw-chart" viewBox="0 0 {width} {height}" role="img"
           aria-label="Füllstandverlauf: Anstieg zwischen den Leerungen, Sprung auf 0 % bei jeder Leerung">
        {''.join(grid)}
        <path class="saw-path" d="{' '.join(paths)}"/>
        {''.join(dots)}
        <text x="{pad_left}" y="{height - 10}" class="saw-axis">{_esc(first.strftime('%d.%m.%Y'))}</text>
        <text x="{width - pad_right}" y="{height - 10}" class="saw-axis" text-anchor="end">{_esc(last.strftime('%d.%m.%Y'))}</text>
      </svg>
    """


def _explanation(row: Mapping[str, Any]) -> str:
    """One plain-German sentence explaining the cadence (read from the data)."""
    status = str(row.get("status", "ok"))
    current = row.get("current_cadence_days")
    proposed = row.get("proposed_cadence_days")
    rate = row.get("rate_pct_per_day")
    fill = row.get("avg_fill_status_quo_pct")
    skip = row.get("skip_14d")

    current_txt = (
        f"{_de(current, 0)}" if current is not None and current == current else "?"
    )
    proposed_txt = f"{_de(proposed, 0)}"

    if status == "yellow":
        return (
            f"Im Status quo nur {_de(fill, 0)} % voll geleert, im Mentor-Takt "
            f"{int(skip)}× übersprungen → Takt {current_txt} → {proposed_txt} Tage."
        )
    if status == "red":
        return (
            f"{int(row.get('overflow_events_status_quo', 0))} Überlauf-Ereignisse im "
            f"Status quo → Takt {current_txt} → {proposed_txt} Tage."
        )
    return (
        f"Kommt mit {_de(rate, 1)} % pro Tag, im Status quo zu {_de(fill, 0)} % geleert "
        f"→ Takt {current_txt} → {proposed_txt} Tage."
    )


def _detail_body_html(row: Mapping[str, Any] | None) -> str:
    """Server-side rendering of the container detail (works without JavaScript)."""
    if not row:
        return '<p class="muted">Container wählen, um den Verlauf zu sehen.</p>'

    current = row.get("current_cadence_days")
    current_txt = "–" if current is None or current != current else f"{_de(current, 0)} Tage"

    return f"""
      <div class="cadence-detail-title">
        <h3>{_esc(row.get('site_title', ''))}</h3>
        <span class="status-pill status-{_esc(row.get('status', 'ok'))}">
          {_esc(row.get('status_label', ''))}
        </span>
      </div>
      <p class="muted">
        {_esc(row.get('area_label', ''))} · {_esc(row.get('material_label', ''))} ·
        Füllrate {_de(row.get('rate_pct_per_day'), 1)} %/Tag ·
        {_de(row.get('emptyings_status_quo'), 0)} Leerungen im Status quo ·
        {_de(row.get('skip_14d'), 0)}× im Mentor-Takt übersprungen
      </p>
      <p class="cadence-explain">{_esc(row.get('explanation', ''))}</p>
      <div class="kpi-grid">
        <div class="card"><div class="label">Takt heute</div>
          <div class="value">{_esc(current_txt)}</div></div>
        <div class="card"><div class="label">Takt neu</div>
          <div class="value">{_de(row.get('proposed_cadence_days'), 0)} Tage</div></div>
        <div class="card"><div class="label">Ø Füllstand (Status quo)</div>
          <div class="value">{_de(row.get('avg_fill_status_quo_pct'), 1)} %</div></div>
        <div class="card"><div class="label">Ø Füllstand (Mentor)</div>
          <div class="value">{_de(row.get('avg_fill_mentor_pct'), 1)} %</div></div>
      </div>
      {_sawtooth_svg(row.get('history') or ())}
    """


def build_container_detail_html(
    containers: pd.DataFrame | None,
    readings_df: pd.DataFrame | None,
    reference_date: str,
    missing: Sequence[str] = (),
) -> str:
    """View 2 — the container detail with the sawtooth chart and the sentence."""
    if containers is None or containers.empty:
        return _missing_block("Die Container-Detailansicht", missing)

    payload = containers.to_dict(orient="records")
    for row in payload:
        row["site_title"] = _site_title(row.get("location_id", ""), row.get("material", ""))
        row["material_label"] = _material_label(str(row.get("material", "")))
        row["area_label"] = _area_label(str(row.get("area", "urban")))
        row["status_label"] = _status_label(str(row.get("status", "ok")))
        row["explanation"] = _explanation(row)
        row["history"] = [
            [pd.Timestamp(ts).strftime("%Y-%m-%d"), float(level)]
            for ts, level in _measurement_history(
                readings_df, str(row.get("location_id", "")), str(row.get("material", ""))
            )
        ]

    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    detail_body_html = _detail_body_html(payload[0] if payload else None)
    return f"""
    <section id="view-cadence-detail" class="view-panel cadence-detail-view">
      <div class="section-head">
        <h2>Container im Detail</h2>
        <p class="muted">
          Der Verlauf zeigt alle Messungen: der Füllstand steigt an und springt bei
          jeder Leerung auf 0&nbsp;%. Jeder Besuch ist eine Messung <b>und</b> eine Leerung.
        </p>
      </div>

      <div class="cadence-detail-toolbar">
        <label for="cadence-detail-select">Container wählen:</label>
        <select id="cadence-detail-select" aria-label="Container für die Detailansicht"></select>
      </div>

      <div id="cadence-detail-body" class="cadence-detail-body">
        {detail_body_html}
      </div>

      <script id="cadence-detail-payload" type="application/json">{data_json}</script>
    </section>
    """


# --- View 3: Diese Woche -----------------------------------------------------------------


def build_week_view_html(
    containers: pd.DataFrame | None,
    reference_date: str,
    route_html: str = "",
    route_metrics: Mapping[str, Any] | None = None,
    missing: Sequence[str] = (),
) -> str:
    """View 3 — the containers due this week, grouped by area.

    Map and route are only a collapsible extra.
    """
    if containers is None or containers.empty:
        return _missing_block("Die Wochenansicht", missing)

    work = containers.copy()
    work["due_in_days"] = _days_until_next_emptying(work)

    due = work[(work["due_in_days"] >= 0) & (work["due_in_days"] <= 7.0)].copy()
    due = due.sort_values(["due_in_days", "location_id"])

    groups: list[str] = []
    for area in ("urban", "rural"):
        subset = due[due["area"] == area]
        if subset.empty:
            continue
        rows = subset.to_dict(orient="records")
        body = "".join(
            f'<tr><td>{_esc(_site_title(r.get("location_id", ""), r.get("material", "")))}</td>'
            f"<td>{_esc(_material_label(str(r.get('material', ''))))}</td>"
            f'<td class="num">{_de(r.get("rate_pct_per_day"), 1)} %/Tag</td>'
            f'<td class="num">{_de(r.get("cadence_days_T"), 0)} Tage</td>'
            f'<td class="num">{_de(r.get("due_in_days"), 0)} Tage</td>'
            f'<td><span class="status-pill status-{_esc(r.get("status", "ok"))}">'
            f"{_esc(_status_label(str(r.get('status', 'ok'))))}</span></td></tr>"
            for r in rows
        )
        groups.append(
            f"""
            <div class="week-group">
              <h3>{_esc(_area_label(area))} <span class="badge">{_de(len(rows), 0)} Container</span></h3>
              <div class="table-scroll">
                <table class="cadence-table week-table">
                  <thead>
                    <tr>
                      <th scope="col">Container / Standort</th>
                      <th scope="col">Glasart</th>
                      <th scope="col">Füllrate</th>
                      <th scope="col">Takt</th>
                      <th scope="col">Fällig in</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>{body}</tbody>
                </table>
              </div>
            </div>
            """
        )

    if not groups:
        groups.append(
            '<p class="muted">In dieser Woche ist kein Container fällig.</p>'
        )

    metrics_html = ""
    if route_metrics:
        metrics_html = (
            '<div class="kpi-grid">'
            f'<div class="card"><div class="label">Stopps</div>'
            f'<div class="value">{_de(route_metrics.get("num_stops"), 0)}</div></div>'
            f'<div class="card"><div class="label">Strecke</div>'
            f'<div class="value">{_de(route_metrics.get("planned_km"), 1)} km</div></div>'
            f'<div class="card"><div class="label">Fahrzeuge</div>'
            f'<div class="value">{_de(route_metrics.get("vehicles_needed"), 0)}</div></div>'
            f'<div class="card"><div class="label">Sammelmenge</div>'
            f'<div class="value">{_de(route_metrics.get("t_collected"), 1)} t</div></div>'
            "</div>"
        )

    route_extra = ""
    if route_html:
        route_extra = (
            '<details class="cadence-route-extra">'
            "<summary>Karte und Route (zusätzlich)</summary>"
            f"{metrics_html}"
            f'<div class="map-wrap">{route_html}</div>'
            "</details>"
        )

    return f"""
    <section id="view-cadence-week" class="view-panel cadence-week-view">
      <div class="section-head">
        <h2>Diese Woche</h2>
        <p class="muted">
          Container, die in den nächsten 7 Tagen fällig werden — nach Gebiet gruppiert.
          Die Woche ist die Planungsansicht; das Jahr zeigt, wie sich der Takt einpendelt.
          Stand {_esc(_date_de(reference_date))}.
        </p>
      </div>
      {''.join(groups)}
      {route_extra}
    </section>
    """


# --- the scenario grid (what-if) ----------------------------------------------------------


def build_scenario_grid_html(summary: Mapping[str, Any] | None) -> str:
    """The precomputed scenario grid (offline — no live computation in the browser)."""
    if not summary:
        return _missing_block("Die Szenarioübersicht", ["summary.json"])

    scenarios = list(summary.get("scenarios", []))
    if not scenarios:
        return _missing_block("Die Szenarioübersicht", ["summary.json"])

    by_model: dict[str, list[Mapping[str, Any]]] = {}
    for scenario in scenarios:
        by_model.setdefault(str(scenario.get("time_model", "real")), []).append(scenario)

    time_model_labels = {
        "real": "Real (7/15 min + 5 min/Stopp + Depot)",
        "hop5": "5 min je Hop",
        "hop10": "10 min je Hop",
    }

    blocks: list[str] = []
    for time_model, items in by_model.items():
        rows = []
        for scenario in items:
            flags = scenario.get("flags", {}) or {}
            marks = []
            if flags.get("cheapest"):
                marks.append("günstigste")
            if flags.get("fewest_overflows"):
                marks.append("wenigste Überläufe")
            extra = scenario.get("extra_emptyings_co")
            extra_txt = f" · {extra} mitnehmen" if extra else ""
            rows.append(
                f'<tr class="{"scenario-best" if marks else ""}">'
                f'<td>{_esc(scenario.get("label", scenario.get("id")))}'
                f'{" · " + ", ".join(marks) if marks else ""}</td>'
                f'<td class="num">{_de(scenario.get("avg_fill_at_emptying_pct"), 1)} %</td>'
                f'<td class="num">{_de(scenario.get("overflow_events"), 0)}</td>'
                f'<td class="num">{_de(scenario.get("emptyings_saved_vs_status_quo"), 0)}</td>'
                f'<td class="num">{_de(scenario.get("km"), 0)} km</td>'
                f'<td class="num">{_de(scenario.get("vehicle_days"), 0)}</td>'
                f'<td class="num">{_de(scenario.get("cost_eur"), 0)} €</td>'
                "</tr>"
            )
        blocks.append(
            f"""
            <div class="scenario-block">
              <h3>{_esc(time_model_labels.get(time_model, time_model))}</h3>
              <div class="table-scroll">
                <table class="cadence-table scenario-table">
                  <thead>
                    <tr>
                      <th scope="col">Szenario</th>
                      <th scope="col">Ø Füllstand</th>
                      <th scope="col">Überläufe</th>
                      <th scope="col">Eingesparte Leerungen</th>
                      <th scope="col">km</th>
                      <th scope="col">Fahrzeugtage</th>
                      <th scope="col">Kosten</th>
                    </tr>
                  </thead>
                  <tbody>{''.join(rows)}</tbody>
                </table>
              </div>
            </div>
            """
        )

    period = summary.get("period", {}) or {}
    return f"""
    <section id="view-cadence-scenarios" class="view-panel cadence-scenarios-view">
      <div class="section-head">
        <h2>Szenarien über das ganze Jahr</h2>
        <p class="muted">
          Auswertung über das volle Replay-Jahr ({_de(period.get('days', 349), 0)} Tage,
          {_esc(_date_de(period.get('start')))} bis {_esc(_date_de(period.get('end')))}).
          Erzeugtes Glas: {_de(summary.get('produced_t'), 2)} t — in jedem Szenario
          gleich, die Szenarien unterscheiden sich nur in der Entscheidungsregel.
        </p>
      </div>
      {''.join(blocks)}
    </section>
    """


# --- entry point ------------------------------------------------------------------------


def build_cadence_sections(
    readings_df: pd.DataFrame | None,
    reference_date: str,
    scenario_dir: str | Path = DEFAULT_SCENARIO_DIR,
    route_html: str = "",
    route_metrics: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Build the three cadence views (list, detail, week) plus the scenario grid.

    Reads the scenario output of the model lane; computes nothing itself.
    """
    data = load_scenario_data(scenario_dir)
    containers = (
        _prepare_containers(data.containers) if data.containers is not None else None
    )
    missing = data.missing
    summary = data.summary
    return {
        "list": build_container_list_html(containers, summary, reference_date, missing),
        "detail": build_container_detail_html(
            containers, readings_df, reference_date, missing
        ),
        "week": build_week_view_html(
            containers, reference_date, route_html, route_metrics, missing
        ),
        "scenarios": build_scenario_grid_html(summary),
    }
