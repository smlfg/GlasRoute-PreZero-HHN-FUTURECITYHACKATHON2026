# Heilbronner Lernangebote – kuratierter Bestand (200 Angebote)

Datengrundlage für den Prototyp „Learning Guide“ der aim-Challenge (Future City Hackathon).

Dieses Dokument beschreibt den **reichen Quellbestand** `angebote.json`. Der für den Worker gültige Export nach Projektschema liegt in `offers.json` (siehe `data/README.md` und `scripts/export-offers.py`).
Enthalten sind **200 reale Angebote** der vier im README genannten Institutionen:

| Anbieter | Angebote |
|---|---:|
| aim – Akademie für Innovative Bildung und Management | 55 |
| Haus der Familie Heilbronn | 70 |
| experimenta Heilbronn | 55 |
| IPAI Foundation | 20 |
| **Gesamt** | **200** |

Stand: **14.11.2026**. Jeder Datensatz nennt seine Quell-URL und das Abrufdatum.

## Dateien

- `angebote.json` – der Datensatz (200 Objekte + Metadaten).
- `build_dataset.py` – nachvollziehbarer Aufbau: liest die Rohdaten aus `raw/`, wendet die manuell kuratierten Auswahllisten an und schreibt `angebote.json`.
- `raw/` – Rohdaten-Snapshots der Quellen (JSON), damit der Build reproduzierbar bleibt.

## Schema

```json
{
  "id": "aim-271430UN",
  "provider": "aim | experimenta | hdf | ipai",
  "provider_name": "ausgeschriebener Name",
  "title": "Titel des Angebots",
  "subtitle": "Untertitel / Zielgruppe, falls vorhanden",
  "description": "Kurzbeschreibung aus der Quelle (max. ca. 900 Zeichen)",
  "type": "kurs | workshop | vortrag | show | event | ferienbetreuung | laborkurs | ausstellung | fuehrung | fortbildung | wettbewerb | programm | Format",
  "topics": ["KI", "Coding", "Gaming", "Robotik", "Daten", "MINT", "Medienkompetenz", "Kreativität", "Astronomie", "Ferien", "Berufsorientierung", "Allgemein"],
  "focus_ai_coding_gaming": true,
  "audience": ["kinder", "jugendliche", "eltern", "familien", "lehrkraefte", "erwachsene"],
  "age_min": 10,
  "age_max": 14,
  "age_text": "10–14 Jahre",
  "dates": [
    { "start": "2027-02-03T15:30", "end": "2027-02-03T19:30", "text": "03.02.2027, 15:30–19:30" }
  ],
  "duration_text": "1 Termin",
  "location": { "name": "Hochschule Heilbronn – TechCampus", "address": "Max-Planck-Straße 39, 74081 Heilbronn", "city": "Heilbronn" },
  "price": { "amount": 0, "currency": "EUR", "text": "kostenlos" },
  "registration": { "url": "https://…", "status": "frei" },
  "url": "https://…",
  "source_url": "https://…",
  "retrieved_at": "2026-11-14",
  "collection": "manuell kuratiert"
}
```

Hinweise zu Feldern:

- `price.amount`: `0` = kostenlos, Zahl > 0 = bekannte Gebühr, `null` = Preis nicht auf der Übersichtsseite (z. B. experimenta-Tickets, Gruppenbuchungen, Eventbrite).
- `dates`: leer bei Angeboten ohne festen Termin (Laborkurse mit Gruppenbuchung, laufende Ausstellungen, wiederkehrende IPAI-Formate).
- `age_min`/`age_max`: nur gesetzt, wenn die Quelle ein Alter oder eine Klassenstufe nennt.
- `registration.status`: u. a. `frei`, `ausgebucht`, `Kurs hat begonnen`, `Anmeldung erforderlich`.

## Erhebung und Auswahl

Die Daten wurden **manuell kuratiert**: Jede Zeile wurde über die öffentliche Anbieterseite bzw. Kursdatenbank verifiziert; die Auswahl der Kurse erfolgte über konkrete Kursnummern/Titel, nicht über einen unkontrollierten Crawl. Die Rohdaten-Snapshots in `raw/` sind der Belegstand.

Verwendete Quellen:

- **aim:** Kurslisten für Digitale Bildung (Coding, Gaming, KI, Digitale Kompetenzen), Lernen in Ferien & Freizeit, Kinderuni und Juniorakademie inkl. Detailseiten.
  `https://www.aim-akademie.org/kurse` (Parameter `kfs_sonderrubrik` / `kfs_kursbereich`)
- **experimenta:** Veranstaltungskalender (35 verschiedene Termine/Formate) und Laborkurs-Buchungsshop (20 ausgewählte Laborkurse aus 84).
  `https://www.experimenta.science/besuchen/veranstaltungen/`
  `https://buchung.experimenta.science/ticket-web-shop/Labs/Lab`
- **Haus der Familie:** Kursdatenbank über die öffentliche Kufer-API, gefiltert auf „Schulkinder & Jugendliche“, „Digitale Familienwerkstatt“ und „MINT“.
  `https://hdf-hn.de/kufer-api.php?endpoint=kurse`
- **IPAI Foundation:** Eventseiten, KI Salon, KI Festival, Robotic Weeks, Besucherzentrum, AI Literacy Masterclass, Science Residency.
  `https://ipai-foundation.ai/`

Ergänzend: Alle 173 im Datensatz verwendeten URLs wurden am 14.11.2026 auf HTTP-Status geprüft (alle `200`).

## Datenqualität und Grenzen

- **167 von 200** Angeboten haben mindestens einen festen Termin; 33 sind laufende Formate, Ausstellungen oder Gruppenbuchungen ohne Einzeltermin.
- **78 Angebote sind kostenlos**, 62 haben eine bekannte Gebühr, bei 60 ist der Preis nicht auf der Übersichtsseite angegeben.
- **80 Angebote** sind einem der Challenge-Schwerpunkte KI, Coding oder Gaming zugeordnet (`focus_ai_coding_gaming`), davon 51 mit KI-, 34 mit Coding- und 8 mit Gaming-Bezug (Mehrfachzuordnung möglich).
- Gleiche Titel mit unterschiedlichen Kursnummern sind echte parallele Kurse bzw. verschiedene Termine (z. B. „Roboter – Stufe 2“ oder „Bunt & queerlig“).
- Die Beschreibungen sind aus den Quellen übernommen und gekürzt; Ton und Details können sich mit der Quelle ändern.
- **Rechte:** Titel, Texte und Termine gehören den jeweiligen Anbietern. Der Datensatz ist eine Hackathon-/Prototyp-Grundlage. Vor einer Veröffentlichung müssen Rechte, Aktualität und eine automatisierte Aktualisierung mit den Anbietern geklärt werden.

## Erweitern

Ein neuer Anbieter braucht nur:

1. eine Liste seiner Angebote mit stabiler ID, Titel, Beschreibung, Termin(en), Ort, Preis, Zielgruppe und Quell-URL,
2. eine Zuordnung zu `topics` und `audience`,
3. einen Eintrag in `meta.counts`.

Das Schema ist bewusst flach gehalten, damit weitere Institutionen und Themen ohne Codeänderung ergänzt werden können.
