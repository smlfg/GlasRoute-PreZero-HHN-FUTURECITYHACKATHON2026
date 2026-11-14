# Independent Plan Validation

Verdict: ACCEPT
Checked Plan: `PLAN.md`, insbesondere Geo-Positions-Modul und dessen Abgrenzung zum Gesamtplan.
Attempt: 2/2 (letzter zulässiger Versuch)
Mission: `M-20261114T144015-322994d8`
Session: `S-20261114T144024-d7a17e31`
Plan-SHA256: `f6ebe443dfb3b49f3a790a1ce3af63b03738e4c341faaa150deb67e94d5a0d6b` (aus den gelesenen aktuellen Dateibytes berechnet).
Council-Score: overall 0.938 ≥ threshold 0.75; SCORE_OK; mode live; SHA identisch zum aktuellen Plan. Nachweis: `Projek-Managment/plan-council/grade-PLAN-score_ok-20261114T134613Z.json`. Ein Judge, `degraded=true`: eingeschränkte Redundanz; der Council-Score allein ist keine Build-Freigabe.

## Findings zu sämtlichen Attempt-1-Anweisungen

1. **Schreibgrenzen vollständig aufgenommen — erfüllt.** `PLAN.md`, Abschnitt „Boundaries / Reproduktion“, benennt die erlaubten Dateien sowie die begrenzten Verzeichnisse `data/external/` und `Projek-Managment/` ausdrücklich und schließt alle übrigen Pfade aus. Datenoutputs, Sanity-Karte, Tests und Dokumentation haben konkrete Zielpfade; Statistiken gehen laut Umsetzungsschritt 4 auf stdout. Rawdaten, bestehender Pipeline-Code und Konfiguration bleiben unverändert. Das Slice-Verbot von Commits und Pushes begrenzt den allgemeinen Push-Termin für diese Mission eindeutig.
2. **Endliche Overpass-Timeouts und begrenzte Retries — erfüllt.** `PLAN.md`, Umsetzungsschritt 2, legt 10 s Connect- und 30 s Read-Timeout sowie höchstens zwei Versuche, also einen Retry, fest. Fehler werden sichtbar gemeldet; eine leere Kandidatendatei führt kontrolliert zum Fallback. Damit ist der zuvor offene unbeschränkte Request im Plan adressiert. Die tatsächliche Einhaltung durch die gewählte HTTP-Implementierung ist bei Umsetzung zu prüfen.
3. **Prüfbarer Timeout-Fallback — erfüllt als Planvorgabe.** `PLAN.md`, „Tests und Abnahme“, fordert einen Timeout-Mock, der die vollständige Auflösung aller IDs mit markierten Ersatzdaten nachweist, und prüft Retry-Zähler sowie Timeout-Parameter. Ergänzend sind CLI-Ausfalltests vorgesehen. Es wurden hier keine Tests ausgeführt.
4. **Exakte 449-ID-Abnahme — erfüllt als Planvorgabe.** `PLAN.md`, Abnahme, fordert ausdrücklich 449 Eingabe-IDs, genau 449 Ausgabe-Datenzeilen, eindeutige IDs und exakte Gleichheit der Ausgabe-ID-Menge mit der Eingabe-ID-Menge. Endliche gültige WGS84-Koordinaten sowie `source`, `confidence` und `match_reason` sind zusätzlich vorgeschrieben. Eine bloße Zeilenzählung reicht nach diesem Vertrag nicht aus.
5. **Council und unabhängige Validierung für neuen SHA — erfüllt.** Der zugelassene Council-Nachweis enthält exakt den oben berechneten revidierten SHA und einen Score über der Schwelle. Dieser Report dokumentiert dessen unabhängige Planprüfung in Attempt 2/2.

## Zusätzliche fachliche Prüfung

- **Anonyme IDs / OSM-Ehrlichkeit — erfüllt.** `PLAN.md`, „Ziel und Abgrenzung“ sowie Umsetzungsschritt 3, unterscheidet reale Containerstandorte von deren unbewiesener Zuordnung zu anonymisierten IDs. OSM-Zuordnungen bleiben grundsätzlich `low`; es gibt keine Behauptung einer rekonstruierten Identität. Kandidaten, heuristische Zuordnungen und Synthetik werden statistisch getrennt. Synthetik ist ausschließlich als `synthetic_placeholder/synthetic` zulässig.
- **PreZero-Override — erfüllt.** `PLAN.md`, Umsetzungsschritte 3–5, legt expliziten `real_path` vor `data/external/locations_real.csv` vor bestehenden Matches/Synthetik fest. Direkte Providerdaten mit `Location_id` erhalten `prezero_supplied/high`; die minimale Austauschdatei benötigt `Location_id,lat,lon`. Fehlende IDs werden ergänzt, fehlerhafte Pflichtspalten und Dubletten abgewiesen. Providerpriorität und Refresh mit temporärer PreZero-Datei sind ausdrücklich zu testen.
- **Overpass-Fallback — erfüllt als Planvorgabe.** Netzwerk-, Timeout-, HTTP- und Schemafehler, leere Kandidatendatei, gemeinsame Resolver-API und deterministische Ersatzdaten mit Seed 2026 sind festgelegt. Die Tests müssen die vollständige Ausgabe trotz Ausfall belegen.
- **449-ID-Vertrag — erfüllt als Planvorgabe.** Vollständigkeit, keine zusätzlichen IDs, Eindeutigkeit, Zeilenzahl, Koordinatengültigkeit und Herkunft sind gemeinsam abgedeckt.

Build Release allowed: yes

Die Freigabe gilt für die Umsetzung des beschriebenen Geo-Positions-Slices innerhalb der Plan-Whitelist; sie ersetzt keine Implementierungsabnahme und autorisiert keinen Commit, Push oder Deploy. Keine blockierenden Planbefunde verbleiben. Offen sind Umsetzung und Nachweis der im Plan geforderten Tests und Datenabnahme.

Ausführung: selbst als unabhängiger Validator gemäß ausdrücklichem Auftrag; keine Worker oder anderen Harnesses aufgerufen. Ausschließlich `PLAN.md`, `Projek-Managment/PLAN_VALIDATION_REPORT_ATTEMPT_1.md` und `Projek-Managment/plan-council/grade-PLAN-score_ok-20261114T134613Z.json` gelesen. Ausschließlich `PLAN_VALIDATION_REPORT.md` geschrieben; kein Code, Plan-Rewrite, Build oder Commit.
