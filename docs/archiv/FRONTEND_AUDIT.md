# Frontend-Audit: Backend vs. Website

Stand: Sa 14.11.2026, ca. 17:50 · Pitch: So 15.11.2026, 13:00 · Nur Audit, kein Code geändert.
HAI-Mission: `M-20261114T174434-ddfc07c1`.

**Was als „Website“ zählt:** `prezero ui --date 2026-04-15` → `ui_2026-04-15.html` (`ui.build_ui`).
Tabs: **1 Forecast-Timeline · 2 Bestehende Route (inkl. Freigabe) · 3 Datencheck · 4 Upload**.
Daneben gibt es `ui.build_dashboard` (→ `index.html`, Tabs Übersicht/Heatmap/Prognosekarte/Route).
Diese Funktion ist **noch nicht committet und an keinen CLI-Befehl angeschlossen**. Gebaut wird `index.html` also nicht.

---

## 1. Backend-Fähigkeiten (Inventar)

**CLI (`src/prezero/cli.py`):** `ingest`, `score`, `route`, `forecast`, `heatmap`, `visualize`, `run`,
`propose`, `approve`, `ui`, `copilot overview`, `copilot explain`, `copilot what-if`, `copilot ask`.

**Skripte:** `scripts/benchmark.py` (B0–B4-Vergleich), `scripts/fetch_locations.py` / `refresh_locations.py` (OSM/Overpass), `scripts/01_ingest.py`.

**Module mit Output:**
- `ingest.py`: `clean`, `print_stats`
- `features.py`: Füllrate, Overfull-Quote, Saisonfaktor
- `scoring.py`: `score_containers` (Score und `critical`)
- `routing.py`: `build_route`, `OperationalConfig` (11 Variablen), `load_config`
- `forecast.py`: +0/+7/+14/+21 Tage
- `heatmap.py`: `build_heatmap_matrix`
- `viz.py`: Heatmap, Prognosekarte, Routenkarte, Trends
- `approval.py`: propose, approve, `rejection_record`
- `locations.py`: Auflösung der Standorte, `location_stats`, Sanity-Map
- `ui.py`: `compute_data_check` (Anomalien: Sprünge, Lücken, Overfull), `compute_upload_check`
- `copilot.py`: Overview, Explain, What-if, Ask (Ollama mit deterministischem Fallback)

**Pitch-Zahlen:** `Pitch/NOTES.md` und `Projek-Management/proof/A3_pitch_zahlen.txt`.

---

## 2.–4. Abgleich (sortiert nach Demo-Wert, dann Aufwand)

★ = muss bis Sonntag 13:00 ins UI (Top 3)

| # | Fähigkeit | Backend-Datei | Output | Im UI? | Wo | Was fehlt | Demo-Wert | Aufwand |
|---|---|---|---|---|---|---|---|---|
| 1 ★ | **Heatmap** (Woche × Container, Klick → Karte) | `heatmap.py`, `viz.plot_heatmap`, CLI `heatmap` | `heatmap.html` | teilweise | nicht in `ui_<date>.html`; nur im unverdrahteten `build_dashboard` | als Tab in `ui` aufnehmen oder `build_dashboard` an die CLI hängen; Heatmap im Lauf mit erzeugen | high | S |
| 2 | **Betriebsannahmen** (`OperationalConfig`, 11 Variablen) | `routing.py`, `prezero_config.json` | `assumptions` in `route_<date>.json` | nein | – | Tabelle „Annahmen, von PreZero zu ersetzen“ im Route-Tab. Das ist Slide-1-Schritt „generic … individual variables“ | high | S |
| 3 | **Route und KPIs** | `routing.build_route`, CLI `route` | `route_<date>.json` | ja | Tab 2 (KPIs, Karte, Stoppliste) | 144 von 169 kritischen Standorten werden **nicht** angefahren, das UI sagt es nicht; Schicht pro Fahrzeug fehlt | high | S |
| 4 | **Prognose +0/+7/+14/+21** | `forecast.py`, CLI `forecast` | Tabelle und Karte | ja | Tab 1 | „516 kritisch“ zählt Container-Paare, die Route zählt Standorte (169). Die Einheit steht nicht dabei | high | S |
| 5 ★ | **Fairer Benchmark B0–B4** (Routing- vs. Bedarfseffekt, 4 Daten × 3 Seeds, OR-Tools) | `scripts/benchmark.py` | `docs/BENCHMARK.md`, `benchmark_results.csv`, Balkendiagramm | **nein**, Skript nie gelaufen (keine Ausgabedateien) | – | Skript laufen lassen; Karte oder Tab „Fairer Vergleich“ mit B0/B1/B2/B4 in km und h | high | M |
| 6 ★ | **Copilot What-if** (z. B. Schicht 6 h, Max-Stopps, Fahrzeuggewicht) | `copilot.simulate_what_if`, CLI `copilot what-if` | Baseline vs. Simulation, Delta km/h/Fahrzeuge | nein | nur `docs/copilot_visual_explainer.html` mit Beispielzahlen | 3–4 Szenarien vorberechnen und im Route-Tab als Presets zeigen (statisch, ohne Server) | high | M |
| 7 | **Copilot Explain** (warum dieser Container?) | `copilot.explain_container`, CLI `copilot explain` | Score-Zerlegung, Füllstand, Prognose | nein | – | Klick auf einen Stopp öffnet die vorberechnete Begründung | high | M |
| 8 | **Freigabe (Human-in-the-Loop)** | `approval.py`, CLI `propose` / `approve` | `proposal_*.json`, `approval_*.json` | teilweise | Tab 2: Button „Freigeben“ erzeugt einen JSON-Download im Browser | Ablehnen mit Grund fehlt (`rejection_record`) | medium | S |
| 9 | **Scoring** (0,5 Füllstand + 0,3 Overfull + 0,2 Material×Saison) | `scoring.py`, CLI `score` | `scored_<date>.csv` | teilweise | Score-Spalte in der Stoppliste | Formel und Schwelle nicht erklärt; keine Rangliste aller Container | medium | S |
| 10 | **Standort-Herkunft** (449 × `osm_assigned` / `simulated_mapping`) | `locations.py` | `locations.csv`, `location_stats` | teilweise | Spalte „Ortsquelle“ | Hinweis-Banner „Zuordnung simuliert“ fehlt (Pitch-Notiz 1) | medium | S |
| 11 | **Saison/Muster** (März 85,2 % Ø, 37,6 % Overfull) | `features.py`, `docs/analysen/*`, A3-Beleg | Monatsprofil | teilweise | Tab 3, Trendbild | Kernaussagen als Callout fehlen | medium | S |
| 12 | **Copilot Overview** | `copilot.get_tour_overview` | Tour-Zusammenfassung | indirekt | Tab 2 hat dieselben KPIs | – | low | S |
| 13 | **Datencheck / Anomalien** (Sprünge > 50 pp, Lücken > 90 d, Overfull) | `ui.compute_data_check` | KPIs, Tabellen | ja | Tab 3 | – | medium | – |
| 14 | **Trends** | `viz.plot_trends` | `trends.png` | ja | Tab 3 | – | medium | – |
| 15 | **Upload / Ingest-Check** | `ingest.py`, `ui.compute_upload_check` | Zählwerte | ja | Tab 4 | nur Zählung im Browser, startet keine Pipeline (für die Demo okay) | medium | – |
| 16 | **Copilot Ask** (freie Frage, Ollama) | `copilot.ask_copilot` | Text | nein | – | braucht lokalen Ollama; live zu riskant, höchstens im Terminal zeigen | medium | L |
| 17 | Routenkarte standalone (`visualize`) | `viz.plot_route` | `map_<date>.html` | ja | eingebettet in Tab 2 | – | low | – |
| 18 | Pipeline `run` | `cli.run` | alle Artefakte | n/a | – | – | low | – |
| 19 | OSM-Abruf | `scripts/fetch_locations.py` | Kandidaten-CSV | nein | – | nicht nötig | low | – |

---

## 5. Erfundene, veraltete oder irreführende Zahlen

**A. Veraltete Mockups, im Pitch nicht zeigen**
- `docs/ui_konzept/03_ui_mockup_interaktiv.html` (18 Treffer):
  - 67,92 km vs. 260,82 km, „−74,0 %“, „Saves 192,91 km“, „338 material series“ (aktuell 1.338 Serien)
  - Stoppzeilen mit den alten Herkünften `osm_heuristic` / `synthetic_placeholder`
  - Aktuell gilt: 119,75 / 157,72 km, 24,1 %, `simulated_mapping`
- Alte Begriffe oder Werte laut grep auch in:
  - `docs/ui_konzept/02_technische_darstellung_blueprint.svg` (4)
  - `05_Integrationsplan.md` (4)
  - `04_UML_Architektur.md`
  - `docs/ARCHITEKTUR.md`
  - `docs/GEO_DATENQUELLEN.md`

  Diese Dateien habe ich nicht einzeln geprüft.

**B. Copilot-Explainer mit unbelegtem und unplausiblem Beispiel**
- `docs/copilot_visual_explainer.html` zeigt als What-if `max_shift_hours=6.0` ein Ergebnis von **8,83 h Schicht** (+0,31 h) und 122,14 km.
- Eine Schicht über dem 6-h-Limit ist widersprüchlich.
- Nicht belegt, dass das ein echter Lauf war. Vor dem Zeigen neu erzeugen.

**C. Live-UI: Zahlen stimmen mit der JSON, aber die JSON ist veraltet**
- `ui_2026-04-15.html` zeigt 119,75 km / 157,72 km / 24,1 % / 25 Stopps / 169 kritisch / 2 Fahrzeuge / 8,52 h / 41,8 t. Das passt zu `route_2026-04-15.json` und zum A3-Beleg.
- Allerdings ist `route_2026-04-15.json` von 16:21. Danach wurde `routing.py` geändert (17:38, uncommittet):
  - Aggregation nach physischem Standort (lat/lon)
  - `max_stops` Default `None` = alle kritischen
- Der nächste `prezero ui`-Fallback oder `prezero route`-Lauf ändert also alle Pitch-Zahlen. `prezero run` nutzt weiter `--max-stops 25`.
- Vor dem Pitch: einmal final erzeugen, dann A3 neu prüfen und `Pitch/NOTES.md` angleichen.

**D. 24,1 % sind kein Vergleich unter gleichen Bedingungen** (`routing.py:490-498`)
- `planned_km` (119,75) enthält die Kapazitätslogik: 11 t, 5 Runden, 3 Entladefahrten zur Deponie.
- `full_round_km` (157,72) ist **eine** Nearest-Neighbor-Tour über 431 Standorte, ohne Kapazität und ohne Entladung.
- Die echte volle Runde wäre also länger. Die Zahl ist eher zu niedrig, aber angreifbar.
- `benchmark.py` (B0 vs. B2/B4) ist genau dafür gebaut.

**E. Einheiten-Mix in Tab 1 vs. Tab 2**
- „516 kritisch“ (Container-Paare, rot + schwarz) vs. „169 kritische Standorte“.
- Ohne Label wirkt das wie ein Widerspruch.

**F. Keine erfundenen Zahlen im Live-UI-Code**
- `ui.py` berechnet alle KPIs aus den Daten.
- Die Treffer für `synthetic_placeholder` in `viz.py` und `locations.py` sind Code-Zweige für alte Daten und nicht sichtbar.

---

## Top 3 Lücken

1. **Heatmap fehlt in der Website** (`ui_<date>.html`). Schnell zu beheben (S), hoher Demo-Wert.
2. **Benchmark B0–B4 nie gelaufen und nicht im UI.** Ohne ihn ist der 24,1-%-Vergleich nicht gleichartig (D) und angreifbar.
3. **Copilot What-if (+ Explain) nicht im UI.** Das ist der „generische Planer mit Variablen“ aus Slide 1. Nur der Explainer mit unplausiblen Beispielzahlen existiert.
