# worker/

Cloudflare Worker: nimmt Chat-Nachrichten plus Verlauf (nur im Request), prüft auf PII, extrahiert Alter / Interesse / Format, holt passende Einträge aus dem Angebots-JSON und antwortet mit Vorschlag, Link und Warum.

Noch kein laufender Code. Ziel-Checkpoint: **Sa 20:00**, lokal (`wrangler dev`). Pflicht bis **Sa 22:00**: PII-Filter sitzt vor jedem LLM-Aufruf.

Vorgaben aus [docs/ANFORDERUNGEN.md](../docs/ANFORDERUNGEN.md):

- Nur aus `data/offers.json` antworten (RAG, kein freier Chat).
- Verlauf und Alter/Interessen nur in der Sitzung, nichts persistieren.
- PII (Name, Adresse, Schule, Kontakt) vor dem Senden an das LLM entfernen oder die Anfrage ablehnen.
- System-Prompt: einfache, kurze Sätze; nur Themen AI, Coding, Gaming; KI nicht als Mensch ausgeben.
- Trägerliste aus `data/institutions.json` lesen, nicht im Code fest verdrahten.
- Altersgrenzen des LLM-Anbieters in `docs/DATENSCHUTZ.md` dokumentieren.

Fallback: kleiner lokaler HTTP-Server mit derselben Schnittstelle. LLM-Key fehlt oder AGB unklar → Retrieval plus eigene Satzbausteine.
