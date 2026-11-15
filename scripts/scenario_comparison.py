"""Render docs/SCENARIO_COMPARISON.md from script outputs only (no hand-typed numbers).

    PYTHONPATH=src python3 scripts/run_scenarios.py --time-model km real hop5 hop10
    PYTHONPATH=src python3 scripts/km_decomposition.py
    PYTHONPATH=src python3 scripts/skip_savings.py
    PYTHONPATH=src python3 scripts/scenario_comparison.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SC = ROOT / "data/outputs/scenarios"

ORDER = [
    "d_status_quo", "a_zero_overflow", "b_min_km", "c_max_fill", "e_mentor", "f_fixed_areas",
    "h_area_week_rhythm_b10", "h_area_week_rhythm", "h_area_week_rhythm_b30",
    "g_co_empty_x70", "g_co_empty", "g_co_empty_x30",
    "d_status_quo_per_colour", "a_zero_overflow_per_colour", "g_co_empty_per_colour",
]
TM_LABEL = {
    "real": "Zeitmodell Mentor (7/15 min Fahrt, 5 min/Halt, Depot)",
    "km": "km-Modell (25 km/h, Rüst-/Hubzeit aus Config)",
    "hop5": "Normierte Distanz: jeder Sprung 5 min",
    "hop10": "Normierte Distanz: jeder Sprung 10 min",
}


def de(x: float, nd: int = 1) -> str:
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, base: float) -> str:
    if not base:
        return "–"
    v = (x - base) / base * 100.0
    return ("+" if v > 0 else "") + de(v, 1) + " %"


def table(entries: list[dict], tm: str) -> list[str]:
    rows = {e["id"]: e for e in entries if e["time_model"] == tm}
    sq = rows["d_status_quo"]
    out = [
        f"### {TM_LABEL.get(tm, tm)}",
        "",
        "| Szenario | gesammelt t | Endbestand t | Überlauf-Tage | übervoll bei Leerung | Ø Füllstand % | Leerungen | Halte | Fahrzeugtage | Stunden | km | Kosten € | Δ Kosten |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for sid in ORDER:
        e = rows.get(sid)
        if not e:
            continue
        marks = []
        if e["flags"].get("cheapest"):
            marks.append("**günstigste**")
        if e["flags"].get("fewest_overflows"):
            marks.append("**wenigste Überläufe**")
        name = f"`{sid}`" + (" " + ", ".join(marks) if marks else "")
        out.append(
            f"| {name} | {de(e['collected_t'], 1)} | {de(e['end_stock_t'], 1)} | {de(e['overflow_events'], 0)} | "
            f"{de(e['overfull_at_emptying'], 0)} | {de(e['avg_fill_at_emptying_pct'], 1)} | {de(e['emptyings'], 0)} | "
            f"{de(e['stops'], 0)} | {de(e['vehicle_days'], 0)} | {de(e['hours'], 1)} | {de(e['km'], 0)} | "
            f"{de(e['cost_eur'], 0)} | {pct(e['cost_eur'], sq['cost_eur'])} |"
        )
    out.append("")
    return out


def main() -> None:
    s = json.loads((SC / "summary.json").read_text(encoding="utf-8"))
    kd = json.loads((SC / "km_decomposition.json").read_text(encoding="utf-8"))
    sk_path = SC / "skip_savings.json"
    sk = json.loads(sk_path.read_text(encoding="utf-8")) if sk_path.exists() else None
    tms = [tm for tm in ["real", "km", "hop5", "hop10"] if any(e["time_model"] == tm for e in s["scenarios"])]

    L: list[str] = [
        "# Szenario-Vergleich (gleiche Glasmenge)",
        "",
        f"Erzeugt von `scripts/scenario_comparison.py` aus `data/outputs/scenarios/summary.json` "
        f"(generated_at {s['generated_at']}), `km_decomposition.json`"
        + (", `skip_savings.json`" if sk else "")
        + ". Keine Zahl ist von Hand eingetragen. Modell: `docs/MODEL_SPEC.md`.",
        "",
        f"**Zeitraum:** {s['period']['start']} bis {s['period']['end']} ({s['period']['days']} Tage). "
        f"**Produziertes Glas: {de(s['produced_t'], 2)} t in jedem Szenario** "
        f"(Massenbilanz `gesammelt + Endbestand = produziert` geprüft je Szenario, "
        f"`mass_balance_ok` = {all(e['mass_balance_ok'] for e in s['scenarios'])}).",
        "",
        "Spalten: *Überlauf-Tage* = Container-Tage mit Füllstand ≥ 110 %; *übervoll bei Leerung* = Leerungen bei ≥ 110 %; "
        "*Halte* = angefahrene Punkte (lat/lon). Kosten (Annahme) = Fahrzeugtage × 500 € + Crew-h × 64 € + km × 0,65 €. "
        "„günstigste“ / „wenigste Überläufe“ gelten je Zeitmodell. `_per_colour` = ein LKW je Glasfarbe "
        "(`truck_mode`), sonst Mehrkammer-Annahme.",
        "",
        "## Szenarien",
        "",
    ]
    for tm in tms:
        L += table(s["scenarios"], tm)

    L += [
        "## Warum der reine Timer mehr km fährt (km-Modell, gegenüber Status quo)",
        "",
        "Methode und Rohwerte: `data/outputs/scenarios/km_decomposition.json` (sequenzielle Zerlegung, keine eindeutige Zuordnung).",
        "",
        "| Politik | Δ km gesamt | (1) mehr Leerungen | (2) Tages-Streuung / Sprunglänge | (3) Fahrzeuge Depot hin/zurück | (4) Entladefahrten | (5) Farben getrennt | Container je Halt (Status quo) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for pid, c in kd["decomposition"].items():
        L.append(
            f"| `{pid}` | {de(c['delta_km'], 0)} | {de(c['1_extra_emptyings_km'], 0)} | {de(c['2_scattered_due_sets_km'], 0)} | "
            f"{de(c['3_extra_vehicles_depot_km'], 0)} | {de(c['4_extra_unload_trips_km'], 0)} | {de(c['5_colour_splitting_km'], 0)} | "
            f"{de(c['containers_per_stop'], 2)} ({de(c['containers_per_stop_status_quo'], 2)}) |"
        )
    L += [
        "",
        "Lesart: (2) ist negativ, wenn mehr Halte pro Tag die Sprünge kürzer machen; die Streuung der Fälligkeiten "
        "zeigt sich daher vor allem in (5), nicht in der Sprunglänge.",
        "",
    ]
    if sk:
        L += ["## Einsparung durch Auslassen von Leerungen ≤ 20 % (Status quo, Mentor 15.11.)", "",
              "Quelle: `data/outputs/scenarios/skip_savings.json`.", "",
              "```json", json.dumps(sk, indent=2, ensure_ascii=False)[:4000], "```", ""]
    L += [
        "## Grenzen (ehrlich)",
        "",
        "- **Standorte simuliert:** 449 IDs liegen zufällig auf 121 OSM-Punkten (`MODEL_SPEC.md` §10). Bündelung am Halt "
        "(Szenario g) ist dadurch in der Simulation leichter als in der Realität; absolute km/Halte sind illustrativ.",
        "- **Mehrkammer oder ein LKW je Farbe ist unbekannt** → beide Varianten stehen in der Tabelle.",
        "- **Kostensätze sind Annahmen**, keine PreZero-Preise.",
        "- **Füllraten** aus gekappten Messungen (overfull = 110 %) unterschätzen stark überlaufende Container.",
        "",
    ]
    path = ROOT / "docs/SCENARIO_COMPARISON.md"
    path.write_text("\n".join(L), encoding="utf-8")
    print(f"Written: {path}")


if __name__ == "__main__":
    main()
