# PLAN — Lernlotse

Arbeitsanweisung bis zur Abgabe. Alle Zeiten in **Europe/Berlin**.

## Stand jetzt

**Sa 14.11.2026, ca. 13:35.** Das Repo war leer. Gerüst, Schema und dieser Plan liegen jetzt auf `main`.

Festgelegt: Challenge **aim** (Learning Guide), Name **Lernlotse**, Ansatz Gesprächs-Agent mit echten Angeboten und Lücken-Ansicht.

Noch offen: Pitch-Zeit bei aim (heute persönlich holen).

Nächster Wegpunkt: **Sa 14:00 — Slot sichern.**

Realistisches Budget: etwa **12 Arbeitsstunden** plus Schlaf. Bis So 13:00 sind es rund 23 Stunden, die Nacht gehört dem Schlafen. Pitch und README müssen **So 11:00** stehen.

## Spielregeln

1. Nach einem Wegpunkt den Haken in der README-Statusliste setzen und den Satz unter „Stand jetzt“ aktualisieren.
2. Scraping: **maximal 30 Minuten**. Danach nur noch von Hand.
3. Cloudflare-Deploy ist ein Ziel, keine Voraussetzung. Eine stabile lokale Demo schlägt ein wackliges Deploy.
4. Keine erfundenen Angebote. Keine personenbezogenen Daten speichern.
5. Um 22:00 Schluss für heute. Fehlt der Checkpoint „UI im Browser“ knapp, härtester Cut um 23:00 — danach schlafen.
6. So 13:00 ist hart: Hacken stoppt, abgeben was steht.

## Übersicht

| Wann | Was | Wo | Checkpoint (RE) | Dient vor allem |
|---|---|---|---|---|
| Sa 14:00 | Slot bei aim holen | vor Ort, `docs/aim-notizen.md` | Uhrzeit des Slots steht in der Notiz | Machbarkeit, Teamwork |
| Sa 16:00 | Angebote sammeln | `data/offers.json` | ≥20 echte Angebote mit gültigem Link | Machbarkeit, Zuverlässigkeit |
| Sa 18:00 | Taggen + Filter | `data/`, `worker/` | Testfrage liefert ≥1 Treffer | Technikwahl, Machbarkeit |
| Sa 20:00 | Worker-Gespräch | `worker/` | 1 kompletter Demo-Dialog lokal, keine PII | Zuverlässigkeit, Originalität |
| Sa 22:00 | Minimale UI, dann schlafen | `web/` | Im Browser: Frage → Angebot + Link | Zuverlässigkeit |
| Nacht | Schlafen | — | Um 08:00 ausgeruht weiter | Zuverlässigkeit (morgen) |
| So 08:00 | Szenarien + Lücken | `docs/demo-szenarien.md` | 2 Szenarien reproduzierbar, Lücken skizziert | Nutzen, Originalität, Verständnis |
| So 10:00 | Provider / Showcase | vor Ort | Feedback notiert, Demo bleibt lauffähig | Teamwork, Zukunft |
| So 11:00 | Pitch + README | `docs/PITCH.md`, `README.md` | Kriterien abgedeckt, Startanleitung stimmt | Dokumentation, Verständnis |
| So 12:30 | Live-Test, Push | `main` | Demo einmal durch, Code online | Zuverlässigkeit |
| So 13:00 | Abgabe, Stop | dieses Repo, vor Ort | Präsentation + Code abgegeben | — |

## Wegpunkte im Detail

### Sa 14:00 — Slot bei aim

- **Was:** Persönlich zum aim-Stand bzw. zur Provider-Betreuung. Pitch-Zeitslot sichern. Kurz fragen, was aim am wichtigsten ist (Entdeckbarkeit, Wiederkommen, Sichtbarkeit von Lücken?).
- **Wie:** Hingehen, nicht mailen. Zeit und Kontakt sofort aufschreiben.
- **Wo:** vor Ort; Ergebnis in `docs/aim-notizen.md` (Slot, Name, drei Stichworte Feedback).
- **RE / Checkpoint:** Eine konkrete Uhrzeit für den Pitch steht in `docs/aim-notizen.md`.
- **Fallback:** Stand nicht auffindbar → Organisation / Hilfe vor Ort fragen. Ohne Slot trotzdem bauen; in der Notiz festhalten, dass nachgefragt wurde.
- **Kriterien:** Machbarkeit & Zukunft (Anschluss an den Träger), Teamwork (Kontakt trotz Solo).

### Sa 16:00 — Daten sammeln

- **Was:** 30–50 aktuelle, echte Angebote zu AI, Coding, Gaming (und nahen Themen) der vier Träger. Ziel 30–50, Pflichtschwelle 20.
- **Wie:** Zuerst höchstens 30 Minuten das Skript unter `scripts/` versuchen. Läuft es nicht sauber: sofort abbrechen und von den offiziellen Seiten der Träger per Hand übernehmen. Jeden Link öffnen und prüfen. Nichts erfinden.
- **Wo:** Schema `data/offers.schema.json`, Daten `data/offers.json`. Die Datei `data/offers.example.json` zeigt nur das Format — erfunden, nicht in die Demo übernehmen.
- **RE / Checkpoint:** `python3 scripts/validate-offers.py` ist grün. Mindestens 20 Objekte, jedes mit Titel, Träger, Thema, Alter von/bis, Format, Ort, gültigem Link und Beschreibung. In `data/README.md` stehen Erhebungsdatum und Träger, keine ungeprüften URLs.
- **Fallback:** Um 16:00 weniger als 20 Angebote → mit dem geprüften Bestand weiterbauen und die Lücke in `data/README.md` notieren. Qualität vor Quantität: 15 geprüfte Einträge schlagen 40 unsichere.
- **Kriterien:** Machbarkeit, Zuverlässigkeit (echte Daten), Verständnis (Datenmodell).

### Sa 18:00 — Taggen und Retrieval

- **Was:** Jedes Angebot ist typisiert (Thema, Zielgruppe, Format, grobe Schwierigkeit). Eine Suche über Felder (und optional Text) funktioniert.
- **Wie:** Fehlende Tags lieber 30 Minuten von Hand setzen als unsicher automatisch. Embeddings / Vectorize nur, wenn die Filter bereits laufen und Zeit übrig ist.
- **Wo:** `data/offers.json` (Feld `tags`), Retrieval-Einstieg in `worker/` (auch als kleines lokales Skript zulässig).
- **RE / Checkpoint:** Die Testfrage „Kind, 10 Jahre, Coding, Wochenende“ liefert mindestens einen nachvollziehbaren Treffer. Existiert im Bestand keiner, den Fall als Lücke dokumentieren und eine zweite Testfrage mit Treffer wählen.
- **Fallback:** Keine Embeddings. Noch kein Worker? Dann ein kurzer Filter in `scripts/search-offers.py`, den der Worker später aufruft.
- **Kriterien:** Technologie-Wahl, Machbarkeit.

### Sa 20:00 — Worker: Gespräch und Empfehlung

- **Was:** Das Backend nimmt Nachricht plus bisherigen Verlauf (nur im Request, nicht gespeichert), zieht Alter / Interesse / Format, holt Angebote und antwortet freundlich, altersangemessen, mit einem Vorschlag, Link und Warum.
- **Wie:** Cloudflare Worker, lokal mit `wrangler dev`. Prompt kurz halten: erst klären, dann empfehlen, nichts erfinden, nur Angebote aus dem JSON.
- **Wo:** `worker/` (Handler, Prompt, Retrieval, gebündeltes oder geladenes JSON).
- **RE / Checkpoint:** Ein Dialog von der Begrüßung bis zur Empfehlung läuft lokal durch. Es wird kein Verlauf und keine Personenangabe auf Platte oder in eine Datenbank geschrieben.
- **Fallback:** Kein wrangler / Cloudflare in der Zeit → kleiner lokaler HTTP-Server in `worker/` mit derselben Schnittstelle. LLM-Key fehlt → Retrieval plus feste Satzbausteine, LLM später nachziehen.
- **Kriterien:** Zuverlässigkeit, Originalität (Gespräch statt Filter-Dashboard), Technologie-Wahl.

### Sa 22:00 — Chat-UI, danach schlafen

- **Was:** Eine Seite: Chat, verbunden mit dem Worker. Lesbar, nicht perfekt. Dann Feierabend.
- **Wie:** Schlichtes HTML/CSS/JS oder ein minimales Frontend. Styling darf an Skizzen aus `smlfg/agent` erinnern, muss aber nicht.
- **Wo:** `web/`
- **RE / Checkpoint:** Im Browser eine Frage stellen und ein Angebot mit Link sehen. Den Demo-Pfad in `docs/demo-szenarien.md` beginnen.
- **Fallback:** Eine einzige `web/index.html`, die den Worker oder den lokalen Server aufruft. Deploy kann warten. Cut spätestens 23:00, dann schlafen — eine müde Demo morgen ist das größere Risiko.
- **Kriterien:** Zuverlässigkeit; später Dokumentation (vorzeigbare Demo).

### Nacht — Schlafen

Kein Feature mehr. Wecker so, dass **So 08:00** Arbeitsbeginn möglich ist.

### So 08:00 — Demo-Szenarien und Lücken

- **Was:** Zwei bis drei fest probierte Gespräche (z. B. Kind Coding, Elternteil sucht KI-Einstieg, Jugendliche Gaming). Lücken-Ansicht: Nachfrage-Intention gegen Bestand, anonym.
- **Wie:** Die Dialoge einmal durchspielen und festhalten (Schritte, erwartetes Angebot). Lücken zuerst aus dem Bestand und aus „kein Treffer“-Fällen; keine Personenbezüge.
- **Wo:** `docs/demo-szenarien.md`; Lücken als einfache Seite in `web/` oder als Abschnitt in Docs / Pitch.
- **RE / Checkpoint:** Zwei Szenarien sind reproduzierbar. Die Lücken-Ansicht existiert mindestens als klare, ehrliche Auswertung (auch statisch).
- **Fallback:** Keine Live-Zählung → eine statische Seite oder Folie aus dem Angebotsbestand („Themen oder Altersgruppen mit wenig Angebot“). Nicht schönerrechnen.
- **Kriterien:** Problem & Nutzen, Originalität, Verständnis, Zukunft (was fehlt).

### So 10:00 — Provider / Showcase

- **Was:** Ab 10:00 Treffen mit dem Provider / Showcase. Feedback stichwortartig mitnehmen. Nur noch ändern, was die Demo nicht gefährdet.
- **Wie:** Zeigen, was läuft. Zuhören. Kein Live-Rewrite der Architektur.
- **Wo:** vor Ort; Ergänzung in `docs/aim-notizen.md`.
- **RE / Checkpoint:** Feedback notiert. Die Demo läuft danach noch (oder nur mit einer sicheren Kleinigkeit besser).
- **Fallback:** Treffen dauert länger → Pitch-Struktur ist schon in `docs/PITCH.md` vorbereitet. Das README nicht erst nach dem Treffen beginnen.
- **Kriterien:** Teamwork, Machbarkeit & Zukunft.

### So 11:00 — Pitch und README fertig (hartes Ziel)

- **Was:** Abgabefähige Präsentation und ein README, mit dem jemand anderes die Lösung versteht und startet.
- **Wie:** Pitch entlang von `docs/PITCH.md` (den Kriterien bereits zugeordnet). README: Einzeiler, Problem, Lösung, Demo, Architektur, Technik, Datenschutz, Starten, Status.
- **Wo:** `docs/PITCH.md` plus Folien oder PDF, falls du welche baust; `README.md`.
- **RE / Checkpoint:** Jedes Kriterium (Teil A und B) hat eine klare Stelle im Pitch. Die README-Startanleitung entspricht dem, was wirklich läuft (lokal und/oder deployed).
- **Fallback:** Keine gestalteten Folien → `docs/PITCH.md` als Vortragskarte oder PDF-Export. README geht vor Folien-Optik.
- **Kriterien:** Dokumentation, Verständnis der eigenen Lösung, dazu die inhaltlichen Kriterien aus Teil A; Teamwork (Doku gleicht das fehlende Team teilweise aus).

### So 12:30 — Puffer, Live-Test, Push

- **Was:** Komplette Demo einmal analog zur Bühne. Offene Fehler nur fixen, wenn die Demo sonst bricht. Stand auf `main` pushen.
- **Wie:** Dieselben Schritte wie in `docs/demo-szenarien.md`. Optional Cloudflare-Deploy. Backup: Bildschirmaufnahme der lokalen Demo.
- **Wo:** `web/`, `worker/`, Branch `main`.
- **RE / Checkpoint:** Ein Durchlauf hat funktioniert. Aktueller Code ist auf GitHub. Startanleitung und Realität stimmen überein.
- **Fallback:** Deploy scheitert → lokale Demo plus kurze Aufnahme. In den letzten 30 Minuten nicht die Plattform wechseln.
- **Kriterien:** Zuverlässigkeit, Technologie-Wahl.

### So 13:00 — Stopp und Abgabe

- **Was:** Hacken beenden. Finale Präsentation und Code abgeben. Danach Vorauswahl.
- **Wie:** Nur noch das Abgabeformat der Organisation, keine Features mehr.
- **Wo:** laut Vorgabe vor Ort; Code: dieses Repo.
- **RE / Checkpoint:** Abgabe ist raus. Laptop bereit für den Pitch.
- **Fallback:** Etwas unfertig? Das Stabile zeigen und den Rest im Pitch ehrlich als nächsten Schritt benennen (Zukunft) — nicht so tun, als liefe es.
- **Kriterien:** alle — bewertet wird, was zuverlässig läuft und was du erklären kannst.

## Bewertungskriterien — wo sie im Plan sitzen

**Teil A — Idee**

| Kriterium | Wo du es erfüllst |
|---|---|
| Problem & Nutzen | Pitch-Einstieg, Demo-Flow, konkrete Empfehlung statt Liste |
| Originalität | Gesprächs-Agent (HAI) statt Kalender; Lücken-Ansicht |
| Machbarkeit & Zukunft | Kuratierter Bestand jetzt; später mehr Träger/APIs; Lücken steuern das Angebot |

**Teil B — Umsetzung**

| Kriterium | Wo du es erfüllst |
|---|---|
| Zuverlässigkeit | JSON-Bestand, lokale Demo, feste Szenarien, Deploy-Fallback |
| Verständnis der eigenen Lösung | README, Architektur, du kannst Retrieval und Prompt erklären |
| Teamwork | Solo: Provider-Kontakt, klare Doku und Architekturbild als Ausgleich |
| Dokumentation | README, dieser Plan, Datenschutz, Pitch, Demo-Szenarien |
| Technologie-Wahl | Cloudflare + JSON + optionales LLM, jeweils mit Fallback-Begründung |

## Wenn ein Wegpunkt reißt

Immer dasselbe: **Fallback des aktuellen Wegpunkts**, dann den nächsten beginnen. Nicht zwei Baustellen gleichzeitig aufmachen.

Priorität, falls Zeit brennt:

1. Echte Angebote plus ein funktionierender Dialog im Browser
2. README plus Pitch (So 11:00)
3. Lücken-Ansicht (auch statisch)
4. Embeddings, schönes UI, Cloudflare-Deploy
