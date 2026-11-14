# Independent Plan Validation
Verdict: REPLAN
Checked Plan: `PLAN.md`, Geo-Positions-Slice, Zeilen 36–62; Gesamtplan auf Scope-Konflikte geprüft.
Attempt: 1/2
Mission: `M-20261114T144015-322994d8`; Session: `S-20261114T144024-d7a17e31`.
Plan-SHA256: `cd0c6e4c27c9f6eccf76dd56d9466a1d73320cc49d5744263fd0eafa6fe735ec` (aktuell berechnet; identisch zum Council-Nachweis).
Council: `Projek-Managment/plan-council/grade-PLAN-score_ok-20261114T134151Z.json`: overall 0.938 ≥ threshold 0.75, SCORE_OK, live; ein Judge, `degraded=true`, daher eingeschränkte Redundanz und keine eigenständige Build-Freigabe.

## Prüffindings
- Erfüllt — ID-/OSM-Ehrlichkeit (`PLAN.md:40,48,57`): anonyme Zuordnung ausdrücklich unbewiesen, OSM höchstens low, Kandidaten und Zuordnungen statistisch getrennt; keine behauptete Identitätsrekonstruktion.
- Erfüllt — PreZero-Override (`PLAN.md:48–50,55–56`): expliziter Pfad vor Defaultdatei vor Matches/Synthetik; Providerdaten high; minimaler CSV-Vertrag und Tests für Priorität sowie Refresh vorgesehen.
- Teilweise erfüllt — Overpass-Fallback (`PLAN.md:47,55–56`): HTTP-/Netzwerk-/Schemafehler, leere Kandidatendatei und Ausfalltests sind vorgesehen. Ein endliches Request-Timeout und ein begrenztes Retry-Budget fehlen; ein hängender Request muss sonst den beschriebenen Fallback nicht erreichen. Prüfkriterium: Timeout-Fall erreicht innerhalb einer festgelegten Frist den Resolver und liefert markierte Ersatzdaten.
- Erfüllt als Planvorgabe — 449-Zeilen-DoD (`PLAN.md:40,58`): genau eine Koordinate je der 449 IDs plus Eindeutigkeit ergibt genau 449 Datenzeilen; endliche WGS84-Werte und Herkunftsspalten sind gefordert. Die Abnahme sollte Zeilenzahl und Gleichheit zur Eingabe-ID-Menge ausdrücklich prüfen; keine Ausführung oder Datenprüfung erfolgt.
- Blockierend — Scope (`PLAN.md:42,62`): fachliche Nicht-Ziele sind klar, aber erlaubte Schreibpfade werden ausschließlich über einen nicht enthaltenen Missionsvertrag referenziert. Für `locations*.csv`, Statistiken, Karte und Tests fehlen vollständige Zielpfade. Aus den beiden zugelassenen Prüfdateien lässt sich die Schreibfreigabe nicht rekonstruieren. Der globale Push-Termin (`PLAN.md:22`) ist durch das Slice-Verbot (`PLAN.md:42`) für diese Mission ausgeschlossen.

## Replan Instructions
1. In `PLAN.md` eine vollständige, eindeutige Liste erlaubter Schreibdateien beziehungsweise eng begrenzter Verzeichnisse für diesen Slice aufnehmen, einschließlich Datenoutputs, Karte, Statistiken, Tests und Dokumentation; übrige Pfade ausdrücklich ausschließen.
2. In `PLAN.md` endliches Overpass-Timeout, begrenztes Retry-Budget und einen prüfbaren Timeout-Fallback-Test festlegen; die 449-Abnahme explizit um Datenzeilenzahl und exakte Eingabe-ID-Menge ergänzen. Anschließend Council-Nachweis für den neuen SHA und unabhängige Validierung erneuern.
Build Release allowed: no
Ausführung: selbst ausgeführt, weil OpenCode an `/dev/fd/63` scheiterte, mcode ohne Antwort abgebrochen wurde, Codex am Trusted-Directory-Check scheiterte, Claude nicht angemeldet war und Cursor keine Runtime-Verzeichnisse anlegen konnte; Hermes gemäß dokumentiertem Hänger-Hinweis übersprungen. Geändert wurde ausschließlich dieser Report; kein Code, Plan-Rewrite, Build oder Commit. Offen bleiben die oben genannten Planpräzisierungen.
