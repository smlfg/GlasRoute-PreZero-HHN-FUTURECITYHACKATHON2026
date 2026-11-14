# Datenschutz — Lernlotse

Kurzfassung für Bau, Demo und Pitch. Keine Rechtsberatung.

## Grundsatz

Lernlotse richtet sich auch an Familien und Minderjährige. Deshalb gilt: **so wenig Daten wie möglich, am besten keine personenbezogenen Daten.**

## Was der Dienst tun darf

- Im laufenden Request den Gesprächsverlauf halten, um die nächste Frage oder Empfehlung zu erzeugen.
- Öffentliche Angebotsdaten der Träger verwenden (Titel, Alter, Ort, Link, Beschreibung).
- Für die Lücken-Ansicht höchstens anonyme Zähler führen, z. B. „Thema Coding, Altersband 8–12, kein Treffer“. Ohne Zeitstempel, der eine Person reidentifiziert. Ohne freie Texte aus dem Chat.

## Was der Dienst nicht darf

- Keine Namen, Alter als Identifikator, Kontaktdaten, Schul- oder Wohnortangaben speichern.
- Keine Chat-Verläufe auf Platte, in R2, in Logs oder in einer Datenbank ablegen.
- Keine Accounts, keine Cookies zur Wiedererkennung, kein Tracking, kein Profiling.
- Keine Empfehlung „für genau dieses Kind“ über Sitzungen hinweg merken.
- Keine personenbezogenen Beispiele in Folien, README oder Issues.

## Technisch

- Logs in der Demo ohne Nachrichteninhalt halten oder ganz weglassen.
- Anbieter-Keys nur in `.dev.vars` / `.env`, nie im Repo.
- Angebote in `data/offers.json` enthalten nur öffentliche Trägerangaben, keine Teilnehmerlisten.

## Auf der Bühne

- Demo mit fiktiven, unspezifischen Angaben („ein Kind, 10 Jahre“) führen — das sind Rollen, keine echten Personendaten.
- Diesen Text im Pitch in einem Satz zusammenfassen: „Wir speichern keine Gespräche und keine Angaben zu Kindern.“
