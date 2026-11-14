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

## PII-Filter (vor jedem LLM-Aufruf)

Im Chat werden keine Namen, Adressen, Schulen oder Kontaktdaten erfragt. Stehen solche Angaben trotzdem in einer Nachricht, filtert der Worker sie **bevor** etwas an Claude, Workers AI oder einen anderen Anbieter geht: entweder entfernen und nur den restlichen, sachlichen Teil senden — oder die Anfrage ablehnen und um eine Nachricht ohne persönliche Angaben bitten. Die Originalnachricht mit PII wird nicht gespeichert und nicht weitergegeben.

Alter und Interessen dürfen für die Passung verwendet werden, aber nur in der laufenden Sitzung.

## Löschkonzept

Kurz: Es soll fast nichts zu löschen geben, weil personenbezogene Daten nicht gespeichert werden. Trotzdem muss klar sein, wer worauf zugreift und wann etwas weg ist.

### Was existiert

| Daten | Wo | Personenbezogen? | Lebensdauer |
|---|---|---|---|
| Chat-Nachrichten und Verlauf | nur im aktuellen Request und ggf. im Browser-Tab | möglicherweise (deshalb filtern) | Ende der Sitzung: Tab schließen oder neu laden |
| Gefilterte LLM-Anfrage | kurz beim gewählten Anbieter, falls ein Modell genutzt wird | soll keine PII enthalten | kein Speichern bei uns; Aufbewahrung beim Anbieter laut dessen AGB |
| Anonyme Lücken-Zähler | nur falls überhaupt geführt, ohne Freitext und ohne reidentifizierende Zeitstempel | nein, wenn wirklich anonym | können jederzeit auf null gesetzt werden; im Zweifel gar nicht persistieren |
| Angebote | `data/offers.json` | nein (nur öffentliche Trägerangaben) | bleiben, solange das Angebot gilt |
| Trägerliste | `data/institutions.json` | nein | Konfiguration |
| Eltern-Teilen | Link wird auf dem Gerät der Nutzerin oder des Nutzers geöffnet (WhatsApp/E-Mail) | wir speichern keine Empfänger | wir senden und behalten nichts |

### Wer hat Zugriff

Im Hackathon: nur die Autorin bzw. der Autor des Repos (API-Keys in `.dev.vars` / `.env`, nicht im Git). Keine geteilten Kinder-Accounts. Betreiber-Logs enthalten keine Nachrichteninhalte. Drittanbieter (LLM) bekommen höchstens gefilterte, sachliche Texte plus öffentliche Angebotsausschnitte — keine Kinderprofile.

### Wann wird gelöscht

- **Sitzungsende** (Tab zu, Seite neu, „neu starten“): Verlauf im Browser ist weg. Das ist der Normalfall und der Datenschutzstandardweg (Gastmodus, ohne Registrierung).
- **Keine Serverpersistenz:** nichts auf Platte, in R2, in einer Datenbank oder in langlebigen Logs. Gibt es trotzdem versehentlich einen Logeintrag mit Nachrichtentext, wird er sofort gelöscht.
- **Anfrage auf Löschung:** Weil keine Personenprofile existieren, gibt es in der Regel nichts nachzutragen. Falls doch ein Rest in Logs auftaucht, wird er gelöscht, sobald er bekannt wird.
- **Keys und lokale Dev-Dateien:** nicht committen; nach dem Hackathon Keys rotieren, wenn sie geteilt oder in Logs gelandet sein könnten.

### Anbieter-AGB (Altersgrenzen)

Vor dem Einsatz eines LLM mit Minderjährigen die Nutzungsbedingungen prüfen und das Ergebnis hier eintragen. Bis **Sa 20:00** (siehe [PLAN.md](../PLAN.md)).

- Gewählter Anbieter:
- Dokument / URL, geprüft am:
- Altersgrenze bzw. relevante Klausel (kurz, mit Fundstelle):
- Folge für Lernlotse (ok / nur mit Eltern / anderer Anbieter / erst Satzbausteine ohne LLM):

Solange das nicht geklärt ist: kein ungeprüftes LLM gegenüber Kindern; Fallback ist Retrieval plus feste, selbst geschriebene Satzbausteine (Antworten bleiben im eigenen System).

### Eltern-Teilen

Der Button erzeugt nur einen Anteil-Link mit der **öffentlichen Angebots-URL** (und dem Titel). Keine Chatverläufe, keine Namen, keine Alterangaben. Lernlotse verschickt die Nachricht nicht selbst und speichert keine Empfängeradressen.

