#!/usr/bin/env python3
"""Prüft data/offers.json: Pflichtfelder, grobe Typen, keine Beispiel-Einträge."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OFFERS_PATH = ROOT / "data" / "offers.json"
REQUIRED = (
    "title",
    "institution",
    "topic",
    "age_min",
    "age_max",
    "format",
    "date",
    "location",
    "link",
    "description",
    "tags",
)
EXAMPLE_HINTS = ("example.com", "nicht-echt", "nicht verwenden")


def is_example(item: dict) -> bool:
    # "Beispiel" allein ist ein normales deutsches Wort ("zum Beispiel") und
    # kommt in echten Kursbeschreibungen vor. Platzhalter erkennt man am
    # Titelpräfix oder an den expliziten Markern.
    title = str(item.get("title", "")).strip().lower()
    if title.startswith("beispiel"):
        return True
    blob = " ".join(
        [
            str(item.get("link", "")),
            str(item.get("location", "")),
            str(item.get("description", "")),
            " ".join(str(t) for t in item.get("tags", []) if isinstance(item.get("tags"), list)),
        ]
    ).lower()
    return any(hint in blob for hint in EXAMPLE_HINTS)


def validate(items: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(items, list):
        return ["offers.json muss ein JSON-Array sein."]

    for index, item in enumerate(items):
        prefix = f"Eintrag {index}"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: muss ein Objekt sein.")
            continue
        missing = [key for key in REQUIRED if key not in item]
        if missing:
            errors.append(f"{prefix}: Pflichtfelder fehlen: {', '.join(missing)}")
        for key in ("title", "institution", "topic", "format", "location", "link", "description"):
            value = item.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}: '{key}' muss eine nicht-leere Zeichenkette sein.")
        link = item.get("link")
        if isinstance(link, str) and link.strip() and not link.startswith(("http://", "https://")):
            errors.append(f"{prefix}: 'link' muss mit http:// oder https:// beginnen.")
        for key in ("age_min", "age_max"):
            value = item.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"{prefix}: '{key}' muss eine ganze Zahl >= 0 sein.")
        if (
            isinstance(item.get("age_min"), int)
            and isinstance(item.get("age_max"), int)
            and not isinstance(item.get("age_min"), bool)
            and not isinstance(item.get("age_max"), bool)
            and item["age_min"] > item["age_max"]
        ):
            errors.append(f"{prefix}: age_min darf nicht größer als age_max sein.")
        date = item.get("date")
        if date is not None and (not isinstance(date, str) or not date.strip()):
            errors.append(f"{prefix}: 'date' muss eine nicht-leere Zeichenkette oder null sein.")
        tags = item.get("tags")
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            errors.append(f"{prefix}: 'tags' muss ein Array nicht-leerer Zeichenketten sein.")
        extra = sorted(set(item) - set(REQUIRED))
        if extra:
            errors.append(f"{prefix}: unbekannte Felder: {', '.join(extra)}")
        if is_example(item):
            errors.append(
                f"{prefix}: sieht nach Beispiel-/Platzhalterdaten aus. "
                "Nur echte Angebote gehören in offers.json (siehe offers.example.json)."
            )
    return errors


def main() -> int:
    if not OFFERS_PATH.exists():
        print(f"Fehlt: {OFFERS_PATH}", file=sys.stderr)
        return 1
    try:
        items = json.loads(OFFERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Ungültiges JSON in {OFFERS_PATH}: {exc}", file=sys.stderr)
        return 1

    errors = validate(items)
    count = len(items) if isinstance(items, list) else 0
    if errors:
        print(f"{OFFERS_PATH}: {count} Einträge, {len(errors)} Fehler.")
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if count == 0:
        print(f"{OFFERS_PATH}: gültig, aber noch leer (0 Angebote). Checkpoint Sa 16:00 braucht mindestens 20 echte Einträge.")
        return 0

    note = ""
    if count < 20:
        note = f" Warnung: Checkpoint Sa 16:00 verlangt mindestens 20, aktuell {count}."
    print(f"{OFFERS_PATH}: {count} Einträge, Prüfung bestanden.{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
