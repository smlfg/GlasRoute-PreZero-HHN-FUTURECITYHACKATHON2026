# Pitch Deck — GlasRoute (PreZero Challenge / Future City Hackathon 2026)

**Format:** Markdown-Source der Pitch-Folien · Ziel: **3–4 Min, max. 10 Folien** · Sprache: **Deutsch** ·
**Charts:** einfache Text-/Tabellen-Charts aus dem Repo (ASCII-Balken, Markdown-Tabellen) — **keine gerenderten Preview-Bilder**.

**Dauer:** Ziel **3:30 Min** (Deck: 10 Folien; Zeitbudget summiert auf ca. **3:56 Min**) · **Abgabe:** Sonntag, 15.11.2026, 13:00 Uhr
**Demo-Datum:** **15.04.2026**

---

## Quellen & Zahlenstand (Pflicht-Check bei jeder Folie)

| Quelle | Inhalt |
|---|---|
| `docs/PITCH.md` | Pitch-Struktur, fairer Benchmark B0–B4 |
| `Pitch/NOTES.md` | Stand **14.11.2026, 19:00 Uhr** — „Messen und Leeren"-Fix, Live-Hook |
| `docs/BENCHMARK.md` | Fairer Vergleich (4 Tage × 3 Seeds), Effektberechnung |
| `docs/analysen/36_hypothesen_mentor.md` | Mentor-Insights, Datenlücken, Fragen an Mentor |
| `docs/TODO.md` | offene Aufgaben bis Freeze/Abgabe, ROADMAP-Abschnitt |
| `Projek-Management/proof/A3_pitch_zahlen.txt` | Verifikation gegen Pipeline: **ALL MATCH** |
| `data/raw/glass_fill_levels_anonymized_f.csv` | 11.701 Messungen, 449 IDs, 1.192 `overfull` |
| `data/processed/route_2026-04-15.json` | Tages-Tour: 25 Stopps, 125,21 km, 2 Fahrzeuge, 7 Runden, 10,51 h, 63,58 t |

**Belegt im aktuellen Zahlenstand (nach „Messen und Leeren"-Fix, Commits `52fbedf`, `085b816`, `759ab31`):**

- **11.701 reale Messungen** · **449 Container** · **1.338 Standort-Material-Zeitreihen** · **1.192 `overfull`-Ereignisse** · 731 davon **Weißglas** (61,3 %)
- **Bedarfs-Effekt: 81,0 %** (nur kritische Container anfahren) · **Routing-Effekt: 9,6 %** (instabil: 0–13 %) · **Gesamt: 82,8 %** (B1→B4) bzw. **84,1 %** (B0→B4)
- **Tages-Tour (Stopp-Limit 25):** **125,21 km** vs. **1.202,24 km** Vollkette → **−89,6 %** (1077,03 km gespart)

---

## Deck-Übersicht (Folien → Jury-Kriterium → Zeit)

| # | Folie | Titel | Jury-Kriterium | Zeit |
|---|---|---|---|---|
| 1 | Problem | Überfüllung & halb-leere Touren | Problem & Benefit | 25 s |
| 2 | Status quo | So leert heute keiner so richtig | Understanding | 20 s |
| 3 | Data | Ist es vorhersagbar? | Understanding | 25 s |
| 4 | Solution | Daten → kritische Container → Freigabe → Tour | Technology | 30 s |
| 5 | Live Demo | Fahrer · Disponentin · Analyse | Feasibility | 30 s |
| 6 | Result | −84,1 % km (fair: B0 → B4) | Problem & Benefit | 20 s |
| 7 | Honesty | Echte Füllstände, simulierte Orte | Reliability | 15 s |
| 8 | Closed Loop | Fahrer-Feedback → neue Prognose | Technology | 15 s |
| 9 | Roadmap | Was als Nächstes kommt | Feasibility | 10 s |
| 10 | Ask | Was wir von PreZero brauchen | Feasibility | 15 s |
| | **Summe** | | | **~236 s ≈ 3:56 min** |

---

## Slide 1 — Problem

- **Folie:** „Überfüllung & halb-leere Touren"
- **Jury-Kriterium:** Problem & Benefit
- **Zeit:** **25 s**

### Folien-Text

- Glascontainer in Heilbronn werden nach **festem Plan** geleert — „area by area". Unabhängig vom Füllstand.
- **Mentor (PreZero):** *„Emptying these containers usually takes place area by area. Then all containers in the area are emptied, regardless of the actual fill level ('you'll drive past there anyway')."*
- **Belegt:** 11.701 Messungen · 449 Container · **1.192 `overfull`-Ereignisse** — jeder vierte betrifft **Weißglas** (731/1.192).
- Folge: LKW fahren zu **halbleeren** Containern, während andere **überlaufen**; Fahrt, Zeit, CO₂.

### Chart (einfach, aus Repo)

```
Anteil overfull je Kalendermonat (Messungen; Quelle: data/raw):
Jan    11,6 %    ██
Feb    12,9 %    ██
Mär    37,6 %    ████████
Apr    23,3 %    ████
Mai    22,7 %    ████
Jun     5,2 %    █
Jul     5,0 %    █
Aug     2,8 %
```

→ Peak **Januar–Mai** (März: 37,6 %), Einbruch Sommer.

### Speaker Notes

- **0–5 s:** Hook: „Heute fahren wir zu halb vollen Containern — und lassen andere voll werden."
- **5–12 s:** Zitat des Mentors vorlesen, exakt.
- **12–20 s:** Belegt: 11.701 Messungen, 449 Container, 1.192 Überläufe; jeder vierte Weißglas.
- **20–25 s:** Transition: „Genau deshalb ist ein Routing-Modell aus diesen Daten gefragt."

### Quellen / Zahlenstand

- `docs/PITCH.md` (Zitat), `Pitch/NOTES.md` (Belegt-Zahlen), `data/raw/glass_fill_levels_anonymized_f.csv`.
- Zahlen: **11.701 ✓**, **449 ✓**, **1.192 ✓**, **731 ✓** (61,3 %) — alle belegt.

---

## Slide 2 — Status quo Prozess

- **Folie:** „So leert heute keiner so richtig"
- **Jury-Kriterium:** Understanding
- **Zeit:** **20 s**

### Folien-Text

- Status quo: feste Leerungsrunden/Listen — Disposition plant, Fahrer leert.
- Fahrer **scannt** Füllstand, **schätzt** in **10-%-Schritten**, **fährt zur Leerung**, **leert**. **Keine Sensoren, keine Echtzeit-Erfassung.**
- Nach „Messen und Leeren" (18:45): Fahrer **misst beim Besuch** und **leert**; Zahlen rechnen mit **geschätztem Stand heute** (Füllrate × Tage seit letzter Leerung) — nicht mit dem vorgefundenen Stand.
- Human-Agent: Agent **schlägt** vor, Disponentin **gibt frei**; ohne Freigabe kein Dispatch.

### Speaker Notes

- **0–7 s:** Status quo in einem Satz: „Fester Plan, Listen, Fahrer schätzt, leert."
- **7–12 s:** „Scan → Schätzung (10-%-Schritte) → Leerung. Keine Sensoren."
- **12–20 s:** Nach dem Fix: „Messen und Leeren": Der Fahrer misst beim Besuch, leert; das Modell nutzt den geschätzten Stand.
- Transition: „Wir haben aus genau diesen Mustern eine priorisierte Tour gemacht."

### Quellen / Zahlenstand

- `docs/PITCH.md` (§4 Prozess, Fix-Beschreibung), `Pitch/NOTES.md` („Messen und Leeren (neu, 18:45)"), `src/prezero/ingest.py`, `src/prezero/features.py`.

---

## Slide 3 — Data

- **Folie:** „Ist es vorhersagbar?"
- **Jury-Kriterium:** Understanding
- **Zeit:** **25 s**

### Folien-Text

- **11.701 reale Messungen** · **1.338 Standort-Material-Zeitreihen** · **449 Container** · Zeitraum **17.10.2025–30.09.2026** · 229 Messstage · 3 Materialien.
- **Frage: Ist das überhaupt vorhersagbar?** → **Ja** — aus Füllmustern ableitbar.
- Material-Median: **66,3 %** der Vorhersagen innerhalb **±20 Prozentpunkten**, **MAE 21,0**.
- Weißglas: **66,4 %** der Weißglas-Messungen ≥ 80 %, vs. **14,7 %** bei Braun. Überfüllungsquote: **10,2 %**.

### Chart / Tabelle (einfach, aus Repo)

| Modell | MAE (pp) | ±20 pp |
|---|---:|---:|
| Material-Median | **21,0** | **66,3 %** |
| Persistence | 25,4 | 59,4 % |
| Drift | 27,5 | 51,6 % |

| Glas | Anteil Messungen ≥ 80 % | Overfull-Rate |
|---|---:|---:|
| Weiß | **66,4 %** | **16,5 %** (höchste) |
| Grün | — | 8,6 % |
| Braun | **14,7 %** | 3,4 % |

### Speaker Notes

- **0–8 s:** Datenbasis: 11.701 Messungen, 1.338 Serien, 449 Container, 3 Materialien.
- **8–15 s:** Frage „Ist es vorhersagbar?" — mit Ja beantworten; Material-Median 66,3 % innerhalb ±20 pp (MAE 21,0).
- **15–25 s:** Weißglas als Haupttreiber; Überfüllungsquote 10,2 %.
- Transition: „Daraus folgt: kritische Container sind identifizierbar."

### Quellen / Zahlenstand

- `docs/archiv/PITCH_EXECUTIVE_SUMMARY.md`, `docs/analysen/21_prognosemodell.md`, `docs/analysen/33_geschaeftliche_kennzahlen.md`, `docs/analysen/06_materialvergleich.md`.
- Zahlen: **11.701 ✓**, **1.338 ✓**, **66,4 % ✓**, **14,7 % ✓**, **10,2 % ✓**, **21,0 ✓**, **66,3 % ✓**.

---

## Slide 4 — Solution

- **Folie:** „Daten → kritische Container → Freigabe → Tour"
- **Jury-Kriterium:** Technology
- **Zeit:** **30 s**

### Folien-Text

- Pipeline: **Ingest → Features → Scoring → Routing → Freigabe → Export**.
- User Story: **Als Disponentin möchte ich kritische Container selektieren → Tour → Freigabe → Fahrer.**
- Agent **schlägt** vor (`prezero-route propose`); Disponentin **gibt frei** (`approve` / `--reject`) → Beleg mit Zeitstempel, Route, Kennzahlen. **Ohne Freigabe wird nichts dispatcht.**

### Speaker Notes

- **0–10 s:** Pipeline in einem Satz.
- **10–22 s:** User Story: Disponentin wählt; Agent schlägt vor; Freigabe; Fahrer fährt.
- **22–30 s:** Human-in-the-Loop: propose → approve; kein Dispatch ohne Freigabe.

### Quellen / Zahlenstand

- `docs/PITCH.md` (§4, §5), `src/prezero/cli.py`, `src/prezero/approval.py`, `Pitch/NOTES.md`.

---

## Slide 5 — Live Demo

- **Folie:** „Live: Fahrer · Disponentin · Analyse"
- **Jury-Kriterium:** Feasibility
- **Zeit:** **30 s**

### Folien-Text

- Demo-Tag **15.04.2026**:
```bash
prezero-route run --date 2026-04-15
prezero-route propose
prezero-route approve --by "Disponentin (Heilbronn)"
```
- **Erwartete Ausgabe:** 25 Stopps · **125,21 km** · 2 Fahrzeuge · 7 Runden · **10,51 h** · **63,58 t** · saved **1077,03 km (89,6 %)**.
- UI mit Rollen: **Fahrer / Disponentin / Analyse** (Forecast-Timeline, Bestehende Route + Freigabe, Datencheck, Upload, Copilot).

### Speaker Notes

- **0–8 s:** Live-Demo-Start: Pipeline + propose.
- **8–16 s:** Freigabe durch Disponentin.
- **16–24 s:** Ergebnis: 25 Stopps, 125,21 km, 2 Fahrzeuge, saved 89,6 %.
- **24–30 s:** Rollen im UI: Fahrer sieht Tour, Disponentin entscheidet, Analyst prüft Daten.

### Quellen / Zahlenstand

- `README.md` (Demo-Ablauf), `Pitch/NOTES.md` (§Live-Demo), `src/prezero/ui.py`, `data/processed/route_2026-04-15.json`.

---

## Slide 6 — Result

- **Folie:** „Ersparnis: −84,1 % km (fair: B0 → B4)"
- **Jury-Kriterium:** Problem & Benefit
- **Zeit:** **20 s**

### Folien-Text

| Variante | Standorte | km |
|---|---:|---:|
| **B0 Status quo** (Papierliste) | 121 | **1.795,91** |
| **B4 kritisch + OR-Tools** | **73** | **285,79** |

- **Ersparnis: −84,1 %** (B0 Status quo → B4 kritisch + OR-Tools).
- Davon **Bedarfs-Effekt (Auswahl): 81,0 %** (B1 → B2, nur kritische Container angefahren) · **Routing-Effekt (gleiche Stopps): 9,6 %** (B2 → B4; instabil: 0–13 %).
- Gesamt **−82,8 %** (B1 optimierter Status quo → B4; größter Teil kommt aus der **Auswahl**, Routing „nur ca. 10 %").

- Tages-Tour (Stopp-Limit 25): **125,21 km** vs. **1.202,24 km** Vollkette → **−89,6 %** · saved **1077,03 km** · 63,58 t · 2 Fahrzeuge.

### Speaker Notes

- **0–7 s:** Fairer Vergleich: B0 Status quo (Papierliste) 1.795,91 km vs. B4 kritisch + OR-Tools 285,79 km.
- **7–12 s:** → **−84,1 %** km gespart. Davon Auswahl **81,0 %**, Routing **9,6 %**.
- **12–17 s:** Gesamt **−82,8 %** (B1 → B4) — großer Teil aus der Auswahl, Routing nur „bis ca. 10 %".
- **17–20 s:** Tages-Tour: **−89,6 %** (125,21 vs. 1.202,24 km Vollkette).

### Quellen / Zahlenstand

- `docs/BENCHMARK.md`, `benchmark_results.csv`, `Projek-Management/proof/A3_pitch_zahlen.txt` (**ALL MATCH**).
- **Belegt:** **81,0 % ✓**, **9,6 % ✓**, **82,8 % ✓**, **84,1 % ✓**.

**Hinweis (Zahlenstand):** Die in der Aufgabenstellung genannten Kürzel **−81,5 % km**, **81,2 % Auswahl**, **1,5 % Routing** sind als zusammengesetzte Kennzahl **nicht** aus den Repo-Quellen belegt → **[TODO]**. Im Repo belegt sind: Bedarfs-**81,0 %**, Routing-**9,6 %**, Gesamt-**82,8 %** (B1→B4) bzw. **84,1 %** (B0→B4).

---

## Slide 7 — Honesty

- **Folie:** „Ehrlich bleiben: was die Daten sind und was nicht"
- **Jury-Kriterium:** Reliability
- **Zeit:** **15 s**

### Folien-Text

- **Füllstände:** echt — 11.701 Messungen; Fahrer misst beim Besuch, leert; Forecast aus Mustern.
- **Standorte:** **simuliert** zugeordnet — 449 OSM-Punkte, ID-Zuordnung `osm_assigned` / `simulated_mapping`; offen so gesagt.
- Echter Tausch: `data/external/locations_real.csv` + `scripts/refresh_locations.py --real` → **ohne Codeänderung**.
- Route: Haversine + Umwegfaktor **1,35**, kein Straßenrouting; Routing-Effekt **instabil** (0–13 %).

### Speaker Notes

- **0–5 s:** Füllstände sind echt; Fahrer misst und leert; Forecast aus Mustern.
- **5–10 s:** Standorte: simuliert zugeordnet — klar so gesagt; echter Tausch ohne Codeänderung möglich.
- **10–15 s:** Route: Näherung; Routing-Effekt instabil.

### Quellen / Zahlenstand

- `docs/PITCH.md` (§5, „Offene Punkte"), `docs/archiv/GEO_DATENQUELLEN.md`, `README.md` („Geo coordinates / PreZero swap").
- Simulierte Zuordnung: `osm_assigned` / `simulated_mapping` ✓; Swap-Pfad ✓.

---

## Slide 8 — Closed Loop

- **Folie:** „Fahrer-Feedback → neue Prognose"
- **Jury-Kriterium:** Technology
- **Zeit:** **15 s**

### Folien-Text

- Flow: **Scan → Schätzung → Prognose → Tour** (User Story Fahrer).
- Fahrer misst/schätzt beim Abholen → Entleerung → **Feedback** → **Forecast** (Timeline +0/+7/+14/+21; KW 16–19).
- Freigabe → Tour → Entleerung → Forecast.

### Speaker Notes

- **0–7 s:** Closed Loop erklären: Scan, Schätzung, Prognose, Tour.
- **7–15 s:** Fahrer-Feedback (Messung + Entleerung) fließt zurück ins Forecast.

### Quellen / Zahlenstand

- `docs/UI_PLAN.md` (User Story „Scan → Schätzung → Prognose → Tour"), `src/prezero/forecast.py`, `src/prezero/approval.py`.

---

## Slide 9 — Roadmap

- **Folie:** „Roadmap"
- **Jury-Kriterium:** Feasibility
- **Zeit:** **10 s**

### Folien-Text

- **Multi-User:** zentrale, mehrbenutzerfähige Freigaben (statt Browser-localStorage).
- **Echte PreZero-Koordinaten** (Swap-Pfad bereit).
- **Events:** Weindorf, Weihnachten (Saison/Veranstaltungen).
  - [TODO: „Weindorf" als Event ist aus den Repo-Quellen **nicht eindeutig belegt** — im UI-Test als verbotenes Mock-Event genannt; nachweisbar ist die Weihnachts-/Jahreswechsel-Spitze (Analysen 11–13).]
- **Live-Fahrzeugpositionen**, Zeitfenster, Verkehr, Beladung.

### Speaker Notes

- **0–5 s:** Roadmap in 4 Punkten: Freigaben, Koordinaten, Events, Live.
- **5–10 s:** Events: Weindorf, Weihnachten.

### Quellen / Zahlenstand

- `docs/TODO.md`, `docs/UI_PLAN.md`, `docs/analysen/12_ferien_feiertage.md`, `docs/analysen/13_nachweihnachtsspitze.md`.

---

## Slide 10 — Ask / Next Step

- **Folie:** „Was wir von PreZero brauchen"
- **Jury-Kriterium:** Feasibility
- **Zeit:** **15 s**

### Folien-Text

- **11 Betriebsvariablen** („Annahme, von PreZero zu ersetzen"): Density je Glasfarbe, Containervolumen, LKW-Gewicht **und -Volumen (26 m³)**, Umwegfaktor, Tempo, Betriebshof, Entsorgung, Schicht, Servicezeiten.
- Live austauschbar: Dichte **300** / Umweg **1,2** → **5 statt 7 Runden, 8,8 h, 47,7 t, 100 km** (statt 7 Runden, 10,5 h, 63,6 t, 125 km).

### Speaker Notes

- **0–6 s:** Live-Hook: Betriebsvariablen sind „Annahme, von PreZero zu ersetzen".
- **6–11 s:** Beispiel: Dichte 300 / Umweg 1,2 → sichtbar andere Zahlen.
- **11–15 s:** Ask: bitte drei operative Zahlen von PreZero; dann läuft die Route neu.

### Quellen / Zahlenstand

- `Pitch/NOTES.md` (§Live-Hook, „Der stärkste Live-Impuls"), `prezero_config.json`, `src/prezero/routing.py`.

---

## Zeit- und Qualitäts-Check

- **Gesamtdauer:** ~236 s Redezeit + ~24 s Chart-/Demo-Zeit = **~4:00 Min** (Rahmen 3–4 Min, max. ok).
- **Max. 10 Folien:** erfüllt (10 Folien).
- **Keine gerenderten Preview-Bilder:** erfüllt (ASCII/Tabellen/Markdown-Code only).
- **Deutsch:** erfüllt.
- **Nur Zahlen aus Repo:** mit **[TODO]** markiert für nicht nachweisbare Werte (z. B. „−81,5 % km / 81,2 % / 1,5 % Routing" auf Slide 6).

## Offene Punkte / [TODO]s

| Punkt | Status | Folie |
|---|---|---|
| −81,5 % km / 81,2 % Auswahl / 1,5 % Routing | **nicht im Repo belegt** | Slide 6 |
| Echte PreZero-Koordinaten | offen — `osm_assigned` / `simulated_mapping` | Slides 7, 9, 10 |
| Echte Leerungsereignisse / Fahrzeugdaten | offen (Mentor-Fragen 1–5) | Slides 7, 10 |
| Straßenrouting statt Haversine | offen (Umwegfaktor 1,35) | Slide 7 |
| Multi-User / Live-Positionen | Roadmap | Slide 9 |
| Prognosegenauigkeit (MAE 21,0) | belegt, Limitierungen | Slide 3 |
