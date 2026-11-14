# Pitch – GlasRoute (PreZero Challenge)

Dauer: ca. 3 Minuten · Demo-Datum: **15.04.2026**

Alle Zahlen sind aus `data/raw/glass_fill_levels_anonymized_f.csv` und den Pipeline-Outputs
(`data/processed/scored_2026-04-15.csv`, `route_2026-04-15.json`, `benchmark_results.csv`) reproduzierbar.
Beleg: `Projek-Management/proof/A3_pitch_zahlen.txt` (Stand 14.11.2026, 19:40, `RESULT: ALL MATCH`).

---

## 1. Problem

Glascontainer in Heilbronn werden nach festem Plan geleert. Laster fahren zu halbleeren Containern,
während andere überlaufen.

**PreZero selbst formuliert es so (Pitch-Folie 2):**
> „Emptying these containers usually takes place area by area. Then all containers in the area are emptied,
> regardless of the actual fill level ('you'll drive past there anyway')."

→ Das ist unser Status quo (Benchmark B1): alle 121 physischen Standorte leeren. Der Großteil der
Ersparnis (Bedarfs-Effekt 29,9 % am 15.04., 29–67 % übers Jahr) kommt daher, **nur fällige Container
anzufahren**; das Routing bringt bei gleichen Stopps weitere 9,7 % (2–14 %).

**Belegt:** 11.701 Messungen, 449 Container, 1.192 `overfull`-Ereignisse — jeder vierte
Überlauf-Fall betrifft Weißglas (731 von 1.192).

## 1b. Die Erkenntnis aus den Daten: Braunglas wird viel zu oft geleert

| Glasfarbe | ideal bis 80 % | heute tatsächlich | zu oft geleert | zu selten geleert |
|---|---|---|---|---|
| **Braunglas** | **95 Tage** | **42 Tage** | **89 %** | 2 % |
| Grünglas | 42 Tage | 34 Tage | 45 % | 7 % |
| Weißglas | 33 Tage | 33 Tage | 12 % | 16 % |

Bei 30 % aller Besuche war der Container unter 50 % voll, bei 11 % lief er über.
Daraus folgt: **ein Timer pro Container** statt eines festen Gebietsrhythmus.
Beleg: `docs/BACKTEST.md` (`python scripts/backtest.py`).

## 2. Warum löst es das?

Jede unnötige Fahrt kostet Sprit, Zeit und CO₂. Überfüllte Container ärgern Bürger und
verschmutzen die Stadt. Der Disponent entscheidet heute aus dem Bauchgefühl, weil Füllstandsdaten
nicht in Routen übersetzt werden.

## 3. Was man spart (Demo 15.04.2026)

**Fairer Vergleich** (`scripts/benchmark.py`, Website-Tab „Fairer Vergleich“): alle Varianten mit
denselben Regeln (11 t und 26 m³ pro Runde, Entladung am Wertstoffhof, max. 8 h, Stopp = physischer Standort).
Stichtag 15.04.2026, Zuordnungs-Seed 42.

| Variante | Standorte | km | Runden |
|---|---|---|---|
| B1 Status quo: alle Standorte, optimierte Reihenfolge | 121 | 1.662,70 | 98 |
| B2 nur fällige (Timer abgelaufen), Nearest Neighbor | 112 | 1.165,90 | 67 |
| B4 nur fällige, OR-Tools | 112 | **1.053,29** | 55 |

| Effekt | Wert | Spanne (4 Stichtage × 3 Seeds) |
|---|---|---|
| **Bedarfs-Effekt** (B1 → B2) | **29,9 %** | 28,6–67,1 % |
| **Routing-Effekt** (B2 → B4) | **9,7 %** | 2,3–14,1 % |
| **Gesamt** (B1 → B4) | **36,7 %** | 32,9–70,7 % |

Modell: Der Fahrer misst beim Besuch und leert; Füllrate = vorgefundener Stand ÷ Tage seit der Leerung;
ein Container ist **fällig, sobald Füllrate × Tage seit der letzten Leerung 80 % erreicht** (Timer).
Keine Score-Faktoren, kein fester Saisonfaktor (der Backtest hat ihn widerlegt). Mitte April sind
509 von 1.269 Containern fällig, darum ist der Bedarfs-Effekt an diesem Tag klein. Frühere Zahlen
(24,1 %, 70,7 %, 81 %) sind ungültig.

| Tages-Tour (Stopp-Limit 25) | Wert | Herkunft |
|---|---|---|
| Fällige Standorte | 106 physische Orte (509 Container) | `route_2026-04-15.json` |
| In dieser Tour | 25 von 106 (81 offen) | `route_2026-04-15.json` |
| Strecke | 249,9 km | `route_2026-04-15.json` |
| Fahrzeuge / Runden | 4 / 19 | `route_2026-04-15.json` |
| Fahrzeugstunden gesamt / längste Schicht | 22,68 h / 7,58 h (Limit 8 h) | `route_2026-04-15.json` |
| Sammelmenge | 142,8 t | `route_2026-04-15.json` |

Formulierung im Pitch: „Mitte April ist fast jeder Standort fällig, da spart Weglassen ein Drittel
(über das Jahr 30–67 %). Der eigentliche Hebel ist der Rhythmus: Braunglas fahren wir doppelt so
oft wie nötig, Weißglas läuft über. Deshalb ein Timer pro Container.“

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
4. **Routing** – Nearest-Neighbor über Haversine, Kapazitäts-, Schicht- und Umschlaggrenzen, mehrere Fahrzeuge je Tag.
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

> Route proposal for 2026-04-15 — 25 stops · planned 249.9 km · vehicles 4 ·
> vehicle hours 22.68 (longest shift 7.58 h) · collected 142.82 t

## Live-Nachfrage an PreZero: die Betriebsvariablen

PreZero ist das ganze Wochenende bei HHN (*„Feel free to reach out anytime if you have questions or
need additional data."*). Unsere 11 Betriebsvariablen sind im Code als **„Annahme, von PreZero zu
ersetzen"** markiert — das ist exakt seine Anforderung „incorporate configurable operational variables".

```bash
# Vorher (Annahmen)
prezero-route route --date 2026-04-15 --max-stops 25
# → 4 Fahrzeuge, 19 Runden, 22,7 h, 142,8 t, 250 km

# Nachher (Zahlen von PreZero, z. B. Dichte 300, Umwegfaktor 1,2 in prezero_config.json)
prezero-route route --date 2026-04-15 --max-stops 25 --config prezero_config.json
# → 3 Fahrzeuge, 19 Runden, 21,6 h, 107,1 t, 214 km
```

Live ausgetauscht (z. B. Dichte 400 → 300 kg/m³, Umwegfaktor 1,35 → 1,2) ändert sich das Ergebnis
sichtbar: **3 statt 4 Fahrzeuge, 214 statt 250 km**. Das belegt live, dass das Tool nicht auf die
Daten hineingebaut wurde, sondern konfigurierbar ist.

## Offene Punkte (bewusst offen)

- Echte PreZero-Koordinaten fehlen → die Zuordnung der anonymisierten IDs bleibt simuliert
  (`osm_assigned` / `simulated_mapping`); Austauschpfad ist vorbereitet.
- Die Route ist eine Luftlinien-Näherung (Umwegfaktor 1,35), kein Straßenrouting.
- Kein Flottenoptimum: gezeigt wird eine Tages-Tour mit 4 Fahrzeugen und 19 Runden, nicht das Optimum über die Woche.
- Die Betriebsvariablen sind Annahmen, bis PreZero Zahlen liefert — das ist der Live-Hook, kein Mangel.

### Kosten & Nutzen: historischer Zeitraum statt einzelner Demo-Tag

Bei 66,0 % gemessener Füllung wurden die Behälter geleert. Im Replay erreicht GlasRoute 80,9 %. Gegenüber denselben Besuchstagen mit identischem modelliertem Glaszufluss sammelt GlasRoute 1.515,7 t mehr. Die modellierten Kosten steigen um 169,4 €/Betriebstag. Keine belegte Flottenreduktion.

Orte simuliert, Besuchstage aus Daten. Eurobeträge sind Szenariowerte, keine PreZero-Kostendaten. [Rechenweg und Grenzen](KOSTENMODELL.md).
