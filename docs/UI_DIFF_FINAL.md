# Finaler Frontend ↔ Backend Diff-Audit vor dem Freeze

**Datum:** 2026-11-15 (vor dem Freeze So 11:00)  
**Bezug:** Abgleich aller UI-Tabs und Einzelseiten gegen Backend-Module, CLI-Befehle und mathematische Wahrheiten.  
**Prüfmethode:** Read-only Code-Inspektion via `git log -1 -L:<func>:<file>`, Konsistenzprüfung der Kennzahlen gegen `route_2026-04-15.json`, `benchmark_results.csv`, `data/raw/glass_fill_levels_anonymized_f.csv` und `walkforward_replay_summary.json`.

---

## 1. Audit-Tabelle nach Reife und Alter (Oldest commit first)

| Tab / Seite | Letzter Commit (Datum) | Render-Funktion / Datei | Backend-Quelle | In Sync? | Veraltete / falsche Zahlen? | Fehlende Features / Mängel | Fix (S / M) |
|---|---|---|---|---|---|---|---|
| **Tab 9: Upload** (`view-upload`) | `9908e00` (2026-11-14 17:03:58) | `_build_upload_section_html` (`src/prezero/ui.py`) | `ingest.py`, `compute_upload_check()` | Ja | Keine falschen Zahlen (449 Standorte, 1.061 Serien, 11.701 Zeilen), aber irreführendes Label: 449 war als „Container / Standorte“ betitelt | Fehlender „Stand &lt;Datum&gt;“-Badge; unformatiertes snake_case `material_type` | **S** (Label präzisieren auf „Standorte (physisch)“, Code-Tags, Stand-Badge) |
| **Seite: Trends Chart** | `32f9e14` (2026-11-14 15:14:49) | `plot_trends` (`src/prezero/viz.py`) | Matplotlib, `data/raw/` | Ja | Keine; Monatsdurchschnitte nach Glasfarbe | Statisches PNG ohne interaktive Hover-Tooltips | **M** (nach Freeze: interaktives Plotly-Chart) |
| **Tab 2: Forecast** (`view-forecast`) | `085b816` (2026-11-14 18:33:55) | `render_forecast_timeline_map_html` (`src/prezero/ui.py`) | `forecast.py`, `viz.plot_forecast_map` | Ja | Keine; Horizons (+0/+7/+14/+21 d) und Füllstandsdeckel 110 % korrekt erklärt | Fehlendes „Kartenkoordinaten simuliert“-Honesty-Banner direkt über der Karte | **S** (Honesty-Banner für simulierte OSM-Kartenpunkte ergänzen) |
| **Tab 3: Heatmap** (`view-heatmap`) | `085b816` (2026-11-14 18:33:55) | `_build_heatmap_section_html` (`src/prezero/ui.py`) | `heatmap.py`, `data/processed/scored_*.csv` | Ja | Keine; 52 Kalenderwochen synchron mit Rohdaten | Fehlender Stand-Badge; Link zu Tab 4 („Route & Freigabe“) im Beschreibungstext war rein statischer Text | **S** (Stand-Badge im Header; interaktiven Sprunglink zu Tab 4 verdrahten) |
| **Tab 6: Variablen** (`view-variables`) | `8070765` (2026-11-14 18:38:10) | `_build_variables_section_html` (`src/prezero/ui.py`) | `prezero_config.json`, `OperationalConfig` | Ja | Keine; 11 t Gewicht, 26 m³ Volumen, 8 h Schicht, 1.202,24 km Vollrunde | Fehlender Stand-Badge; Text sprach von „heute selbst gescrapt“ statt präzise „simulierte Zuordnung auf OSM-Containerpunkten“ | **S** (Stand-Badge; Präzisierung der OSM-Zuordnung) |
| **Tab 2: Backtest-Card** (`view-forecast`) | `2005f7f` (2026-11-14 19:33:48) | `_build_backtest_section_html` (`src/prezero/ui.py`) | `scripts/backtest.py`, `backtest_summary.json` | Ja | Keine; Braunglas-Median 95,4 d vs. 42,0 d, Weißglas 32,5 d, MAE 19,9 pp | Vollständig synchron mit Pitch-Proof A3 | **Kein Fix nötig** |
| **Tab 4: Stopp-Daten** (`view-route`) | `cdd7529` (2026-11-14 19:35:37) | `render_route_view_data` (`src/prezero/ui.py`) | `routing.py`, `tour.py` | Ja | Keine; 25 Stopps, 19 Runden, 4 Fahrzeuge, 142,82 t, 249,9 km | Vollständig synchron mit Backend-Route | **Kein Fix nötig** |
| **Tab 1: Daten** (`view-data`) | `abd9ca2` (2026-11-14 20:13:45) | `_build_data_section_html` (`src/prezero/ui.py`) | `compute_measurement_analysis`, `glass_fill_levels_anonymized_f.csv` | Ja | Keine; 11.701 Messungen, 1.192 overfull, 1.061 Container | Fehlender Stand-Badge; Hinweis in Top 20 zum Copilot war nicht verlinkt | **S** (Stand-Badge ergänzen; Tab-Link zu Tab 5 Copilot setzen) |
| **Tab 4: Route & Freigabe** (`view-route`) | `abd9ca2` (2026-11-14 20:13:45) | `_build_route_section_html` (`src/prezero/ui.py`) | `routing.py`, `approval.py`, `tour.py` | Ja | Keine; 249,9 km vs. 1.202,24 km Status Quo Vollrunde | Querverweis „Tab ‚Fairer Vergleich‘“ war unklickbarer Text | **S** (Klickbaren Tab-Sprung zu Tab 7 einbauen) |
| **Tab 7: Fairer Vergleich** (`view-benchmark`) | `abd9ca2` (2026-11-14 20:13:45) | `_build_benchmark_section_html` (`src/prezero/ui.py`) | `benchmark_results.csv`, `compute_benchmark_summary()` | Ja | Keine; B0 (1.795,9 km), B1 (1.662,7 km), B2 (1.165,9 km), B4 (1.053,3 km), Bedarfs-Effekt 29,9 %, Gesamt vs B1 36,7 % | Fehlender Stand-Badge; unstyled snake_case im Quellenhinweis (`benchmark_results.csv`) | **S** (Stand-Badge; `<code>`-Formatierung für Dateinamen) |
| **Tab 8: Datencheck** (`view-datacheck`) | `abd9ca2` (2026-11-14 20:13:45) | `_build_datacheck_section_html` (`src/prezero/ui.py`) | `compute_data_check()`, `cleaned_readings.csv` | Ja | Keine; 1.061 Serien, 1.192 Überfüllungen, 0,551 Regularity Score | Fehlender Stand-Badge; unstyled snake_case `cleaned_readings` | **S** (Stand-Badge; `<code>cleaned_readings.csv</code>`) |
| **Tab 10: Standortplanung** (`view-location-planning`) | `0194d20` (2026-11-14 22:07:35) | `_build_location_planning_section_html` (`src/prezero/ui.py`) | `location_planning.py` | Ja | Keine; 3 Kandidaten (#1 49.143, 9.221, Score 0.77), 12 Wochen Adoptionszeit | Fehlender Stand-Badge im Section-Header; Honesty-Banner ist bereits vorhanden | **S** (Stand-Badge im Section-Header ergänzen) |
| **Tab 11: A/B Replay** (`view-demo`) | `0194d20` (2026-11-14 22:07:35) | `build_demo_section_html` (`src/prezero/demo.py`) | `demo.py`, `demo_playback_cache.json` | Ja | Keine; 349 Tage, 11.701 vs 11.321 Leerungen (-380), 0 vs 1.192 Überläufe, 66,0 % vs 83,5 % Füllstand | Großes Honesty-Banner bereits vorhanden; Datumsauswahl über Replay-Slider | **Kein Fix nötig** |
| **Header: Today Hero** | `2210c74` (2026-11-14 23:08:21) | `build_hero_html` (`src/prezero/hero.py`) | `hero.py`, Snapshot-Metriken | Ja | Keine; „249,9 km statt 1.202,2 km (Status quo)“, 4 LKW, 7,58 h Schicht, 142,82 t | Alle Zahlen synchron mit A3-Proof; Prozesskette 1..5 vorhanden | **Kein Fix nötig** |
| **Header: Disponenten-Slideshow** | `6d46b3c` (2026-11-14 23:15:35) | `_build_dispatcher_slideshow_html` (`src/prezero/ui.py`) | SVG-Generatoren in `ui.py` | Ja | Keine; Slide 1 Prognose, Slide 2 Glasarten, Slide 3 Varianten (Baseline, 6h, 8t, +1 Fahrzeug, alle kritischen) | Vollständig synchron; Kennzahlen-Labels rechts formatiert | **Kein Fix nötig** |
| **Fahrer-Tour & GPX/Maps/QR** | `89ea38d` (2026-11-14 23:07:44) | `tour.py`, `_render_driver_rows_html` | `src/prezero/tour.py` | Ja | Keine; Interleaving von Betriebshof-Start, Stopps, Depot-Entladungen und Schichtende | GPX 1.1 Export, Google Maps Deep-Links, Offline-QR-Code vorhanden | **Kein Fix nötig** |
| **Tab 5: Copilot** (`view-copilot`) | `cb2f00f` (2026-11-15 09:11:39) | `_build_copilot_section_html` (`src/prezero/ui.py`) | `copilot.py` | Ja | Keine; alle 10 Domain-Intents mit Stand `<Datum>` und Quellenbelegen verdrahtet | Vollständig synchron; Knowledge-Cards für alle 10 Intents implementiert | **Kein Fix nötig** |
| **Multi-Stream Transfer** | `167e3d7` (2026-11-14 23:10:34) | `model.py`, `cli.py`, `paper_ui_2026-04-15.html` | `WasteStream` (Papier, Bio, Gastro, Plastik) | Ja | Deterministischer Generator (Seed 42) generiert identische Struktur | Papier existiert als eigene Seite (`paper_ui_2026-04-15.html`), kein In-Page Dropdown-Umschalter | **M** (nach Freeze: Dropdown im UI für Live-Umschaltung des Abfallstroms) |

---

## 2. Die Top 5 identifizierten Mängel

1. **Tab 9 (`view-upload`) KPI-Label-Konflation (Standorte vs. Container):**  
   Die erste Kennzahl-Karte trug das Label `Container / Standorte` mit dem Wert `449` und Unterzeile `Serien: 1061`. Dies führte zu Unklarheit, da 449 die physischen Standorte (`Location_id`) sind und 1.061 die tatsächlichen Container (`Location_id × material_type`).  
   *Behebung (S):* Präzisierung auf `Standorte (physisch)` mit Untertitel `Container (Serien): 1.061 · Messzeilen: 11.701`.

2. **Inkonsistente „Stand &lt;Datum&gt;“-Badges in Sekundär-Tabs:**  
   Während Header, Tab 2, Tab 4 und Tab 5 vorbildlich mit dem Stichtag-Badge (`Stand 15.04.2026`) versehen waren, fehlte dieser Badge in den Section-Headern von Tab 1, 3, 6, 7, 8, 9 und 10.  
   *Behebung (S):* Einheitliche Auszeichnung aller Tab-Header mit `<span class="badge stand-badge stand-label" data-stand-date="{date}">{stand_de}</span>`.

3. **Fehlendes Honesty-Banner für Kartenkoordinaten in Tab 2 (`view-forecast`):**  
   Tab 2 bettet eine interaktive Heilbronn-Karte ein, verfügte aber im Gegensatz zu Tab 10 und Tab 11 über kein lokales Banner, das klarstellt, dass die Pins auf simulierten OSM-Glascontainer-Standorten basieren. In Tab 6 wurde zudem die veraltete Formulierung „selbst gescrapt“ verwendet.  
   *Behebung (S):* Honesty-Banner in Tab 2 ergänzt und Formulierung in Tab 6 auf „simulierte Zuordnung auf OSM-Containerpunkten“ geschärft.

4. **Unklickbare Querverweise zwischen Tabs (Tab-Wiring):**  
   In Tab 4 stand als reiner Text `Pitch-Zahl (alle kritischen): Tab „Fairer Vergleich“`, in Tab 3 `Tab „Route & Freigabe“`, in Tab 1 der Hinweis auf den Copilot. Ein Klick darauf bewirkte nichts.  
   *Behebung (S):* Auszeichnung als interaktive Buttons/Links mit `onclick="activateTab('...')"` und CSS-Klasse `.tab-link-btn`.

5. **Unformatierte Code- und Spaltennamen (snake_case-Hygiene):**  
   In Tab 9 waren Pflichtspalten (`Location_id, material_type, date, fill`), in Tab 8 `cleaned_readings` und in Tab 7 `benchmark_results.csv` als unformatierter Fließtext gerendert.  
   *Behebung (S):* Durchgängige Typografie mit `<code>`-Tags.

---

## 3. Liste der M-Features („Nach Freeze“)

1. **In-UI Abfallstrom-Umschalter:**  
   Aktuell wird für alternative Abfallströme (z. B. Papier) eine separate Seite `paper_ui_2026-04-15.html` via CLI erzeugt. Ein dynamischer Live-Umschalter im Frontend-Header erfordert gebündelte JSON-Payloads aller Ströme (Aufwand: M).
2. **Reales Straßennetz-Routing (OSRM / OpenRouteService):**  
   Aktuell wird die Straßenentfernung über Haversine-Luftlinie × 1,30 Umwegfaktor approximiert. Turn-by-Turn Routing erfordert einen laufenden OSRM-Container (Aufwand: M).
3. **Flottenoptimierung mit Flottenobergrenze und gemischten Fahrzeugtypen:**  
   Aktuell rechnet das System mit homogener 11-t-Flotte ohne Beschränkung der LKW-Zahl (Aufwand: M).
4. **Standortspezifische Behältervolumina:**  
   Aktuell haben alle Behälter ein einheitliches Nennvolumen von 3,0 m³ (Aufwand: M).

---

## 4. Status Quo Differenzierung: 1.202,24 km vs. B1 (1.662,70 km)

Im UI wird sauber und belegbar zwischen zwei Referenzpunkten differenziert:
- **1.202,24 km (Status Quo Vollrunde für den Demo-Tag in Tab 4 / Hero):**  
  Berechnet in `src/prezero/routing.py` als kapazitätsbeschränkte Nearest-Neighbor-Tour über alle 121 physischen Standorte unter denselben physikalischen Regeln (11 t Gewicht, 26 m³ Volumen, 8 h Schicht, Depots). Dient als direkter operativer Vergleich zur geplanten 25-Stopp-Tour (249,9 km, -79,2 % km).
- **1.662,70 km (B1 im wissenschaftlichen Benchmark in Tab 7):**  
  Berechnet in `scripts/benchmark.py` als optimierter Status Quo über 121 Standorte im 4-Stufen-Vergleich gegen B0 (1.795,9 km), B2 (1.165,9 km) und B4 (1.053,3 km), woraus sich der Bedarfs-Effekt (29,9 %) und der Gesamteffekt (36,7 %) ableiten.
