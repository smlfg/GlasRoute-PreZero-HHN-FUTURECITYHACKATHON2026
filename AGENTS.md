# AGENTS.md — PreZero Route (Future City Hackathon 2026)

Lies diese Datei vor jeder Arbeit in diesem Repo. Sie überschreibt keine HAI-Vorgabe, sondern
ergänzt sie um die Projektgrenze.

## Was dieses Projekt ist

Prototyp für die **PreZero-Challenge**: aus Füllstandsdaten von Glascontainern in Heilbronn
eine priorisierte Leerungsroute für ein Fahrzeug erzeugen. Abgabe So 13:00.

Einstieg: `README.md` · Plan: `PLAN.md` · Anforderungen: `docs/ANFORDERUNGEN.md` ·
Geo-Quellen: `docs/GEO_DATENQUELLEN.md` · Pitch: `docs/PITCH.md`

## Titel zuerst, ID in Klammern

Opaque IDs bleiben der technische Schlüssel, sichtbar ist der Titel. Nenne zuerst den Titel,
die ID nur in Klammern. Dateinamen und `_new_id` nicht umbenennen.

Beispiel: `Routenheuristik für kritische Container (M-20261114T144015-322994d8)`

## Scope — was dieses Projekt baut

**Baut:**

- CLI-Pipeline: Ingest → Features → Scoring → Route → Visualisierung → Freigabe → Export
- Kritikalitäts-Score aus den vorhandenen Messungen
- Route für **ein** Fahrzeug, Distanz über Haversine
- Statische Visualisierungen (Folium-Karte, Matplotlib-Trends)
- Dokumentation: README, `docs/ARCHITEKTUR.md`, `docs/PITCH.md`

**Baut nicht:**

- Mehrere Fahrzeuge oder Flottenoptimierung
- Depot-, Schicht- oder Gewichtsmodelle (keine Daten vorhanden)
- Interaktives Web-Dashboard
- ML-Prognose des Füllstands
- Rekonstruierte Identität anonymisierter IDs

Der Readme der Challenge erlaubt das ausdrücklich: *"We understand the scope and time limits of
a hackathon. Our main goal is to see your creative problem-solving approach and prototype concept."*

## Daten-Wahrheit

Jede Kennzahl im Pitch kommt aus `data/raw/glass_fill_levels_anonymized_f.csv` (11.701 Messungen,
449 Locations, 1.192 `overfull`).

Ortsdaten sind nicht Teil der Challenge. `data/external/locations.csv` führt je Zeile
`source` und `confidence`:

| source | confidence | Bedeutung |
|---|---|---|
| `prezero_supplied` | `high` | Direktes Mapping von PreZero |
| `osm_heuristic` | `low` | OSM-Standort, Zuordnung unbestätigt |
| `synthetic_placeholder` | `synthetic` | Platzhalter, Seed 2026 |

Eine Zuordnung über Material ist **Heuristik, keine Identität**. Behaupte nie, ein Container
sei einem realen Standort zugeordnet. Der Austauschpfad ist vorbereitet: echte
`Location_id,lat,lon`-Daten in `data/external/locations_real.csv` ablegen, ohne Codeänderung
übernommen.

## Arbeitsweise

**TDD an den Modulen `features`, `scoring`, `routing`.** Rot vor Grün, eine Scheibe zur Zeit.
Kein Refactoring im Loop — das gehört ins Review.

`tests/test_locations.py` ist die Spezifikation für das Geo-Modul. Wenn ein Test und die
Implementierung auseinanderlaufen: **der Test ist die Spezifikation** — implementiere den Test,
nicht umgekehrt.

Prüfkriterien je Stufe stehen in `PLAN.md`. Eine Stufe gilt als fertig, wenn ihr Prüfkriterium
erfüllt ist und ihr Output in `data/processed/` liegt.

## Ein Schreiber zur Zeit

Zwei Agenten haben bereits gleichzeitig in dieses Repo committet. **Ab jetzt schreibt nur einer
zur Zeit.** Vor jedem Commit:

1. `git status` + `git log --oneline -3` — ist die Arbeit eines anderen drin?
2. Bei Konflikt: warten, bis dessen Commit durch ist, dann neu bauen. Nicht überschreiben.
3. Commit nur den eigenen Scope (`git add <eigene Pfade>`), nicht `git add -A`.

Wer gerade schreibt, steht in `docs/STATUS.md` unter „Aktive Schreiber“.

## Agenten

**Arbeitsvertrag für jeden Worker:**

- Goal (ein Satz)
- Non-Goal (was ausdrücklich nicht)
- Boundaries (Write-Root; außerhalb ist verboten)
- DoD (prüfbares Fertigkriterium)
- Stop (wann anhalten und Samuel fragen)
- `mission_id` und Lease, falls vorhanden

Ergebnis ist ein **Evidenzpfad** zurück in die Mission, nicht nur Chat-Text.

Freigabe-Punkte (nur Samuel entscheidet): bereinigte Daten validiert · Feature-Formeln ·
Top-Kritikalität plausibel · Route nachvollziehbar · Pitch-Zahlen belegt · Abgabe vor 13:00.

## HAI-Sequenz

Wenn `hai-mcp` verfügbar ist, ist es der verpflichtende Control-Plane-Pfad:

1. `hai_health` → `hai_status`
2. `hai_open_mission` (bzw. aktive Mission) + `hai_authorize_session`
3. `hai_checkpoint`; bei Abweichung `hai_check_activity` oder parken
4. `hai_close_mission` — oder `PARKED` / `BLOCKED` mit Evidenzpfad und genau einem nächsten Schritt

Fehlt MCP oder Health/Status: sichtbar `DEGRADED` — nur lesen und parken, keine Schreibarbeit.
Ein stiller Bypass ist verboten.

## Aufschreiben

- `03_HAI/LOGBUCH.md` — Entscheidungen, Fails, Lernregeln (append-only)
- `UPSTREAM_SEARCH.md` — Upstream-Recherche vor eigenem Bau
- `PLAN_VALIDATION_REPORT.md` — unabhängige Planfreigabe
- `Projek-Managment/fails/NNNN-kurzname.json` — strukturierte Fail-Records

Neue Erkenntnisse gehören in diese Dateien, nicht in den Chat.

## Do's

- CLI-first, kleine prüfbare Schritte, Output je Stufe in `data/processed/`
- Muster, die sich aus den Daten belegen lassen
- Anonymisiertes `Location_id` nie umbenennen
- Kern steht um 23:00; Sonntagmorgen nur Pitch und Polieren

## Don'ts

- Dashboard-Overengineering (Streamlit, Dash, React)
- Flottenoptimierung oder zweites Fahrzeug
- Zahlen ohne Beleg aus der CSV
- Realitätsbehauptung über synthetische oder heuristische Koordinaten
- Scope-Erweiterung nach So 11:00
