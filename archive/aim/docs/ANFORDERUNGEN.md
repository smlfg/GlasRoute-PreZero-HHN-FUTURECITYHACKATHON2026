# Anforderungen der aim-Challenge

Pflicht aus der Challenge **Build a Learning Guide**. Verdichtet für den RAG-Chat-Agenten. Quelle: Vorgaben von aim (Do’s, Don’ts, Hard Requirements). Die Pitch-Checkliste steht auch in der [README](../README.md#checkliste-vor-dem-pitch).

## Hard Requirements (muss erfüllt sein)

| # | Vorgabe | Bedeutung für Lernlotse |
|---|---|---|
| 1 | Zielgruppe Kinder/Jugendliche **und** Eltern | Einstieg **„Für mich / Für mein Kind“**. Beide müssen allein zurechtkommen. |
| 2 | Keine reine Liste, kein klassischer Kalender | Der Chat ist die Oberfläche, keine Filterliste als Hauptweg. |
| 3 | Fokus auf genau vier Institutionen | nur aim, experimenta, Haus der Familie, IPAI Foundation (`data/institutions.json`). |
| 4 | Themenfokus AI, Coding, Gaming | andere Themen höchstens optional, nicht empfohlen. |
| 5 | Skalierbarkeit ohne Programmierkenntnisse | neue Träger/Quellen über JSON-Dateien ergänzen, nicht im Code. |
| 6 | Wartung gering / halbautomatisch | Import möglich, aber jede Einspielung durch eine **menschliche Kontrollschleife**. |
| 7 | Transparente Code-Struktur | nachvollziehbare Entscheidungen in README, Plan und Code. |
| 8 | Datenschutz für Kinder von Anfang an | keine Registrierung, keine dauerhafte Speicherung, PII-Filter, Löschkonzept. |

## Do’s

**Produkt und UX**

- Einstieg nach Zielgruppe trennen: „Für mich“ vs. „Für mein Kind“.
- Einfache Sprache, kurze Sätze, große serifenlose Schrift; Kinder ab etwa 8 Jahren sollen allein zurechtkommen.
- Bilder, Icons, Symbole zusätzlich zum Text.
- Im Gespräch (nicht als Excel-Filter) Thema, Altersgruppe, Datum und Veranstaltungsart klären.
- Spielerische Entdeckung: Interesse sagen, passendes Angebot bekommen.
- Eltern-Freigabe: Kind findet ein Angebot und teilt es zum Anmelden; keine Selbstregistrierung für Minderjährige.
- Mobile-first und barrierearm.
- Ohne Registrierung nutzbar.

**Daten und Wartung**

- Quellen der Träger prüfen (API, RSS, iCalendar, CSV/JSON), sonst manuell von der offiziellen Website.
- Menschliche Kontrolle vor der Übernahme nach `data/offers.json`.
- Konfiguration über Dateien (`data/institutions.json`), damit Nicht-Techniker Quellen ergänzen können.
- Klares Datenmodell: Titel, Institution, Thema, Alter, Datum, Ort, Link, Beschreibung, Tags.

**Datenschutz und KI**

- KI klar als KI kennzeichnen, nie wie ein Mensch wirken.
- Altersgerechte, kurze Antworten; schwierige Begriffe erklären.
- Keine Namen, Adressen, Schulen oder Kontaktdaten abfragen.
- Eingaben auf PII prüfen und filtern, **bevor** sie an ein LLM gehen.
- Chat-Verlauf nicht speichern, höchstens in der laufenden Sitzung (Gastmodus).
- Altersgrenzen in den AGB der LLM-Anbieter prüfen und dokumentieren.
- Löschkonzept festhalten: wer worauf zugreift, wann etwas weg ist — siehe [DATENSCHUTZ.md](DATENSCHUTZ.md).

## Don’ts

| Bereich | Nicht tun | Warum |
|---|---|---|
| Registrierung | Keine Selbstregistrierung für Kinder | Minderjährige können keine wirksame Einwilligung geben. |
| Speicherung | Keine dauerhaften Profile, Favoriten oder Suchhistorien für Kinder | so wenig personenbezogene Daten wie möglich |
| Gamification | Keine Bestenlisten mit echten Namen, keine Login-Belohnungen | keine Druckerzeugung, Kinderrechte |
| KI-Sicherheit | Keine ungefilterten LLM-Antworten ohne Inhaltsschutz | Schutz vor unangemessenen Inhalten |
| Datenweitergabe | Keine Kinderdaten an Drittanbieter | DSGVO, AI Act |
| Ortung | Keine exakte Adresse, keine Standortprofile | Datenschutz |
| Umfang | Nicht alle Bildungsangebote Heilbronns abdecken | auf Träger und Themen begrenzen |
| UI | Keine excel-artige Liste oder ein klassischer Eventkalender als Lösung | explizit ausgeschlossen |

## Auswirkungen auf den RAG-Agenten

Die Challenge nennt einen KI-Assistenten mit Rückfragen ausdrücklich als Bonus. Der Gesprächs-Agent erfüllt die Vorgabe „keine Liste“, wenn die folgenden Punkte fest eingebaut sind:

1. **KI-Label sofort sichtbar:** „Ich bin ein KI-Assistent und helfe dir, ein passendes Angebot zu finden.“
2. **Nur RAG, kein freier Chat:** Antworten nur aus dem Angebotsbestand, nicht allgemein plaudern.
3. **Keine Profilabfrage zum Speichern:** Alter und Interessen dürfen im Chat stehen, bleiben aber **nur in der Sitzung**.
4. **PII-Filter vor dem LLM:** Namen, Adressen, Schulen erkennen; dann entfernen oder die Anfrage ablehnen — nichts davon an den Anbieter senden.
5. **Eltern-Teilen:** Button „Dieses Angebot an Mama oder Papa weiterleiten“ (z. B. WhatsApp- oder E-Mail-Link mit der **Angebots-URL**, ohne Kinderdaten).
6. **Einfache Sprache** im System-Prompt: kurze Sätze, freundlicher Ton.
7. **Themengrenze** im Prompt: nur AI, Coding, Gaming empfehlen.
8. **Transparenz:** README und Datenschutz erklären, welche Daten wohin gehen.
9. **Einstieg „Für mich / Für mein Kind“**, mobile-first, ohne Registrierung.
10. **institutions.json** als erweiterbare Trägerliste; importierte Angebote erst nach menschlicher Prüfung live.
11. **Anbieter-AGB** (Altersgrenzen von Claude/Anthropic bzw. gewähltem LLM) prüfen, bevor der Dienst mit Minderjährigen genutzt wird.

## Checkliste vor dem Pitch

Steht in der README und wird So 11:00 / 12:30 abgehakt.
