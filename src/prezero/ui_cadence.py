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

Recommendation rule: the ``recommendation`` column of ``containers.csv`` (länger /
kürzer / gleich) is shown as is; the UI derives nothing.

The views (persona: PreZero dispatcher - thinks in fixed areas and weeks):

1. **Wochenplan** - one card per Gebiet: how many containers get a longer / shorter
   rhythm and the top 5 recommendations as sentences. Needs the columns
   ``rhythm_weeks_status_quo, rhythm_weeks_new, recommendation, interval_status_quo_days``
   of ``containers.csv``; if they are missing the card says "Daten folgen".
2. **Wirkung** - two headline numbers (fill at emptying, overflows; today -> new)
   from ``summary.json`` (time model real, ``d_status_quo`` vs ``h_area_week_rhythm``,
   fallback ``f_fixed_areas``), small: emptyings, hours, cost. Worse is shown red.
3. **Container im Detail** - the container's raw measured readings
   (``data/processed/cleaned_readings.csv``) as a sawtooth, plus one sentence.
4. **Ausblick: Routing & Szenarien** - the full scenario tables and the km
   decomposition, collapsed by default.

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

#: Weekdays of the areas 0-4 (fixed area days, Mo-Fr).
AREA_WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr")

#: Columns the Wochenplan needs from containers.csv (delivered by the engine lane).
WEEK_PLAN_COLUMNS = (
    "area",
    "rhythm_weeks_status_quo",
    "rhythm_weeks_new",
    "recommendation",
    "interval_status_quo_days",
    "avg_fill_status_quo_pct",
    "overflow_events_status_quo",
    "material",
    "location_id",
)

#: The sentence the owner wants shown literally.
KEY_SENTENCE = (
    "Container, die regelmäßig halb leer sind, bekommen einen längeren Takt. "
    "Die frei gewordene Zeit geht an die kritischen. "
    "Der Takt passt sich nach jeder neuen Messung an."
)

#: Hint when a column of the engine output has not arrived yet.
PENDING_HINT = "Daten folgen"

#: Scenario id of the new area/week rhythm and its fallback.
NEW_SCENARIO_IDS = ("h_area_week_rhythm_b10", "h_area_week_rhythm", "f_fixed_areas")
#: Shown next to the area plan in the fill-class table (daily cadence per container).
CADENCE_SCENARIO_ID = "c_max_fill"

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
        number = int(float(area))
    except (TypeError, ValueError):
        return f"{AREA_PREFIX} {area}"
    day = AREA_WEEKDAYS[number] if 0 <= number < len(AREA_WEEKDAYS) else "?"
    return f"{AREA_PREFIX} {number + 1} ({day})"


def _rhythm_txt(weeks: Any) -> str:
    """'jede Woche' / 'alle 3 Wochen' for a rhythm in weeks."""
    try:
        w = float(weeks)
    except (TypeError, ValueError):
        return "?"
    if w != w:
        return "?"
    return "jede Woche" if round(w) == 1 else f"alle {_de(w, 0)} Wochen"


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


def _prepare_containers(containers: pd.DataFrame) -> pd.DataFrame:
    """Normalise types of ``containers.csv``; derives nothing."""
    work = containers.copy()
    work["location_id"] = work["location_id"].astype(str)
    work["material"] = work["material"].astype(str).str.lower()
    for column in (
        "rate_pct_per_day", "cadence_days_T", "emptyings_status_quo", "emptyings_mentor",
        "avg_fill_status_quo_pct", "avg_fill_mentor_pct", "overflow_events_status_quo",
        "skip_14d", "rhythm_weeks_status_quo", "rhythm_weeks_new", "interval_status_quo_days",
    ):
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce").astype(float)
    return work


def load_scenario_data(scenario_dir: str | Path = DEFAULT_SCENARIO_DIR) -> ScenarioData:
    """Read the scenario output of the engine."""
    return ScenarioData(scenario_dir)


# --- View 1: Wochenplan ---------------------------------------------------------------------


def _recommendation_sentence(row: Mapping[str, Any]) -> str:
    """One plain sentence for a container, built from the columns of the file."""
    site = f"Standort {str(row['location_id'])[:8]}…, {_material_label(row['material'])}"
    change = (
        f"{_rhythm_txt(row['rhythm_weeks_new'])} statt "
        f"{_rhythm_txt(row['rhythm_weeks_status_quo'])}"
    )
    if row.get("recommendation") == "länger":
        why = f"war im Schnitt nur {_de(row.get('avg_fill_status_quo_pct'), 0)} % voll"
    else:
        n = row.get("overflow_events_status_quo") or 0
        why = f"lief {_de(n, 0)}× über" if n else f"war im Schnitt {_de(row.get('avg_fill_status_quo_pct'), 0)} % voll"
    return f"{site}: {change} – {why}"


def _area_card_html(area: Any, group: pd.DataFrame) -> str:
    longer = group[group["recommendation"] == "länger"]
    shorter = group[group["recommendation"] == "kürzer"]

    def pairs(frame: pd.DataFrame) -> str:
        if frame.empty:
            return ""
        counts = (
            frame.groupby(["rhythm_weeks_new", "rhythm_weeks_status_quo"]).size()
            .sort_values(ascending=False)
        )
        return "; ".join(
            f"{_de(n, 0)}× {_rhythm_txt(new)} statt {_rhythm_txt(old)}"
            for (new, old), n in counts.items()
        )

    changed = group[group["recommendation"].isin(["länger", "kürzer"])].copy()
    changed["_step"] = (changed["rhythm_weeks_new"] - changed["rhythm_weeks_status_quo"]).abs()
    changed = changed.sort_values(
        ["_step", "overflow_events_status_quo"], ascending=[False, False]
    ).head(5)
    items = "".join(
        f'<li><a href="#cadence-detail" class="cadence-detail-link" '
        f'data-location="{_esc(r["location_id"])}" data-material="{_esc(r["material"])}">'
        f"{_esc(_recommendation_sentence(r))}</a></li>"
        for r in changed.to_dict(orient="records")
    )
    return f"""
      <div class="card cadence-area-card">
        <h3>{_esc(_area_label(area))}</h3>
        <p><strong>{_de(len(group), 0)}</strong> Container</p>
        <p><strong>{_de(len(longer), 0)}</strong> bekommen einen längeren Rhythmus
           <span class="muted">{_esc(pairs(longer))}</span></p>
        <p><strong>{_de(len(shorter), 0)}</strong> bekommen einen kürzeren Rhythmus
           <span class="muted">{_esc(pairs(shorter))}</span></p>
        <h4>Die wichtigsten Empfehlungen</h4>
        <ul class="cadence-recs">{items or '<li class="muted">Keine Änderung empfohlen.</li>'}</ul>
      </div>
    """


def build_week_plan_html(
    containers: pd.DataFrame | None,
    summary: Mapping[str, Any] | None,
    reference_date: str,
    missing: Sequence[str] = (),
) -> str:
    """View 1 - the Wochenplan: one card per Gebiet."""
    if containers is None or containers.empty:
        return _missing_block("Der Wochenplan", missing)

    absent = [c for c in WEEK_PLAN_COLUMNS if c not in containers.columns]
    if absent:
        body = f"""
        <div class="cadence-missing" role="status">
          <strong>{_esc(PENDING_HINT)}</strong>
          <p class="muted">Die Empfehlungen je Gebiet brauchen Spalten der Szenario-Engine,
          die noch nicht geliefert wurden: {_esc(", ".join(absent))}.
          Es werden bewusst keine Ersatzzahlen gezeigt.</p>
        </div>"""
    else:
        cards = "".join(
            _area_card_html(area, group)
            for area, group in containers.groupby("area", sort=True)
        )
        body = f'<div class="cadence-area-grid">{cards}</div>'

    return f"""
    <section id="view-cadence" class="view-panel cadence-view active">
      <div class="section-head">
        <h2>Wochenplan</h2>
        <p class="cadence-key-sentence"><strong>{_esc(KEY_SENTENCE)}</strong></p>
        <p class="muted">Jedes Gebiet hat feste Tage in der Woche (Gebiet 1 = Montag bis
          Gebiet 5 = Freitag). Stand {_esc(_date_de(reference_date))}.</p>
      </div>
      {body}
    </section>
    """


# --- View 2: Wirkung ------------------------------------------------------------------------


def _pick_scenarios(summary: Mapping[str, Any] | None) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    """Status quo and the new scenario (real time model; h, else f)."""
    today = new = None
    for sc in (summary or {}).get("scenarios", []):
        if str(sc.get("time_model")) != DEFAULT_TIME_MODEL:
            continue
        if sc.get("id") == "d_status_quo":
            today = sc
    for wanted in NEW_SCENARIO_IDS:
        for sc in (summary or {}).get("scenarios", []):
            if str(sc.get("time_model")) == DEFAULT_TIME_MODEL and sc.get("id") == wanted:
                return today, sc
    return today, new


def _delta_cell(today: Any, new: Any, digits: int, unit: str, higher_is_better: bool | None) -> str:
    """'today -> new' with an arrow; red when it got worse, green when better."""
    try:
        diff = float(new) - float(today)
    except (TypeError, ValueError):
        return f"{_de(today, digits)}{unit} → {_de(new, digits)}{unit}"
    arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
    cls = "same"
    if diff != 0 and higher_is_better is not None:
        cls = "good" if (diff > 0) == higher_is_better else "bad"
    return (
        f'<span class="impact-{cls}">{_de(today, digits)}{unit} → '
        f'{_de(new, digits)}{unit} <span class="impact-arrow">{arrow}</span></span>'
    )


def build_impact_html(summary: Mapping[str, Any] | None, missing: Sequence[str] = ()) -> str:
    """View 2 - the two headline numbers and three small ones."""
    today, new = _pick_scenarios(summary)
    if summary is None or today is None:
        return _missing_block("Die Wirkung", missing or ["summary.json"])
    if new is None:
        return f"""
        <section id="view-cadence-impact" class="view-panel cadence-impact-view">
          <div class="section-head"><h2>Wirkung</h2>
          <p class="muted"><strong>{_esc(PENDING_HINT)}</strong> – das neue Szenario
          ({_esc(NEW_SCENARIO_IDS[0])}) liegt noch nicht in summary.json.</p></div>
        </section>"""

    note = ""
    if new.get("id") != NEW_SCENARIO_IDS[0]:
        note = (f"Hinweis: Das Szenario {NEW_SCENARIO_IDS[0]} liegt noch nicht vor; "
                f"verglichen wird mit „{new.get('label', new.get('id'))}“.")

    def big(label: str, cell: str) -> str:
        return f'<div class="card impact-big"><div class="label">{label}</div><div class="value">{cell}</div></div>'

    def small(label: str, cell: str) -> str:
        return f'<div class="card"><div class="label">{label}</div><div class="value">{cell}</div></div>'

    has_classes = today.get("share_fits_pct") is not None and new.get("share_fits_pct") is not None
    if has_classes:
        big_cards = (
            big("Leerungen im passenden Fenster 50–100 % (heute → neu)",
                _delta_cell(today.get("share_fits_pct"), new.get("share_fits_pct"), 1, " %", True))
            + big("Überläufe (heute → neu)",
                  _delta_cell(today.get("overflow_events"), new.get("overflow_events"), 0, "", False))
        )
    else:
        big_cards = (
            big("Ø Füllgrad bei Leerung (heute → neu)",
                _delta_cell(today.get("avg_fill_at_emptying_pct"), new.get("avg_fill_at_emptying_pct"), 1, " %", True))
            + big("Überläufe (heute → neu)",
                  _delta_cell(today.get("overflow_events"), new.get("overflow_events"), 0, "", False))
        )
    class_rows = ""
    if has_classes:
        cadence = next(
            (sc for sc in summary.get("scenarios", [])
             if sc.get("id") == CADENCE_SCENARIO_ID and str(sc.get("time_model")) == DEFAULT_TIME_MODEL),
            None,
        )
        rows = [("Heute (Status quo)", today), ("Neu: feste Gebiete + Wochentakt", new)]
        if cadence is not None and cadence.get("share_fits_pct") is not None:
            rows.append(("Ausblick: Takt pro Container (täglich)", cadence))
        body = "".join(
            f"<tr><td>{_esc(name)}</td><td>{_de(sc.get('share_too_early_pct'), 1)} %</td>"
            f"<td><strong>{_de(sc.get('share_fits_pct'), 1)} %</strong></td>"
            f"<td>{_de(sc.get('share_overfull_pct'), 1)} %</td>"
            f"<td>{_de(sc.get('avg_fill_at_emptying_pct'), 1)} %</td></tr>"
            for name, sc in rows
        )
        class_rows = f"""
      <div class="card">
        <div class="label">Der Durchschnitt versteckt zwei Probleme: zu früh geleert und übergelaufen.</div>
        <table class="slide-table cadence-classes">
          <thead><tr><th>Leerungen</th><th>zu früh (&lt; 50 %)</th><th>passt (50–100 %)</th>
          <th>übervoll (&gt; 100 %)</th><th>Ø Füllgrad</th></tr></thead>
          <tbody>{body}</tbody>
        </table>
        <p class="muted">Ø Füllgrad heute enthält übergelaufenes Glas (über 100 %); deshalb zählt der
          Anteil im passenden Fenster.</p>
      </div>"""
    small_cards = (
        small("Ø Füllgrad", _delta_cell(today.get("avg_fill_at_emptying_pct"), new.get("avg_fill_at_emptying_pct"), 1, " %", True))
        +
        small("Leerungen", _delta_cell(today.get("emptyings"), new.get("emptyings"), 0, "", None))
        + small("Stunden", _delta_cell(today.get("hours"), new.get("hours"), 0, " h", False))
        + small("Kosten", _delta_cell(today.get("cost_eur"), new.get("cost_eur"), 0, " €", False))
    )
    return f"""
    <section id="view-cadence-impact" class="view-panel cadence-impact-view">
      <div class="section-head">
        <h2>Wirkung</h2>
        <p class="muted">Status quo gegen „{_esc(new.get('label', new.get('id')))}“ über den ganzen
          Zeitraum, bei gleicher Glasmenge ({_de(summary.get('produced_t'), 2)} t).
          Rot = schlechter als heute, grün = besser.</p>
        {f'<p class="muted">{_esc(note)}</p>' if note else ''}
      </div>
      <div class="kpi-grid impact-big-grid">{big_cards}</div>
      {class_rows}
      <div class="kpi-grid impact-small-grid">{small_cards}</div>
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
    """One plain-German sentence from the columns of the file."""
    if row.get("rhythm_weeks_new") is None or row.get("rhythm_weeks_status_quo") is None:
        return f"Takt heute / neu: {PENDING_HINT}. Der Takt wird nach jeder Messung neu berechnet."
    return (
        f"Takt heute {_de(row['rhythm_weeks_status_quo'], 0)} Wochen → neu "
        f"{_de(row['rhythm_weeks_new'], 0)} Wochen, wird nach jeder Messung neu berechnet."
    )


def _detail_body_html(row: Mapping[str, Any] | None) -> str:
    """Server-side rendering of the container detail (works without JavaScript)."""
    if not row:
        return '<p class="muted">Container wählen, um den Verlauf zu sehen.</p>'
    return f"""
      <div class="cadence-detail-title">
        <h3>{_esc(row.get('site_title', ''))}</h3>
        <span class="status-pill">{_esc(row.get('recommendation_label', ''))}</span>
      </div>
      <p class="muted">
        {_esc(row.get('area_label', ''))} · {_esc(row.get('material_label', ''))} ·
        füllt sich täglich um etwa {_de(row.get('rate_pct_per_day'), 1)} % ·
        {_de(row.get('emptyings_status_quo'), 0)} Leerungen im Status quo
      </p>
      <p class="cadence-explain">{_esc(row.get('explanation', ''))}</p>
      <div class="kpi-grid">
        <div class="card"><div class="label">Ø Füllgrad heute</div>
          <div class="value">{_de(row.get('avg_fill_status_quo_pct'), 1)} %</div></div>
        <div class="card"><div class="label">Ø Füllgrad neu</div>
          <div class="value">{_de(row.get('avg_fill_mentor_pct'), 1)} %</div></div>
        <div class="card"><div class="label">Überläufe heute</div>
          <div class="value">{_de(row.get('overflow_events_status_quo'), 0)}</div></div>
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
        row["recommendation_label"] = {"länger": "Längerer Takt", "kürzer": "Kürzerer Takt",
                                       "gleich": "Takt bleibt"}.get(str(row.get("recommendation")), "")
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


# --- shared constants of the scenario views -----------------------------------------------------------------

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


def _route_extra(route_html: str, route_metrics: Mapping[str, Any] | None) -> str:
    if not route_html:
        return ""
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
    return (
        '<details class="cadence-route-extra">'
        "<summary>Karte und Route (zusätzlich)</summary>"
        f'{metrics_html}<div class="map-wrap">{route_html}</div></details>'
    )


def build_scenario_grid_html(
    summary: Mapping[str, Any] | None,
    containers: pd.DataFrame | None = None,
    km_decomposition: Mapping[str, Any] | None = None,
    missing: Sequence[str] = (),
    route_html: str = "",
    route_metrics: Mapping[str, Any] | None = None,
) -> str:
    """View 4 - Ausblick: one table per time model (real first), caveats, km decomposition.

    Everything is collapsed by default; map and route are a further collapsible extra.
    """
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
        <h2>Ausblick: Routing &amp; Szenarien</h2>
        <p class="muted">Die Route ist nur der Ausblick: Sie bündelt, was der Takt fällig macht.</p>
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
      <details class="cadence-all">
        <summary>Szenario-Tabellen und km-Zerlegung anzeigen</summary>
        {blocks}
        {_km_decomposition_html(km_decomposition, summary)}
      </details>
      {_route_extra(route_html, route_metrics)}
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
    """Build the four views: plan, impact, detail, scenarios.

    Reads the scenario output of the engine; computes nothing itself.
    """
    data = load_scenario_data(scenario_dir)
    containers = _prepare_containers(data.containers) if data.containers is not None else None
    summary = data.summary
    return {
        "plan": build_week_plan_html(containers, summary, reference_date, data.missing),
        "impact": build_impact_html(summary, data.missing),
        "detail": build_container_detail_html(containers, readings_df, reference_date, data.missing),
        "scenarios": build_scenario_grid_html(
            summary, containers, data.km_decomposition, data.missing, route_html, route_metrics
        ),
    }
