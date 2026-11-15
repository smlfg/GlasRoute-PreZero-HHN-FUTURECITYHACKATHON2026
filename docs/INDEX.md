# Dokumenten-Index

Eine Zeile pro Dokument. **Wer ein Dokument anlegt, verschiebt oder für veraltet erklärt, ändert
diese Tabelle im selben Commit.** Stand: 14.11.2026, Code `abd9ca2`.

## Einstieg (in dieser Reihenfolge lesen)

| Dokument | Zweck | Stand |
|---|---|---|
| [`STATUS.md`](STATUS.md) | 1 Seite: was läuft (mit Befehl), Pitch-Zahlen, was simuliert ist, was offen ist | **aktuell** |
| [`TODO.md`](TODO.md) | Aufgaben bis Feature-Freeze (So 11:00) und Abgabe (So 13:00), mit Timebox | **aktuell** |
| [`STAKEHOLDER.md`](STAKEHOLDER.md) | Die sechs fixierten PreZero-/Mentor-Regeln und wo jede im Code umgesetzt ist | **aktuell** |
| [`../README.md`](../README.md) | Installation, Demo-Ablauf, alle CLI-Befehle, Geo-Austauschpfad | **aktuell** |

## Fachliche Dokumente

| Dokument | Zweck | Stand |
|---|---|---|
| [`PITCH.md`](PITCH.md) | Pitch-Struktur (3 Min), belegte Zahlen, Demo-Ablauf, Betriebsvariablen als Live-Hook | **aktuell** |
| [`EXPORT_RECHERCHE.md`](EXPORT_RECHERCHE.md) | Recherche zu GPX/KML/CSV-Export und Google Maps / OsmAnd / Garmin Support | **aktuell** |
| [`KOSTENMODELL.md`](KOSTENMODELL.md) | Kosten- und Ledger-Vergleich: Status Quo vs. GlasRoute über 349 Tage | **aktuell** |
| [`ARCHITEKTUR.md`](ARCHITEKTUR.md) | Module, Datenfluss, Verantwortlichkeiten, Geo-Swap | **aktuell** |
| [`DATENMODELL.md`](DATENMODELL.md) | Dataclasses in `src/prezero/model.py` (Standort, Container, Messung, Fahrzeug) | **aktuell** |
| [`ABFALLARTEN.md`](ABFALLARTEN.md) | `WasteStream`-Modell, 4 synthetische Abfallarten, Generator & CLI `--stream` | **aktuell** |
| [`BACKTEST.md`](BACKTEST.md) | Ist der Füllstand vorhersagbar? Leerungsrhythmus je Glasfarbe | **generiert** von `scripts/backtest.py` |
| [`BENCHMARK.md`](BENCHMARK.md) | Fairer Vergleich B0–B4 über 4 Stichtage × 3 Seeds | **generiert** von `scripts/benchmark.py` |
| [`UI_PLAN.md`](UI_PLAN.md) | Soll-Zustand der Website: Datums-first (`#global-date-picker`), Rollen, Ansichtsgrenzen | **aktuell** (umgesetzt) |
| [`UI_DIFF_FINAL.md`](UI_DIFF_FINAL.md) | Finaler Frontend ↔ Backend Diff-Audit vor dem Freeze: Status aller Tabs & Seiten, S/M-Fixes | **aktuell** |
| [`UI_SPRACHE.md`](UI_SPRACHE.md) | Nielsen #2: keine UUIDs, kein snake_case, keine englischen Enums in sichtbarem Text | **aktuell** |
| [`STANDORTPLANUNG.md`](STANDORTPLANUNG.md) | Annahmen des Standortplanung-What-if Tabs (simulierte Koordinaten, Radius, Adoptionskurve) | **aktuell** |
| [`ANFORDERUNGEN.md`](ANFORDERUNGEN.md) | Anforderungen aus der Challenge-Readme (Quelle, nicht verhandelbar) | **aktuell** |
| [`analysen/INDEX.md`](analysen/INDEX.md) | 36 Datenanalysen: je eine Kennzahl und Kernaussage | **aktuell** |
| [`analysen/01…36`](analysen/) | Datengrundlage der Pitch-Aussagen (Ausnahmen sind dort markiert) | **aktuell**, außer als „archiviert“ markiert |
| [`copilot_visual_explainer.html`](copilot_visual_explainer.html) | Interaktiver Erklärartefakt zum Copilot-Tab | **aktuell**, kein Abgabebestandteil |
| [`pipeline_explainer.html`](pipeline_explainer.html) | Interaktiver 1-Seiten-Explainer der Datenpipeline (CSV bis Fahrertour, Echt vs. Annahme) | **aktuell** |
| [`../Mathe/README.md`](../Mathe/README.md) | Formelsammlung, CFO-Kostenmodell, Stresstest-Analyse (+20 % Zufluss) | **aktuell** |
| [`Mathe/codex_dispatch_kritik.md`](Mathe/codex_dispatch_kritik.md) | Mathematische & methodische Prüfung des Q3-Quartalsexperiments (`€/t` vs. Überlauf) | **aktuell** |

## Projekt-Steuerung

| Dokument | Zweck | Stand |
|---|---|---|
| [`../AGENTS.md`](../AGENTS.md) | Arbeitsvertrag: Ein-Schreiber-Regel, Datei-Ownership, Commit-Regeln, Scope | **aktuell** |
| [`../Pitch/NOTES.md`](../Pitch/NOTES.md) | Bühnennotizen, Live-Demo-Skript, Fragen an PreZero, Zahlenstand | **aktuell** |
| [`../Pitch/deck.md`](../Pitch/deck.md) | 10 Folien als Markdown-Quelle (3:30 Min) | **aktuell** |
| [`../Pitch/slides.html`](../Pitch/slides.html) | Interaktive 16:9-Präsentationsfolien mit Speaker-Notes, Timer & PDF-Export | **aktuell** |
| [`../Pitch/pitch_deck.pdf`](../Pitch/pitch_deck.pdf) | Druckfertige 10-Seiten-PDF-Präsentation im 16:9 Querformat | **aktuell** |
| [`../Pitch/QA.md`](../Pitch/QA.md) | Jury-Q&A: 12 harte Fragen, ehrliche Antworten, Bühnen-Kurzliste | **aktuell** |
| [`../Pitch/fallback/`](../Pitch/fallback/) | Offline-Fallback: fertige Demo-Tour als JSON + CSV plus Anleitung für den Pitch ohne laufenden Rechner | **aktuell** |
| [`../Pitch/VERGLEICHSWERT_WETTBEWERBER.md`](../Pitch/VERGLEICHSWERT_WETTBEWERBER.md) | Wettbewerbsanalyse („Garbage Collector“): Vergleichswerte, Stärken/Schwächen, Pitch-Hebel | **aktuell** |
| [`../Projek-Management/proof/A3_pitch_zahlen.txt`](../Projek-Management/proof/A3_pitch_zahlen.txt) | Beleg: jede Pitch-Zahl gegen die Pipeline geprüft (`RESULT: ALL MATCH`) | **aktuell** |
| [`../Projek-Management/proof/`](../Projek-Management/proof/) | A1 Freigabe-Verhalten, A2 Beleg, A4 README-Demo, A5 Tests | **aktuell** |
| [`../PLAN.md`](../PLAN.md) | Hackathon-Plan mit Prüfkriterien je Stufe | **historisch** (14.11.) |
| [`../PLAN_VALIDATION_REPORT.md`](../PLAN_VALIDATION_REPORT.md) | Unabhängige Freigabe des Plans | **historisch** (14.11.) |
| [`../UPSTREAM_SEARCH.md`](../UPSTREAM_SEARCH.md) | Upstream-Recherche vor Eigenbau (Geo-Quellen) | **historisch** (14.11.) |
| [`../Projek-Management/plan-council/`](../Projek-Management/plan-council/) | Bewertung des Plans durch den Plan-Council | **historisch** |

## Archiv (veraltet, nur Historie)

| Dokument | Zweck | Stand |
|---|---|---|
| [`archiv/README.md`](archiv/README.md) | Tabelle: was ist veraltet, seit welchem Commit, und was gilt stattdessen | **Archiv** |
| [`archiv/GEO_DATENQUELLEN.md`](archiv/GEO_DATENQUELLEN.md) | OSM/Overpass-Quellen, Lizenz, „126 reale / 323 Platzhalter“ | veraltet seit `d12331f` |
| [`archiv/PITCH_EXECUTIVE_SUMMARY.md`](archiv/PITCH_EXECUTIVE_SUMMARY.md) | 1-Seiter Datenbefunde mit materialabhängigen Intervallen | veraltet seit `127d502` |
| [`archiv/FRONTEND_AUDIT.md`](archiv/FRONTEND_AUDIT.md) | Backend-vs-Website-Audit der 4-Tab-Oberfläche | veraltet seit `1353f28` |
| [`archiv/ROADMAP.md`](archiv/ROADMAP.md) | UI-Roadmap | veraltet seit `1577c74` (→ `TODO.md`) |
| [`archiv/analysen/16_leerungen_erkennen.md`](archiv/analysen/16_leerungen_erkennen.md) | Leerungen über negative Sprünge erkennen | veraltet seit `127d502` |
| [`archiv/ui_konzept/`](archiv/ui_konzept/) | Skizze, Blueprint, 03_ui_mockup (67,92 km / −74 %), UML, Integrationsplan | veraltet seit `2005f7f` |
