#!/usr/bin/env python3
"""Exportiert den kuratierten Bestand (data/angebote.json) in das Projekt-Schema
data/offers.json, das scripts/validate-offers.py prüft.

Die Abbildung ist bewusst konservativ:
- age_min/age_max sind Pflichtzahlen. Fehlt eine Altersangabe in der Quelle,
  wird sie aus der Zielgruppe abgeleitet und mit dem Tag "alter-geschaetzt"
  markiert. Es werden keine Termine oder Preise erfunden.
- date ist das Startdatum des ersten Termins, "laufend" bei laufenden Formaten
  oder null, wenn kein Termin bekannt ist.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "angebote.json"
DST = ROOT / "data" / "offers.json"

TOPIC_ORDER = [
    ("KI", "AI"),
    ("Coding", "Coding"),
    ("Gaming", "Gaming"),
    ("Robotik", "Robotik"),
    ("Daten", "Daten"),
    ("MINT", "MINT"),
    ("Medienkompetenz", "Medien"),
    ("Kreativität", "Kreativ"),
    ("Astronomie", "MINT"),
    ("Ferien", "Ferien"),
    ("Berufsorientierung", "Beruf"),
    ("Allgemein", "Allgemein"),
]

FORMATS = {
    "kurs": "Kurs",
    "workshop": "Workshop",
    "vortrag": "Vortrag",
    "show": "Show",
    "event": "Event",
    "ferienbetreuung": "Ferienbetreuung",
    "laborkurs": "Laborkurs",
    "ausstellung": "Ausstellung",
    "fuehrung": "Führung",
    "fortbildung": "Fortbildung",
    "wettbewerb": "Wettbewerb",
    "programm": "Programm",
    "festival": "Festival",
    "offenes angebot": "Offenes Angebot",
    "event-format": "Event",
    "workshop-format": "Workshop",
    "vortrag-format": "Vortrag",
}

INSTITUTIONS = {
    "aim": "aim",
    "experimenta": "experimenta",
    "hdf": "Haus der Familie",
    "ipai": "IPAI Foundation",
}

TAG_SLUG = {
    "KI": "ai",
    "Coding": "coding",
    "Gaming": "gaming",
    "Robotik": "robotik",
    "Daten": "daten",
    "MINT": "mint",
    "Medienkompetenz": "medien",
    "Kreativität": "kreativ",
    "Astronomie": "astronomie",
    "Ferien": "ferien",
    "Berufsorientierung": "beruf",
    "Allgemein": "allgemein",
}


def pick_topic(item: dict) -> str:
    topics = item.get("topics") or []
    for source, target in TOPIC_ORDER:
        if source in topics:
            return target
    return "Allgemein"


def fallback_age(item: dict) -> tuple[int, int, bool]:
    lo, hi = item.get("age_min"), item.get("age_max")
    if isinstance(lo, int) and isinstance(hi, int) and lo <= hi:
        return lo, hi, False
    audience = item.get("audience") or []
    if isinstance(lo, int):
        return lo, 99, False
    if "kinder" in audience or "jugendliche" in audience:
        return 6, 17, True
    if "lehrkraefte" in audience:
        return 18, 99, True
    if "eltern" in audience or "erwachsene" in audience:
        return 18, 99, True
    return 0, 99, True


def pick_date(item: dict) -> str | None:
    dates = item.get("dates") or []
    if dates and dates[0].get("start"):
        return dates[0]["start"][:10]
    if item.get("type") in {"laborkurs", "kurs", "workshop", "fortbildung"}:
        return None
    if item.get("type") in {"ausstellung", "programm", "festival", "event-format", "workshop-format", "vortrag-format"}:
        return "laufend"
    return None


def make_tags(item: dict, age_estimated: bool) -> list[str]:
    tags = []
    for topic in item.get("topics") or []:
        slug = TAG_SLUG.get(topic)
        if slug and slug not in tags:
            tags.append(slug)
    for group in item.get("audience") or []:
        if group not in tags:
            tags.append(group)
    price = item.get("price") or {}
    if price.get("amount") == 0 and "kostenlos" not in tags:
        tags.append("kostenlos")
    status = ((item.get("registration") or {}).get("status") or "").lower()
    if "ausgebucht" in status:
        tags.append("ausgebucht")
    dates = item.get("dates") or []
    if dates and dates[0].get("start"):
        try:
            import datetime
            weekday = datetime.date.fromisoformat(dates[0]["start"][:10]).weekday()
            if weekday >= 5:
                tags.append("wochenende")
        except ValueError:
            pass
    if age_estimated:
        tags.append("alter-geschaetzt")
    return tags[:10]


def convert(item: dict) -> dict:
    age_min, age_max, estimated = fallback_age(item)
    location = item.get("location") or {}
    city = (location.get("city") or "").strip()
    name = (location.get("name") or "").strip()
    if city.lower() == "online":
        place = "online"
    elif name and city:
        place = f"{name}, {city}"
    else:
        place = name or city or "Heilbronn"
    return {
        "title": item["title"],
        "institution": INSTITUTIONS[item["provider"]],
        "topic": pick_topic(item),
        "age_min": age_min,
        "age_max": age_max,
        "format": FORMATS.get(item["type"], item["type"]),
        "date": pick_date(item),
        "location": place,
        "link": item["url"],
        "description": item["description"],
        "tags": make_tags(item, estimated),
    }


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    offers = [convert(item) for item in data["offers"]]
    DST.write_text(json.dumps(offers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    estimated = sum(1 for o in offers if "alter-geschaetzt" in o["tags"])
    print(f"{DST.relative_to(ROOT)}: {len(offers)} Angebote geschrieben, davon {estimated} mit geschätztem Alter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
