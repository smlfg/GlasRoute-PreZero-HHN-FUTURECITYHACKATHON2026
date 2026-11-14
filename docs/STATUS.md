# GlasRoute (PreZero Route) – Projektstatus

**Stand:** Samstag, 14.11.2026, 15:55 Uhr · **Abgabe:** Sonntag, 15.11.2026, 13:00 Uhr

---

## 1. Was ist GlasRoute?

**GlasRoute** ist ein Prototyp für **PreZero / kommunale Entsorgungsdisponenten** in Heilbronn, der
historische und aktuelle Glascontainer-Füllstände in priorisierte, vom Menschen freigegebene Abholrouten
übersetzt, um Leerfahrten zu vermeiden und Überläufe zu verhindern.

---

## 2. Aktive Schreiber

**Ein Schreiber zur Zeit** (bis Sa 14:30 liefen zwei Agenten parallel — siehe Git-Historie).

| Agent | Scope | Status |
|---|---|---|
| **Hauptsession (Samuel/OpenCode)** | `approval.py`, `cli.py`, `tests/test_approval.py`, `Pitch/`, `docs/PITCH.md`, `README.md`, `AGENTS.md` | aktiv |
| frei | — | — |

Vor jedem Commit: `git status` + `git log --oneline -3` prüfen, nur eigene Pfade stagen.

---

## 3. Pipeline-Überblick

```mermaid
flowchart LR
    CSV["CSV Rohdaten<br/>(11.701 Zeilen, 449 IDs)"] --> INGEST["ingest.py"]
    INGEST --> LOC["locations.py"]
    INGEST --> FEAT["features.py"]
    FEAT --> SCORE["scoring.py"]
    SCORE --> ROUTE["routing.py"]
    LOC --> ROUTE
    ROUTE --> OUT_JSON["route.json"]
    ROUTE --> VIZ["viz.py"]
    FEAT --> VIZ
    VIZ --> OUT_MAP["map.html"]
    VIZ --> OUT_TRENDS["trends.png"]
    CLI["cli.py"] -. steuert .-> INGEST
    CLI -. steuert .-> FEAT
    CLI -. steuert .-> SCORE
    CLI -. steuert .-> ROUTE
    CLI -. steuert .-> VIZ

    classDef done fill:#d4edda,stroke:#28a745,color:#155724;
    classDef partial fill:#fff3cd,stroke:#ffc107,color:#856404;

    class CSV,INGEST,LOC,FEAT,SCORE,ROUTE,VIZ,OUT_JSON,OUT_MAP,OUT_TRENDS done;
    class CLI partial;
```

*Legende: **Grün** = fertig & getestet · **Gelb** = teilweise umgesetzt*

---

## 4. Wo wir stehen

**Testlauf:** `PYTHONPATH=src pytest -q` → **35 passed**.
**End-to-End:** `PYTHONPATH=src python3 -m prezero.cli run --date 2026-04-15` läuft ohne Fehler.

| Modul | Status | Datei | Tests | Was noch fehlt |
|---|---|---|---|---|
| **CSV (Rohdaten)** | Fertig | `data/raw/glass_fill_levels_anonymized_f.csv` | `test_load_raw`, `test_full_raw_dataset_has_exactly_449_ids` | Nichts |
| **ingest** | Fertig | `src/prezero/ingest.py` (`scripts/01_ingest.py`) | 2 Tests | Nichts; `cleaned_readings.csv` existiert |
| **locations** | Fertig | `src/prezero/locations.py`, `scripts/fetch_locations.py`, `scripts/refresh_locations.py` | 16 Tests | Echte PreZero-Zuordnung (`locations_real.csv`) |
| **features** | Fertig | `src/prezero/features.py` | 3 Tests | Nichts |
| **scoring** | Fertig | `src/prezero/scoring.py` | 4 Tests | Nichts |
| **routing** | Fertig | `src/prezero/routing.py` | 7 Tests | Nichts |
| **viz** | Fertig | `src/prezero/viz.py` | 3 Tests | Nichts |
| **cli** | Fertig | `src/prezero/cli.py` | — (End-to-End geprüft) | Eigene CLI-Tests (`CliRunner`) |
| **Outputs** | Fertig | `route_2026-04-15.json`, `map_2026-04-15.html`, `trends.png` | — | Nichts |

---

## 5. Zahlen für den Pitch (belegt aus der Pipeline)

Demo-Datum **15.04.2026**:

| Kennzahl | Wert |
|---|---|
| Kritische Standorte | 72 physische Orte (108 IDs, 118 Container) |
| Aktive Standorte gesamt | 121 physische Orte |
| Tages-Tour (25 Stopps) | **125,21 km** |
| Volle Runde, gleiche Regeln (121 Stopps) | 1.202,24 km |
| **Fairer Vergleich (Benchmark)** | **Bedarfs-Effekt 81,0 % · Routing-Effekt 9,6 % (instabil 0–13 %) · gesamt 82,8 %** |
| Benötigte Fahrzeuge | 2 (7 Runden) |
| Fahrzeugstunden gesamt / längste Schicht | 10,51 h / 7,26 h (Limit 8,0 h) |
| Sammelmenge | 63,6 t (geschätzter Stand heute, 2,5 m³/Container, 400 kg/m³) |

Weitere Muster aus den Rohdaten: Weißglas erzeugt die meisten `overfull`-Ereignisse (731 von 1.192),
saisonaler Peak Januar–April, Einbruch im Juni/Juli.

Annahmen sind vollständig in `route_2026-04-15.json` unter `assumptions` dokumentiert
(Dichte, Containervolumen, Fahrzeuglast, Umwegfaktor 1,35, Tempo 25 km/h, Umschlagzeiten).

---

## 6. Zeitplan bis zur Abgabe

```mermaid
flowchart LR
    NOW["Sa 15:45 (JETZT)<br/>Kernpipeline läuft<br/>End-to-End grün"] --> DOCS["Sa 17:00<br/>README + PITCH.md<br/>mit echten Zahlen"]
    DOCS --> HAI["Sa 19:00<br/>Disponent-Freigabe<br/>(Human-Agent-Interface)"]
    HAI --> DRY["Sa 21:00<br/>Demo-Probelauf<br/>3 Szenarien"]
    DRY --> CORE["Sa 23:00<br/>Doku final<br/>Keine neuen Features"]
    CORE --> FREEZE["So 11:00 Freeze<br/>Nur noch Bugfixes"]
    FREEZE --> SUB["So 13:00 Abgabe<br/>Code + Pitch"]

    style NOW fill:#d4edda,stroke:#28a745,color:#155724
    style FREEZE fill:#f8d7da,stroke:#dc3545,color:#721c24
```

---

## 7. Nächste Schritte

1. **Pitch-Deck** (Slides) für 13:00 — `Pitch/NOTES.md` + `docs/PITCH.md` liefern Struktur, Zahlen,
   Live-Ablauf und die Fragen an PreZero.
2. **Live-Hook üben:** die Betriebsvariablen aus `prezero_config.json` mit echten Zahlen füttern und
   `prezero-route route --config prezero_config.json` laufen lassen (7 Runden/125 km → 5 Runden/100 km bei Dichte 300, Umweg 1,2).
3. **README-Demo-Ablauf durchspielen** — drei Befehle, ein Datum, mit Erwartungsausgaben.
4. **Präsentationsfolien bauen** und einmal mit Timer durchgehen.
5. **Optional, wenn Zeit bleibt:** CLI-Tests für `propose`/`approve` mit `CliRunner`.

Der Disponent-Freigabe-Schritt (Human-Agent-Interface) ist **fertig und getestet**:
`prezero-route propose` → `prezero-route approve` (oder `--reject`) → Beleg in
`data/processed/approval_<date>.json` mit Zeitstempel, Freigebender, Route und Kennzahlen.

Der Stakeholder erwartet laut Readme/PPT **keine Koordinaten** — er will Muster, Priorisierung und
eine Route gegen „alles abfahren". Alle vier Deliverables sind abgedeckt; die 11 Betriebsvariablen
sind der Live-Hook (PreZero ist das ganze Wochenende bei HHN).

---

## 8. Risiken & Gegenmaßnahmen

1. **Keine echten PreZero-Koordinaten** → 126 reale OSM-Standorte, Zuordnung bleibt
   `confidence=low`/`UNVERIFIED`; Rest sind benannte Platzhalter (Seed 2026). Austauschpfad:
   `data/external/locations_real.csv` + `scripts/refresh_locations.py --real`, ohne Codeänderung.
2. **Scope Creep** (Web-UI, lokales LLM/RAG & Voice) → bewusst zurückgestellt. Fokus: ein Fahrzeug,
   harter Feature-Freeze So 11:00.
3. **Overpass-Last** → Area-Query scheitert unter Last; BBox-Fallback liefert zuverlässig. Rohpayload
   wird gespeichert, damit der Demo-Lauf nicht vom Netz abhängt.
4. **Zeitdruck** → Kern steht vor So 11:00; Sonntagmorgen nur Pitch und Polieren.
