#!/usr/bin/env python3
"""Baut data/angebote.json: 200 reale Angebote aus aim, experimenta, Haus der Familie und IPAI.

Quellen (Abruf 2026-11-14):
- aim: Kurslisten + Detailseiten auf aim-akademie.org
- experimenta: Veranstaltungskalender + Laborkurs-Buchungsshop
- Haus der Familie: Kurs-API hdf-hn.de/kufer-api.php (Kursdatenbank)
- IPAI Foundation: Website/Eventseiten

Die Auswahl ist manuell kuratiert (KNr-/Titel-Listen), die Feldwerte stammen
aus den Quellseiten. Jeder Datensatz nennt seine Quell-URL.
"""
import json, re, html, datetime, unicodedata, os

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angebote.json")
TODAY = "2026-11-14"
RETRIEVED = "2026-11-14"

PROVIDERS = {
    "aim": {
        "name": "aim – Akademie für Innovative Bildung und Management Heilbronn-Franken",
        "short": "aim",
        "url": "https://www.aim-akademie.org/",
    },
    "experimenta": {
        "name": "experimenta gGmbH – Science Center Heilbronn",
        "short": "experimenta",
        "url": "https://www.experimenta.science/",
    },
    "hdf": {
        "name": "Haus der Familie Heilbronn",
        "short": "Haus der Familie",
        "url": "https://hdf-hn.de/",
    },
    "ipai": {
        "name": "IPAI Foundation gGmbH",
        "short": "IPAI",
        "url": "https://ipai-foundation.ai/",
    },
}


def clean(s, limit=None):
    if not s:
        return ""
    s = html.unescape(str(s))
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if limit and len(s) > limit:
        cut = s[:limit]
        p = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        s = (cut[:p + 1] if p > limit * 0.55 else cut.rsplit(" ", 1)[0]) + " …"
    return s


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:60]


def auto_topics(title, desc, base=None):
    t = (title + " " + desc).lower()
    topics = list(base or [])
    rules = [
        ("KI", r"künstliche intelligenz|\bki\b|ki-|deepfake|chatgpt|claude|generative|algorithm"),
        ("Coding", r"programmier|coding|\bcode\b|scratch|python|\bunity\b|javascript|html|css|mikrocontroller|webentwicklung|informatik|server|internet of things|\biot\b"),
        ("Gaming", r"videospiel|spieleentwicklung|spielewelt|game-?design|game-?based|gaming|\bgames?\b(?!\s*-?\s*changer)|\bunity\b|minecraft|fortnite|among us|pokémon"),
        ("Robotik", r"roboter|robotik|lego|\bpib\b"),
        ("Daten", r"datenanalyse|datenbank|data literacy|power bi|statistik|daten"),
        ("MINT", r"mint|mathe|physik|chemie|biologie|technik|elektronik|löten|strom|magnet|energie|optik|naturwissenschaft|forscher|experiment"),
        ("Medienkompetenz", r"medien|social media|influencer|smartphone|digital|deepfake|fake|desinformation"),
        ("Kreativität", r"kreativ|kunst|bastel|theater|musik|literatur|märchen|vorlesen|film|foto"),
        ("Ferien", r"ferien"),
        ("Berufsorientierung", r"beruf|ausbildung|bewerbung|studium"),
    ]
    for name, pat in rules:
        if re.search(pat, t) and name not in topics:
            topics.append(name)
    return topics[:4] or ["Allgemein"]


def focus_flag(topics):
    return bool({"KI", "Coding", "Gaming"} & set(topics))


def termine(n):
    return f"{n} Termin" if n == 1 else f"{n} Termine"


# ---------------------------------------------------------------- aim
aim_raw = json.load(open(f"{RAW}/aim_raw.json"))
AIM_KEEP = set([x["knr"] for x in aim_raw[:35]]) | {
    "26293MOS", "271932EU", "271931EU", "271931", "271932",
    "262993CHNB", "271993MGPB", "271993JKIT", "271993XQP", "271991ARHL",
    "271993JLMM", "271992TZPC", "271993KIEK", "271993JKCK", "272995JSVS",
    "262993JLKK", "271993SDMO", "271993AOGD", "271993JGCS", "271993CSSM",
}

AIM_TYPES = [
    (r"Kinderuni|Elternuni", "vortrag"),
    (r"Juniorakademie", "kurs"),
    (r"Zukunftswerkstatt|Round Table", "workshop"),
    (r"KI-Orientierung|Deepfakes|Im Sog der Likes|Was spielst du", "vortrag"),
]

def aim_type(x):
    for pat, typ in AIM_TYPES:
        if re.search(pat, x["title"]):
            return typ
    return "kurs" if len(x["dates"]) > 1 else "workshop"


def parse_age_aim(x):
    blob = x["detail_title"] + " " + x["participants_text"]
    m = re.search(r"(\d{1,2})\s*[–-]\s*(\d{1,2})\s*Jahr", blob)
    if m:
        return int(m.group(1)), int(m.group(2)), f"{m.group(1)}–{m.group(2)} Jahre"
    m = re.search(r"ab\s+(\d{1,2})\s+bis\s+(\d{1,2})\s*Jahr", blob)
    if m:
        return int(m.group(1)), int(m.group(2)), f"{m.group(1)}–{m.group(2)} Jahre"
    m = re.search(r"\bab\s+(\d{1,2})\s*Jahr", blob)
    if m:
        return int(m.group(1)), None, f"ab {m.group(1)} Jahren"
    m = re.search(r"zwischen\s+(\d{1,2})\s+und\s+(\d{1,2})\s+Jahren", blob)
    if m:
        return int(m.group(1)), int(m.group(2)), f"{m.group(1)}–{m.group(2)} Jahre"
    m = re.search(r"\(Kl\.?\s*(\d{1,2})\s*[-–]\s*(\d{1,2})\)", blob)
    if m:
        lo = int(m.group(1)) + 5
        hi = int(m.group(2)) + 6
        return lo, hi, f"Klasse {m.group(1)}–{m.group(2)}"
    return None, None, ""


def aim_audience(x, age_min=None):
    tg = " ".join(x["target_groups"])
    out = []
    if "Schüler" in tg or "Juniorstudierende" in tg:
        if age_min is not None and age_min >= 10:
            out.append("jugendliche")
        else:
            out += ["kinder", "jugendliche"]
    if "Eltern" in tg:
        out.append("eltern")
    if "Lehrkraft" in tg or "Schulleitung" in tg or "Referendar" in tg or "Ganztages" in tg or "Schulsozial" in tg:
        out.append("lehrkraefte")
    if "Interessierte" in tg or "Studierende" in tg or "Auszubildende" in tg:
        out.append("erwachsene")
    return list(dict.fromkeys(out)) or ["erwachsene"]


def iso_from_de(d, t):
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", d or "")
    if not m:
        return None, None
    day, mon, year = m.groups()
    tm = re.search(r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})", t or "")
    if tm:
        h1, m1, h2, m2 = tm.groups()
        start = f"{year}-{mon}-{day}T{int(h1):02d}:{m1}"
        end = f"{year}-{mon}-{day}T{int(h2):02d}:{m2}"
    else:
        start, end = f"{year}-{mon}-{day}", None
    return start, end


aim_offers = []
for x in aim_raw:
    if x["knr"] not in AIM_KEEP:
        continue
    age_min, age_max, age_text = parse_age_aim(x)
    dates = []
    for d in x["dates"]:
        if not re.search(r"\d{1,2}:\d{2}", d["time"] or ""):
            continue
        s, e = iso_from_de(d["date"], d["time"])
        if s and s[:10] >= TODAY:
            dates.append({"start": s, "end": e,
                          "text": f"{d['date']}, {d['time'].replace(' - ', '–').replace(' Uhr','')}"})
    desc_clean = clean(x["description"], 1800)
    if "THEMENBEREICH" in desc_clean:
        desc_clean = desc_clean[desc_clean.index("THEMENBEREICH"):]
    desc_clean = clean(desc_clean, 900)
    topics = auto_topics(x["detail_title"], desc_clean)
    city = "Heilbronn"
    if "Online" in x["location"] or "Online" in x["address"]:
        city = "online"
    elif "Mosbach" in x["location"] or "Mosbach" in x["address"]:
        city = "Mosbach"
    loc = x["address"] or (x["location"] + (", Heilbronn" if city == "Heilbronn" else ""))
    aim_offers.append({
        "id": f"aim-{x['knr']}",
        "provider": "aim",
        "provider_name": PROVIDERS["aim"]["name"],
        "title": x["detail_title"],
        "subtitle": "",
        "description": desc_clean,
        "type": aim_type(x),
        "topics": topics,
        "focus_ai_coding_gaming": focus_flag(topics),
        "audience": aim_audience(x, age_min),
        "age_min": age_min,
        "age_max": age_max,
        "age_text": age_text,
        "dates": dates,
        "duration_text": (termine(len(dates)) if dates else "nach Ankündigung"),
        "location": {"name": x["location"], "address": loc, "city": city},
        "price": {"amount": 0, "currency": "EUR", "text": "kostenlos"},
        "registration": {"url": x["url"], "status": x["status"] or "siehe Quelle"},
        "url": x["url"],
        "source_url": x["url"],
        "retrieved_at": RETRIEVED,
        "collection": "manuell kuratiert",
    })

# ---------------------------------------------------------------- Haus der Familie
hdf_all = json.load(open(f"{RAW}/hdfall.json"))
HDF_DROP = {"261H207016", "261H207017", "261H302018", "261H302020",
            "261H305004", "261H305011", "261H305002", "261H305054"}

def hdf_selected():
    def has(x, cat): return cat in (x["kategorien"] or {}).values()
    def theme(x, t): return t in (x["themen"] or {}).values()
    sel = [x for x in hdf_all
           if has(x, "Schulkinder & Jugendliche (ab 6 Jahren)")
           or theme(x, "Digitale Familienwerkstatt") or theme(x, "MINT")]
    sel = [x for x in sel if x["knr"] not in HDF_DROP]
    return sorted(sel, key=lambda x: (x["beginndat"], x["haupttitel"]))


def hdf_age(x):
    cats = list((x["kategorien"] or {}).values())
    ages = []
    for c in cats:
        if "Baby" in c: ages.append((0, 1))
        elif "Kleinkind" in c: ages.append((1, 3))
        elif "Kindergarten" in c: ages.append((3, 6))
        elif "Schulkinder" in c: ages.append((6, 17))
    sub = (x["hauptuntertitel"] or "") + " " + (x["web_info"] or "")[:200]
    m = re.search(r"ab\s+(\d{1,2})\s+Jahr", sub)
    m2 = re.search(r"(\d{1,2})\s+bis\s+(\d{1,2})\s+Jahr", sub)
    if m2:
        lo, hi = int(m2.group(1)), int(m2.group(2))
        return lo, hi, f"{lo}–{hi} Jahre"
    if m:
        lo = int(m.group(1))
        return lo, None, f"ab {lo} Jahren"
    if not ages:
        return None, None, ""
    lo = min(a for a, b in ages); hi = max(b for a, b in ages)
    return lo, hi, (f"{lo}–{hi} Jahre" if lo != hi else f"{lo} Jahre")


def hdf_audience(x):
    cats = " ".join((x["kategorien"] or {}).values())
    out = []
    if "Schulkinder" in cats or "Kindergarten" in cats: out += ["kinder", "jugendliche"]
    if "Baby" in cats or "Kleinkind" in cats: out.append("familien")
    if "Eltern" in cats or "Väter" in cats or "Großeltern" in cats: out.append("eltern")
    if "Frauen" in cats or "Paare" in cats: out.append("erwachsene")
    return list(dict.fromkeys(out)) or ["familien"]


def hdf_type(x):
    txt = (x["kurstyp"] or "") + " " + " ".join((x["themen"] or {}).values())
    if "Ferienbetreuung" in txt: return "ferienbetreuung"
    if "Vortrag" in txt: return "vortrag"
    if "offene" in txt: return "offenes angebot"
    if "Workshop" in x["hauptuntertitel"]: return "workshop"
    return "kurs"


def hdf_price(x):
    fees = x["gebuehren"] or []
    total = sum(float(f.get("betragnorm") or 0) for f in fees)
    extras = [f["text"] for f in fees if f.get("text") and f["text"] not in ("€", "Gebühr", "")]
    txt = "kostenlos" if total == 0 else f"{total:.2f} €".replace(".", ",")
    if extras:
        txt += " (" + ", ".join(sorted(set(extras))) + ")"
    return {"amount": round(total, 2), "currency": "EUR", "text": txt}


hdf_offers = []
for x in hdf_selected():
    lo, hi, at = hdf_age(x)
    dates = []
    for t in x["termine"] or []:
        s = f"{t['tag']}T{t['zeitvon'][:5]}"
        e = f"{t['tag']}T{t['zeitbis'][:5]}" if t.get("zeitbis") else None
        parts = t["tag"].split("-")
        de = f"{parts[2]}.{parts[1]}.{parts[0]}"
        dates.append({"start": s, "end": e, "text": f"{de}, {t['zeitvon'][:5]}–{t['zeitbis'][:5]}"})
    desc = x["web_info"] or x["inhalt"]
    desc_clean = clean(desc, 900)
    topics = auto_topics(x["haupttitel"] + " " + (x["hauptuntertitel"] or ""), desc_clean,
                         base=[v for v in (x["themen"] or {}).values() if v in ("MINT", "Digitale Familienwerkstatt")])
    topics = ["MINT" if t == "MINT" else ("Medienkompetenz" if t == "Digitale Familienwerkstatt" else t) for t in topics]
    tn, tmax = int(x["tnanmeldungen"] or 0), int(x["tnmax"] or 0)
    status = "ausgebucht" if tmax and tn >= tmax else "freie Plätze"
    hdf_offers.append({
        "id": f"hdf-{x['knr']}",
        "provider": "hdf",
        "provider_name": PROVIDERS["hdf"]["name"],
        "title": x["haupttitel"].strip(),
        "subtitle": clean(x["hauptuntertitel"], 120),
        "description": desc_clean,
        "type": hdf_type(x),
        "topics": list(dict.fromkeys(topics)),
        "focus_ai_coding_gaming": focus_flag(topics),
        "audience": hdf_audience(x),
        "age_min": lo,
        "age_max": hi,
        "age_text": at,
        "dates": dates,
        "duration_text": termine(len(dates)) if dates else "siehe Quelle",
        "location": {"name": x["ortraumname"] or x["ort"], "address": x["ort"], "city": x["ortname"] or "Heilbronn"},
        "price": hdf_price(x),
        "registration": {"url": f"https://hdf-hn.de/kurs/{x['knr']}/", "status": status},
        "url": f"https://hdf-hn.de/kurs/{x['knr']}/",
        "source_url": "https://hdf-hn.de/kurse/",
        "retrieved_at": RETRIEVED,
        "collection": "manuell kuratiert",
    })

# ---------------------------------------------------------------- experimenta
exp_events = json.load(open(f"{RAW}/exp_cal.json"))
exp_labs = json.load(open(f"{RAW}/exp_labs.json"))
exp_aud = json.load(open(f"{RAW}/exp_labs_aud.json"))

EXP_LAB_KEEP = [
    "Kleiner Roboter auf großer Reise",
    "Mikrocontroller-Programmierung",
    "Programmier-Werkstatt",
    "Mission to Mars: Robotik Fortgeschrittenenkurs",
    "Kombiangebot: Programmier-Werkstatt + 42",
    "Roboter auf Mission: Robotik Basiskurs",
    "Produktentwicklung mit CAD – Entwirf deinen Handyhalter!",
    "Bau eines Solarmobils",
    "Bau eines Elektromotors",
    "Löten einer Blinkschaltung",
    "Bau einer Kurbeltaschenlampe: Licht durch Bewegung",
    "Unter Strom!",
    "Energie und Energieumwandlung",
    "Grundlagen der Elektrizität",
    "Weltreise einer Jeans: GIS & Globalisierung",
    "Karten lesen lernen: Orientierung mit digitalen Globen",
    "Mathematik sofort kapiert",
    "Optikdetektive",
    "Kleine Gummibärenfabrik",
    "Materialiencheck: Kunststoff, Papier und Recycling",
]

EXP_GROUPS_DE = {
    "familien": "Familien", "ab-6-jahren": "ab 6 Jahren", "ab-8-jahren": "ab 8 Jahren",
    "ab-10-jahren": "ab 10 Jahren", "ab-14-jahren": "ab 14 Jahren",
    "jugendliche": "Jugendliche", "erwachsene": "Erwachsene",
    "grundschule": "Grundschule", "5-10-klasse": "Klasse 5–10",
    "8-10-klasse": "Klasse 8–10", "11-13-klasse": "Klasse 11–13",
    "schulkinder": "Schulkinder", "eltern": "Eltern",
}

def exp_event_type(groups):
    if "science-dome-shows" in groups or "science-dome-special" in groups: return "show"
    if "workshop" in groups or "experimentierkueche" in groups: return "workshop"
    if "fortbildung" in groups: return "fortbildung"
    if "wettbewerbe" in groups: return "wettbewerb"
    if "vortrag" in groups or "robert-mayer-lecture" in groups: return "vortrag"
    return "event"


def exp_event_age(groups):
    for g in groups:
        m = re.match(r"ab-(\d+)-jahren", g)
        if m:
            return int(m.group(1)), None, f"ab {m.group(1)} Jahren"
    if "grundschule" in groups:
        return 6, 10, "Klasse 1–4"
    for g, lo, hi in [("5-10-klasse", 10, 16), ("8-10-klasse", 13, 16), ("11-13-klasse", 16, 19)]:
        if g in groups:
            return lo, hi, f"Klasse {g.replace('-klasse','').replace('-','–')}"
    if "jugendliche" in groups:
        return 12, 18, "Jugendliche"
    return None, None, ""


def exp_subtitle(groups):
    labels = [EXP_GROUPS_DE[g] for g in groups if g in EXP_GROUPS_DE][:3]
    return ", ".join(labels)


exp_offers = []
for e in exp_events:
    groups = e["categories"]
    dates = []
    for d in e["dates"]:
        if not d.get("start_unix"):
            continue
        dt = datetime.datetime.fromtimestamp(d["start_unix"])
        start = dt.strftime("%Y-%m-%dT%H:%M")
        end = None
        tm = re.search(r"(\d{1,2}):(\d{2})\s*(?:bis|–|-)\s*(\d{1,2}):(\d{2})", d.get("time") or "")
        if tm and d.get("day"):
            h1, m1, h2, m2 = tm.groups()
            day = dt.strftime("%Y-%m-%d")
            start = f"{day}T{int(h1):02d}:{m1}"
            end = f"{day}T{int(h2):02d}:{m2}"
        txt = f"{dt.strftime('%d.%m.%Y')}"
        if tm:
            txt += f", {int(tm.group(1)):02d}:{tm.group(2)}–{int(tm.group(3)):02d}:{tm.group(4)}"
        dates.append({"start": start, "end": end, "text": txt})
    lo, hi, at = exp_event_age(groups)
    topics = auto_topics(e["title"], e["description"], base=["MINT"])
    if "science-dome" in " ".join(groups):
        topics = list(dict.fromkeys(["MINT", "Astronomie"] + topics))[:4]
    desc = e["description"]
    sold_out = "ausgebucht" in desc.lower()
    desc = re.sub(r"\*\*\*.*?ausgebucht.*?\*\*\*", "", desc, flags=re.I).strip()
    desc_clean = clean(desc, 900)
    exp_offers.append({
        "id": "exp-event-" + slug(e["title"]),
        "provider": "experimenta",
        "provider_name": PROVIDERS["experimenta"]["name"],
        "title": e["title"],
        "subtitle": exp_subtitle(groups),
        "description": desc_clean,
        "type": exp_event_type(groups),
        "topics": topics,
        "focus_ai_coding_gaming": focus_flag(topics),
        "audience": ["familien"] if "familien" in groups else (["jugendliche"] if "jugendliche" in groups else ["erwachsene"]),
        "age_min": lo,
        "age_max": hi,
        "age_text": at,
        "dates": dates,
        "duration_text": termine(len(dates)),
        "location": {"name": "experimenta", "address": "Experimenta-Platz, 74072 Heilbronn", "city": "Heilbronn"},
        "price": {"amount": None, "currency": "EUR", "text": "Ticket/Anmeldung über experimenta"},
        "registration": {"url": e["url"], "status": "ausgebucht" if sold_out else "Anmeldung erforderlich"},
        "url": e["url"],
        "source_url": "https://www.experimenta.science/besuchen/veranstaltungen/",
        "retrieved_at": RETRIEVED,
        "collection": "manuell kuratiert",
    })

labs_by_title = {l["t"]: l for l in exp_labs}
for title in EXP_LAB_KEEP:
    l = labs_by_title.get(title)
    if not l:
        raise SystemExit("Lab nicht gefunden: " + title)
    auds = [k for k, v in exp_aud.items() if title in v]
    if "Kindergarten" in auds:
        lo, hi, at = 3, 6, "3–6 Jahre (Kindergarten)"
        audience = ["kinder", "lehrkraefte"]
    elif "Grundschule" in auds:
        lo, hi, at = 6, 10, "Klasse 1–4"
        audience = ["kinder", "lehrkraefte"]
    elif auds:
        lo, hi, at = 10, 18, "Klasse 5–13"
        audience = ["jugendliche", "lehrkraefte"]
    else:
        lo, hi, at = None, None, ""
        audience = ["lehrkraefte"]
    topics = auto_topics(title, l["d"], base=["MINT"])
    exp_offers.append({
        "id": "exp-lab-" + slug(title),
        "provider": "experimenta",
        "provider_name": PROVIDERS["experimenta"]["name"],
        "title": title,
        "subtitle": "Laborkurs für Gruppen",
        "description": clean(l["d"], 900),
        "type": "laborkurs",
        "topics": topics,
        "focus_ai_coding_gaming": focus_flag(topics),
        "audience": audience,
        "age_min": lo,
        "age_max": hi,
        "age_text": at,
        "dates": [],
        "duration_text": clean(l["du"], 60),
        "location": {"name": "experimenta Labore", "address": "Experimenta-Platz, 74072 Heilbronn", "city": "Heilbronn"},
        "price": {"amount": None, "currency": "EUR", "text": "Gruppenbuchung, Preis auf Anfrage"},
        "registration": {"url": "https://buchung.experimenta.science/ticket-web-shop/Labs/Lab", "status": "Buchung nach Vereinbarung"},
        "url": "https://buchung.experimenta.science/ticket-web-shop/Labs/Lab",
        "source_url": "https://buchung.experimenta.science/ticket-web-shop/Labs/Lab?dateNext=21d",
        "retrieved_at": RETRIEVED,
        "collection": "manuell kuratiert",
    })

# ---------------------------------------------------------------- IPAI
IPAI_LOC = {"name": "IPAI Spaces", "address": "Im Zukunftspark 11/13, 74076 Heilbronn", "city": "Heilbronn"}
IPAI = [
    dict(id="ipai-living-room", title="IPAI Living Room – Besucherzentrum",
         subtitle="Interaktive KI-Ausstellung, AI Demo Space, Education Space",
         desc="Das IPAI-Wohnzimmer ist das öffentliche KI-Besucherzentrum in den IPAI SPACES: interaktive Exponate, Kunst-Installationen, Anwendungen von Unternehmen, ein Rennen gegen eine KI und der Blick auf den entstehenden IPAI CAMPUS. Eintritt kostenlos, montags bis freitags 9–17 Uhr.",
         type="ausstellung", topics=["KI", "Medienkompetenz"], audience=["familien", "kinder", "jugendliche", "erwachsene"],
         age_min=None, age_max=None, age_text="alle Altersgruppen",
         dates=[], duration="laufend, Mo–Fr 9–17 Uhr", price=0, price_text="Eintritt kostenlos",
         status="offen", url="https://ipai-foundation.ai/besucherzentrum/"),
    dict(id="ipai-fuehrungen", title="Kostenlose Führungen durch den IPAI Living Room",
         subtitle="Jeden Dienstag und Donnerstag, 10 und 14 Uhr",
         desc="Offene Führungen durch das Besucherzentrum mit Erläuterungen zu den Exponaten und zur KI in Heilbronn. Für individuelle Gruppenführungen kann ein Termin per E-Mail an guidedtours@ipai-foundation.ai vereinbart werden.",
         type="fuehrung", topics=["KI"], audience=["familien", "erwachsene", "jugendliche"],
         age_min=None, age_max=None, age_text="alle Altersgruppen",
         dates=[], duration="ca. 60 Minuten", price=0, price_text="kostenlos",
         status="offen", url="https://ipai-foundation.ai/besucherzentrum/"),
    dict(id="ipai-living-room-session-10", title="Living Room Session #10: Women in AI / Women in Robotics",
         subtitle="Couch-Talk, Führungen, Food & Drinks",
         desc="Afterwork-Event im IPAI mit Couch-Talk zu Robotikforschung und Unternehmen, Führungen, Essen und Getränken. Gäste: Leona Grulich (byte robotics), Maike Kaufman (Polybot), Gesche Held (Fraunhofer IPA), Moderation Sirid Böhm.",
         type="event", topics=["KI", "Robotik"], audience=["erwachsene", "jugendliche"],
         age_min=16, age_max=None, age_text="ab 16 Jahren",
         dates=[{"start": "2026-11-18T18:00", "end": "2026-11-18T21:00", "text": "18.11.2026, 18:00–21:00"}],
         duration="3 Stunden", price=None, price_text="Anmeldung über Eventbrite",
         status="Anmeldung erforderlich", url="https://ipai-foundation.ai/"),
    dict(id="ipai-ki-salon-vibe-coding", title="KI Salon Workshop: Vibe Coding & KI-Agenten – Von der Idee zur Anwendung",
         subtitle="Workshop mit Juan Gómez Fernández und Diana Thim (Schwarz Digits Data & AI Academy)",
         desc="Kompakte Einführung in KI-Agenten und Vibe Coding: Was sind KI-Agenten, was bedeutet Vibe Coding, Live-Demo von der Idee bis zur fertigen Anwendung, Best Practices, typische Stolpersteine und Austausch. Kein eigener Laptop nötig.",
         type="workshop", topics=["KI", "Coding"], audience=["erwachsene", "jugendliche"],
         age_min=16, age_max=None, age_text="ab 16 Jahren",
         dates=[{"start": "2026-11-23T15:00", "end": "2026-11-23T17:00", "text": "23.11.2026, 15:00–17:00"}],
         duration="2 Stunden", price=0, price_text="kostenfrei",
         status="Anmeldung erforderlich (max. 25)", url="https://ipai-foundation.ai/event/ki-salon-workshop-vibe-coding-ki-agenten-von-der-idee-zur-anwendung/"),
    dict(id="ipai-ki-salon-board-of-excellence", title="KI Salon Workshop: Erstelle dein Board of Excellence",
         subtitle="Persönliches Experten-Team in ChatGPT oder Claude",
         desc="Praxisworkshop mit Rafaela Fleischer: eigenes „Board of Excellence“ in ChatGPT oder Claude aufbauen, Rollen und Widerspruch gestalten, KI als Denk- und Sparringspartner nutzen. Für KI-Einsteiger:innen mit Laptop und aktivem Bezahl-Account bei Anthropic oder OpenAI.",
         type="workshop", topics=["KI"], audience=["erwachsene"],
         age_min=18, age_max=None, age_text="Erwachsene",
         dates=[{"start": "2026-11-30T12:30", "end": "2026-11-30T14:30", "text": "30.11.2026, 12:30–14:30"}],
         duration="2 Stunden", price=0, price_text="kostenfrei",
         status="Anmeldung erforderlich (max. 25)", url="https://ipai-foundation.ai/event/ki-salon-workshop-erstelle-dein-board-of-excellence/"),
    dict(id="ipai-ki-salon-community-21", title="KI Salon Community Event #21",
         subtitle="KI-Community, Impulse, Austausch",
         desc="Community-Abend des KI Salon im IPAI SPACES mit Impulsen zu KI-Trends, StudyOrbit (KI-Lernumgebungen), HumanAI und KI-Sicherheit sowie Networking bei Snacks und Getränken. Für Interessierte, Expert:innen, Bürger:innen und Laien.",
         type="event", topics=["KI"], audience=["erwachsene", "jugendliche"],
         age_min=16, age_max=None, age_text="ab 16 Jahren",
         dates=[{"start": "2026-12-01T17:30", "end": "2026-12-01T20:30", "text": "01.12.2026, 17:30–20:30"}],
         duration="3 Stunden", price=0, price_text="kostenfrei",
         status="Anmeldung erforderlich", url="https://ipai-foundation.ai/event/ki-salon-community-event-21/"),
    dict(id="ipai-ki-salon-impuls-hallensleben", title="KI Salon Impuls: Dr. Sebastian Hallensleben – Regulieren wir uns an die Wand?",
         subtitle="Keynote und Diskussion zur KI-Regulierung",
         desc="Keynote mit anschließendem Austausch: Europa als Vorreiter der KI-Regulierung – was bringt sie, wo bremst sie, und wie messen wir Fähigkeiten und Grenzen von KI-Produkten nüchtern? Für Entscheider:innen, Entwickler:innen, Gestalter:innen und alle KI-Interessierten.",
         type="vortrag", topics=["KI"], audience=["erwachsene", "jugendliche"],
         age_min=16, age_max=None, age_text="ab 16 Jahren",
         dates=[{"start": "2026-12-08T18:30", "end": "2026-12-08T20:30", "text": "08.12.2026, 18:30–20:30"}],
         duration="2 Stunden", price=0, price_text="kostenfrei",
         status="Anmeldung erforderlich (max. 100)", url="https://ipai-foundation.ai/event/ki-salon-impuls-prof-dr-sebastian-hallensleben-regulieren-wir-uns-an-die-wand/"),
    dict(id="ipai-ki-salon-workshops", title="KI Salon Workshops – Technologie anwenden",
         subtitle="Zweimal im Monat: ChatGPT Basics, sprachbasiertes Programmieren, KI im Beruf",
         desc="Regelmäßige Praxis-Workshops des KI Salon zu konkreten KI-Anwendungen – von ChatGPT-Grundlagen über sprachbasiertes Programmieren bis zu KI im Beruf. Termine und Anmeldung über den KI-Salon-Kalender.",
         type="workshop-format", topics=["KI", "Coding"], audience=["erwachsene"],
         age_min=16, age_max=None, age_text="ab 16 Jahren",
         dates=[], duration="laufendes Format", price=None, price_text="je Workshop",
         status="wechselnde Termine", url="https://ipai-foundation.ai/ki-salon/"),
    dict(id="ipai-ki-salon-specials", title="KI Salon Specials – Gemeinsam unterwegs",
         subtitle="Monatlicher Besuch von Ausstellungen, Theater und Orten mit KI-Einsatz",
         desc="Einmal im Monat geht der KI Salon raus aus den IPAI SPACES und schaut sich KI-Einsatz vor Ort an – in Ausstellungen, im Theater oder an anderen spannenden Orten.",
         type="event-format", topics=["KI", "Kreativität"], audience=["erwachsene", "familien"],
         age_min=None, age_max=None, age_text="offen",
         dates=[], duration="laufendes Format", price=None, price_text="je Veranstaltung",
         status="wechselnde Termine", url="https://ipai-foundation.ai/ki-salon/"),
    dict(id="ipai-ki-salon-community", title="KI Salon Community – Afterwork-Update",
         subtitle="Viermal im Jahr: Impulse, Neuigkeiten, Austausch",
         desc="Vierteljährliches Community-Format mit kurzen Impulsen, Neuigkeiten aus der KI-Welt und viel Zeit für persönlichen Austausch.",
         type="event-format", topics=["KI"], audience=["erwachsene"],
         age_min=16, age_max=None, age_text="ab 16 Jahren",
         dates=[], duration="laufendes Format", price=0, price_text="kostenfrei",
         status="wechselnde Termine", url="https://ipai-foundation.ai/ki-salon/"),
    dict(id="ipai-ki-salon-disput", title="KI Salon Disput – kontroverse KI-Themen",
         subtitle="Zweimal im Jahr: Streitgespräch und Diskurs",
         desc="Format für kontroverse Fragen rund um KI: Positionen werden offen gegenübergestellt und gemeinsam diskutiert.",
         type="event-format", topics=["KI"], audience=["erwachsene", "jugendliche"],
         age_min=16, age_max=None, age_text="ab 16 Jahren",
         dates=[], duration="laufendes Format", price=0, price_text="kostenfrei",
         status="wechselnde Termine", url="https://ipai-foundation.ai/ki-salon/"),
    dict(id="ipai-ki-salon-impuls", title="KI Salon Impuls – exklusives Fachwissen",
         subtitle="Vorträge renommierter Expert:innen",
         desc="Unregelmäßige Impuls-Vorträge mit Expert:innen zu aktuellen KI-Fragen, jeweils mit anschließendem Austausch.",
         type="vortrag-format", topics=["KI"], audience=["erwachsene", "jugendliche"],
         age_min=16, age_max=None, age_text="ab 16 Jahren",
         dates=[], duration="laufendes Format", price=0, price_text="kostenfrei",
         status="wechselnde Termine", url="https://ipai-foundation.ai/ki-salon/"),
    dict(id="ipai-ki-festival-2027", title="KI Festival 2027",
         subtitle="Zweitägiges Festival für alle Generationen",
         desc="Das KI-Festival der IPAI Foundation zeigt KI in all ihren Facetten: interaktive Erlebnisse, Live-Musik, Vorträge, künstlerische Installationen und praxisnahe Workshops für alle. 2026 kamen rund 14.000 Gäste.",
         type="festival", topics=["KI", "Medienkompetenz"], audience=["familien", "kinder", "jugendliche", "erwachsene"],
         age_min=None, age_max=None, age_text="alle Altersgruppen",
         dates=[{"start": "2027-07-17", "end": "2027-07-18", "text": "17.–18.07.2027"}],
         duration="2 Tage", price=0, price_text="Eintritt kostenlos",
         status="Save the date", url="https://ipai-foundation.ai/ki-festival/"),
    dict(id="ipai-robotic-weeks-gessbot", title="Robotic Weeks: Gessbot von Gessmann",
         subtitle="Mobile Robotik in Aktion erleben",
         desc="Der mobile Gessbot zeigt praxisnah, wie flexible Robotik und smarte Services den Arbeitsalltag von morgen erleichtern. Teil der Robotic Weeks 2026 in den IPAI SPACES.",
         type="ausstellung", topics=["Robotik", "KI"], audience=["familien", "jugendliche", "erwachsene"],
         age_min=None, age_max=None, age_text="alle Altersgruppen",
         dates=[{"start": "2026-11-16", "end": "2026-11-18", "text": "16.–18.11.2026, 9–17 Uhr"}],
         duration="3 Tage", price=0, price_text="kostenfrei",
         status="offen", url="https://ipai-foundation.ai/robotic-weeks/"),
    dict(id="ipai-robotic-weeks-fraunhofer", title="Robotic Weeks: Roboter-Verhalten in VR erproben (Fraunhofer IAO)",
         subtitle="Reinigungsroboter im Umgang mit Menschen",
         desc="Gemeinsam mit dem Fraunhofer IAO probieren Besucher:innen hautnah aus, wie ein automatischer Reinigungsroboter im Alltag mit Menschen umgeht – in virtueller Realität.",
         type="workshop", topics=["Robotik", "KI"], audience=["familien", "jugendliche", "erwachsene"],
         age_min=10, age_max=None, age_text="ab 10 Jahren",
         dates=[{"start": "2026-11-19", "end": "2026-11-19", "text": "19.11.2026"}],
         duration="1 Tag", price=0, price_text="kostenfrei",
         status="offen", url="https://ipai-foundation.ai/robotic-weeks/"),
    dict(id="ipai-robotic-weeks-streichelzoo", title="Robotic Weeks: Elektronischer Streichelzoo",
         subtitle="Robotermeerschweinchen mit dem ZKM Karlsruhe",
         desc="Dauerausstellung der Robotic Weeks: Eine lebhafte Bande aus Robotermeerschweinchen zum Anfassen und Beobachten, entwickelt mit dem ZKM | Zentrum für Kunst und Medien Karlsruhe.",
         type="ausstellung", topics=["Robotik", "Kreativität"], audience=["familien", "kinder"],
         age_min=3, age_max=None, age_text="ab 3 Jahren",
         dates=[{"start": "2026-10-20", "end": "2026-11-20", "text": "20.10.–20.11.2026, 9–17 Uhr"}],
         duration="laufend", price=0, price_text="kostenfrei",
         status="offen", url="https://ipai-foundation.ai/robotic-weeks/"),
    dict(id="ipai-ai-literacy-masterclass", title="AI Literacy Masterclass",
         subtitle="Weiterbildung in 5 Modulen für Bildungsarbeit",
         desc="Fünf aufeinander aufbauende Module zu KI-Grundlagen, KI-Kompetenzmodellen, KI im Arbeitsalltag und der Vermittlung von KI-Kompetenz – mit Vertiefungsaufgaben, Begleitmaterialien und Teilnahmebestätigung. Für Einsteiger:innen bis Fortgeschrittene in der Bildungsarbeit.",
         type="fortbildung", topics=["KI", "Medienkompetenz"], audience=["lehrkraefte", "erwachsene"],
         age_min=18, age_max=None, age_text="Erwachsene",
         dates=[], duration="5 Veranstaltungen", price=None, price_text="siehe Programm",
         status="Anmeldung über IPAI", url="https://ipai-foundation.ai/ai-masterclass/"),
    dict(id="ipai-science-residency", title="IPAI Science Residency",
         subtitle="Einjähriges KI-Fellowship für Postdocs",
         desc="Fellowship für Forschende, die ihre KI-Forschung an der Schnittstelle von Wirtschaft, Gesellschaft und öffentlichem Sektor anwenden wollen: eigenes Projekt, sechsstellige Förderung, digitale Infrastruktur und individuelle Betreuung.",
         type="programm", topics=["KI"], audience=["erwachsene"],
         age_min=18, age_max=None, age_text="Postdocs",
         dates=[], duration="1 Jahr", price=None, price_text="gefördert",
         status="Bewerbung", url="https://ipai-foundation.ai/science-residency/"),
    dict(id="ipai-future-home", title="IPAI Future Home – Ausstellung zum entstehenden KI-Quartier",
         subtitle="Interaktive Ausstellung zu Planung und Bau des IPAI CAMPUS",
         desc="Das Herzstück des Besucherzentrums: eine interaktive Ausstellung mit exklusiven Einblicken in Planung, Baufortschritt und Konzepte des künftigen KI-Quartiers IPAI CAMPUS.",
         type="ausstellung", topics=["KI"], audience=["familien", "erwachsene", "jugendliche"],
         age_min=None, age_max=None, age_text="alle Altersgruppen",
         dates=[], duration="laufend, Mo–Fr 9–17 Uhr", price=0, price_text="Eintritt kostenlos",
         status="offen", url="https://ipai-foundation.ai/besucherzentrum/"),
    dict(id="ipai-art-space-archive", title="Art Space: Archive of Possible Lives (Florian Mehnert)",
         subtitle="Interaktive KI-Installation zu alternativen Biografien",
         desc="Begehbare KI-Installation: Nach Eingabe eines Namens öffnen Besucher:innen sechs Schubladen mit KI-generierten Fragmenten eines möglichen Lebens – Kindheit, Selbstwahrnehmung, Beziehungen, Entscheidungen, ein anderes mögliches Leben. Das Projekt fragt, wie generative Systeme Identität und Erinnerung prägen.",
         type="ausstellung", topics=["KI", "Kreativität", "Medienkompetenz"], audience=["jugendliche", "erwachsene"],
         age_min=14, age_max=None, age_text="ab 14 Jahren",
         dates=[], duration="laufende Ausstellung", price=0, price_text="Eintritt kostenlos",
         status="offen", url="https://ipai-foundation.ai/archive-of-possible-lives/"),
]
ipai_offers = []
for o in IPAI:
    topics = o["topics"]
    ipai_offers.append({
        "id": o["id"],
        "provider": "ipai",
        "provider_name": PROVIDERS["ipai"]["name"],
        "title": o["title"],
        "subtitle": o["subtitle"],
        "description": o["desc"],
        "type": o["type"],
        "topics": topics,
        "focus_ai_coding_gaming": focus_flag(topics),
        "audience": o["audience"],
        "age_min": o["age_min"],
        "age_max": o["age_max"],
        "age_text": o["age_text"],
        "dates": o["dates"],
        "duration_text": o["duration"],
        "location": IPAI_LOC,
        "price": {"amount": o["price"], "currency": "EUR", "text": o["price_text"]},
        "registration": {"url": o["url"], "status": o["status"]},
        "url": o["url"],
        "source_url": o["url"],
        "retrieved_at": RETRIEVED,
        "collection": "manuell kuratiert",
    })

# ---------------------------------------------------------------- assemble
offers = aim_offers + hdf_offers + exp_offers + ipai_offers
ids = [o["id"] for o in offers]
assert len(ids) == len(set(ids)), "doppelte IDs: " + str([i for i in ids if ids.count(i) > 1])

counts = {}
for o in offers:
    counts[o["provider"]] = counts.get(o["provider"], 0) + 1

data = {
    "meta": {
        "title": "Heilbronner Lernangebote – kuratierter Datensatz",
        "description": "200 reale Angebote für Kinder, Jugendliche und Familien von aim, experimenta, Haus der Familie und IPAI Foundation in Heilbronn.",
        "collected_at": RETRIEVED,
        "method": "Manuell kuratiert auf Basis der öffentlichen Anbieter-Websites und Kursdatenbanken; jede Zeile enthält Quell-URL und Abrufdatum.",
        "scope": {
            "providers": list(PROVIDERS.keys()),
            "city": "Heilbronn",
            "topics_focus": ["KI", "Coding", "Gaming"],
        },
        "counts": counts,
        "total": len(offers),
        "license_note": "Die Rechte an Titeln, Beschreibungen und Terminen liegen bei den jeweiligen Anbietern. Der Datensatz dient als Prototyp-/Hackathon-Grundlage; vor Veröffentlichung Rechte und Aktualität mit den Anbietern klären.",
        "schema": {
            "id": "eindeutige ID (Anbieter-Präfix + Kursnummer/Slug)",
            "provider": "aim | experimenta | hdf | ipai",
            "title": "Titel des Angebots",
            "description": "Kurzbeschreibung aus der Quelle",
            "type": "kurs | workshop | vortrag | show | event | ferienbetreuung | laborkurs | ausstellung | fuehrung | fortbildung | wettbewerb | programm | Format",
            "topics": "KI, Coding, Gaming, Robotik, Daten, MINT, Medienkompetenz, Kreativität, Astronomie, Ferien, Berufsorientierung, Allgemein",
            "focus_ai_coding_gaming": "true, wenn mindestens eines der Challenge-Schwerpunktthemen gesetzt ist",
            "audience": "kinder, jugendliche, eltern, familien, lehrkraefte, erwachsene",
            "age_min/age_max/age_text": "Alter, soweit in der Quelle angegeben",
            "dates": "Liste aus start/end (ISO 8601) und text",
            "location": "Name, Adresse, Stadt",
            "price": "Betrag in EUR (0 = kostenlos, null = unbekannt) plus Text",
            "registration": "Anmelde-URL und Status",
            "url": "Detailseite des Angebots",
            "source_url": "verwendete Übersichts-/Detailquelle",
            "retrieved_at": "Abrufdatum",
        },
    },
    "offers": offers,
}

with open(OUT, "w", encoding="utf8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("geschrieben:", OUT)
print("gesamt:", len(offers), counts)
print("Fokus KI/Coding/Gaming:", sum(1 for o in offers if o["focus_ai_coding_gaming"]))
