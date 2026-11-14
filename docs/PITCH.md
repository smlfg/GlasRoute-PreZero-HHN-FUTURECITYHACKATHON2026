# Pitch – GlasRoute (PreZero Challenge)

Dauer: ca. 3 Minuten · Demo-Datum: **15.04.2026**

Alle Zahlen sind aus `data/raw/glass_fill_levels_anonymized_f.csv` und den Pipeline-Outputs
(`data/processed/scored_2026-04-15.csv`, `route_2026-04-15.json`, `benchmark_results.csv`) reproduzierbar.
Beleg: `Projek-Management/proof/A3_pitch_zahlen.txt` (Stand 14.11.2026, 18:30).

---

## 1. Problem

Glascontainer in Heilbronn werden nach festem Plan geleert. Laster fahren zu halbleeren Containern,
während andere überlaufen.

**PreZero selbst formuliert es so (Pitch-Folie 2):**
> „Emptying these containers usually takes place area by area. Then all containers in the area are emptied,
> regardless of the actual fill level ('you'll drive past there anyway')."

→ Das ist unser Status quo (Benchmark B1): alle 121 physischen Standorte leeren. Der Großteil der
Ersparnis (Bedarfs-Effekt 81,2 %) kommt daher, **nur die kritischen anzufahren**; das Routing selbst
bringt bei gleichen Stopps nur weitere 1,5 %.

**Belegt:** 11.701 Messungen, 449 Container, 1.192 `overfull`-Ereignisse — jeder vierte
Überlauf-Fall betrifft Weißglas (731 von 1.192).

## 2. Warum löst es das?

Jede unnötige Fahrt kostet Sprit, Zeit und CO₂. Überfüllte Container ärgern Bürger und
verschmutzen die Stadt. Der Disponent entscheidet heute aus dem Bauchgefühl, weil Füllstandsdaten
nicht in Routen übersetzt werden.

## 3. Was man spart (Demo 15.04.2026)

**Fairer Vergleich** (`scripts/benchmark.py`, Website-Tab „Fairer Vergleich“): alle Varianten mit
denselben Regeln (11 t pro Runde, Entladung am Wertstoffhof, max. 8 h, Stopp = physischer Standort).
Stichtag 15.04.2026, Zuordnungs-Seed 42.

| Variante | Standorte | km | Runden |
|---|---|---|---|
| B1 Status quo: alle Standorte, optimierte Reihenfolge | 121 | 1.584,92 | 93 |
| B2 nur kritische, Nearest Neighbor | 73 | 297,30 | 13 |
| B4 nur kritische, OR-Tools | 73 | **292,84** | 12 |

| Effekt | Wert | Spanne (4 Stichtage × 3 Seeds) |
|---|---|---|
| **Bedarfs-Effekt** (B1 → B2) | **81,2 %** | 79,0–97,1 % |
| **Routing-Effekt** (B2 → B4) | **1,5 %** | 0,0–17,1 % |
| **Gesamt** (B1 → B4) | **81,5 %** | 81,0–97,1 % |

Gilt pro kompletter Gebietsleerung (Status quo leert alle 808,2 t auf einmal). Alle Füllstände sind der geschätzte Stand heute: Der Fahrer misst beim Besuch und leert, danach füllt sich der Container wieder ab ca. 0 %. Die alte Zahl
24,1 % (119,75 vs. 157,72 km) ist ungültig: Sie verglich eine Tour mit Kapazitätsgrenzen gegen eine
volle Runde ohne.

| Tages-Tour (Stopp-Limit 25) | Wert | Herkunft |
|---|---|---|
| Kritische Standorte | 72 physische Orte (108 IDs) | `route_2026-04-15.json` |
| In dieser Tour | 25 von 72 (47 offen) | `route_2026-04-15.json` |
| Strecke | 125,21 km | `route_2026-04-15.json` |
| Fahrzeuge / Runden | 2 / 7 | `route_2026-04-15.json` |
| Fahrzeugstunden gesamt / längste Schicht | 10,51 h / 7,26 h (Limit 8 h) | `route_2026-04-15.json` |
| Sammelmenge | 63,6 t | `route_2026-04-15.json` |

Formulierung im Pitch: „Heute wird das ganze Gebiet geleert: 1.585 km. Nur die 73 kritischen
Standorte: 297 km, 81,2 % weniger. Der Solver holt bei gleichen Stopps nur noch 1,5 % raus: 293 km.“

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
- **Generisch, wie in der Challenge gefordert** („incorporate configurable operational variables"):
  11 Betriebsvariablen liegen in `prezero_config.json`, nicht im Code. Jede Annahme ist im Code als
  „Annahme, von PreZero zu ersetzen" markiert.
- Ortsdaten heute: **alle 449 Standorte sind echte OSM-Glascontainer** in Heilbronn. Weil die
  PreZero-IDs anonymisiert sind, ist die Zuordnung **simuliert** (`source=osm_assigned`,
  `confidence=simulated_mapping`) — im Pitch offen so gesagt. PreZero erwähnt in seiner Challenge
  keine Koordinaten; die Datenanalyse steht im Mittelpunkt. Sobald PreZero die echte
  Zuordnungstabelle einspielt, übernimmt das System sie ohne Codeänderung.


---

## Demo-Ablauf

```bash
prezero-route run --date 2026-04-15     # Pipeline
prezero-route propose                   # Vorschlag anzeigen
prezero-route approve --by "Disponentin"  # Freigabe + Beleg
```

Erwartete Ausgabe:

> Route proposal for 2026-04-15 — 25 stops · planned 125.21 km · vehicles 2 ·
> vehicle hours 10.51 (longest shift 7.26 h) · collected 63.58 t

## Live-Nachfrage an PreZero: die Betriebsvariablen

PreZero ist das ganze Wochenende bei HHN (*„Feel free to reach out anytime if you have questions or
need additional data."*). Unsere 11 Betriebsvariablen sind im Code als **„Annahme, von PreZero zu
ersetzen"** markiert — das ist exakt seine Anforderung „incorporate configurable operational variables".

```bash
# Vorher (Annahmen)
prezero-route route --date 2026-04-15 --max-stops 25
# → 2 Fahrzeuge, 7 Runden, 10,5 h, 63,6 t, 125 km

# Nachher (Zahlen von PreZero, z. B. Dichte 300, Umwegfaktor 1,2 in prezero_config.json)
prezero-route route --date 2026-04-15 --max-stops 25 --config prezero_config.json
# → 2 Fahrzeuge, 5 Runden, 8,8 h, 47,7 t, 100 km
```

Live ausgetauscht (z. B. Dichte 400 → 300 kg/m³, Umwegfaktor 1,35 → 1,2) ändert sich das Ergebnis
sichtbar: **5 statt 7 Runden, 100 statt 125 km**. Das belegt live, dass das Tool nicht auf die
Daten hineingebaut wurde, sondern konfigurierbar ist.

## Offene Punkte (bewusst offen)

- Echte PreZero-Koordinaten fehlen → die Zuordnung der anonymisierten IDs bleibt simuliert
  (`osm_assigned` / `simulated_mapping`); Austauschpfad ist vorbereitet.
- Die Route ist eine Luftlinien-Näherung (Umwegfaktor 1,35), kein Straßenrouting.
- Kein Multi-Fahrzeug-Optimum: gezeigt wird, dass 2 Fahrzeuge nötig sind, und wie man sie verteilt.
- Die Betriebsvariablen sind Annahmen, bis PreZero Zahlen liefert — das ist der Live-Hook, kein Mangel.
