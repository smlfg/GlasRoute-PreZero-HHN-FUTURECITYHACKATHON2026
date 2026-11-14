# GlasRoute — Integrationsplan (reMarkable UI-Konzept → `prezero-routing-hackathon-2026`)

**Stand:** Samstag, 14.11.2026 · **Ziel:** Nahtlose Integration des 3-stufigen UI-Konzepts aus der reMarkable-Skizze (`01_remarkable_skizze_original.png`) in das bestehende CLI-Projekt `prezero-routing-hackathon-2026`, ohne bestehende Tests oder CLI-Workflows zu brechen.

---

## 1. IST-Stand & Governance-Abgleich

### Bereits vorhanden im Repo (`prezero-routing-hackathon-2026`)
- **Kernmodule (`src/prezero/`):** `ingest.py`, `locations.py`, `features.py`, `scoring.py`, `routing.py`, `viz.py`, `cli.py` sind vollständig implementiert.
- **Erzeugte Demo-Outputs:**
  - `route_2026-04-15.json` (`25` Stops aus `169` kritischen von `431` aktiven Standorten, `67,92 km` statt `260,82 km` = **`-74,0%` / `192,91 km` Ersparnis**).
  - `map_2026-04-15.html` (interaktive Folium-Karte mit Provenienz-Unterscheidung `osm_heuristic` vs. `synthetic_placeholder`).
  - `trends.png` (Matplotlib-Monatsverlauf nach Material).
- **Wissensbasis für RAG (`PreZero/analysen/`):** 36 dokumentierte Einzelanalysen (`01_ueberfuellungsrisiko.md` bis `36_hypothesen_mentor.md`) inkl. `INDEX.md`.

### Scope- & Architektur-Abgleich (`AGENTS.md` vs. `PLAN.md`)
- `AGENTS.md` definiert **CLI-first** und warnt vor *„Dashboard-Overengineering (Streamlit, Dash, React)“*.
- `PLAN.md` (Abschnitt 3: *Konzept-Entwurf für Schritt 2*) beschreibt exakt die gezeichnete Oberfläche: **kleines lokales Web-Frontend** mit CSV-Drag-and-Drop, Pandas-Plots und einem **recommendation-based RAG-System (Text + optional Voice)** nach dem **Re-Planning-Gate**.
- **Architektur-Entscheidung:** Keine schwere SPA/React/Streamlit-Umgebung, sondern **ein einziger schlanker FastAPI-/HTTP-Adapter (`src/prezero/web.py`)**, der die vorhandene `src/prezero`-Logik direkt aufruft und unsere statische Einzeldatei (`03_ui_mockup_interaktiv.html`) ausliefert. Alle CLI-Befehle (`ingest`, `score`, `route`, `visualize`, `run`) bleiben zu 100 % unverändert.

---

## 2. Zielarchitektur der Integration

```text
prezero-routing-hackathon-2026/
├── src/prezero/
│   ├── ingest.py / features.py / scoring.py / routing.py / viz.py  (UNVERÄNDERT)
│   ├── web.py                 <-- NEU (Slice 1): FastAPI/Starlette-Adapter + API
│   ├── rag.py                 <-- NEU (Slice 2): Leichtgewichtiger Index über analysen/*.md + route.json
│   └── static/
│       └── index.html         <-- NEU (Slice 1): Produktiv-Version von 03_ui_mockup_interaktiv.html
└── tests/
    └── test_web.py            <-- NEU (Slice 4): API- & Upload-Tests ohne UI-Overhead
```

---

## 3. Phasen- & Zeitplan (4 kleine, prüfbare Slices)

### Slice 1 — API-Adapter & CSV Drag-and-Drop (`~45 Min`)
- **Ziel:** Stufe ① (`Drag & Drop .csv`) und Stufe ② (`Animation "processing"` + echte 6-Karten-JSON-Werte) mit dem echten `prezero`-Backend verbinden.
- **Umsetzung:**
  1. `src/prezero/web.py` mit 2 Endpunkten anlegen:
     - `GET /` → liefert die eingebettete HTML-Oberfläche (`static/index.html`) aus.
     - `POST /api/upload` → nimmt hochgeladene CSV entgegen, speichert temporär unter `Projek-Managment/tmp/`, führt `ingest.clean()` → `locations.resolve_locations()` → `features.build_features()` → `scoring.score_containers()` → `routing.build_route()` aus und liefert das JSON-Paket für die 6 Pandas-Karten + Top-25-Route zurück.
  2. In `cli.py` optional einen Subcommand `serve` (`--port 8000`) ergänzen.
- **DoD / Prüfung:** Upload von `glass_fill_levels_anonymized_f.csv` liefert HTTP 200 mit exakt `11.701` Zeilen, `449` IDs und `planned_km: 67.92`.

### Slice 2 — Echte Pandas-Kennzahlen, Anomalie-Highlight & Karten-Anbindung (`~45 Min`)
- **Ziel:** Die 6 Kacheln in Stufe ②/③ mit den dynamisch berechneten Werten aus dem jeweils hochgeladenen CSV befüllen und Folium (`map_YYYY-MM-DD.html`) per Modal/Link einbinden.
- **Umsetzung:**
  1. Hilfsfunktion `summarize_cards(cleaned_df, scored_df, route_dict)` berechnen lassen:
     - Karte 1: Materialmittel & Overfull-Anteil (`white / green / brown`).
     - Karte 2: Monatsmittel + Erkennung von Nachweihnachts-/Saisonspitzen (`>40%` Overfull → Anomalie-Flag).
     - Karte 3: Anteil `>= 80%`, `overfull`-Anzahl, Serien `> 0.9` Score.
     - Karte 4: Median-Zuwachs (`pp/Tag`), geschätzte Leerungen.
     - Karte 5: Große Sprünge (`> 50 pp`) & Reihen mit `> 90` Tagen Messlücke (Anomalie-Flag).
     - Karte 6: Vergleich `planned_km` vs. `full_round_km` + `saved_pct`.
  2. `GET /api/map` liefert die aktuell generierte Folium-Karte aus `viz.plot_route(...)`.
- **DoD / Prüfung:** UI zeigt identische Kennzahlen wie `ANALYSE_GLASS_FILL_LEVELS.md` und `route_2026-04-15.json`.

### Slice 3 — Lokales RAG (`PreZero/analysen/*.md`) + Voice (`Piper TTS`) (`~60 Min`)
- **Ziel:** Stufe ③ (`Chat with Agent RAG` + `Voice + Text` + `Node-Binding`) funktionsfähig machen.
- **Umsetzung:**
  1. `src/prezero/rag.py`:
     - Lädt beim Start alle 36 Markdown-Dateien (`PreZero/analysen/*.md`) sowie das aktuelle `route_*.json`.
     - **Stufe A (Offline-Fallback, 0 API-Abhängigkeit):** TF-IDF-/Keyword-Retrieval auf Abschnittsebene + strukturiertes Prompt-Template mit exakten Zahlen-Zitaten (läuft auch bei fehlendem Ollama/LLM während des Pitchs garantiert stabil).
     - **Stufe B (Lokales LLM, optional über Env `LOCAL_LLM_URL`):** Übergibt die Top-3 abgerufenen Markdown-Abschnitte + aktive `selected_node_id` + aktuelle Top-Stops an ein lokales Modell (z. B. Ollama) im Modus **recommendation-only**.
  2. `POST /api/chat` (`{ question, selected_node_id, anomaly_only }`) liefert Antwort + Quellenliste (`["13_nachweihnachtsspitze.md", "route_2026-04-15.json"]`).
  3. **Voice-Integration (`POST /api/voice`):** Nutzt die lokal vorhandene Piper-Stimme (`~/.local/share/pycoach-tts/de_DE-thorsten-high.onnx`) zur WAV-Erzeugung für die Audio-Ausgabe im Browser (oder Browser-WebSpeech als Zero-Config-Fallback).
- **DoD / Prüfung:** Klick auf Karte 5 + Frage nach Lücken zitiert `15_anomalien.md` / `18_messluecken.md` und liest die Zusammenfassung optional vor.

### Slice 4 — Human-in-the-Loop Freigabe & Pitch-Absicherung (`~30 Min`)
- **Ziel:** Dispatcher-Freigabe persistieren und Demo gegen WLAN-/Netzwerkausfall härten.
- **Umsetzung:**
  1. `POST /api/approve` schreibt einen Audit-Eintrag (`timestamp`, `date`, `num_stops`, `planned_km`, `approved_by`) neben `route_YYYY-MM-DD.json`.
  2. `tests/test_web.py` ergänzt End-to-End-Tests für `/api/upload`, `/api/chat` und `/api/approve`.
  3. **Fallback-Regel für So 13:00:** Falls beim Live-Pitch kein lokaler Server gestartet werden soll, bleibt `03_ui_mockup_interaktiv.html` als 100 % eigenständige, vorausgefüllte Offline-Demo sofort vorzeigbar.

---

## 4. Abhängigkeiten & Verifikations-Checkliste

- **Minimale Zusatzpakete (nur bei Umsetzung von `web.py`):** `fastapi` + `uvicorn` + `python-multipart` (oder reine Python-Stdlib `http.server` für 0 neue Abhängigkeiten).
- **Vor Merge / Pitch prüfen:**
  - [ ] Bestehende Tests laufen weiterhin grün (`PYTHONPATH=src pytest -v`).
  - [ ] Neue Web-Tests (`tests/test_web.py`) grün.
  - [ ] Provenienz-Hinweis (`osm_heuristic` vs. `synthetic_placeholder`) bleibt in Route-Tabelle und Map sichtbar (`AGENTS.md` Daten-Wahrheit).
  - [ ] Kein autonomes Auslösen von Touren — immer **Recommendation + menschliche Freigabe**.
