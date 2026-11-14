# Pitch-Notizen für Sonntag 13:00

Stand: Samstag, 14.11.2026, 18:30 Uhr. Demo-Datum: **15.04.2026**.
Alle Zahlen sind gegen `route_2026-04-15.json`, `benchmark_results.csv`, die Website und `data/raw/` geprüft (Beleg: `Projek-Management/proof/A3_pitch_zahlen.txt`, Skript `verify_pitch_numbers.py`).

---

## Was der Stakeholder gesagt hat (und was daraus folgt)

Quelle: `20261113_Readme Challenge PZ.docx` + `PreZero.pptx`.

**Sein Kernproblem (Slide 2, wörtlich):**
> „Emptying these containers usually takes place area by area. Then all containers in the area are emptied,
> regardless of the actual fill level (‘you'll drive past there anyway')."

→ Das ist **unser Status quo** (Benchmark B0/B1): alle Container des Gebiets leeren. Der Bedarfs-Effekt (70,7 %) ist genau das,
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
| B0 Status quo, Listenreihenfolge | 121 | 1.838,75 | 175,03 h | 102 |
| B1 Status quo, optimierte Reihenfolge | 121 | 1.736,53 | 171,28 h | 103 |
| B2 nur kritische, Nearest Neighbor | 95 | 508,36 | 42,15 h | 24 |
| **B4 nur kritische, OR-Tools** | **95** | **475,43** | **40,17 h** | **22** |

| Effekt | Wert | Spanne (4 Stichtage × 3 Seeds) |
|---|---|---|
| **Bedarfs-Effekt** B1 → B2 (nur kritische anfahren) | **70,7 %** | 68,6–97,8 % |
| **Routing-Effekt** B2 → B4 (gleiche Stopps, bessere Reihenfolge) | **6,5 %** | 1,1–16,8 % |
| **Gesamt** vs. optimierter Status quo B1 | **72,6 %** | 72,6–97,9 % |
| Gesamt vs. Papierliste B0 (obere Schranke) | 74,1 % | – |

**Richtig formulieren:**
> „Wenn das ganze Gebiet geleert wird, wie heute, sind es 1.737 km. Fahren wir nur die 95 kritischen
> Standorte an, sind es 508 km, also 70,7 % weniger. Der Solver holt bei gleichen Stopps noch einmal
> 6,5 % raus: 475 km. Der Großteil kommt aus dem Bedarf, nicht aus dem Routing.“

**Ehrlich dazusagen:**
- Status quo heißt hier „alle 121 Standorte mit allen Behältern auf einmal leeren“ (892,7 t). Der echte
  Plan verteilt das über Tage. Die Prozent gelten **pro kompletter Gebietsleerung**.
- Die Spanne ist groß: Im Winter gibt es kaum kritische Standorte (Bedarfs-Effekt bis 97,8 %), im März
  und April viele (ca. 70 %). 70,7 % am Demo-Tag ist das untere Ende.
- B4 nutzt OR-Tools mit 30 s Zeitlimit. Ist der Solver schlechter als Nearest Neighbor, wird NN behalten
  und in `benchmark_results.csv` als `nn_kept` markiert: B4 in 1 von 12 Fällen, B3 (2-opt) in 2 von 12,
  darunter der Demo-Tag (B3 = B2 = 508,36 km). Am Demo-Tag schlägt der Solver NN (475,43 km).
  Die km können je Lauf leicht schwanken.

**Die Tages-Tour im Tab „Route & Freigabe“** ist ein anderer Fall: Stopp-Limit 25, also **25 von 97
kritischen Standorten** (72 bleiben offen). 194,54 km, 2 Fahrzeuge, 11 Runden, 84,4 t. Die 83,5 %
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

### 3. Was wir sparen (60 Sek.) — Demo

| Kennzahl | Wert |
|---|---|
| Kritische Standorte heute (physische Orte) | 97 (169 IDs, 213 Container) |
| Status quo, ganzes Gebiet (B1) | 1.736,53 km · 103 Runden |
| Nur kritische (B2 → B4 Solver) | 508,36 → **475,43 km** · 22 Runden |
| **Bedarfs-Effekt** | **70,7 %** |
| **Routing-Effekt** | **6,5 %** |
| **Gesamt vs. Status quo** | **72,6 %** |
| Tages-Tour (Stopp-Limit 25) | 194,54 km · 2 Fahrzeuge · längste Schicht 7,83 h · 84,4 t |


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
Pipeline complete for 2026-04-15: 97 critical physical sites (169 critical IDs, 213 containers).
194.54 km planned (25 stops) vs. 1179.03 km full round (121 stops, same capacity rules)
```

```
Route proposal for 2026-04-15
  stops:          25
  planned:        194.54 km
  saved:          984.49 km (83.5 %)
  vehicles:       2
  vehicle hours:  15.47 (sum over all vehicles)
  longest shift:  7.83 h
  collected:      84.4 t
Nothing is dispatched until a dispatcher approves it.
```

Die 83,5 % hier sind die Teil-Tour (25 von 97) gegen „alles leeren“. Im Pitch die Benchmark-Zahlen nennen.

**Website `ui_2026-04-15.html`** (liegt neben `heatmap.html`, beide im selben Ordner lassen):

| Tab | Zeigen |
|---|---|
| 3. Heatmap | Klick auf ein Kästchen springt zur Karte im Tab „Route & Freigabe“ |
| 4. Route & Freigabe | „25 von 97 kritischen“, What-if-Knöpfe, Klick auf Stopp = Begründung, Freigeben |
| 5. Fairer Vergleich | Bedarfs- vs. Routing-Effekt (die Pitch-Zahlen) |

**What-if-Knöpfe (vorberechnet, Baseline 194,54 km / 2 Fahrzeuge):**

| Knopf | Ergebnis |
|---|---|
| Schicht 6 h | 3 Fahrzeuge, längste Schicht 5,55 h, 174,61 km |
| LKW 8 t | 3 Fahrzeuge, 218,87 km |
| +1 Fahrzeug | 48 statt 25 Standorte, 244,32 km, 49 kritische offen |
| Alle kritischen | 97 Standorte, 5 Fahrzeuge, 382,87 km |

Der alte Explainer-Fall „6 h → 8,83 h“ war die **Summe** der Fahrzeugstunden, als Schicht beschriftet.
Jetzt stehen Fahrzeugstunden gesamt und längste Einzelschicht getrennt da.


### Teil 2 — Prognose (nur wenn Zeit bleibt)

```bash
prezero-route forecast --date 2026-04-15
```

Erwartete Ausgabe (Kalenderwochen-Format, aktueller Stand):

```
KW 16: 281 rot, 235 schwarz
KW 17: 383 rot, 246 schwarz
KW 18: 371 rot, 290 schwarz
KW 19: 373 rot, 291 schwarz
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
| 70,7 % / 6,5 % | Bedarfs- vs. Routing-Effekt pro kompletter Gebietsleerung, gleiche Regeln (Tab „Fairer Vergleich“) |
| Flottenoptimum | Tages-Tour: 2 Fahrzeuge, längste Schicht 7,83 h (Limit 8 h); What-if zeigt +1 Fahrzeug |

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
# → 2 Fahrzeuge, 11 Runden, 15,5 h, 84,4 t, 195 km

# Nachher — Beispiel: Dichte 300 kg/m³, Umwegfaktor 1,2
prezero-route route --date 2026-04-15 --max-stops 25 --config prezero_config.json
# → 2 Fahrzeuge, 7 Runden, 11,4 h, 63,3 t, 126 km
```

**Der Effekt ist sofort sichtbar:** Dichte 400 → 300 kg/m³ und Umwegfaktor 1,35 → 1,2 ergeben
**7 statt 11 Runden und 126 statt 195 km** (h = Fahrzeugstunden gesamt). Das ist der stärkste Beweis im ganzen Pitch: das Tool
ist nicht auf die Daten hineingebaut, sondern nimmt die Betriebsvariablen entgegen.

**Vorbereitung:** Lege vor dem Pitch eine Datei `prezero_config.json` mit den **Default-Werten**
unseres `OperationalConfig` an. Dann ist der Wechsel auf seine Zahlen ein Einzeiler:

```bash
cp prezero_config.json prezero_config_backup.json
# → Zahlen von PreZero eintragen (oder live im Editor)
prezero-route route --date 2026-04-15 --config prezero_config.json
```

**Falls die Zeit knapp wird:** Lass nur **eine** Variable live austauschen (z. B. `vehicle_max_weight_kg`
11.000 → 7.500 → 3 Fahrzeuge, 15 Runden, 209 km). Das genügt als Beweis und dauert 20 Sekunden.

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

