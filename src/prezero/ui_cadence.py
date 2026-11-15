"""The GlasRoute UI around the container (producer-consumer cadence).

**This module renders only; it computes no model.** The single source of every
number is the scenario engine output (branch ``lane/model-integration``) in
``data/outputs/scenarios/``:

* ``summary.json``                       - one row per scenario and time model
* ``containers.csv``                     - rate, cadence T, area, status inputs per container
* ``<id>__<time_model>_daily.csv``       - the daily course of a scenario
* ``km_decomposition.json``              - where the extra km come from

If a file is missing, the view says so ("Szenariodaten fehlen
(scripts/run_scenarios.py ausführen)") and shows no substitute numbers.

Status rules (pure display rules on columns of ``containers.csv``, no simulation):

* red    - ``overflow_events_status_quo > 0`` (the container overflowed in the status quo)
* yellow - ``skip_14d > 0`` (the mentor policy skipped it: found at/below the skip threshold)
* ok     - everything else (red wins over yellow)

"Takt heute" is the mean interval of the status quo, shown as the two given
numbers divided: ``period.days / emptyings_status_quo`` (labelled as such).

The views:

1. **Container list** - rate, cadence today, cadence T, status, approval per row.
2. **Container detail** - the container's raw measured readings
   (``data/processed/cleaned_readings.csv``) as a sawtooth, plus one sentence.
3. **Diese Woche** - the last week of the scenario course and the containers
   per area; map and route are only a collapsible extra.
4. **Szenarien** - one table per time model, plus the km decomposition.

Everything is generated statically (no server, no live computation in the browser).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

#: Default location of the scenario output (owned by the model lane).
DEFAULT_SCENARIO_DIR = Path("data/outputs/scenarios")

#: Label of the material types (German).
MATERIAL_LABELS: dict[str, str] = {
    "white": "Weißglas",
    "green": "Grünglas",
    "brown": "Braunglas",
}

#: Label of the areas (``area`` in containers.csv is the cluster number of policy f).
AREA_PREFIX = "Gebiet"

#: Status labels and the row class behind them.
STATUS_LABELS: dict[str, str] = {
    "red": "Kritisch",
    "yellow": "Im Mentor-Takt übersprungen",
    "ok": "Im Takt",
}

#: Hint shown when the scenario output is missing.
MISSING_HINT = "Szenariodaten fehlen (scripts/run_scenarios.py ausführen)"


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


def _area_label(area: Any) -> str:
    try:
        return f"{AREA_PREFIX} {int(float(area)) + 1}"
    except (TypeError, ValueError):
        return f"{AREA_PREFIX} {area}"


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
        self.km_decomposition: dict[str, Any] | None = None
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

        km_path = self.dir / "km_decomposition.json"
        if km_path.is_file():
            try:
                self.km_decomposition = json.loads(km_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.missing.append("km_decomposition.json")
        else:
            self.missing.append("km_decomposition.json")

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


def _prepare_containers(containers: pd.DataFrame, period_days: float | None = None) -> pd.DataFrame:
    """Add display columns to ``containers.csv`` (display rules, no simulation).

    * ``current_cadence_days`` - mean interval of the status quo:
      ``period_days / emptyings_status_quo`` (None when there is no emptying).
    * ``proposed_cadence_days`` - ``cadence_days_T`` of the file, unchanged.
    * ``status`` - red/yellow/ok, see the module docstring.
    """
    work = containers.copy()
    work["location_id"] = work["location_id"].astype(str)
    work["material"] = work["material"].astype(str).str.lower()
    if "area" not in work.columns:
        work["area"] = 0

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
            work[column] = float("nan")
        work[column] = pd.to_numeric(work[column], errors="coerce").astype(float)

    if period_days:
        emptyings = work["emptyings_status_quo"].where(work["emptyings_status_quo"] > 0)
        work["current_cadence_days"] = (float(period_days) / emptyings).astype(float)
    else:
        work["current_cadence_days"] = float("nan")
    work["proposed_cadence_days"] = work["cadence_days_T"]

    work["status"] = "ok"
    work.loc[work["skip_14d"].fillna(0) > 0, "status"] = "yellow"
    work.loc[work["overflow_events_status_quo"].fillna(0) > 0, "status"] = "red"
    return work


def load_scenario_data(scenario_dir: str | Path = DEFAULT_SCENARIO_DIR) -> ScenarioData:
    """Read the scenario output of the engine."""
    return ScenarioData(scenario_dir)


# --- View 1: container list ---------------------------------------------------------------


def compute_header_kpis(
    containers: pd.DataFrame,
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Header KPIs of the container list - sums/means of columns of the files."""
    empty = {
        "containers": 0,
        "avg_fill_status_quo_pct": None,
        "overflow_events": 0,
        "emptyings_status_quo": 0,
        "emptyings_mentor": 0,
        "cadence_change_needed": 0,
        "produced_t": (summary or {}).get("produced_t"),
        "too_often_emptied": 0,
        "containers_with_overflow": 0,
    }
    if containers is None or containers.empty:
        return empty

    fills = containers["avg_fill_status_quo_pct"].fillna(0.0)
    weights = containers["emptyings_status_quo"].fillna(0.0)
    total = float(weights.sum())
    avg_fill = float((fills * weights).sum() / total) if total else None

    delta = (containers["proposed_cadence_days"] - containers["current_cadence_days"]).abs()
    return {
        "containers": int(len(containers)),
        "avg_fill_status_quo_pct": avg_fill,
        "overflow_events": int(containers["overflow_events_status_quo"].fillna(0).sum()),
        "emptyings_status_quo": int(weights.sum()),
        "emptyings_mentor": int(containers["emptyings_mentor"].fillna(0).sum()),
        "cadence_change_needed": int((delta >= 1.0).sum()),
        "too_often_emptied": int(
            ((containers["skip_14d"] > 0)
             | (containers["avg_fill_status_quo_pct"] < OFTEN_EMPTIED_BELOW_PCT)).sum()
        ),
        "containers_with_overflow": int((containers["overflow_events_status_quo"] > 0).sum()),
        "produced_t": (summary or {}).get("produced_t"),
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
            f'<td>{_esc(_area_label(row.get("area")))}</td>'
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


#: Upper bounds (days) of the cadence buckets of the histogram; the last bucket is open.
CADENCE_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("≤ 7 Tage", float("-inf"), 7.0),
    ("8–14 Tage", 7.0, 14.0),
    ("15–30 Tage", 14.0, 30.0),
    ("> 30 Tage", 30.0, float("inf")),
)

#: Bar colours per glass colour (decorative).
MATERIAL_COLORS: dict[str, str] = {"white": "#9aa7b4", "green": "#4c9a5a", "brown": "#8b5e3c"}

#: A container counts as "zu oft geleert" below this mean fill (display rule) or when skipped.
OFTEN_EMPTIED_BELOW_PCT = 50.0

#: Rows per short list.
SHORT_LIST_ROWS = 10


def _best_scenario(summary: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    """The cheapest scenario of the real time model (``flags.cheapest``)."""
    for scenario in (summary or {}).get("scenarios", []):
        if str(scenario.get("time_model")) == DEFAULT_TIME_MODEL and (
            scenario.get("flags") or {}
        ).get("cheapest"):
            return scenario
    return None


def _short_list_html(title: str, hint: str, rows: Sequence[Mapping[str, Any]]) -> str:
    body = "".join(
        "<tr>"
        f'<td class="cadence-site"><a href="#cadence-detail" class="cadence-detail-link" '
        f'data-location="{_esc(r["location_id"])}" data-material="{_esc(r["material"])}">'
        f'{_esc(str(r["location_id"])[:8])}</a></td>'
        f'<td>{_esc(_material_label(r["material"]))}</td>'
        f'<td class="num">{_de(r.get("rate_pct_per_day"), 1)} %/Tag</td>'
        f'<td class="num">{_de(r.get("current_cadence_days"), 0)} → {_de(r.get("proposed_cadence_days"), 0)} Tage</td>'
        f'<td class="num">{_de(r.get("avg_fill_status_quo_pct"), 1)} %</td>'
        "</tr>"
        for r in rows
    )
    return f"""
      <div class="cadence-short-list">
        <h3>{_esc(title)}</h3>
        <p class="muted">{_esc(hint)}</p>
        <div class="table-scroll"><table class="cadence-table">
          <thead><tr>
            <th scope="col">Standort-ID</th><th scope="col">Farbe</th>
            <th scope="col">Rate</th><th scope="col">Takt heute → Takt T</th>
            <th scope="col">Ø Füllstand</th>
          </tr></thead>
          <tbody>{body}</tbody>
        </table></div>
      </div>
    """


def _cadence_histogram_svg(containers: pd.DataFrame) -> str:
    """Bars of the cadence_days_T buckets per colour (counts of containers.csv rows)."""
    materials = [m for m in MATERIAL_COLORS if m in set(containers["material"])]
    counts: dict[str, list[int]] = {}
    for m in materials:
        t = containers.loc[containers["material"] == m, "cadence_days_T"]
        counts[m] = [int(((t > lo) & (t <= hi)).sum()) for _, lo, hi in CADENCE_BUCKETS]
    peak = max((c for v in counts.values() for c in v), default=0) or 1
    width, height, pad_l, pad_b, pad_t = 640, 240, 40, 36, 16
    group_w = (width - pad_l - 10) / len(CADENCE_BUCKETS)
    bar_w = group_w * 0.8 / max(1, len(materials))
    plot_h = height - pad_b - pad_t
    out = []
    for gi, (label, _, _) in enumerate(CADENCE_BUCKETS):
        gx = pad_l + gi * group_w
        for mi, m in enumerate(materials):
            n = counts[m][gi]
            h = n / peak * plot_h
            x = gx + group_w * 0.1 + mi * bar_w
            out.append(
                f'<rect x="{x:.1f}" y="{pad_t + plot_h - h:.1f}" width="{bar_w:.1f}" '
                f'height="{h:.1f}" fill="{MATERIAL_COLORS[m]}"><title>{_esc(_material_label(m))}, '
                f'{_esc(label)}: {n}</title></rect>'
                f'<text x="{x + bar_w / 2:.1f}" y="{pad_t + plot_h - h - 3:.1f}" '
                f'class="saw-axis" text-anchor="middle">{n}</text>'
            )
        out.append(
            f'<text x="{gx + group_w / 2:.1f}" y="{height - 14}" class="saw-axis" '
            f'text-anchor="middle">{_esc(label)}</text>'
        )
    legend = " ".join(
        f'<span><i style="background:{MATERIAL_COLORS[m]};display:inline-block;width:10px;height:10px"></i> '
        f"{_esc(_material_label(m))}</span>"
        for m in materials
    )
    return f"""
      <div class="cadence-histogram">
        <h3>Takt T der Container (Anzahl je Glasfarbe)</h3>
        <svg class="saw-chart" viewBox="0 0 {width} {height}" role="img"
             aria-label="Verteilung des Takts T nach Glasfarbe">{''.join(out)}</svg>
        <p class="muted">{legend}</p>
      </div>
    """


def build_container_list_html(
    containers: pd.DataFrame | None,
    summary: Mapping[str, Any] | None,
    reference_date: str,
    missing: Sequence[str] = (),
) -> str:
    """View 1 - KPIs, two short lists, cadence histogram; the full list is collapsed."""
    if containers is None or containers.empty:
        return _missing_block("Die Container-Übersicht", missing)

    kpis = compute_header_kpis(containers, summary)
    best = _best_scenario(summary)
    if best is not None:
        saved_value = _de(best.get("emptyings_saved_vs_status_quo"), 0)
        saved_sub = f"günstigstes Szenario (real): {_esc(best.get('label', best.get('id')))}"
    else:
        saved_value, saved_sub = "-", "kein günstigstes Szenario in summary.json"

    kpi_cards = f"""
      <div class="card kpi-cadence">
        <div class="label">Glas produziert</div>
        <div class="value">{_de(kpis['produced_t'], 1)} t</div>
        <div class="sub">in jedem Szenario gleich</div>
      </div>
      <div class="card kpi-cadence">
        <div class="label">Zu oft geleert</div>
        <div class="value">{_de(kpis['too_often_emptied'], 0)}</div>
        <div class="sub">Container, im Mentor-Takt übersprungen oder Ø Füllstand unter {_de(OFTEN_EMPTIED_BELOW_PCT, 0)} %</div>
      </div>
      <div class="card kpi-cadence">
        <div class="label">Mit Überläufen (Status quo)</div>
        <div class="value">{_de(kpis['containers_with_overflow'], 0)}</div>
        <div class="sub">von {_de(kpis['containers'], 0)} Containern</div>
      </div>
      <div class="card kpi-cadence">
        <div class="label">Leerungen vs. Status quo</div>
        <div class="value">{saved_value}</div>
        <div class="sub">{saved_sub}; positiv = gespart</div>
      </div>
    """

    overflow_rows = (
        containers[containers["overflow_events_status_quo"] > 0]
        .sort_values("overflow_events_status_quo", ascending=False)
        .head(SHORT_LIST_ROWS)
        .to_dict(orient="records")
    )
    often_mask = (containers["skip_14d"] > 0) | (
        containers["avg_fill_status_quo_pct"] < OFTEN_EMPTIED_BELOW_PCT
    )
    often_rows = (
        containers[often_mask]
        .sort_values("avg_fill_status_quo_pct", ascending=True)
        .head(SHORT_LIST_ROWS)
        .to_dict(orient="records")
    )

    ordered = _sort_table(containers)
    rows = ordered.to_dict(orient="records")
    status_counts = ordered["status"].value_counts().to_dict()
    filter_buttons = "".join(
        f'<button type="button" class="cadence-filter-btn{" active" if key == "all" else ""}" '
        f'data-filter="{_esc(key)}">{_esc(label)}</button>'
        for key, label in (
            ("all", f"Alle ({_de(kpis['containers'], 0)})"),
            ("red", f"Kritisch ({_de(status_counts.get('red', 0), 0)})"),
            ("yellow", f"Übersprungen ({_de(status_counts.get('yellow', 0), 0)})"),
            ("ok", f"Im Takt ({_de(status_counts.get('ok', 0), 0)})"),
        )
    )

    return f"""
    <section id="view-cadence" class="view-panel cadence-view active">
      <div class="section-head">
        <h2>Container &amp; Takt</h2>
        <p class="muted">
          Jeder Container ist ein Erzeuger-Verbraucher-System: Er füllt sich mit
          <b>r</b> % pro Tag und wird alle <b>T</b> Tage geleert
          (<b>T = (Kapazität − Puffer) / r</b>). Die Route ist nur eine nachgelagerte Bündelung.
          Stand {_esc(_date_de(reference_date))}.
        </p>
      </div>

      <div class="kpi-grid cadence-kpi-grid">{kpi_cards}</div>

      <div class="cadence-lists">
        {_short_list_html("Läuft über – Takt zu lang",
                          "Die zehn Container mit den meisten Überlauf-Ereignissen im Status quo.",
                          overflow_rows)}
        {_short_list_html("Zu oft geleert – Takt zu kurz",
                          "Die zehn Container mit dem niedrigsten Ø Füllstand bei Leerung.",
                          often_rows)}
      </div>

      {_cadence_histogram_svg(containers)}

      <details class="cadence-all">
        <summary>Alle {_de(kpis['containers'], 0)} Container anzeigen</summary>
        <div class="cadence-toolbar">
          <input type="search" id="cadence-search" placeholder="Standort-ID oder Farbe suchen"
                 aria-label="Container suchen">
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
      </details>

      <p class="muted">
        <b>Rot</b> = Überlauf-Ereignisse im Status quo. <b>Gelb</b> = im Mentor-Takt
        übersprungen (<code>skip_14d</code>).
        „Takt heute“ = Zeitraum ÷ Leerungen im Status quo (Mittelwert, Annahme: gleichmäßig verteilt);
        „Takt T“ = <code>cadence_days_T</code> aus der Szenario-Ausgabe (Modell: docs/MODEL_SPEC.md).
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

    current_txt = _de(current, 0) if current is not None and current == current else "?"
    proposed_txt = _de(proposed, 0)
    takt = f"Takt {current_txt} → {proposed_txt} Tage"

    if status == "red":
        return (
            f"{_de(row.get('overflow_events_status_quo'), 0)} Überlauf-Ereignisse im "
            f"Status quo bei {_de(rate, 1)} % Füllrate pro Tag → {takt}."
        )
    if status == "yellow":
        return (
            f"Im Status quo im Mittel zu {_de(fill, 0)} % voll geleert und im Mentor-Takt "
            f"übersprungen → {takt}."
        )
    return (
        f"Füllt sich mit {_de(rate, 1)} % pro Tag, im Status quo zu {_de(fill, 0)} % "
        f"geleert → {takt}."
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
        {"im Mentor-Takt übersprungen" if (row.get('skip_14d') or 0) > 0 else "im Mentor-Takt nicht übersprungen"}
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

    payload = json.loads(containers.to_json(orient="records"))
    for row in payload:
        row["site_title"] = _site_title(row.get("location_id", ""), row.get("material", ""))
        row["material_label"] = _material_label(str(row.get("material", "")))
        row["area_label"] = _area_label(row.get("area"))
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

#: The time model shown first (the realistic one).
DEFAULT_TIME_MODEL = "real"

TIME_MODEL_LABELS: dict[str, str] = {
    "real": "Real (7/15 min Fahrt, 5 min je Halt, Depot)",
    "km": "km-Modell (km / Geschwindigkeit, Rüst- und Hubzeit aus Config)",
    "hop5": "Normierte Distanz: jeder Sprung 5 min",
    "hop10": "Normierte Distanz: jeder Sprung 10 min",
}

#: Order of the time models in the scenario tab (unknown ones are appended).
TIME_MODEL_ORDER = ("real", "km", "hop5", "hop10")

#: German names of the km components in ``km_decomposition.json``.
KM_PART_LABELS: dict[str, str] = {
    "1_extra_emptyings_km": "Mehr Leerungen",
    "2_scattered_due_sets_km": "Gestreute Fälligkeiten",
    "3_extra_vehicles_depot_km": "Mehr Fahrzeuge (Depot)",
    "4_extra_unload_trips_km": "Mehr Entladefahrten",
    "5_colour_splitting_km": "Farbtrennung",
}


def _scenario_label(summary: Mapping[str, Any] | None, scenario_id: str) -> str:
    for scenario in (summary or {}).get("scenarios", []):
        if str(scenario.get("id")) == scenario_id:
            return str(scenario.get("label") or scenario_id)
    return scenario_id


def _week_scenario_table(data: ScenarioData) -> str:
    """Last 7 days of every scenario's daily course (real time model) - sums of the file."""
    rows: list[str] = []
    window = ""
    for scenario in data.scenarios:
        if str(scenario.get("time_model")) != DEFAULT_TIME_MODEL:
            continue
        daily = data.daily.get((str(scenario.get("id")), DEFAULT_TIME_MODEL))
        if daily is None or daily.empty:
            continue
        last = daily.tail(7)
        window = f"{_date_de(last['date'].iloc[0])} bis {_date_de(last['date'].iloc[-1])}"
        rows.append(
            "<tr>"
            f"<td>{_esc(scenario.get('label') or scenario.get('id'))}</td>"
            f'<td class="num">{_de(last["n_emptyings"].sum(), 0)}</td>'
            f'<td class="num">{_de(last["n_overflow_events"].sum(), 0)}</td>'
            f'<td class="num">{_de(last["tonnage_t"].sum(), 1)} t</td>'
            f'<td class="num">{_de(last["stops"].sum(), 0)}</td>'
            f'<td class="num">{_de(last["vehicles_needed"].max(), 0)}</td>'
            f'<td class="num">{_de(last["shift_hours"].sum(), 1)} h</td>'
            f'<td class="num">{_de(last["km"].sum(), 0)} km</td>'
            "</tr>"
        )
    if not rows:
        return '<p class="muted">Keine Tagesverläufe vorhanden.</p>'
    return f"""
      <h3>Letzte Woche des Zeitraums ({_esc(window)})</h3>
      <div class="table-scroll">
        <table class="cadence-table week-table">
          <thead><tr>
            <th scope="col">Szenario</th>
            <th scope="col">Leerungen</th>
            <th scope="col">Überläufe</th>
            <th scope="col">Gesammelt</th>
            <th scope="col">Halte</th>
            <th scope="col">Fahrzeuge (max.)</th>
            <th scope="col">Stunden</th>
            <th scope="col">km</th>
          </tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </div>
    """


def _week_area_table(containers: pd.DataFrame) -> str:
    """Containers per area (cluster of policy f) - counts and means of containers.csv."""
    rows: list[str] = []
    for area, group in containers.groupby("area", sort=True):
        rows.append(
            "<tr>"
            f"<td>{_esc(_area_label(area))}</td>"
            f'<td class="num">{_de(len(group), 0)}</td>'
            f'<td class="num">{_de(group["rate_pct_per_day"].mean(), 1)} %/Tag</td>'
            f'<td class="num">{_de(group["cadence_days_T"].median(), 0)} Tage</td>'
            f'<td class="num">{_de((group["status"] == "red").sum(), 0)}</td>'
            f'<td class="num">{_de((group["status"] == "yellow").sum(), 0)}</td>'
            "</tr>"
        )
    return f"""
      <h3>Container je Gebiet</h3>
      <div class="table-scroll">
        <table class="cadence-table week-table">
          <thead><tr>
            <th scope="col">Gebiet</th>
            <th scope="col">Container</th>
            <th scope="col">Ø Füllrate</th>
            <th scope="col">Takt neu (Median)</th>
            <th scope="col">Kritisch</th>
            <th scope="col">Übersprungen</th>
          </tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </div>
    """


def build_week_view_html(
    data: ScenarioData,
    containers: pd.DataFrame | None,
    reference_date: str,
    route_html: str = "",
    route_metrics: Mapping[str, Any] | None = None,
) -> str:
    """View 3 - the last week of the scenario course and the containers per area.

    Map and route are only a collapsible extra.
    """
    if containers is None or containers.empty or not data.daily:
        return _missing_block("Die Wochenansicht", data.missing)

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
          Wochenausschnitt aus dem Szenario-Verlauf (Tageswerte der Engine) und die
          Container je Gebiet. Die Woche ist die Planungsansicht; das Jahr zeigt, wie sich
          der Takt einpendelt. Stand {_esc(_date_de(reference_date))}.
        </p>
      </div>
      {_week_scenario_table(data)}
      {_week_area_table(containers)}
      {route_extra}
    </section>
    """


# --- View 4: scenarios ---------------------------------------------------------------------


def _flag_marks(scenario: Mapping[str, Any]) -> list[str]:
    flags = scenario.get("flags", {}) or {}
    marks = []
    if flags.get("cheapest"):
        marks.append("günstigste")
    if flags.get("fewest_overflows"):
        marks.append("wenigste Überläufe")
    return marks


def _scenario_table(items: Sequence[Mapping[str, Any]]) -> str:
    rows = []
    for scenario in items:
        marks = _flag_marks(scenario)
        mode = scenario.get("truck_mode")
        mode_txt = (
            " (ein LKW je Farbe)" if mode == "per_colour"
            else " (Mehrkammer)" if mode == "multi_chamber" else ""
        )
        rows.append(
            f'<tr class="{"scenario-best" if marks else ""}" '
            f'data-scenario="{_esc(scenario.get("id"))}">'
            f'<td><code>{_esc(scenario.get("id"))}</code> {_esc(scenario.get("label", ""))}'
            f"{_esc(mode_txt)}</td>"
            f'<td class="num">{_de(scenario.get("collected_t"), 1)}</td>'
            f'<td class="num">{_de(scenario.get("end_stock_t"), 1)}</td>'
            f'<td class="num">{_de(scenario.get("overflow_events"), 0)}</td>'
            f'<td class="num">{_de(scenario.get("avg_fill_at_emptying_pct"), 1)} %</td>'
            f'<td class="num">{_de(scenario.get("emptyings"), 0)}</td>'
            f'<td class="num">{_de(scenario.get("stops"), 0)}</td>'
            f'<td class="num">{_de(scenario.get("vehicle_days"), 0)}</td>'
            f'<td class="num">{_de(scenario.get("hours"), 1)}</td>'
            f'<td class="num">{_de(scenario.get("km"), 0)}</td>'
            f'<td class="num">{_de(scenario.get("cost_eur"), 0)} €</td>'
            f"<td>{_esc(', '.join(marks))}</td>"
            "</tr>"
        )
    return f"""
      <div class="table-scroll">
        <table class="cadence-table scenario-table">
          <thead><tr>
            <th scope="col">Szenario</th>
            <th scope="col">Gesammelt (t)</th>
            <th scope="col">Endbestand (t)</th>
            <th scope="col">Überlauf-Ereignisse</th>
            <th scope="col">Ø Füllstand bei Leerung</th>
            <th scope="col">Leerungen</th>
            <th scope="col">Halte</th>
            <th scope="col">Fahrzeugtage</th>
            <th scope="col">Stunden</th>
            <th scope="col">km</th>
            <th scope="col">Kosten</th>
            <th scope="col">Hinweis</th>
          </tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </div>
    """


def _km_decomposition_html(
    km: Mapping[str, Any] | None, summary: Mapping[str, Any] | None
) -> str:
    """The km decomposition table of ``km_decomposition.json`` (policy vs. status quo)."""
    decomposition = (km or {}).get("decomposition") if km else None
    if not decomposition:
        return _missing_block("Die km-Zerlegung", ["km_decomposition.json"])
    part_keys = [k for k in KM_PART_LABELS if any(k in v for v in decomposition.values())]
    rows = []
    for policy_id, values in decomposition.items():
        parts = "".join(
            f'<td class="num">{_de(values.get(k), 0)}</td>' for k in part_keys
        )
        rows.append(
            "<tr>"
            f"<td><code>{_esc(policy_id)}</code> {_esc(_scenario_label(summary, policy_id))}</td>"
            f'<td class="num">{_de(values.get("km_status_quo"), 0)}</td>'
            f'<td class="num">{_de(values.get("km_policy"), 0)}</td>'
            f'<td class="num">{_de(values.get("delta_km"), 0)}</td>'
            f"{parts}"
            f'<td class="num">{_de(values.get("containers_per_stop"), 2)}</td>'
            "</tr>"
        )
    part_heads = "".join(f'<th scope="col">{_esc(KM_PART_LABELS[k])} (km)</th>' for k in part_keys)
    return f"""
      <div class="scenario-block km-decomposition">
        <h3>Woher kommen die Mehr-km? (Zerlegung gegen den Status quo)</h3>
        <div class="table-scroll">
          <table class="cadence-table km-table">
            <thead><tr>
              <th scope="col">Szenario</th>
              <th scope="col">km Status quo</th>
              <th scope="col">km Szenario</th>
              <th scope="col">Δ km</th>
              {part_heads}
              <th scope="col">Container je Halt</th>
            </tr></thead>
            <tbody>{"".join(rows)}</tbody>
          </table>
        </div>
        <p class="muted">Die Aufteilung ist eine Methode, keine eindeutige Zuordnung
        (Quelle: <code>km_decomposition.json</code>).</p>
      </div>
    """


def build_scenario_grid_html(
    summary: Mapping[str, Any] | None,
    containers: pd.DataFrame | None = None,
    km_decomposition: Mapping[str, Any] | None = None,
    missing: Sequence[str] = (),
) -> str:
    """View 4 - one table per time model (real first), caveats, km decomposition."""
    scenarios = list((summary or {}).get("scenarios", []))
    if not scenarios:
        return _missing_block("Die Szenarioübersicht", missing or ["summary.json"])

    by_model: dict[str, list[Mapping[str, Any]]] = {}
    for scenario in scenarios:
        by_model.setdefault(str(scenario.get("time_model", DEFAULT_TIME_MODEL)), []).append(scenario)
    ordered = [m for m in TIME_MODEL_ORDER if m in by_model] + [
        m for m in by_model if m not in TIME_MODEL_ORDER
    ]

    blocks = "".join(
        f"""
        <div class="scenario-block" data-time-model="{_esc(model)}">
          <h3>Zeitmodell: {_esc(TIME_MODEL_LABELS.get(model, model))}</h3>
          {_scenario_table(by_model[model])}
        </div>
        """
        for model in ordered
    )

    # Caveat 1 - read off the container table: IDs vs. distinct OSM points.
    if containers is not None and not containers.empty:
        ids = int(containers["location_id"].nunique())
        points = int(containers[["lat", "lon"]].drop_duplicates().shape[0])
        sites = f"Standorte simuliert: {_de(ids, 0)} IDs auf {_de(points, 0)} OSM-Punkten"
    else:
        sites = "Standorte simuliert: IDs auf OSM-Punkten"

    period = (summary or {}).get("period", {}) or {}
    return f"""
    <section id="view-cadence-scenarios" class="view-panel cadence-scenarios-view">
      <div class="section-head">
        <h2>Szenarien über den ganzen Zeitraum</h2>
        <p class="muted">
          Zeitraum {_esc(_date_de(period.get('start')))} bis {_esc(_date_de(period.get('end')))}
          ({_de(period.get('days'), 0)} Tage).
          <strong>Gleiche Glasmenge: {_de((summary or {}).get('produced_t'), 2)} t in jedem Szenario</strong>
          - die Szenarien unterscheiden sich nur in der Entscheidungsregel.
          Quelle: <code>summary.json</code> der Szenario-Engine.
        </p>
        <ul class="cadence-caveats">
          <li><strong>{_esc(sites)}</strong> (zufällig zugeordnet); Bündelung am Halt ist in der
            Simulation leichter als in der Realität, absolute km und Halte sind illustrativ.</li>
          <li><strong>Mehrkammer vs. ein LKW je Farbe unbekannt</strong> - beide Varianten stehen in den Tabellen.</li>
        </ul>
      </div>
      {blocks}
      {_km_decomposition_html(km_decomposition, summary)}
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
    """Build the four cadence views (list, detail, week, scenarios).

    Reads the scenario output of the engine; computes nothing itself.
    """
    data = load_scenario_data(scenario_dir)
    containers = None
    if data.containers is not None:
        containers = _prepare_containers(data.containers, data.period.get("days"))
    summary = data.summary
    return {
        "list": build_container_list_html(containers, summary, reference_date, data.missing),
        "detail": build_container_detail_html(containers, readings_df, reference_date, data.missing),
        "week": build_week_view_html(data, containers, reference_date, route_html, route_metrics),
        "scenarios": build_scenario_grid_html(
            summary, containers, data.km_decomposition, data.missing
        ),
    }
