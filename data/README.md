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

## Erhebung (Sa 16:00 ausfüllen)

- Stand der Erhebung:
- Träger, die tatsächlich erfasst wurden:
- Anzahl geprüfter Angebote:
- Abweichung vom Ziel 20 / 30–50:
- Quelle: nur offizielle, geöffnete Seiten der Träger (URLs hier erst eintragen, wenn geprüft)

## Menschliche Kontrollschleife

Kein Import landet ungeprüft in `offers.json`.

1. Rohdaten sammeln (Website, optional API/RSS/iCal/CSV — höchstens 30 Minuten Automatisierung).
2. Jeden Datensatz öffnen und prüfen: echter Träger aus `institutions.json`, Thema AI/Coding/Gaming (andere nicht als Empfehlung), Alter, Datum, Ort, funktionierender Link, Beschreibung laut Träger — nichts erfinden.
3. Erst dann nach `offers.json` übernehmen.
4. In der Erhebung unten kurz festhalten, wer geprüft hat (Vorname reicht) und wann.

## Weitere Institution ergänzen (ohne Code)

In `institutions.json` ein Objekt mit `id`, `name` und `url` anhängen. Die `url` nur eintragen, wenn die offizielle Website geprüft ist, sonst leer lassen. Danach Angebote dieses Trägers wie oben prüfen und in `offers.json` legen.
