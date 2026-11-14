# Pitch-Notizen für Sonntag 13:00

Stand: Samstag, 14.11.2026, 19:00 Uhr (Messen-und-Leeren, Dichte je Glasfarbe, LKW 11 t / 26 m³). Demo-Datum: **15.04.2026**.
Alle Zahlen sind gegen `route_2026-04-15.json`, `benchmark_results.csv`, die Website und `data/raw/` geprüft (Beleg: `Projek-Management/proof/A3_pitch_zahlen.txt`, Skript `verify_pitch_numbers.py`).

---

## Was der Stakeholder gesagt hat (und was daraus folgt)

Quelle: `20261113_Readme Challenge PZ.docx` + `PreZero.pptx`.

**Sein Kernproblem (Slide 2, wörtlich):**
> „Emptying these containers usually takes place area by area. Then all containers in the area are emptied,
> regardless of the actual fill level (‘you'll drive past there anyway')."

→ Das ist **unser Status quo** (Benchmark B0/B1): alle Container des Gebiets leeren. Der Bedarfs-Effekt (81,0 %) ist genau das,
was er beschreibt. In den Pitch so aufmachen, es kommt aus seiner own Stimme.

**Slide 1 — vier Schritte, alle abgedeckt:**

| Sein Schritt | Unser Deliverable |
|---|---|
| „Analyze: Find patterns … of more than a year" | `features.py` — Füllrate, Overfull-Quote, Saison, Verhaltensprofil |
| „Combine: See, if there are containers with the same **'behavior'**" | Material-/Verhaltenscluster, Kritikalitäts-Score |
| „Build: Create a universal tool where we can see the patterns" | CLI + Karten + Trendplots |
| „Create: Develop a **generic** route-planning tool, based on individual variables" | `OperationalConfig` — 11 konfigurierbare Betriebsvariablen |

**Deliverables (Spec 5):** Data Ingestion Tool ✅ · Pattern Visualization ✅ · Route Engine ✅ · Documentation ✅

**Und noch etwas Wichtiges:** Er erwähnt **Koordinaten kein einziges Mal** — weder Readme noch PPT noch
CSV enthalten Adresse, Lat/Lon oder einen Ort-Key. Die IDs sind bewusst anonymisiert. Die Challenge
handelt von **Füllstandsintelligenz**, nicht von Geodaten:
> „these algorithms cannot deliver true efficiency without real-time fill-level intelligence"

→ Seine Erwartung ist *nicht* „126 echte Standorte, 323 Platzhalter". Er will Muster, Priorisierung
und eine Route, die sich gegen „alles abfahren" beweist.

---

## 🟤 Kernbotschaft: Braunglas wird viel zu oft geleert

Beleg: `docs/BACKTEST.md`, Abschnitt „Passt der heutige Leerungsrhythmus?“ (`python scripts/backtest.py`,
geprüft in A3). Je Container: idealer Abstand = 80 % ÷ Füllrate, tatsächlich = Median der Tage zwischen Besuchen.

| Glasfarbe | ideal bis 80 % | heute tatsächlich | zu oft geleert | zu selten geleert |
|---|---|---|---|---|
| **Braunglas** | **95 Tage** | **42 Tage** | **89 %** der Container | 2 % |
| Grünglas | 42 Tage | 34 Tage | 45 % | 7 % |
| Weißglas | 33 Tage | 33 Tage | 12 % | **16 %** |

- Bei **30 % aller Besuche** war der Container **unter 50 %** voll: Die Fahrt war zu früh.
- Bei **11 %** lief er über.
- **Braunglas könnte gut doppelt so lange stehen** (95 statt 42 Tage). Weißglas passt im Mittel, aber
  jeder sechste Weißglas-Container wird zu selten geleert und läuft über.

**So im Pitch sagen:**
> „Sie haben gesagt: Wenn ich weiß, dass ein Container nur 20 % voll ist, komme ich eine Woche später.
> Die Daten sagen genau das: Braunglas wird alle 42 Tage geleert, füllt sich aber erst nach 95 Tagen auf
> 80 %. 89 % der Braunglas-Container werden zu oft angefahren. Weißglas dagegen läuft teils über.
> Deshalb bekommt bei uns jeder Container einen eigenen Timer statt eines Gebietsrhythmus.“

**Ehrlich dazusagen:** Die Füllrate stammt aus Schätzungen des Fahrers in 10-%-Stufen. Der Backtest
zeigt: Die Vorhersage ist nicht zufällig (Fehler Ø 19,9 pp gegen 22,3 pp für „Durchschnitt bisher“),
aber auch nicht exakt.

---

## ⚠️ Drei Dinge, die du wissen musst

### 1. Standorte: alle 449 auf OSM-Punkten, Zuordnung simuliert

`data/external/locations.csv` enthält **449 Zeilen `source=osm_assigned`, `confidence=simulated_mapping`**
— jeder Standort ist ein echter OSM-Glascontainer in Heilbronn, die Zuordnung zu den anonymisierten
IDs ist **simuliert** (jeder Punkt wird bis zu 9× vergeben). Es gibt aktuell **keine Platzhalter**.

Die alte Formulierung „126 echte / 323 Platzhalter" gilt **nicht mehr** — der Geo-Vertrag wurde in
`d12331f` bewusst auf `osm_assigned` / `simulated_mapping` umgestellt (Mission D2: „ID assignment
simulated"). Das ist Design, kein Bug.

**So im Pitch sagen:**
> „Alle 449 Standorte sind echte Glascontainer in Heilbronn, aus OpenStreetMap. Weil die Container-IDs
> anonymisiert sind, ist die Zuordnung simuliert — wir markieren das als `simulated_mapping`. Sobald
> PreZero die echte Zuordnungstabelle einspielt, übernimmt das System sie ohne Codeänderung."

Nicht sagen: „126 echte / 323 Platzhalter" (veraltet), nicht „wir haben alle Standorte identifiziert".


### 2. Die alten 24,1 % sind tot. Neue Zahlen und was sie bedeuten

Die alte Zahl verglich eine Tour **mit** 11-t-Kapazität und Entladefahrten gegen eine „volle Runde“
**ohne** Kapazität. Seit Stopps pro physischem Standort zählen (121 Punkte), zeigte sie 0 %. Jetzt
gelten für alle Varianten dieselben Regeln: 11 t pro Runde, Entladung am Wertstoffhof, max. 8 h.

**Pitch-Zahlen aus dem fairen Benchmark** (`scripts/benchmark.py`, Stichtag 15.04.2026, Seed 42,
Website-Tab „5. Fairer Vergleich“):

| Variante | Standorte | km | Fahrzeugstunden | Runden |
|---|---|---|---|---|
| B0 Status quo, Listenreihenfolge | 121 | 1.795,91 | 170,99 h | 95 |
| B1 Status quo, optimierte Reihenfolge | 121 | 1.662,70 | 166,66 h | 98 |
| B2 nur kritische, Nearest Neighbor | 73 | 316,31 | 25,65 h | 14 |
| **B4 nur kritische, OR-Tools** | **73** | **285,79** | **24,10 h** | **13** |

| Effekt | Wert | Spanne (4 Stichtage × 3 Seeds) |
|---|---|---|
| **Bedarfs-Effekt** B1 → B2 (nur kritische anfahren) | **81,0 %** | 79,7–97,3 % |
| **Routing-Effekt** B2 → B4 (gleiche Stopps, bessere Reihenfolge) | **9,6 %** | 0,0–13,0 % |
| **Gesamt** vs. optimierter Status quo B1 | **82,8 %** | 80,7–97,3 % |
| Gesamt vs. Papierliste B0 (obere Schranke) | 84,1 % | – |

**Richtig formulieren:**
> „Wenn das ganze Gebiet geleert wird, wie heute, sind es 1.663 km. Fahren wir nur die 73 kritischen
> Standorte an, sind es 316 km, also 81 % weniger. Der Solver holt bei gleichen Stopps noch etwa
> 10 % raus: 286 km. Der Großteil kommt aus dem Bedarf, nicht aus dem Routing.“

**Ehrlich dazusagen:**
- Status quo heißt hier „alle 121 Standorte mit allen Behältern auf einmal leeren“ (808,2 t, geschätzter Stand heute). Der echte
  Plan verteilt das über Tage. Die Prozent gelten **pro kompletter Gebietsleerung**.
- Die Spanne ist groß: Im Winter gibt es kaum kritische Standorte (Bedarfs-Effekt bis 97,3 %), im April
  viele (ca. 80 %). 81,0 % am Demo-Tag liegt am unteren Ende.
- B4 nutzt OR-Tools mit 30 s Zeitlimit. Ist der Solver schlechter als Nearest Neighbor, wird NN behalten
  und in `benchmark_results.csv` als `nn_kept` markiert: B4 in 1 von 12 Fällen, B3 (2-opt) in 2 von 12,
  in diesem Lauf B4 in 2, B3 in 3 von 12 Fällen; am Demo-Tag in keinem (B3 299,65 km, B4 285,79 km).
- **Der Routing-Effekt ist instabil** (0–13 % über 12 Fälle, am Demo-Tag zwischen Läufen 1,5–9,6 %), weil
  OR-Tools nach 30 s abbricht. Im Pitch „bis ca. 10 %“ sagen, nicht eine feste Zahl.
  Die km können je Lauf leicht schwanken.

**Die Tages-Tour im Tab „Route & Freigabe“** ist ein anderer Fall: Stopp-Limit 25, also **25 von 72
kritischen Standorten** (47 bleiben offen). 125,21 km, 2 Fahrzeuge, 7 Runden, 63,6 t. Die 89,6 %
auf der Karte vergleichen diese Teil-Tour mit „alles leeren“ und sind **keine Pitch-Zahl**.


### 3. Zwei Agenten haben gleichzeitig committet

Bis jetzt laufen zwei Agenten parallel ins Repo. **Ab jetzt nur einer zur Zeit.**
Konkret: `git log` vor jedem Commit prüfen (`git status` + `git log --oneline -3`), und wenn
schon jemand anderes committen will, warten bis dessen Commit durch ist.

---

## Pitch-Struktur (3 Minuten)

### 1. Problem (30 Sek.)
> „Glascontainer in Heilbronn werden nach festem Plan geleert. Laster fahren zu halbleeren
> Containern, während andere überlaufen."

Belegt: 11.701 Messungen, 449 Container, **1.192 `overfull`-Ereignisse**. Jeder vierte Überlauf-Fall
betrifft Weißglas (731 von 1.192).

### 2. Warum lösen (20 Sek.)
Jede unnötige Fahrt kostet Sprit, Zeit und CO₂. Überfüllte Container ärgern Bürger. Der Disponent
entscheidet heute aus dem Bauchgefühl, weil Füllstandsdaten nicht in Routen übersetzt werden.

### 2b. Die Erkenntnis (30 Sek.) — Braunglas

„Braunglas: alle 42 Tage geleert, voll erst nach 95. 89 % zu oft angefahren. Weißglas teils zu selten.
30 % aller Fahrten kamen zu früh.“ → Jeder Container bekommt einen **Timer** (fällig am …).

### 3. Was wir sparen (60 Sek.) — Demo

| Kennzahl | Wert |
|---|---|
| Kritische Standorte heute (physische Orte) | 72 (108 IDs, 118 Container) |
| Status quo, ganzes Gebiet (B1) | 1.662,70 km · 98 Runden |
| Nur kritische (B2 → B4 Solver) | 316,31 → **285,79 km** · 13 Runden |
| **Bedarfs-Effekt** | **81,0 %** |
| **Routing-Effekt** | **9,6 %** (instabil, 0–13 %) |
| **Gesamt vs. Status quo** | **82,8 %** |
| Tages-Tour (Stopp-Limit 25) | 125,21 km · 2 Fahrzeuge · längste Schicht 7,26 h · 63,6 t |


**Saisonalität** (Anteil `overfull` je Monat, aus den Rohdaten):

| Jan | Feb | **Mär** | Apr | Mai | Jun | Jul | Aug |
|---|---|---|---|---|---|---|---|
| 11,6 % | 12,9 % | **37,6 %** | 23,3 % | 22,7 % | 5,2 % | 5,0 % | 2,8 % |

→ Planung muss **material- und standortspezifisch** sein: Weißglas im Frühjahr, Sommer anders.

### 4. Wie funktioniert's (40 Sek.)
Ingest → Features (letzter Füllstand, Füllrate, Overfull-Quote, Saison) → Kritikalitäts-Score →
Routing (Nearest-Neighbor, Haversine, ein Fahrzeug, Kapazitäts-/Schicht-/Umschlaggrenzen) →
**Freigabe** → Export.

### 5. Umsetzung (30 Sek.)
- Läuft auf den **vorhandenen** Fillinq-Daten, ein Fahrzeug genügt als Start.
- **Generisch**, wie von ihm gefordert: 11 Betriebsvariablen in einer Config-Datei, nicht im Code —
  dadurch für andere Abfallarten und andere Städte wiederverwendbar.
- Python-CLI, modular (`ingest` → `features` → `scoring` → `routing` → `viz` → `propose` → `approve`).
- **Austauschbar:** echte Koordinaten kommen als `Location_id,lat,lon` in
  `data/external/locations_real.csv` — ohne Codeänderung (`scripts/refresh_locations.py --real`).
- **Human-Agent-Interface:** Der Agent *schlägt* vor, die Disponentin *gibt frei*. Ohne Freigabe wird
  nichts dispatcht. Jede Entscheidung wird als Beleg protokolliert.

---

## Live-Demo

### Teil 1 — Kern (Pflicht)

```bash
python scripts/benchmark.py             # einmal vorher, ca. 1 min (B0–B4, 4 Tage × 3 Seeds)
prezero-route run --date 2026-04-15     # Pipeline + Website ui_2026-04-15.html
prezero-route propose
prezero-route approve --by "Disponentin (Heilbronn)"
```

Erwartete Ausgabe:

```
Pipeline complete for 2026-04-15: 72 critical physical sites (108 critical IDs, 118 containers).
125.21 km planned (25 stops) vs. 1202.24 km full round (121 stops, same capacity rules)
```

```
Route proposal for 2026-04-15
  stops:          25
  planned:        125.21 km
  saved:          1077.03 km (89.6 %)
  vehicles:       2
  vehicle hours:  10.51 (sum over all vehicles)
  longest shift:  7.26 h
  collected:      63.58 t
Nothing is dispatched until a dispatcher approves it.
```

Die 89,6 % hier sind die Teil-Tour (25 von 72) gegen „alles leeren“. Im Pitch die Benchmark-Zahlen nennen.

**Website `ui_2026-04-15.html`** (liegt neben `heatmap.html`, beide im selben Ordner lassen):

| Tab | Zeigen |
|---|---|
| 3. Heatmap | Klick auf ein Kästchen springt zur Karte im Tab „Route & Freigabe“ |
| 4. Route & Freigabe | „25 von 72 kritischen“, What-if-Knöpfe, Klick auf Stopp = Begründung, Freigeben |
| 5. Fairer Vergleich | Bedarfs- vs. Routing-Effekt (die Pitch-Zahlen) |

**What-if-Knöpfe (vorberechnet, Baseline 125,21 km / 2 Fahrzeuge / 7 Runden):**

| Knopf | Ergebnis |
|---|---|
| Schicht 6 h | weiter 2 Fahrzeuge, längste Schicht 5,57 h, 128,72 km |
| LKW 8 t | 2 Fahrzeuge, 10 statt 7 Runden, 177,53 km |
| +1 Fahrzeug | 68 von 72 kritischen: 3 Fahrzeuge, 258,24 km, 4 offen |
| Alle kritischen | 72 Standorte, 3 Fahrzeuge, 270,94 km |

Der alte Explainer-Fall „6 h → 8,83 h“ war die **Summe** der Fahrzeugstunden, als Schicht beschriftet.
Jetzt stehen Fahrzeugstunden gesamt und längste Einzelschicht getrennt da.

**Variablen (Spec 3/4):** Tab „5. Variablen“ zeigt alle Annahmen und ob sie im Routing wirken: Dichte je
Glasfarbe (heute überall 400 kg/m³), Behälter 2,5 m³, LKW 11 t **und 26 m³** (neu), Tempo, Umwegfaktor,
Entsorgungsdepot, Betriebshof, Schicht, Servicezeiten, dazu den berechneten Flotteneinsatz.
**Ortsdaten:** Das Banner sagt jetzt klar: nicht von PreZero, selbst gescrapt, IDs zufällig verteilt.

**Messen und Leeren (neu, 18:45):** Der Fahrer schätzt den Füllstand beim Besuch und leert. Alle Zahlen
rechnen jetzt mit dem *geschätzten Stand heute* (Füllrate × Tage seit der letzten Leerung), nicht mehr
mit dem vorgefundenen Stand vor der Leerung. Website-Tabs „Daten“ und „Forecast“ erklären das.


### Teil 2 — Prognose (nur wenn Zeit bleibt)

```bash
prezero-route forecast --date 2026-04-15
```

Erwartete Ausgabe (Kalenderwochen-Format, aktueller Stand):

```
KW 16: 183 rot, 325 schwarz
KW 17: 195 rot, 434 schwarz
KW 18: 214 rot, 526 schwarz
KW 19: 204 rot, 607 schwarz
Forecast map: forecast_16.html
```

Die Prognose steht in der Website im Tab „2. Forecast-Timeline“ (+0/+7/+14/+21 Tage, gezählt in
**Containern** = ID × Glasfarbe, nicht in Standorten). `forecast_16.html` ist die Einzelkarte dazu.

---


## Offene Punkte — aktiv ansprechen

| Punkt | Stand |
|---|---|
| Echte PreZero-Koordinaten | fehlen → alle 449 auf OSM-Punkten, Zuordnung `simulated_mapping` |
| Route ist Luftlinien-Näherung | Umwegfaktor 1,35, kein Straßenrouting |
| 81,0 % / 9,6 % | Bedarfs- vs. Routing-Effekt pro kompletter Gebietsleerung, gleiche Regeln (Tab „Fairer Vergleich“) |
| Flottenoptimum | Tages-Tour: 2 Fahrzeuge, längste Schicht 7,26 h (Limit 8 h); mit 3 Fahrzeugen alle 72 kritischen (270,94 km) |

---

## 🎯 Der stärkste Live-Impuls: Betriebsvariablen von PreZero holen

PreZero ist **Samstag und Sonntag den ganzen Tag bei HHN** (Readme: *„I will be present at HHN
throughout the weekend. Feel free to reach out anytime if you have questions or need additional data."*).

In `src/prezero/routing.py` stehen **11 Betriebsvariablen** — jede mit dem Kommentar
`# Annahme, von PreZero zu ersetzen`:

| Variable | Unser Wert | Frage an PreZero |
|---|---|---|
| `density_kg_per_m3` | 400 | „Welche Dichte setzen Sie für Glas an?“ |
| `container_volume_m3` | 2,5 | „Wie groß ist ein Glascontainer?“ |
| `vehicle_max_weight_kg` | 11.000 | „Wie voll wird der Lader maximal?“ |
| `road_detour_factor` | 1,35 | „Wie viel Umweg nehmen Sie je Strecke an?“ |
| `avg_speed_kmh` | 25 | „Welche Durchschnittsgeschwindigkeit?“ |
| `yard_depot` | 49.1427 / 9.2109 | „Wo liegt Ihr Betriebshof?“ |
| `disposal_depot` | 49.1780 / 9.2085 | „Wo ist die Entsorgungsstelle?“ |
| `max_shift_hours` | 8,0 | „Wie lang ist eine Schicht?“ |
| `stop_setup_min` | 2 | „Wie lange dauert das Anfahren je Container?“ |
| `lift_time_per_bin_min` | 3 | „Wie lange braucht das Umschlagen?“ |
| `unload_time_min` | 20 | „Wie lange dauert das Entladen?“ |

**Die Dramaturgie:**
1. Pitch (3 Min.) mit den Annahmen als Grundlage.
2. Danach: *„Die Betriebsvariablen sind aktuell Annahmen. PreZero ist heute hier — nennen Sie mir drei
   Zahlen, und das Tool rechnet sofort neu.“*
3. Zahlen eintragen → `prezero-route run --date 2026-04-15` → neue km, neue Fahrzeuge, neue Schichtstunden.
4. Der Unterschied zwischen Annahme und echter Zahl ist der Beweis, dass das Tool **nicht auf die
   Daten hineingebaut**, sondern konfigurierbar ist.

Das ist genau seine Spec-3-Forderung: *„incorporate configurable operational variables into your
routing model"* — live demonstriert statt behauptet.

### Der Live-Befehl (bereits getestet)

```bash
# Vorher — mit unseren Annahmen (prezero_config.json = Defaults)
prezero-route route --date 2026-04-15 --max-stops 25 --config prezero_config.json
# → 2 Fahrzeuge, 7 Runden, 10,5 h, 63,6 t, 125 km

# Nachher — Beispiel: Dichte 300 kg/m³, Umwegfaktor 1,2
prezero-route route --date 2026-04-15 --max-stops 25 --config prezero_config.json
# → 2 Fahrzeuge, 5 Runden, 8,8 h, 47,7 t, 100 km
```

**Der Effekt ist sofort sichtbar:** Dichte 400 → 300 kg/m³ und Umwegfaktor 1,35 → 1,2 ergeben
**5 statt 7 Runden und 100 statt 125 km** (h = Fahrzeugstunden gesamt). Das ist der stärkste Beweis im ganzen Pitch: das Tool
ist nicht auf die Daten hineingebaut, sondern nimmt die Betriebsvariablen entgegen.

**Vorbereitung:** Lege vor dem Pitch eine Datei `prezero_config.json` mit den **Default-Werten**
unseres `OperationalConfig` an. Dann ist der Wechsel auf seine Zahlen ein Einzeiler:

```bash
cp prezero_config.json prezero_config_backup.json
# → Zahlen von PreZero eintragen (oder live im Editor)
prezero-route route --date 2026-04-15 --config prezero_config.json
```

**Falls die Zeit knapp wird:** Lass nur **eine** Variable live austauschen (z. B. `vehicle_max_weight_kg`
11.000 → 7.500 → 3 Fahrzeuge, 13 Runden, 222 km). Das genügt als Beweis und dauert 20 Sekunden.

**Konkrete Fragen, wenn er Zeit hat:**
- „Wo liegt Ihr Betriebshof und Ihre Entsorgungsstelle?“
- „Wie viele Container schafft ein Fahrzeug pro Runde, und wie viele Fahrzeuge setzen Sie ein?“
- „Gibt es Daten, die wir abrufen können — eine Schnittstelle, CSV-Export oder iCal für die Termine?“
- „Dürfen wir die Koordinaten der Container bekommen? Dann ist die Zuordnung echt statt simuliert.“

---

## Prognosekarte mit Wochenauswahl — offen

Der Stakeholder will eine **Prognosekarte mit Wochenauswahl** sehen. Frage an Samuel: soll Zed das
als Nächstes bauen?

**Einschätzung, bevor gebaut wird:**

- **Was es geben müsste:** Karte mit Container-Standorten, eingefärbt nach prognostiziertem Füllstand
  für einen gewählten Wochentag, plus eine Wochen-Auswahl (Mo–So).
- **Was die Daten hergeben:** `scored_<date>.csv` hat bereits `season_factor` und `avg_daily_increase`
  je Container. Eine Wochentags-Prognose ist also rechnerisch möglich — ohne neues ML.
- **Risiko:** Genau das ist der Bereich, in dem letzte Nacht Zeit versickert. Ein zweites
  Prognosemodell neben der Kernpipeline ist Scope-Creep.
- **Vorschlag:** Wenn ja, dann als **kleine Erweiterung der bestehenden Map** (ein Wochentags-Dropdown
  über der vorhandenen `map_<date>.html`), nicht als neue Visualisierung. Scope: ~1 h, kein neues
  Modul. Erst wenn der Kern-Pitch (Abschnitt 1–5) durch ist.

**Entscheidung: offen — wartet auf Samuel.**

