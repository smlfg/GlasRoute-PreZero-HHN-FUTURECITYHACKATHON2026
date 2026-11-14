# web/

Eine Seite: Chat-UI, an den Worker angebunden. Hosting-Ziel: Cloudflare Pages.

Noch kein laufender Code. Ziel-Checkpoint: **Sa 22:00**, dann schlafen.

Pflicht in der Oberfläche (siehe [docs/ANFORDERUNGEN.md](../docs/ANFORDERUNGEN.md)):

- Einstieg **„Für mich / Für mein Kind“**.
- KI-Label sofort sichtbar: „Ich bin ein KI-Assistent und helfe dir, ein passendes Angebot zu finden.“
- Einfache Sprache, kurze Sätze, große serifenlose Schrift, Icons zusätzlich zum Text.
- Mobile-first, ohne Registrierung, kein Login, keine Favoriten- oder Verlaufsspeicherung.
- Nach einer Empfehlung: Button **„Dieses Angebot an Mama oder Papa weiterleiten“** (WhatsApp- oder E-Mail-Link nur mit der Angebots-URL, ohne Kinderdaten).

RE: Im Browser Einstieg wählen, sichtbares KI-Label, eine Frage stellen, ein Angebot mit Link und Teilen-Button sehen.

Fallback: eine einzige `index.html`. Deploy kann auf Sonntag warten.
