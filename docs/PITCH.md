# Pitch-Gliederung — Lernlotse

Ziel: So 15.11.2026, 11:00 Europe/Berlin fertig (hart). Folien oder diese Karte als Vortrag. Jeder Block ist einem Kriterium zugeordnet.

Länge knapp halten. Was nicht zuverlässig läuft, nicht als laufend verkaufen.

Pflichtvorgaben und Don’ts: [ANFORDERUNGEN.md](ANFORDERUNGEN.md). Vor dem Pitch die Checkliste in der README durchgehen. Datenschutz und Löschkonzept: [DATENSCHUTZ.md](DATENSCHUTZ.md).

## Teil A — Idee

### 1. Problem und Nutzen

- Angebote in Heilbronn sind über Träger verstreut; Familien finden schlecht, was zu Alter, Interesse und Zeit passt.
- Nutzen: in einem kurzen Gespräch zu **einem** konkreten, echten Angebot mit Link kommen — und wiederkommen können, ohne mehrere Kalender zu durchsuchen.
- Live oder anhand eines Szenarios: Frage → Empfehlung → Link.

### 2. Originalität

- Kein Eventkalender und kein Filter-Dashboard.
- Human-Agent-Interface: der Agent klärt im Gespräch, was passt, und begründet die Empfehlung (Warum).
- Lücken-Ansicht: was junge Menschen suchen und was im Bestand fehlt — anonym, ohne Personenprofile.
- Abgrenzung: führt zu den Angeboten der Träger, nicht zu Inhalten des Autors.

### 3. Machbarkeit und Zukunft

- Jetzt: kuratierter, geprüfter Bestand (JSON), stabil in der Demo.
- Danach: mehr Träger, bessere Schnittstellen, Lücken-Signale (anonym) als Hinweis an die Bildungsakteure, wo Angebot fehlt.
- Ehrlich sagen, was in 12 Arbeitsstunden bewusst weggelassen wurde (z. B. Embeddings, Live-Scraping, Chat-Accounts).

## Teil B — Umsetzung

### 4. Zuverlässigkeit

- Daten liegen im Repo, nicht als Live-Crawl auf der Bühne.
- Feste Demo-Szenarien (`docs/demo-szenarien.md`).
- Fallback: lokale Demo, falls das Deploy hängt; Aufnahme als Backup.

### 5. Verständnis der eigenen Lösung

- Architektur aus dem README in einem Bild zeigen (UI → Worker → JSON / LLM).
- In einem Satz: wie Retrieval filtert, warum der Agent nichts erfindet, warum nichts gespeichert wird.
- Eine bewusste Grenze nennen.

### 6. Teamwork

- Solo-Projekt. Ausgleich: Kontakt zum Provider (Slot, Showcase So 10:00), nachvollziehbare Doku, klares Architekturbild.
- Feedback von aim, falls vorhanden, in einem Satz aufgreifen.

### 7. Dokumentation

- README (Starten, Status), dieser Pitch, `PLAN.md`, Datenschutz, Demo-Szenarien.
- Repo-Link nennen.

### 8. Technologie-Wahl

- Cloudflare Pages + Worker, JSON (gebündelt oder R2), LLM (Claude oder Workers AI), Filter vor optionalen Embeddings.
- Jede Wahl mit einem Warum und einem Fallback (siehe README-Tabelle).

## Abschluss

- Eine Empfehlung noch einmal zeigen.
- Ein Satz zur Lücke / zum nächsten Schritt.
- Stopp. Fragen.
