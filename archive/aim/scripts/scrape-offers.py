#!/usr/bin/env python3
"""Platzhalter. Nicht als Produktionscrawler gedacht."""

import sys

MESSAGE = """
Lernlotse — Scraping-Platzhalter
================================
Dieses Skript sammelt noch keine Angebote.

Regel: maximal 30 Minuten für Automatisierung. Läuft in dieser Zeit nichts
Sauberes, abbrechen und Angebote von den offiziellen Seiten der Träger
per Hand in data/offers.json eintragen.

Träger (Fokus): aim, experimenta, Haus der Familie, IPAI Foundation.
Nur geprüfte, öffentliche Angaben. Nichts erfinden, keine Beispiel-URLs.

Danach: python3 scripts/validate-offers.py
"""

def main() -> int:
    print(MESSAGE.strip())
    return 2

if __name__ == "__main__":
    sys.exit(main())
