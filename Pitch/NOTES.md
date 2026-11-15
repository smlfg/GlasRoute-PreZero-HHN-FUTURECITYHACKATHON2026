# Pitch-Notizen für Sonntag 13:00

Stand: Samstag, 14.11.2026, 19:40 Uhr (Timer pro Container, ohne Saisonfaktor und Score-Faktoren). Demo-Datum: **15.04.2026**.
Alle Zahlen sind gegen `route_2026-04-15.json`, `benchmark_results.csv`, die Website und `data/raw/` geprüft (Beleg: `Projek-Management/proof/A3_pitch_zahlen.txt`, Skript `verify_pitch_numbers.py`).

---

## Was der Stakeholder gesagt hat (und was daraus folgt)

Quelle: `20261113_Readme Challenge PZ.docx` + `PreZero.pptx`.

**Sein Kernproblem (Slide 2, wörtlich):**
> „Emptying these containers usually takes place area by area. Then all containers in the area are emptied,
> regardless of the actual fill level (‘you'll drive past there anyway')."

→ Das ist **unser Status quo** (Benchmark B0/B1): alle Container des Gebiets leeren. Bedarfs-Effekt (29,9 % am 15.04., 29–67 % übers Jahr) und Braunglas-Rhythmus sind genau das,
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


### 2. Die Effekte (fairer Vergleich) — Stand 19:40, Timer-Modell

Frühere Zahlen (24,1 %, 70,7 %, 81 %) sind ungültig: Sie beruhten auf Dauersensor-Annahme, festem
Saisonfaktor und gewichteten Score-Faktoren. Jetzt gilt: **Fahrer misst und leert → Füllrate → Timer;
fällig = geschätzt ≥ 80 %.** Alle Varianten mit denselben Regeln (11 t / 26 m³, Entladung, 8 h).
Der Benchmark ist jetzt deterministisch (zwei Läufe, gleiche Zahlen).

Stichtag 15.04.2026, Zuordnungs-Seed 42 (Website-Tab „Fairer Vergleich“):

| Variante | Standorte | km | Fahrzeugstunden | Runden |
|---|---|---|---|---|
| B0 Status quo, Listenreihenfolge | 121 | 1.795,91 | 170,99 h | 95 |
| B1 Status quo, optimierte Reihenfolge | 121 | 1.662,70 | 166,66 h | 98 |
| B2 nur fällige, Nearest Neighbor | 112 | 1.165,90 | 98,15 h | 67 |
| **B4 nur fällige, OR-Tools** | **112** | **1.053,29** | **89,65 h** | **55** |

| Effekt | Wert | Spanne (4 Stichtage × 3 Seeds) |
|---|---|---|
| **Bedarfs-Effekt** B1 → B2 (nur fällige Container leeren) | **29,9 %** | 28,6–67,1 % |
| **Routing-Effekt** B2 → B4 (gleiche Stopps, bessere Reihenfolge) | **9,7 %** | 2,3–14,1 % |
| **Gesamt** vs. optimierter Status quo B1 | **36,7 %** | 32,9–70,7 % |
| Gesamt vs. Papierliste B0 (obere Schranke) | 41,4 % | – |

**Warum der Bedarfs-Effekt am 15.04. klein ist:** Mitte April sind **509 von 1.269 Containern fällig**
(488 überfällig), verteilt auf 106 von 121 Standorten. Wer fast überall hin muss, spart wenig durchs
Weglassen. Über die 4 Stichtage liegt der Effekt bei 29–67 %. **Die stärkere Aussage ist der Rhythmus**
(Kernbotschaft Braunglas oben): Braunglas wird zu oft, Weißglas teils zu selten geleert.

**Richtig formulieren:**
> „Heute Mitte April ist fast jeder Standort fällig, da spart Weglassen nur ein Drittel. Über das Jahr
> sind es 30 bis 67 %. Der eigentliche Hebel ist der Rhythmus: Braunglas fahren wir doppelt so oft wie
> nötig, Weißglas läuft über. Deshalb ein Timer pro Container.“

**Ehrlich dazusagen:**
- Status quo = alle 121 Standorte mit allen Behältern leeren (808,5 t geschätzter Stand heute).
- Standorte sind selbst gescrapt, IDs zufällig verteilt: absolute km sind Illustration.
- Wenn 2-opt oder Solver schlechter als Nearest Neighbor sind, wird NN behalten (`nn_kept`): B4 in 2,
  B3 in 4 von 12 Fällen.

**Die Tages-Tour im Tab „Route & Freigabe“:** Stopp-Limit 25, also **25 von 127 fälligen Standorten**
(102 offen): 227,2 km, 3 Fahrzeuge, 16 Runden, 116,2 t, längste Schicht 7,96 h. Die 83,4 % auf der Karte
vergleichen diese Teil-Tour mit „alles leeren“ und sind **keine Pitch-Zahl**.

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
| Fällige Container heute (Timer abgelaufen) | 509 von 1.269 (488 überfällig) |
| Fällige Standorte (physische Orte) | 106 von 121 |
| Status quo, ganzes Gebiet (B1) | 1.662,70 km · 98 Runden |
| Nur fällige (B2 → B4 Solver) | 1.165,90 → **1.053,29 km** · 55 Runden |
| **Bedarfs-Effekt** | **29,9 %** (über das Jahr 29–67 %) |
| **Routing-Effekt** | **9,7 %** |
| **Gesamt vs. Status quo** | **36,7 %** |
| Rhythmus | **Braunglas: ideal 95 Tage, heute 42 → 89 % zu oft geleert** |
| Vorhersagbar? | ja: Fehler 19,9 pp gegen 22,3 pp (Durchschnitt bisher) |

### 4. Wie funktioniert's (40 Sek.)
Ingest → Features (letzter Füllstand, Füllrate, Overfull-Quote, Saison) → Kritikalitäts-Score →
Routing (Nearest-Neighbor über Haversine, **je Fahrzeug eine Greedy-Route**, Kapazitäts-/Schicht-/Umschlaggrenzen; am Demo-Tag 4 Fahrzeuge, 19 Runden, 22,7 h) →
**Freigabe** → Export.

### 5. Umsetzung (30 Sek.)
- Läuft auf den **vorhandenen** Fillinq-Daten; der Routenaufbau läuft **je Fahrzeug** greedy — am Demo-Tag mit 4 Fahrzeugen, 19 Runden und 22,7 h Fahrzeugstunden gesamt.
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
Pipeline complete for 2026-04-15: 127 critical physical sites (276 critical IDs, 509 containers).
227.23 km planned (25 stops) vs. 1368.78 km full round (142 stops, same capacity rules)
```

```
Route proposal for 2026-04-15
  stops:          25
  planned:        227.23 km
  saved:          1141.55 km (83.4 %)
  vehicles:       3
  vehicle hours:  19.85 (sum over all vehicles)
  longest shift:  7.96 h
  collected:      116.18 t
Nothing is dispatched until a dispatcher approves it.
```

Die 83,4 % hier sind die Teil-Tour (25 von 127) gegen „alles leeren“. Im Pitch die Benchmark-Zahlen nennen.

**Website `ui_2026-04-15.html`** (liegt neben `heatmap.html`, beide im selben Ordner lassen):

| Tab | Zeigen |
|---|---|
| 3. Heatmap | Klick auf ein Kästchen springt zur Karte im Tab „Route & Freigabe“ |
| 4. Route & Freigabe | „25 von 127 kritischen“, Timer-Spalte, What-if-Knöpfe, Klick auf Stopp = Begründung, Freigeben |
| 5. Fairer Vergleich | Bedarfs- vs. Routing-Effekt (die Pitch-Zahlen) |

**What-if-Knöpfe (vorberechnet, Baseline 227,2 km / 3 Fahrzeuge / 16 Runden):**

| Knopf | Ergebnis |
|---|---|
| Schicht 6 h | 4 Fahrzeuge, längste Schicht 5,55 h, 222,51 km |
| LKW 8 t | 3 Fahrzeuge, 16 Runden, 253,36 km |
| +1 Fahrzeug | 43 statt 25 Standorte, 343,12 km, 84 fällige offen |
| Alle fälligen | 127 Standorte, 12 Fahrzeuge, 923,22 km |

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
KW 16: 180 rot, 328 schwarz
KW 17: 195 rot, 434 schwarz
KW 18: 214 rot, 526 schwarz
KW 19: 207 rot, 633 schwarz
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
| 29,9 % / 9,7 % | Bedarfs- vs. Routing-Effekt am 15.04. (über das Jahr 29–67 % / 2–14 %), gleiche Regeln |
| Flottenoptimum | Tages-Tour: 3 Fahrzeuge, längste Schicht 7,96 h (Limit 8 h); alle 127 fälligen bräuchten 12 Fahrzeuge |

---

## 🎯 Der stärkste Live-Impuls: Betriebsvariablen von PreZero holen

PreZero ist **Samstag und Sonntag den ganzen Tag bei HHN** (Readme: *„I will be present at HHN
throughout the weekend. Feel free to reach out anytime if you have questions or need additional data."*).

In `src/prezero/routing.py` stehen **11 Betriebsvariablen** — jede mit dem Kommentar
`# Annahme, von PreZero zu ersetzen`:

### 🎯 Die drei wichtigsten Fragen an PreZero

Wenn nur Zeit für **drei** Fragen ist, sind es diese. Jede deckt eine Gruppe von Annahmen ab
und ändert das Ergebnis sichtbar:

1. **Dichte und Containergröße** — „Welche Dichte setzen Sie für Glas an (wir rechnen mit
   400 kg/m³), und wie groß ist ein Glascontainer (wir nehmen 2,5 m³)?“
   *Warum zuerst:* daraus kommt die Tonnage je Runde. Bei 300 kg/m³ statt 400 sinkt die Flotte
   von 4 auf 3 Fahrzeuge und die Strecke von 250 auf 214 km.
2. **Fahrzeuglast** — „Wie voll wird der Lader maximal beladen (wir nehmen 11.000 kg)?“
   *Warum:* die Kapazitätsgrenze entscheidet, wie viele Runden und Fahrzeuge ein Tag braucht —
   mit 8 t sind es 4 Fahrzeuge, 21 statt 19 Runden und 271,28 km.
3. **Betriebshof und Entsorgungsstelle** — „Wo liegt Ihr Betriebshof (wir rechnen mit
   49.1427 / 9.2109) und wo Ihre Entsorgungsstelle (49.1780 / 9.2085)?“
   *Warum:* Start- und Endpunkt jedes Rundums. Ohne die echten Punkte stimmen die km nicht.

Die **vollständige Tabelle aller 11 Variablen** mit unseren Annahmen und den dazugehörigen
Fragen steht darunter — das ist das Live-Material für die Bühne. Die ausführlichere Liste
(„Konkreten Fragen“ mit Daten, Koordinaten und Fahrzeugzahl) bleibt unten ebenfalls bestehen.

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
# → 3 Fahrzeuge, 16 Runden, 19,9 h, 116,2 t, 227 km

# Nachher — Beispiel: Dichte 300 kg/m³, Umwegfaktor 1,2
prezero-route route --date 2026-04-15 --max-stops 25 --config prezero_config.json
# → 3 Fahrzeuge, 19 Runden, 21,6 h, 107,1 t, 214 km
```

**Der Effekt ist sofort sichtbar:** Dichte 400 → 300 kg/m³ und Umwegfaktor 1,35 → 1,2 ergeben
**3 statt 4 Fahrzeuge und 214 statt 250 km** (h = Fahrzeugstunden gesamt). Das ist der stärkste Beweis im ganzen Pitch: das Tool
ist nicht auf die Daten hineingebaut, sondern nimmt die Betriebsvariablen entgegen.

**Vorbereitung:** Lege vor dem Pitch eine Datei `prezero_config.json` mit den **Default-Werten**
unseres `OperationalConfig` an. Dann ist der Wechsel auf seine Zahlen ein Einzeiler:

```bash
cp prezero_config.json prezero_config_backup.json
# → Zahlen von PreZero eintragen (oder live im Editor)
prezero-route route --date 2026-04-15 --config prezero_config.json
```

**Falls die Zeit knapp wird:** Lass nur **eine** Variable live austauschen (z. B. `vehicle_max_weight_kg`
11.000 → 7.500 → 4 Fahrzeuge, 21 Runden, 271 km). Das genügt als Beweis und dauert 20 Sekunden.

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

