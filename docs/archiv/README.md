# Archiv — veraltete Dokumente

Hier liegt alles, was **nicht mehr den Stand des Projekts beschreibt**. Nichts davon löschen:
Es erklärt, wie wir hierher gekommen sind. Nichts davon im Pitch zeigen.

| Was | Veraltet seit | Warum | Gilt stattdessen |
|---|---|---|---|
| `GEO_DATENQUELLEN.md` | `d12331f` | „126 reale / 323 Platzhalter“ stimmt nicht mehr: alle 449 IDs liegen auf echten OSM-Punkten, Zuordnung simuliert | `README.md` (Geo-Swap), `docs/ARCHITEKTUR.md` |
| `PITCH_EXECUTIVE_SUMMARY.md` | `127d502` | materialabhängige Intervalle (80/70/60 %) wurden durch den Timer je Container ersetzt | `docs/PITCH.md`, `Pitch/NOTES.md` |
| `FRONTEND_AUDIT.md` | `1353f28` | beschreibt 4 Tabs und den gewichteten Score-Faktor; heute 9 Tabs, Timer-Modell | `docs/UI_SPRACHE.md`, `docs/UI_PLAN.md` |
| `ROADMAP.md` | `1577c74` | Inhalt ist in `docs/TODO.md` übergegangen | `docs/TODO.md` |
| `analysen/16_leerungen_erkennen.md` | `127d502` | Leerungserkennung über negative Sprünge war ein Behelf ohne Leerungsmodell | `docs/BACKTEST.md` |
| `ui_konzept/` (Skizze, Blueprint, 03_ui_mockup, UML, Integrationsplan) | `2005f7f` | Konzeptphase; das Mockup nennt 67,92 km / −74 % / `osm_heuristic`, alles überholt | `ui_2026-04-15.html` (aus `prezero-route run`) |

**Regel:** Ein Dokument wandert hierher, sobald es eine Zahl oder ein Modell behauptet, das nicht mehr
stimmt — nicht erst, wenn es alt aussieht. Der Kopf jedes archivierten Textes nennt den Commit.
