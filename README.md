# PreZero Route – Dynamic Glass Collection Routing for Heilbronn

Prototype for the **PreZero Challenge** at Future City Hackathon 2026 (HHN TechCampus Heilbronn).

Turns fill-level data from glass recycling containers into a prioritized, human-approved collection route.

## Problem

Glass containers in Heilbronn are emptied on a fixed schedule, regardless of how full they actually are. Trucks drive to half-empty containers while others overflow. That wastes fuel, time, and CO₂.

## Solution

A CLI tool that:

1. Ingests fill-level CSV data.
2. Analyzes patterns (material, season, overfull frequency).
3. Scores container criticality for a target day.
4. Builds a capacity-constrained route plan (Haversine; the demo date needs 2 vehicles in 5 rounds).
5. Extends it with a weekly fill forecast.
6. Presents the route for dispatcher approval (Human-Agent Interface).

## Quick start

```bash
# Install (editable, puts `prezero-route` on PATH)
pip install -e .

# Without installing: PYTHONPATH=src python3 -m prezero.cli <command>
```

## Demo-Ablauf (das, was am Sonntag läuft)

Drei Befehle, ein Datum:

```bash
prezero-route run --date 2026-04-15
```

Erzeugt `route_2026-04-15.json`, `map_2026-04-15.html`, `trends.png` und
`data/processed/scored_2026-04-15.csv`. Erwartete Ausgabe:

```
Pipeline complete for 2026-04-15: 169 critical locations (213 pairs).
119.75 km planned (25 stops) vs. 157.72 km full round (431 stops)
```

Dann der Human-Agent-Schritt — erst der Vorschlag, dann die Entscheidung:

```bash
prezero-route propose                      # Vorschlag anzeigen + speichern
prezero-route approve --by "Disponentin"   # freigeben -> Beleg mit Zahlen
```

Erwartete Ausgabe:

```
Route proposal for 2026-04-15
  stops:          25
  planned:        119.75 km
  saved:          37.97 km (24.1 %)
  vehicles:       2
  shift hours:    8.52
  collected:      41.8 t
```

`approve` schreibt `data/processed/approval_2026-04-15.json` (Zeitstempel, Freigebende, Route,
entscheidende Kennzahlen). Mit `--reject "<Grund>"` wird stattdessen eine Ablehnung mit Begründung
protokolliert. **Ohne Freigabe wird nichts dispatcht.**

## Alle Befehle

| Befehl | Zweck |
|---|---|
| `ingest` | Roh-CSV einlesen und bereinigen (`overfull` → 110 %) |
| `score --date` | Features + Kritikalitäts-Score bis zum Stichtag |
| `route --date` | Routenplan (Haversine, Kapazität, Schicht, Umschlag); `--config` tauscht die Betriebsvariablen |
| `visualize --date` | `trends.png` + `map_<date>.html` |
| `forecast --date` | Wöchentliche Füllstandsprognose (KW 16–19) → `forecast_16.html` |
| `ui --date` | Lokale 4-View-Weboberfläche aus Pipeline-Daten → `ui_<date>.html` |
| `run --date` | Alles in einem Durchlauf |
| `propose` | Route in einen freigabepflichtigen Vorschlag überführen |
| `approve` | Vorschlag freigeben oder ablehnen, Beleg schreiben |

## Ortsdaten

**Aktueller Stand:** alle 449 Standorte liegen auf echten OSM-Glascontainer-Punkten in Heilbronn
(`source=osm_assigned`, `confidence=simulated_mapping`). Weil die PreZero-IDs anonymisiert sind,
ist die **Zuordnung simuliert** (Punkte werden wiederverwendet) — das System sagt das offen dazu.
Sobald PreZero die echte Zuordnungstabelle liefert, wird sie ohne Codeänderung übernommen.

```bash
python scripts/fetch_locations.py    # OSM-Glascontainer holen (Area-Query, BBox-Fallback)
python scripts/refresh_locations.py  # Standorte neu auflösen
```

Zwischenprodukte: `locations_real_attempt.csv` (rohe Overpass-Kandidaten) und
`locations_matched.csv` (Auflösung vor dem Override) bleiben erhalten, das kanonische
Pipeline-Input ist `data/external/locations.csv` (exakt 449 Zeilen).

## Data

- `data/raw/glass_fill_levels_anonymized_f.csv` – provided by PreZero (11.701 readings, 449 containers).
- `data/external/locations_real_attempt.csv` – real candidate glass containers fetched from open data (Overpass/OSM) with `osm_id/provider_id`, coordinates, material tags, source and address where available.
- `data/external/locations_matched.csv` – per-`Location_id` resolution before final override: heuristic OSM assignments (`confidence=low`, explicitly unverified without a PreZero key) or deterministic synthetic placeholders.
- `data/external/locations.csv` – **canonical** pipeline input with exactly 449 rows (`Location_id, lat, lon, source, confidence, match_reason`).
- `data/external/location_sanity_check.html` – sanity map colored by source.
- `data/external/locations_synthetic.csv` – legacy placeholder file; prefer `locations.csv` / `refresh_locations.py`.

## Geo coordinates / PreZero swap

The location resolver is source-agnostic and labels every coordinate. The OSM points are real
places; because the anonymized IDs carry no mapping key, the assignment is **simulated** and
labeled as such (`osm_assigned` / `simulated_mapping`).

To replace simulated coordinates with PreZero's real mapping:

1. Place real coordinates in `data/external/locations_real.csv` (minimum columns: `Location_id, lat, lon`).
2. Run `python scripts/refresh_locations.py --real data/external/locations_real.csv`.
3. The pipeline automatically uses the real data (`locations_real.csv` is preferred and written into `locations.csv`; no code changes required).

Programmatic use:

```python
from prezero.locations import load_locations, resolve_locations

df = load_locations()  # reads data/external/locations.csv by default
# or resolve from raw readings with an explicit provider file:
# df = resolve_locations(raw_df, real_path="data/external/locations_real.csv")
```

`fetch_locations.py` fails gracefully: if Overpass is unavailable it records the error, writes an empty candidate file and still produces complete, labeled synthetic coordinates and the sanity map.

## Docs

- `docs/ANFORDERUNGEN.md` – challenge requirements
- `docs/ARCHITEKTUR.md` – technical architecture and geo swap path
- `docs/GEO_DATENQUELLEN.md` – checked open-data sources, limits, licenses/attribution
- `docs/INDEX.md` – index of the 10 data analyses (`docs/analysen/`)
- `docs/PITCH.md` – Sunday pitch structure with verified figures
- `docs/PITCH_EXECUTIVE_SUMMARY.md` – one-page summary of the data findings
- `docs/STATUS.md` – current state, pitch numbers, next steps
- `docs/UI_PLAN.md` – plan for the local web UI
- `Pitch/NOTES.md` – stage notes, live-demo script and the questions for PreZero
- `PLAN.md` – hackathon plan with checkpoints
- `AGENTS.md` – scope, data-truth rules and agent contract for this repo

## Tests

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
```

75 Tests: Ingestion, Geo-Auflösung (inkl. 449-ID-Vertrag, Timeout-Fallback, Prioritätslogik),
Features, Scoring, Routing, Visualisierung inkl. Prognose- und Heatmap-Karten, lokale
Weboberfläche und Disponent-Freigabe.

