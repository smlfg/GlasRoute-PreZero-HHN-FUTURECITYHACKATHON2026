# TODO — Sonntag, 15.11.2026

**Fenster:** 08:00 Ankunft · **11:00 Feature-Freeze** · **13:00 Abgabe.**
Regel ab hier: **keine neuen Features**, nur belegbar machen, was schon läuft. Jede Aufgabe hat eine
Timebox und ein Fertig-Kriterium. Wenn eine MUST-Aufgabe überzieht: abbrechen, Rest der Liste
abarbeiten, Überziehung im Bericht nennen.

---

## MUST — vor dem Feature-Freeze (11:00)

| # | Aufgabe | Timebox | Fertig, wenn |
|---|---|---|---|
| M1 | **Offline-Probe der Website.** Laptop in den Flugmodus, `ui_2026-04-15.html` öffnen. | 15 min | Alle 9 Tabs öffnen; Karten leer ist okay und wird mündlich erklärt (Kacheln von OSM), Tabellen/Kennzahlen vollständig. |
| M2 | **Demo-Probelauf 3×** genau in Pitch-Reihenfolge: `run` → `propose` → `approve`, dann Website. | 30 min | 3 Läufe hintereinander ohne Fehler, Ausgabezeile identisch (`25 stops · 249.9 km · 4 vehicles`), Beleg `approval_2026-04-15.json` neu geschrieben. |
| M3 | **Falsche Zahlen aus README/PITCH entfernen.** | 20 min | Kein „2 Fahrzeuge / 5 Runden“, kein „ein Fahrzeug“, kein Beleg-Zeitstempel von gestern. Gegenprobe: `grep -n "2 Fahrzeuge\|5 Runden"`. |
| M4 | **Deck mit Stoppuhr** (`Pitch/deck.md`, 10 Folien, Ziel 3:30). | 25 min | Ein Durchlauf ≤ 4:00, jede Zahl auf der Folie steht so in `A3_pitch_zahlen.txt`. |
| M5 | **PreZero-Live-Hook üben:** `prezero_config.json` auf Dichte 300 / Umweg 1,2, `route` neu rechnen. | 20 min | Ausgabe „3 statt 4 Fahrzeuge, 214 statt 250 km“ in ≤ 60 s, danach Original-Config zurück. |
| M6 | **Fallback bauen:** Screenshot-Serie der 9 Tabs + `route_2026-04-15.json` in einen Ordner `Pitch/fallback/`. | 20 min | Ordner liegt offline auf dem Desktop; Video/Screenshots zeigen die Tour ohne laufenden Rechner. |
| M7 | **Freeze-Check.** | 10 min | `git status` clean · `pytest -q` grün · `verify_pitch_numbers.py` = ALL MATCH · gepusht. |

## SHOULD — nach 11:00, nur wenn M1–M7 stehen

| # | Aufgabe | Timebox | Fertig, wenn |
|---|---|---|---|
| S1 | **Copilot-Tab durchklicken** (vorberechnete Antworten, What-if-Knöpfe). | 15 min | Jede der 4 Beispiel-Fragen liefert eine Antwort ohne JS-Fehler in der Konsole. |
| S2 | **Fahrer-Loop zeigen können:** „geleert“ + Füllstand in 10er-Schritten → CSV-Export. | 15 min | `tour_feedback_<datum>.csv` heruntergeladen, Inhalt im Pitch in einem Satz erklärbar. |
| S3 | **`STATUS.md` final datieren** (neuer Commit-Hash, Uhrzeit). | 5 min | Kopfzeile nennt den letzten Commit vor der Abgabe. |
| S4 | **Jury-Fragen vorbereiten** (5 Stück, je 2 Sätze Antwort). | 20 min | Antworten stehen in `Pitch/NOTES.md`: Standorte echt?, Datenqualität?, Skalierung?, Kosten?, warum Timer? |
| S5 | **Fragen an PreZero auf 3 kürzen** (aktuell 12). | 10 min | `Pitch/NOTES.md` nennt die drei wichtigsten (Dichte, Fahrzeuglast, Depots). |
| S6 | **Abgabe-Paket prüfen**: Repo-Link, Deck-Export, Belege. | 15 min | Alles aus einer Hand kopierbar, keine lokalen Pfade im Text. |

## ROADMAP — nicht jetzt (nach der Abgabe)

| # | Vorhaben | Aufwand | Warum nicht jetzt |
|---|---|---|---|
| R1 | Wochenauswahl auf der Prognosekarte (Mo–So-Dropdown über `map_<datum>.html`) | ~1 h | Zweites Prognosemodell neben der Kernpipeline = Scope-Creep; Kern muss stehen. |
| R2 | Echte PreZero-Koordinaten + Straßenrouting (OSRM) statt Haversine × 1,35 | 1–2 Tage | Ohne die Zuordnungstabelle von PreZero nicht belegbar. |
| R3 | Mehrfahrzeug-Optimierung über mehrere Tage als echtes VRP | 2–3 Tage | Tages-Tour reicht als Beweis; Flottenoptimum ist eine eigene Aussage. |
| R4 | Straßennamen vollständig (`data/external/street_lookup.json` deckt nur aufgelöste Punkte) | ~2 h | Kosmetik; Lücken sind sichtbar, aber nicht falsch. |
| R5 | Zentrale Freigaben statt Browser-`localStorage`, Rollen, Auth | 1 Woche | Prototyp zeigt den Ablauf, nicht den Betrieb. |
| R6 | Live-Fahrzeugposition, Zeitfenster, Verkehr, Störungen | offen | Setzt Digitalisierung bei PreZero voraus (siehe `STAKEHOLDER.md`, R3). |
