# UI-Sprachaustausch & Audit: Nielsen Heuristik #2 („Match between system and the real world“)

Dieses Dokument erfasst alle Stellen im Prototyp `ui_<date>.html`, an denen technische Implementierungsdetails (Implementation Leakage) in die Benutzeroberfläche durchschlagen, anstatt in der Sprache der Anwender (Fahrer und Disponenten bei PreZero / kommunaler Entsorgung) zu sprechen.

---

## 1. Audit-Methodik & Heuristische Grundlagen

Nach **Jakob Nielsens Heuristik #2** gilt:
> *„The design should speak the users' language. Use words, phrases, and concepts familiar to the user, rather than internal jargon. Follow real-world conventions, making information appear in a natural and logical order.“*

Im Entsorgungskontext bedeuten die realen Domänenkonzepte:
- **Disponenten** denken in Touren, Schichten, Standorten, Glasarten, Leerungsintervallen, Dringlichkeiten und Fahrzeugkapazitäten.
- **Fahrer** benötigen eindeutige Adressen / Standortbezeichnungen, die anzufahrende Glasfarbe, Füllstände in Prozent, klare Arbeitsanweisungen (Leerung vs. Entladung am Wertstoffhof) und einfache Eingaben für ihre Rückmeldung.
- **System-Interna**, die in der Oberfläche nichts zu suchen haben:
  - Opaque Primärschlüssel (UUIDs wie `b3ebe810-724a-454e-83c5-68467048b3ec`)
  - Datenbank- und Spaltennamen in `snake_case` (z. B. `Location_id`, `material_type`, `stop_type`, `last_fill_level`, `nn_kept`, `disposal_depot`)
  - Englische Code-Enums (z. B. `white`, `brown`, `green`, `collection`, `depot`)
  - Technische Roh-Floats mit übertriebenen Nachkommastellen (z. B. `0.8333`, `1.318 km`, `10.481 km`)
  - Entwickler-Kürzel und CLI-Flags (z. B. `--no-llm`, `explain_container`, `cleaned_readings.csv`)
  - Booleans (`True`/`False` statt Ja/Nein) und unbeschriftete Einheiten.

---

## 2. Vollständige Audit-Tabelle aller Fundstellen

| Nr. | Bereich / Wo | Technischer Ist-Zustand (Leckage) | Kategorie | Sprache des Fahrers / Disponenten (Soll) | Heuristischer Verstoß & Auswirkung |
|---|---|---|---|---|---|
| **1** | Fahrer-Ansicht (`#driver-tour`) | `<td>white</td>` (25×) | Enum (Englisch) | `<td>Weißglas</td>` (bzw. Braunglas / Grünglas) | Fahrer muss englische Farb-Enums geistig übersetzen. Verstoß gegen vertraute Domänensprache. |
| **2** | Fahrer-Ansicht (`#driver-tour`) | `<strong>disposal_depot</strong><br><code>disposal_depot</code>` | snake_case / System-ID | `<strong>Entsorgungshof</strong><br>Entladestelle (angenommen)` | Technischer Dummy-Key statt verständlichem Entladeziel. Keine Behauptung eines bestätigten Wertstoffhofs. |
| **3** | Fahrer-Ansicht (`#driver-tour`) | `<strong>UUID</strong><br><code>UUID</code>` (doppelt gerendert) | UUID / Schlüssel-Leak | `<strong>Standort #1</strong><br>Achtungstraße (Kernstadt)` | 36-stellige Datenbank-UUID ohne Lesbarkeit. Fahrer benötigt Stoppnummer und echten Straßennamen. ID nur unter Details. |
| **4** | Fahrer-Rückmeldung (`#driver-tour`) | „gleiche Spalten wie cleaned_readings.csv“ | Dateiname / Interna | „im Standard-Tabellenformat für Tourenrückmeldungen“ | Exponiert interne Pipeline-Dateinamen gegenüber dem Fahrer. |
| **5** | Disponenten-Freigabe (`#role-dispatcher` & `#view-route`) | `<input value="dispatcher">` | Englisch / Code-Default | `<input value="Disponent/in" placeholder="Name">` | Englischsprachiges technisches Standard-Token statt echter Rolle. |
| **6** | Route Stopp-Tabelle (`#view-route`) | Spaltenüberschrift `<th>Location_id</th>` | snake_case / DB-Spalte | `<th>Standort / Adresse</th>` | Datenbankspaltenname statt Anwenderbegriff. |
| **7** | Route Stopp-Tabelle (`#view-route`) | Spalte Typ: `<td>collection</td>` (25×) / `<td>depot</td>` | Enum (Englisch) | `<td>Leerung</td>` (bzw. `<td>Entladung</td>`) | Englische Routing-Begriffe statt konkreter Arbeitsanweisung. |
| **8** | Route Stopp-Tabelle (`#view-route`) | Spalte Material: `white`, `green`, `brown` | Enum (Englisch) | `Weißglas`, `Grünglas`, `Braunglas` | Inkonsistenz zu den deutschen Diagrammbeschriftungen. |
| **9** | Route Stopp-Tabelle (`#view-route`) | Spalte Ortsquelle: `osm_assigned (simulated_mapping)` | snake_case / Interna | `OSM-Standort (simulierte Zuordnung)` | Interner Metadaten-Code statt verständlicher Qualitätsangabe. |
| **10** | Route Stopp-Tabelle (`#view-route`) | Etappe / Kumulativ: `1.318 km`, `10.481 km` | Roh-Float / Dezimalpunkt | `1,3 km`, `10,5 km` (deutsches Zahlenformat) | Scheinpräzision auf Millimeter-Ebene und englisches Punkt-Format. |
| **11** | Route Stopp-Tabelle (`#view-route`) | Score: `0.8333`, `0.8845` | Roh-Float / Fehlende Einheit | `0,83 (Priorität: hoch)` | Unbeschriftete Kennzahl ohne Wertebereich oder Skalierung. |
| **12** | Route & Daten Hinweise (`#view-route`, `#view-data`) | `Erklärung für (Location_id, material)` | snake_case / Tuple-Syntax | `Erklärung für Standort und Glasart` | Python-Tupelsyntax in Anwender-Hinweistexten. |
| **13** | Copilot Tab (`#view-copilot`) | Container-Select: `Stopp #1: b3ebe810... (white)` | UUID & Enum | `Stopp #1 · Achtungstraße · Weißglas` | Dropdown unlesbar wegen 36-stelliger Hexadezimal-Strings. Gekürzte IDs gehören nur unter Details. |
| **14** | Copilot Tab (`#view-copilot`) | Top-20 Select: `Top-20: 0004c095... (white)` | UUID & Enum | `Häufig überfüllt · Rappenauer Straße · Weißglas` | Unübersichtliche Auswahlliste ohne Farb-/Ortsübersetzung. |
| **15** | Copilot Tab (`#view-copilot`) | Überschrift: `Container-Erklärung (explain_container)` | Code / Funktionsname | `Container-Detailerklärung` | Python-Funktionsname als UI-Label exponiert. |
| **16** | Copilot Tab (`#view-copilot`) | Header: `--no-llm, vorberechnet beim UI-Build` | CLI-Flag / Tech-Jargon | `Offline-Assistent (vorberechnete Pipeline-Analysen)` | CLI-Kommandozeilenflag im UI-Kopfbereich. |
| **17** | Copilot Beispielfragen (`#view-copilot`) | `Schichtlimit max_shift_hours=6?` | snake_case / Zuweisung | `Schichtlimit auf 6 Stunden verkürzen?` | Programmiercode-Zuweisung in einem Klick-Button. |
| **18** | Copilot Beispielfragen (`#view-copilot`) | `8 t Fahrzeug (vehicle_max_weight_kg=8000)?` | snake_case / Zuweisung | `Fahrzeugkapazität auf 8 t begrenzen?` | Interne Variablennamen und Einheitenkonvertierung sichtbar. |
| **19** | Copilot Beispielfragen (`#view-copilot`) | `Was passiert bei max_stops=20?` | snake_case / Zuweisung | `Tour auf maximal 20 Stopps begrenzen?` | Variablensyntax statt fachlicher Fragestellung. |
| **20** | Copilot Ask Eingabe (`#view-copilot`) | Placeholder: `(<Location_id>:<material>)` | snake_case / Schema | `Standort #1 · Weißglas` | Abstrakte Platzhaltersyntax und UUID-Beispiele verwirren Nutzer. |
| **21** | Copilot What-If Ergebnis (`#view-copilot`) | `max_shift_hours = 6, vehicle_max_weight_kg = ...` | snake_case / Code | `Schichtlimit: 6 h, Maximalgewicht: 8 t` | Code-Parameter-Dump im Ergebnisbereich. |
| **22** | Tab 1 Daten (`#view-data`) | Top 20 Tabelle Spalte Material: `white`, `brown` | Enum (Englisch) | `Weißglas`, `Braunglas` | Inkonsistente Benennung gegenüber Diagrammen. |
| **23** | Tab 8 Datencheck (`#view-datacheck`) | Tabellenkopf: `Overfull (>=110%)` & `Overfull` | Englisch / Code-Begriff | `Überfüllt (≥ 110 %)` & `Überfüllungen` | Denglisch / technisches Schlüsselwort statt deutscher Fachbegriff. |
| **24** | Tab 8 Datencheck (`#view-datacheck`) | Tabellenkopf: `Location_id` | snake_case / DB-Spalte | `Standort-ID` | Unverändertes Datenbankschema in Tabelle. |
| **25** | Tab 8 Datencheck (`#view-datacheck`) | Tabellenkopf: `Regularity Score` | Englisch / Metrik | `Regelmäßigkeit (Score)` | Englische Statistikbezeichnung ohne Erklärung. |
| **26** | Tab 8 Datencheck (`#view-datacheck`) | Spalte Material: `white`, `brown`, `green` | Enum (Englisch) | `Weißglas`, `Braunglas`, `Grünglas` | Rohe Datenbankeinträge direkt ausgegeben. |
| **27** | Tab 8 Datencheck (`#view-datacheck`) | Wert `0.750` | Roh-Float | `0,75` | 3 Nachkommastellen mit Punkt statt Komma. |
| **28** | Tab 7 Fairer Vergleich (`#view-benchmark`) | `Solver schlechter als NN, NN-Reihenfolge behalten` | Abkürzung / Interna | `Bedarfs-Reihenfolge (Nearest Neighbor) kompakter als Solver` | Fachjargon (`NN`, `Solver`) ohne Kontext für den Disponenten. |
| **29** | Tab 7 Fairer Vergleich (`#view-benchmark`) | Hinweis auf `benchmark_results.csv` & `scripts/benchmark.py` | Dateipfade / Interna | `Berechnete Vergleichsbasis aus der Benchmark-Analyse` | Dateipfade gehören in die Entwicklerdoku, nicht in die Fachoberfläche. |
| **30** | Tab 9 Upload (`#view-upload`) | Text: `Pflichtspalten: Location_id, material_type, date, fill_level_perc` | snake_case / Schema | `Pflichtspalten: Standort-ID (Location_id), Glasart (material_type)...` | Rohe Feldnamen ohne Übersetzung für Datenerfasser. |
| **31** | Karten-Popup (`viz.py` / Iframe) | `Last fill: 110%` & `Score: 0.8845` | Englisch & Roh-Float | `Letzter vorgefundener Stand: 110 %`<br>`Dringlichkeits-Score: 0,88` | Denglisch und 4 Nachkommastellen im Karten-Tooltip. |
| **32** | Freigabe-Vorschau (`#view-route`) | JSON-Dump mit `"approved": true` | Boolean / JSON-Dump | Aufgeräumte Bestätigungsmeldung (Ja/Nein) | Technisches JSON-Objekt im Dispatcher-UI. |

---

## 3. Die Top-10-Korrekturen (Priorisiert nach Nutzerwirkung)

Die folgenden 10 Punkte weisen die höchste Heuristik-Verletzung auf und wurden direkt im Code (`src/prezero/ui.py`, `src/prezero/copilot.py`) behoben:

1. **Glasfarben-Lokalisierung (Enum `white/brown/green` &rarr; `Weißglas/Braunglas/Grünglas`):**
   Ersetzung in Fahrer-Tabelle, Route-Stopptabelle, Datencheck-Zusammenfassung und Copilot-Listen.
2. **Eliminierung von `disposal_depot` als Standortname:**
   Anzeige als „Entsorgungshof / Wertstoffhof“ statt technischem snake_case-Bezeichner.
3. **Menschlich lesbare Standortbezeichnungen statt reiner 36-Zeichen-UUIDs:**
   Anzeige nach PreZero-Vorgabe (*Titel zuerst, ID in Klammern*): „Standort (ID: `b3ebe8...`)“ bzw. Straßenname, Vermeidung doppelter UUID-Dumps.
4. **Stopp-Typ-Übersetzung (`collection`/`depot` &rarr; `Leerung`/`Entladung`):**
   Eindeutige Arbeitsanweisungen für Fahrer und Disponenten.
5. **Ersetzung von `Location_id` und `material_type` in Tabellenköpfen und Hinweisen:**
   Umbenennung zu „Standort / Adresse“ und „Glasart“; Beseitigung der Tupel-Syntax `(Location_id, material)`.
6. **Entschärfung der Copilot-Fragen und Dropdowns:**
   Entfernung von `max_shift_hours=6`, `vehicle_max_weight_kg=8000` und `max_stops=20` aus Buttons; Übersetzung der Dropdown-Einträge.
7. **Entfernung von `explain_container` und `--no-llm` aus UI-Überschriften:**
   Ersetzung durch anwendergerechte Begriffe wie „Container-Detailerklärung“ und „Offline-Copilot“.
8. **Lokalisierung von Dezimalzahlen und Strecken (Roh-Floats):**
   Formatierung von Strecken und Zeiten auf 1 Nachkommastelle mit deutschem Dezimalkomma (`1,3 km`, `10,5 km`) und Scores auf 2 Stellen (`0,83`).
9. **Klartext für Ortsquellen-Metadaten (`osm_assigned (simulated_mapping)`):**
   Anzeige als verständliche Herkunft: „OSM-Standort (simulierte Zuordnung)“.
10. **Beseitigung englischer Fachbegriffe (`Overfull`, Default `dispatcher`):**
    Übersetzung zu „Überfüllt (≥ 110 %)“ und Vorgabe einer passenden Rollenbezeichnung („Disponent/in“).

---

## 4. Test-Spezifikation (Verifikation)

Zur dauerhaften Sicherung gegen Regressionen prüft der Test `test_ui_visible_text_no_technical_leakage`:
1. Kein unmaskierter `snake_case` in sichtbaren Anwendertexten (z. B. `osm_assigned`, `simulated_mapping`, `disposal_depot`, `Location_id`, `explain_container`, `max_shift_hours`).
2. Keine rohen 36-Zeichen-UUIDs als alleiniger sichtbarer Primärtitel im Fahrer- und Routenablauf.
3. Keine rohen englischen Enums (`white`, `brown`, `green`, `collection`) in Tabellenzellen.
4. Keine unformatierten Booleans (`True` / `False`) in sichtbaren Statustexten.
5. Keine Roh-Floats mit mehr als 2 Nachkommastellen bei Distanzen oder Scores.
6. Keine gekürzten IDs (`[0-9a-f]{8}...`) in primären Benutzeroberflächen (Fahrertabelle, Routentabelle, Dropdowns, Beispielfragen, Platzhalter). IDs befinden sich ausschließlich unter „Details“.
7. Weder „Wertstoffhof“ noch „bestätigt“ für angenommene Standorte; korrekte Ausweisung als „angenommen“ bzw. „Entladestelle (angenommen)“.
