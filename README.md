# Lernlotse

Ein Gesprächs-Agent, der Familien in Heilbronn zu einem passenden Lernangebot lotst — nicht zu einem Katalog, sondern zu einem konkreten Angebot mit Link und kurzer Begründung.

Projekt für die aim-Challenge **Build a Learning Guide** beim Future City Hackathon 2026 (HHN TechCampus Heilbronn). Solo.

## Problem

Lernangebote in Heilbronn liegen verteilt bei mehreren Trägern. Familien müssen mehrere Kalender durchsuchen und wissen oft nicht, was zum Alter, zum Interesse und zur verfügbaren Zeit passt. Was junge Menschen suchen und was fehlt, wird kaum sichtbar.

## Lösung

Lernlotse führt ein kurzes Gespräch (Alter, Interesse, Format), sucht in einem kuratierten Bestand **echter** Angebote und empfiehlt ein passendes Angebot inkl. Link und einem Satz zum Warum (Nachvollziehbarkeit, Human-Agent-Interface).

Fokus-Träger: aim, experimenta, Haus der Familie, IPAI Foundation.
Fokus-Themen: AI, Coding, Gaming.

Zusätzlich eine Lücken-Ansicht: anonymisierte Nachfrage aus Gesprächs-Absichten im Vergleich zum vorhandenen Angebot — ohne Speicherung personenbezogener Daten.

Ideen und Designhaltung stammen aus [smlfg/agent](https://github.com/smlfg/agent) (Vision- und Design-Repo, keine lauffähige App). Der Agent führt zu den Angeboten der Träger, nicht zu persönlichen Inhalten des Autors.

Pflichtvorgaben der Challenge: [docs/ANFORDERUNGEN.md](docs/ANFORDERUNGEN.md).

## Demo-Flow

1. Einstieg: **„Für mich“** oder **„Für mein Kind“**. Sichtbares KI-Label: „Ich bin ein KI-Assistent und helfe dir, ein passendes Angebot zu finden.“
2. Alter: eigenes Alter oder Alter des Kindes (nur für die Sitzung, nicht speichern).
3. Interesse: Coding, Gaming oder KI.
4. Format: einmaliger Workshop oder regelmäßiger Kurs, grobe Verfügbarkeit.
5. Empfehlung nur aus dem Angebotsbestand: ein konkretes Angebot, Link zur Anmeldung, ein Satz warum es passt.
6. Teilen: Button „Dieses Angebot an Mama oder Papa weiterleiten“ (WhatsApp oder E-Mail, nur die Angebots-URL).
7. Optional: Alternativvorschlag oder ehrlicher Hinweis, wenn nichts passt (fließt in die Lücken-Ansicht).

## Architektur

```mermaid
flowchart LR
  A["Cloudflare Pages<br/>Chat-UI"] <--> B["Cloudflare Worker<br/>Gespräch + Retrieval"]
  B --> C["Angebote als JSON<br/>gebündelt oder R2"]
  B --> F["PII-Filter"]
  F --> D["LLM: Claude oder Workers AI"]
  C -.-> E["optional: Embeddings / Vectorize"]
  B --> G["institutions.json"]
```

In den ersten Stunden läuft alles lokal (`wrangler dev` oder ein lokaler Dev-Server). Ein Cloudflare-Deploy ist das Ziel, nicht die Voraussetzung für die Demo.

## Technik und warum

| Wahl | Warum | Fallback |
|---|---|---|
| Cloudflare Workers + Pages | Bekannter Stack, ein Deploy, wenig Betrieb | Lokal mit wrangler oder statischem HTML |
| Kuratiertes JSON statt Live-Scraping | Zuverlässigkeit auf der Bühne | — |
| Filter zuerst, Embeddings optional | In etwa 12 Arbeitsstunden tragfähig | Keyword- und Feldfilter reichen |
| Claude oder Workers AI | Gesprächsführung; Workers AI ohne extra Key möglich | Feste Satzbausteine plus Retrieval |
| Keine Chat-Persistenz, kein Login | Minderjährige / DSGVO, Pflicht der Challenge | Nur Sitzung; anonyme Zähler für die Lücken-Ansicht |
| `institutions.json` | Neue Träger ohne Code, Wartung durch Nicht-Techniker | — |
| PII-Filter vor dem LLM | Keine Kinderdaten an Drittanbieter | Anfrage ablehnen oder PII entfernen; ohne LLM: Satzbausteine |

## Daten und Datenschutz

Echte Angebote kommen nur aus öffentlich zugänglichen Angaben der vier Träger nach `data/offers.json`. Trägerliste: `data/institutions.json`. Keine erfundenen Termine oder Links. Jeder Import geht durch eine menschliche Prüfung (`data/README.md`).

Der Chat ist ohne Registrierung nutzbar, speichert keine Verläufe, keine Profile und keine Kontaktdaten (nur die laufende Sitzung). Eingaben werden auf PII geprüft, bevor sie an ein LLM gehen. Die Lücken-Ansicht nutzt höchstens anonyme Zähler (z. B. „Interesse Coding, Alter 8–12, kein Treffer“). Löschkonzept und Anbieter-AGB: [docs/DATENSCHUTZ.md](docs/DATENSCHUTZ.md).

## Starten

Dieses Repo ist gerade ein Gerüst. Sobald Daten, Worker und UI stehen:

```bash
python3 scripts/validate-offers.py

cd worker && npx wrangler dev
cd web && npm run dev
```

Die konkreten Befehle hier nachziehen, sobald der jeweilige Teil wirklich existiert. Geheimnisse gehören in `.dev.vars` oder `.env` (nicht committen). Vorlage: `.env.example`.

## Status

- [x] Repo-Gerüst, Plan, Schema (Sa 14.11.2026, ca. 13:35 Europe/Berlin)
- [x] Pflichtanforderungen, Löschkonzept, `institutions.json` (Sa 14.11.2026, ca. 13:50)
- [ ] Pitch-Slot bei aim (Sa 14:00)
- [ ] Mindestens 20 echte, geprüfte Angebote in `data/offers.json` (Sa 16:00)
- [ ] Filter/Retrieval: Testfrage liefert ein Angebot (Sa 18:00)
- [ ] Worker: Demo-Dialog lokal, RAG-only, Session-only, `institutions.json` nutzbar, Anbieter-AGB notiert (Sa 20:00)
- [ ] Chat-UI: Einstieg „Für mich / Für mein Kind“, KI-Label, PII-Filter, Eltern-Teilen, dann schlafen (Sa 22:00)
- [ ] 2–3 Demo-Szenarien, Lücken-Ansicht skizziert (So 08:00)
- [ ] Provider-Treffen ab 10:00, Demo steht (So 10:00)
- [ ] Pitch und README fertig, Checkliste vor dem Pitch gegangen (So 11:00, hart)
- [ ] Live-Test, Code auf `main` (So 12:30)
- [ ] Abgabe Präsentation + Code, Hacken stoppt (So 13:00)

Der verbindliche Zeitplan mit Wegpunkten, Checkpoints und Fallbacks steht in [PLAN.md](PLAN.md).

## Checkliste vor dem Pitch

Spätestens So 11:00 vorbereiten, So 12:30 abhaken. Details: [docs/ANFORDERUNGEN.md](docs/ANFORDERUNGEN.md).

- [ ] Angebote nur von aim, experimenta, Haus der Familie, IPAI Foundation.
- [ ] Themenfokus AI, Coding, Gaming.
- [ ] Interface für Kinder und Eltern erklärbar (Einstieg „Für mich / Für mein Kind“).
- [ ] Keine Selbstregistrierung für Minderjährige.
- [ ] Keine dauerhafte Speicherung von Chat, Profil oder Standort.
- [ ] KI als KI erkennbar.
- [ ] PII-Filter vor der LLM-Anfrage.
- [ ] Einfache Sprache, kurze Sätze.
- [ ] Datenquellen und Wartung dokumentiert (inkl. menschlicher Kontrolle).
- [ ] Skalierbarkeit durch JSON-Konfiguration gezeigt (`institutions.json`).
