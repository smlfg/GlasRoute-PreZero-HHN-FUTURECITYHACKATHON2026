# Pitch-Notizen für Sonntag 13:00

Stand: Samstag, 14.11.2026, 16:50 Uhr. Demo-Datum: **15.04.2026**.
Alle Zahlen sind gegen `data/raw/` und `data/processed/` geprüft (Beleg: `Projek-Management/proof/A3_pitch_zahlen.txt`).

---

## Was der Stakeholder gesagt hat (und was daraus folgt)

Quelle: `20261113_Readme Challenge PZ.docx` + `PreZero.pptx`.

**Sein Kernproblem (Slide 2, wörtlich):**
> „Emptying these containers usually takes place area by area. Then all containers in the area are emptied,
> regardless of the actual fill level (‘you'll drive past there anyway')."

→ Das ist **unser Vergleich**: volle Runde = alle Container des Gebiets. Die 24,1 % sind genau das,
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


### 2. Die 24,1 %: was wird verglichen?

**Die Ersparnis ist eine Bedarfs-Ersparnis, keine Routing-Ersparnis.**

| Vergleich | Stopps | km |
|---|---|---|
| **Geplante Tour** (heute) | 25 | 119,75 |
| **Volle Runde** (Status quo) | 431 | 157,72 |
| **Ersparnis** | | **37,97 km = 24,1 %** |

Die volle Runde fährt **alle 431 Standorte mit Daten** ab — das ist der Status quo, den der
Stakeholder meint („heute fährt der Fahrer alle Container ab“). Es ist **nicht** „dieselben 25
Stopps, nur anders sortiert“. Eine reine Routing-Ersparnis wäre ein anderer Vergleich.

**Richtig formulieren:**
> „Heute fährt das Fahrzeug alle 431 Standorte mit Daten ab — 157,72 km. Unser Tool schlägt vor,
> die 25 kritischsten zuerst zu bedienen: 119,75 km, 24,1 % weniger Strecke, und die überlaufenden
> Container sind zuerst dran."

**Nicht behaupten:** „24 % Routing-Effizienz“ oder „bessere Reihenfolge spart 24 %“. Das wäre falsch.

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
| Kritische Container heute | 169 |
| Tour: 25 Stopps | **119,75 km** |
| Volle Runde: 431 Stopps | 157,72 km |
| **Ersparte Strecke** | **37,97 km = 24,1 %** |
| Fahrzeuge | 2 |
| Schichtstunden | 8,52 h (Limit 8,0 h) |
| Sammelmenge | 41,8 t |

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

### Teil 1 — Kern (Pflicht, 3 Befehle)

```bash
prezero-route run --date 2026-04-15
prezero-route propose
prezero-route approve --by "Disponentin (Heilbronn)"
```

Erwartete Ausgabe:

```
Pipeline complete for 2026-04-15: 169 critical locations (213 pairs).
119.75 km planned (25 stops) vs. 157.72 km full round (431 stops)
```

```
Route proposal for 2026-04-15
  stops: 25 | planned: 119.75 km | saved: 37.97 km (24.1 %)
  vehicles: 2 | shift hours: 8.52 | collected: 41.8 t
Nothing is dispatched until a dispatcher approves it.

Route approved by Disponentin (Heilbronn)
Record written to data/processed/approval_2026-04-15.json
```

Artefakte: `route_2026-04-15.json`, `map_2026-04-15.html`, `trends.png`,
`data/processed/approval_2026-04-15.json`.

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

**Zwei Karten, beide vorhanden — was wann zeigen:**

| Datei | Inhalt | Wann |
|---|---|---|
| `map_2026-04-15.html` | Route + Prognose-Lagen **+0/+7/+14/+21 Tage**, Header „+7 Tage: 629 Container voraussichtlich kritisch", Route als Linie auf „Heute" | wenn die Route im Fokus steht |
| `forecast_16.html` | reine Prognose-Lagen **KW 16–19**, ohne Route | wenn die Prognose im Fokus steht |

Beide ohne Server, per Doppelklick im Browser. **Die Route-Karte zuerst** — sie beweist die
Einsparung. Die Prognose danach, als „was kommt als Nächstes".

---

## Offene Punkte — aktiv ansprechen

| Punkt | Stand |
|---|---|
| Echte PreZero-Koordinaten | fehlen → alle 449 auf OSM-Punkten, Zuordnung `simulated_mapping` |
| Route ist Luftlinien-Näherung | Umwegfaktor 1,35, kein Straßenrouting |
| 24,1 % | Bedarfs-Ersparnis vs. volle Runde, **keine** Routing-Effizienz |
| Flottenoptimum | gezeigt: 2 Fahrzeuge nötig und wie sie verteilt werden |

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
# Vorher — mit unseren Annahmen
prezero-route route --date 2026-04-15
# → 2 Fahrzeuge, 5 Runden, 8,5 h, 41,8 t, 120 km

# Nachher — mit den Zahlen von PreZero
prezero-route route --date 2026-04-15 --config prezero_config.json
# → 1 Fahrzeug, 4 Runden, 7,7 h, 31,4 t, 99 km
```

**Der Effekt ist sofort sichtbar:** Dichte 400 → 300 kg/m³ und Umwegfaktor 1,35 → 1,2 ergeben
**1 statt 2 Fahrzeuge und 99 statt 120 km**. Das ist der stärkste Beweis im ganzen Pitch: das Tool
ist nicht auf die Daten hineingebaut, sondern nimmt die Betriebsvariablen entgegen.

**Vorbereitung:** Lege vor dem Pitch eine Datei `prezero_config.json` mit den **Default-Werten**
unseres `OperationalConfig` an. Dann ist der Wechsel auf seine Zahlen ein Einzeiler:

```bash
cp prezero_config.json prezero_config_backup.json
# → Zahlen von PreZero eintragen (oder live im Editor)
prezero-route route --date 2026-04-15 --config prezero_config.json
```

**Falls die Zeit knapp wird:** Lass nur **eine** Variable live austauschen (z. B. `vehicle_max_weight_kg`
11.000 → 7.500). Das genügt als Beweis und dauert 20 Sekunden.

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

