# data/

Kuratierter Angebotsbestand für Lernlotse.

- `offers.schema.json` — verbindliches Schema.
- `offers.json` — echte, geprüfte Angebote. Aktuell leer. Nichts erfinden.
- `offers.example.json` — nur Formatbeispiele, klar als `BEISPIEL` markiert. Nicht in die Demo übernehmen.
- `institutions.json` — die vier Fokus-Träger (Name + geprüfte offizielle Website). Neue Träger später nur hier ergänzen, ohne Code zu ändern. Das Feld `id` sollte zum Feld `institution` in `offers.json` passen oder klar zuordenbar sein.

Pflichtfelder: `title`, `institution`, `topic`, `age_min`, `age_max`, `format`, `date`, `location`, `link`, `description`, `tags`.

Fokus-Träger: aim, experimenta, Haus der Familie, IPAI Foundation.
Fokus-Themen: AI, Coding, Gaming.

Prüfung: `python3 scripts/validate-offers.py`

## Kuratierter Bestand (Stand 14.11.2026)

- **200 echte Angebote**: aim (55), Haus der Familie (70), experimenta (55), IPAI Foundation (20).
- `offers.json` — der für den Worker gültige, schema-konforme Export (200 Einträge, Validierung bestanden).
- `angebote.json` — die reichere Quelle dahinter: exakte Termine, Preise, Zielgruppen, Quell-URLs, Abrufdatum.
- `raw/` — Rohdaten-Snapshots der Träger; `build_dataset.py` baut daraus `angebote.json`, `../scripts/export-offers.py` erzeugt daraus `offers.json`.
- **80 Angebote** mit Fokus AI/Coding/Gaming. Bei **43** Einträgen fehlte in der Quelle eine Altersangabe; sie ist aus der Zielgruppe abgeleitet und mit `alter-geschaetzt` markiert.
- Alle **173 verwendeten URLs** wurden am 14.11.2026 geprüft (HTTP 200).
- Keine erfundenen Termine, Preise oder Links. Rechte an Texten und Terminen liegen bei den Trägern; vor Veröffentlichung Aktualisierung und Nutzung abstimmen.

## Erhebung (Sa 16:00 ausfüllen)

- Stand der Erhebung: 14.11.2026, 13:45 Europe/Berlin
- Träger, die tatsächlich erfasst wurden: aim, Haus der Familie, experimenta, IPAI Foundation
- Anzahl geprüfter Angebote: 200 (Ziel war 20, Ausbaustufe 30–50)
- Abweichung vom Ziel 20 / 30–50: deutlich darüber; Fokus AI/Coding/Gaming: 80 Angebote
- Quelle: nur offizielle, geöffnete Seiten der Träger; jede Zeile mit Quell-URL und Abrufdatum
- Geprüft: Quellenabruf und Strukturprüfung am 14.11.2026 (alle 173 URLs HTTP 200); fachliche Endkontrolle durch Samuel vor der Demo

## Menschliche Kontrollschleife

Kein Import landet ungeprüft in `offers.json`.

1. Rohdaten sammeln (Website, optional API/RSS/iCal/CSV — höchstens 30 Minuten Automatisierung).
2. Jeden Datensatz öffnen und prüfen: echter Träger aus `institutions.json`, Thema AI/Coding/Gaming (andere nicht als Empfehlung), Alter, Datum, Ort, funktionierender Link, Beschreibung laut Träger — nichts erfinden.
3. Erst dann nach `offers.json` übernehmen.
4. In der Erhebung unten kurz festhalten, wer geprüft hat (Vorname reicht) und wann.

## Weitere Institution ergänzen (ohne Code)

In `institutions.json` ein Objekt mit `id`, `name` und `url` anhängen. Die `url` nur eintragen, wenn die offizielle Website geprüft ist, sonst leer lassen. Danach Angebote dieses Trägers wie oben prüfen und in `offers.json` legen.
