# worker/

Cloudflare Worker: nimmt Chat-Nachrichten plus Verlauf (nur im Request), extrahiert Alter / Interesse / Format, holt passende Einträge aus dem Angebots-JSON und antwortet mit Vorschlag, Link und Warum.

Noch kein laufender Code. Ziel-Checkpoint: **Sa 20:00**, lokal (`wrangler dev`).

Fallback: kleiner lokaler HTTP-Server mit derselben Schnittstelle, falls Cloudflare in der Zeit nicht sitzt. Keine Persistenz von Verläufen oder Personenangaben.

Datenquelle: `data/offers.json` (gebündelt oder später R2). LLM: Claude oder Workers AI; ohne Key erst Retrieval plus Satzbausteine.
