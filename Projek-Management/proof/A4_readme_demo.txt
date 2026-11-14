# All commands referenced in README.md exist

OK   prezero-route ingest
OK   prezero-route score
OK   prezero-route route
OK   prezero-route visualize
OK   prezero-route run
OK   prezero-route propose
OK   prezero-route approve

# Stale script references in README.md:
(none)

# Demo flow section:
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
