# Plan – PreZero Route Hackathon

## Zielbild So 13:00

- Funktionierende CLI-Pipeline
- Statische Karte + Trends
- Route für ein Demo-Datum
- Pitch-Doku

## Zeitplan

| Zeit | Meilenstein | DoD | Fallback |
|---|---|---|---|
| Sa 15:00 | Ingest | `cleaned_readings.csv` valide | Manuelle Bereinigung |
| Sa 17:00 | Features + Scoring | Top-10 kritisch plausibel | Nur 2–3 Features |
| Sa 19:00 | Route | `route.json` erzeugt | Nur Liste, keine Karte |
| Sa 21:00 | Visualisierung | Karte + Plots rendern | Nur PNG |
| Sa 23:00 | Doku + HAI-Step | README + Architektur | Kürzere Docs |
| So 08:00 | Pitch | 3 Demo-Szenarien | 1 Szenario |
| So 10:00 | Dry-Run | End-to-end ohne Crash | Pre-generierte Outputs |
| So 11:00 | **Freeze** | Pitch + README final | Nur Bugfixes |
| So 12:30 | Push | Repo sauber | — |
| So 13:00 | Abgabe | Code + Präsentation | — |

## Risiken

1. Keine echten Koordinaten → `locations_synthetic.csv` als Platzhalter.
2. Scope Creep → Harte Freeze-Zeiten, ein Fahrzeug.
3. Müdigkeit → Kern muss um 23:00 stehen.

## Do's / Don'ts

- Do: CLI-first, kleine Schritte, validieren.
- Don't: Dashboard-Overengineering, Flottenoptimierung, erfundene Zahlen.

## Stand (Sa 17:15)

**Solaufstellung:** das Projekt läuft solo mit Agenten-Workern (Claude Code, Zed/Copilot) — die
ursprüngliche Rollenaufteilung unten ist Geschichte. Geliefert ist:

| Slice | Stand |
|---|---|
| Ingest → Features → Scoring → Routing | ✅ Ende-zu-Ende (`prezero-route run --date 2026-04-15`) |
| Geo-Modul (OSM-Abruf + Resolver) | ✅ siehe Slice unten + Vertragsnotiz |
| Disponent-Freigabe (Human-Agent Interface) | ✅ `propose` / `approve` / `--reject`, Beleg-JSON |
| Forecast (KW 16–19) | ✅ `prezero-route forecast`, `forecast_16.html` |
| Heatmap (alle 449 Container, Wochen-Slider) | ✅ |
| Lokale 4-View-Weboberfläche | ✅ `prezero-route ui`, `ui_<date>.html` |
| Pitch-Material | ✅ `docs/PITCH.md` + `Pitch/NOTES.md`, Zahlen gegen Belege geprüft |
| **Offen** | Folien bauen, Live-Hook üben (`--config`), Dry-Run, **Freeze So 11:00** |

Der Live-Hook: 11 Betriebsvariablen in `prezero_config.json` — mit PreZeros Zahlen gerechnet
(2 Fahrzeuge/120 km → 1 Fahrzeug/99 km, getestet).

## Challenge-Kernfragen: Status (Sa 17:15)

| Kernfrage der Challenge | Status | Umsetzungsgrad & Befund |
|---|---|---|
| **1. Analyze:** Find patterns in collected data of >1 year | ✅ **90 %** | Saisonalität (März-Peak 37,6 % overfull), Materialtrend (61 % Weißglas) und Dynamiken belegt. Taggenaue Feiertags-/Ferienkorrelation fehlt noch. |
| **2. Combine:** See if containers have the same “behavior” | ⚠️ **60 %** | Metriken (Füllrate, Overfull-Quote) und Kritikalitätsklassen vorhanden; formales Kohorten-/Cluster-Modell (z. B. „Hotspots“ vs. „Wohngebiet“) fehlt noch. |
| **3. Build:** Universal tool where we see patterns | ✅ **95 %** | CLI-Pipeline + statische & interaktive Visualisierungen (`forecast_16.html`, `heatmap.py` mit Wochenslider, `ui_<date>.html` 4-View-Dashboard). |
| **4. Create:** Generic route-planning tool on individual variables | ✅/⚠️ **80 %** | 11 Variablen in `prezero_config.json` externalisiert, Schicht-/Kapazitätsgrenzen aktiv; Flottensplitter auf 1 Fahrzeug fokussiert. |

## Gap-Analyse zur Challenge-Vorgabe (Stand Sa 17:15)

Abgleich der aktuellen Pipeline gegen die 5 Aufgabenpunkte der PreZero-Challenge:

### 1. Analyze (Datenanalyse & Muster)
- **Erfüllt:**
  - Distinct Patterns & Saisonalität belegt (z. B. Peak im März mit 37,6 % `overfull`, Sommertief).
  - Material-Trend belegt (Weißglas mit 61 % aller Überläufe).
  - Container-Metriken (Füllrate, Overfull-Quote, Tage seit Leerung).
- **Lücke (Gap):**
  - **Externe Faktoren / Kalender-Events:** Explizite Auswertung von Ferienzeiten (BW) und Feiertagen (Ostern, Weihnachten, Pfingsten) ist in den Daten noch nicht als separates Feature/Visualisierung isoliert.

### 2. Combine (Container-Gruppierung & Verhalten)
- **Erfüllt:**
  - Trennung nach Materialtypen und Priorisierung nach Kritikalitäts-Score.
  - Per-Container-Verhaltensmetriken (`avg_daily_increase`, `overfull_rate`).
- **Lücke (Gap):**
  - **Verhaltens-Clustering:** Es gibt noch keine expliziten Cluster-Labels / Verhaltensgruppen (z. B. *„Schnellfüller / Hotspot“*, *„Regelmäßige Füller“*, *„Saisonale Ausreißer“*).

### 3. Build & General Variables (Betriebsvariablen & Tooling)
- **Erfüllt:**
  - 11 Variablen in `prezero_config.json` externalisiert (Glasdichte 400 kg/m³, Container-Volumen 2,5 m³, Fahrzeugkapazität 11 t, Shift-Limit 8 h, Geschwindigkeiten, Depot-/Umschlagskoordinaten).
  - Universelles Tooling mit CLI (`prezero-route`) und visuellen Dashboards (Heatmap, Forecast-Timeline, Tourenkarte).
- **Lücke (Gap):**
  - Keine funktionale Lücke — vollständig konfigurierbar wie gefordert.

### 4. Create: Route Optimization & Fleet Deployment
- **Erfüllt:**
  - Dynamischer Tourenvorschlag basierend auf Kritikalitäts-Score unter Einhaltung von Schichtzeit, Fahrzeuglast und Umschlagstopps.
  - Human-in-the-Loop-Freigabe (`propose` / `approve` / `--reject`).
- **Lücke (Gap):**
  - **Multi-Vehicle / Fleet Sizing:** Die Challenge fragt *„determine optimal fleet deployment (single or multiple vehicles required)"*. Aktuell ist das Routing als Ein-Fahrzeug-Tourenplanung ausgelegt (Hackathon-Scope). Es fehlt eine explizite Heuristik-Ausgabe wie: *„Für Tag X mit Y Tonnen / Z kritischen Stopps werden N Fahrzeuge empfohlen"*.

### 5. Deliverables & Pitch
- **Erfüllt:**
  - Data Ingestion Tool (CLI-Pipeline).
  - Visualisierungen (Heatmap mit Wochen-Slider, Forecast, Routenkarte, UI).
  - Route Engine Prototyp + Dokumentation (`docs/ARCHITEKTUR.md`, `README.md`).
- **Lücke (Gap):**
  - Finales Pitch-Deck (Folien) erstellen.
  - Rehearsal des Live-Hooks (`--config` Vorführung) und End-to-End Dry-Run vor Freeze.

## Solaufstellung & Re-Planning (historisch, Sa 15:00)

### 1. Rollen & Schritt 1 (Task 1 – Datengrundlage)

- **Ich (Samuel):** Schwerpunkt auf **Task 1 / Schritt 1** (Ingest, Datenbereinigung & Datengrundlage) sowie **Prior-Art-Recherche** (bestehende Konzepte & Lösungen sichten).
- **Kimi:** **Ortsdaten** (Geo-Koordinaten, Standort-Matching, `locations`).
- **Diebsig:** **Visualisierung**, einzelne **Komponenten** und **Datenauswertung**.

### 2. Re-Planning-Gate nach Schritt 1

Sobald Schritt 1 abgeschlossen ist, folgt ein bewusster **Checkpoint**, bevor es in die Schritte 2–5 geht:

1. **Scope-Check:** Prüfen, ob wir noch innerhalb der Challenge-Anforderungen und des Zeitrahmens liegen.
2. **Prior Art auswerten:** Erkenntnisse aus bestehenden Konzepten einfließen lassen.
3. **Projekt restrukturieren & Zielbild schärfen:** Klar festlegen, was wir genau erreichen wollen, und auf der sauberen Datengrundlage aus Schritt 1 die Umsetzung von **Schritt 2, 3, 4 und 5** neu takten.

### 3. Konzept-Entwurf für Schritt 2 (noch vorläufig / beim Gate zu finalisieren)

- **Kleines lokales Web-Frontend:** Drag-and-Drop-Upload für eine CSV-Datei → automatische Berechnung/Auswertung der Daten (für die Demo **lokal** bevorzugt statt Cloudflare-Hosting, um flexibel zu bleiben).
- **Auswertung & Visualisierung:** Datenverarbeitung und Plots mit **Pandas**.
- **Lokales LLM + RAG-System (Recommendation-based, ggf. Voice-based):**
  - Kleines lokales Modell mit **RAG-System**, über das man sich (per Text oder **Voice-based**) über die aktuelle Datenlage unterhalten kann.
  - Bewusst **recommendation-based** (Empfehlungen für den Menschen) statt rein *decision-based* (autonome Entscheidungen).
- **Offene Scope-Creep-Frage für das Re-Planning:**
  - *Festes CSV-Schema* (wie die aktuelle PreZero-CSV) vs. *variable CSV-Struktur mit adaptiven Metriken* zur Auswertung. Entscheidung fällt beim Re-Planning-Gate nach Schritt 1, damit kein unnötiger Scope Creep entsteht.
- **Schritt 3–5:** Werden nach dem Re-Planning-Gate auf Basis der Ergebnisse aus Schritt 1 und der Prior-Art-Recherche konkretisiert.

## Slice: Geo-Positions-Modul (Mission M-20261114T144015-322994d8)

> **Vertragsnotiz (Sa 17:15):** geliefert wurde ein anderer Vertrag als hier geplant: statt
> `osm_heuristic`/`low` + `synthetic_placeholder` entscheidet die gelebte Lösung `osm_assigned` /
> `simulated_mapping` — alle 449 IDs auf echten OSM-Punkten, die ID-Zuordnung ist simuliert
> (Punkte wiederverwendet). Nachvollziehbar in `data/external/locations.csv` und
> `docs/STATUS.md`. Der Austauschpfad (`locations_real.csv`) ist unverändert gültig.

### Ziel und Abgrenzung

Für jede der 449 anonymisierten `Location_id`s genau eine Koordinate mit Herkunft und Verlässlichkeit bereitstellen. Reale OSM-Punkte dokumentieren reale Containerstandorte; ihre Zuordnung zu anonymen IDs bleibt ohne PreZero-Schlüssel eine **unbewiesene Heuristik** und erhält deshalb höchstens `confidence=low`. Spätere PreZero-Koordinaten ersetzen alle Heuristiken ohne Codeänderung.

Nicht-Ziele: keine 1:1-Behauptung, keine schwere GIS-Bibliothek, kein Routing-/Dashboard-Ausbau, keine Secrets, Commits oder Pushes.

### Umsetzung

1. **Recherche / Upstream:** Overpass-API und städtische/regionale Open-Data-Angebote live prüfen; mindestens drei Wiederverwendungskandidaten in `UPSTREAM_SEARCH.md` bewerten. Quellen, Abrufzeitpunkt, Ergebnis und Grenzen in `docs/GEO_DATENQUELLEN.md` festhalten.
2. **Fetch:** `scripts/fetch_locations.py` fragt Recycling-/Glascontainer im dokumentierten Heilbronn-BBox-/Area-Scope über Overpass ab, normalisiert Knoten sowie Ways/Relations über deren Center und schreibt `data/external/locations_real_attempt.csv`. Ein Request hat 10 s Connect- und 30 s Read-Timeout; maximal zwei Versuche (ein Retry) ohne Geheimnisse. Netzwerk-, Timeout-, HTTP- und Schemafehler werden sichtbar gemeldet, erzeugen eine leere Kandidatendatei und führen danach kontrolliert zum Fallback statt zum Abbruch ohne Ausgabe.
3. **Resolve / Match:** `src/prezero/locations.py` validiert IDs, Materialien und WGS84-Werte. `resolve_locations` wählt in fester Priorität (a) expliziter `real_path`, b) vorhandenes `data/external/locations_real.csv`, c) bestehende Matches/Synthetik. Direkte Providerdaten mit `Location_id` erhalten `prezero_supplied/high`; OSM-Zuordnungen sind eindeutig, deterministisch, materialbewertet und grundsätzlich `low`. Fehlende IDs werden mit Seed 2026 innerhalb der dokumentierten Heilbronn-BBox synthetisiert. Fehlende Pflichtspalten und ungültige/verdeckte Dubletten schlagen mit hilfreichen Fehlern fehl.
4. **Refresh:** `scripts/refresh_locations.py` lädt Rohdaten, akzeptiert `--real`, erzeugt/beachtet `data/external/locations_matched.csv` und schreibt das kanonische `data/external/locations.csv`, Statistiken auf stdout sowie `data/external/location_sanity_check.html` mit nach Quelle gefärbten Punkten. Der Fetcher ruft dieselbe Resolver-API auf; kein zweiter Matching-Algorithmus.
5. **Swap:** `data/external/locations_real.csv` mit mindestens `Location_id,lat,lon` genügt; Herkunft/Confidence werden ergänzt. Die zentrale Default-Auflösung bleibt unabhängig vom aktuellen Arbeitsverzeichnis nutzbar, CLI-Pfade bleiben relativ zum Projektroot.
6. **Doku:** README und Architektur erklären Abruf, Refresh, Datei-Priorität, Confidence und die drei Austauschschritte aus dem Auftrag.

### Tests und Abnahme

- Unit-Tests in `tests/test_locations.py` für Materialsets, deterministische Synthetik, eindeutige/heuristische OSM-Matches, direkte Providerpriorität, 449 IDs, ungültige CSVs sowie HTTP-, Schema- und Timeout-Fehler per Mock. Der Timeout-Mock muss belegen, dass der Resolver trotzdem alle IDs mit markierten Ersatzdaten liefert; Retry-Zähler und Timeout-Parameter werden geprüft.
- CLI-End-to-End: Fetch normal und simulierter Ausfall; Refresh ohne und mit temporärer PreZero-CSV; Sanity-HTML existiert und enthält alle Punkte. Temporäre Testdaten liegen ausschließlich unter `Projek-Management/tmp/`.
- Bestehende Pipeline-Tests in `tests/test_pipeline.py` laufen unverändert weiter. Statistik nennt reale Kandidaten, heuristische Zuordnungen und Synthetik getrennt.
- Abnahme: die Eingabe liefert 449 IDs; die Ausgabe hat genau 449 Datenzeilen, deren ID-Menge exakt der Eingabe-ID-Menge entspricht und deren IDs eindeutig sind; endliche `lat/lon` in gültigen WGS84-Bereichen; `source`, `confidence`, `match_reason` vorhanden; Synthetik ausschließlich `synthetic_placeholder/synthetic`; Import `from prezero.locations import load_locations` funktioniert.

### Boundaries / Reproduktion

Erlaubt sind ausschließlich: `PLAN.md`, `README.md`, `UPSTREAM_SEARCH.md`, `PLAN_VALIDATION_REPORT.md`, `docs/ARCHITEKTUR.md`, `docs/GEO_DATENQUELLEN.md`, `scripts/fetch_locations.py`, `scripts/refresh_locations.py`, `src/prezero/locations.py`, `tests/test_locations.py`, neue nicht-sensitive CSV-/HTML-Dateien unter `data/external/` sowie Evidenz, Council-Ausgaben und temporäre Testdaten unter `Projek-Management/`. Alle übrigen Pfade einschließlich Rawdaten, bestehendem Pipeline-Code und Konfiguration bleiben unverändert.

HTTP nutzt die Python-Standardbibliothek; Datenverarbeitung pandas und Karte das bereits deklarierte folium — damit ist keine Konfigurationsänderung nötig. Seed 2026; keine Löschungen. Bei fehlendem externen Datensatz werden ausschließlich klar markierte Platzhalter erzeugt. Plan-Council und unabhängiger Plan-Validator müssen den revidierten SHA vor Feature-Code erneut freigeben.
