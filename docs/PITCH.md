# Pitch – GlasRoute (PreZero Challenge)

Dauer: ca. 3 Minuten · Demo-Datum: **15.04.2026**

Alle Zahlen sind aus `data/raw/glass_fill_levels_anonymized_f.csv` und den Pipeline-Outputs
(`data/processed/scored_2026-04-15.csv`, `route_2026-04-15.json`) reproduzierbar.

---

## 1. Problem

Glascontainer in Heilbronn werden nach festem Plan geleert. Laster fahren zu halbleeren Containern,
während andere überlaufen.

**Belegt:** 11.701 Messungen, 449 Container, 1.192 `overfull`-Ereignisse — jeder vierte
Überlauf-Fall betrifft Weißglas (731 von 1.192).

## 2. Warum löst es das?

Jede unnötige Fahrt kostet Sprit, Zeit und CO₂. Überfüllte Container ärgern Bürger und
verschmutzen die Stadt. Der Disponent entscheidet heute aus dem Bauchgefühl, weil Füllstandsdaten
nicht in Routen übersetzt werden.

## 3. Was man spart (Demo 15.04.2026)

**Was wird verglichen:** die geplante Tour gegen den Status quo „heute fährt der Fahrer alle
Container ab“. Das ist eine **Bedarfs-Ersparnis** (wir fahren nur die kritischen an), **keine
Routing-Ersparnis** (nicht dieselben Stopps in besserer Reihenfolge).

| Vergleich | Stopps | km |
|---|---|---|
| **Geplante Tour** (heute) | 25 | **119,75 km** |
| **Volle Runde** (Status quo, alle Standorte mit Daten) | 431 | 157,72 km |
| **Ersparte Strecke** | | **37,97 km = 24,1 %** |

| Weitere Kennzahl | Wert | Herkunft |
|---|---|---|
| Kritische Container an diesem Tag | 169 | `scored_2026-04-15.csv` |
| Fahrzeuge | 2 (1 Runde je Fahrzeug) | `route_2026-04-15.json` |
| Schichtstunden | 8,52 h (Limit 8,0 h) | `route_2026-04-15.json` |
| Sammelmenge | 41,8 t | `route_2026-04-15.json` |

Formulierung im Pitch: „Heute fährt das Fahrzeug alle 431 Standorte mit Daten ab — 157,72 km.
Unser Tool schlägt vor, die 25 kritischsten zuerst zu bedienen: 119,75 km, 24,1 % weniger Strecke,
und die überlaufenden Container sind zuerst dran."


**Saisonalität, belegt aus den Rohdaten** (Anteil `overfull` je Monat):

| Jan | Feb | **Mär** | Apr | Mai | Jun | Jul | Aug |
|---|---|---|---|---|---|---|---|
| 11,6 % | 12,9 % | **37,6 %** | 23,3 % | 22,7 % | 5,2 % | 5,0 % | 2,8 % |

→ **Peak Januar–Mai, Einbruch im Sommer.** Planung muss material- und standortspezifisch sein.

**Annahmen** (vollständig in `route_2026-04-15.json` unter `assumptions`): 400 kg/m³, 2,5 m³ je
Container, 11.000 kg Fahrzeuglast, Umwegfaktor 1,35, 25 km/h, 2 min Standzeit, 3 min je Container,
20 min Entladung, Yard 49.1427/9.2109, Umschlag 49.178/9.2085.

## 4. Wie funktioniert es

1. **Ingest** – CSV einlesen, `overfull` kodieren (11.701 → 11.701 Zeilen, 449 IDs).
2. **Features** – je Container und Material: letzter Füllstand, Füllrate, Overfull-Quote, Saisonfaktor.
3. **Scoring** – gewichteter Kritikalitäts-Score → `critical`-Flag.
4. **Routing** – Nearest-Neighbor über Haversine, ein Fahrzeug, Kapazitäts-, Schicht- und Umschlaggrenzen.
5. **Freigabe** – der Agent *schlägt* die Route vor, die Disponentin *gibt frei*.
6. **Export** – erst nach Freigabe entsteht der ausführbare Tourenplan.

**Human-Agent-Interface:** `prezero-route propose` erzeugt einen Vorschlag, `prezero-route approve`
oder `--reject` erzeugt einen Beleg mit Zeitstempel, Route und den entscheidenden Kennzahlen
(`data/processed/approval_2026-04-15.json`). Ohne Freigabe wird nichts dispatcht.

## 5. Wie setzt man es um?

- Läuft auf den **vorhandenen** Fillinq-Daten; ein Fahrzeug genügt als Start.
- Python-CLI, modular (`ingest` → `features` → `scoring` → `routing` → `viz` → `approve`).
- **Austauschbar:** echte Koordinaten kommen als `Location_id,lat,lon` in
  `data/external/locations_real.csv` — ohne Codeänderung (`scripts/refresh_locations.py --real`).
- Skalierbar: Betriebsvariablen (Fahrzeuglast, Schichtlänge, Standzeiten, Depot) liegen in einer
  Config-Datei, nicht im Code.
- Ortsdaten heute: **126 reale OSM-Glascontainer** in Heilbronn. Weil die PreZero-IDs anonymisiert
  sind, ist die Zuordnung eine **Heuristik** (`confidence=low`, `source=osm_heuristic`, „UNVERIFIED“),
  keine Identität. Die übrigen **323** Standorte sind deterministische Platzhalter (Seed 2026).
  Im Pitch offen als Demo-Daten gekennzeichnet — mit dem Hinweis, dass PreZero die echte
  Zuordnungstabelle ohne Codeänderung einspielen kann.

---

## Demo-Ablauf

```bash
prezero-route run --date 2026-04-15     # Pipeline
prezero-route propose                   # Vorschlag anzeigen
prezero-route approve --by "Disponentin"  # Freigabe + Beleg
```

Erwartete Ausgabe:

> Route proposal for 2026-04-15 — 25 stops · planned 119.75 km · saved 37.97 km (24.1 %) ·
> vehicles 2 · shift 8.52 h · collected 41.8 t

## Offene Punkte (bewusst offen)

- Echte PreZero-Koordinaten fehlen → Ortszuordnung bleibt Heuristik.
- Die Route ist eine Luftlinien-Näherung (Umwegfaktor 1,35), kein Straßenrouting.
- Kein Multi-Fahrzeug-Optimum: gezeigt wird, dass 2 Fahrzeuge nötig sind, und wie man sie verteilt.
