# LOGBUCH — PreZero Route Hackathon

## 2026-11-14 — Standortplanung-What-if Tab fertiggestellt

**Kontext:** Mission M-20261114T202446-e69c362d (Lease S-20261114T202928-0aeadc67).

**Was passiert ist:**
- Implementation von Tab 10 „Standortplanung“ in `src/prezero/ui.py`, Core-Modul `src/prezero/location_planning.py`, Config-Erweiterung in `prezero_config.json` und `src/prezero/routing.py`, Dokumentation in `docs/STANDORTPLANUNG.md`, Tests in `tests/test_location_planning.py` + Erweiterung `tests/test_ui.py`.
- Laufzeitbug behoben: `_score_grid_cells` und `_compute_demand_transfer` greifen jetzt mit `_get_numeric_series(...)` auf optionale Spalten wie `est_fill_level` zu, statt `pd.to_numeric(scored.get(...))` (liefert bei fehlender Spalte einen Skalar `nan` ohne `.fillna()`).
- `make_subplots` importiert, Timeline-Chart auf `include_plotlyjs=False` gestellt (verhindert `fetch(` im Outer-HTML, was `test_ui_copilot_overview_explain_whatif_ask_and_shift_limit` bricht).
- Syntaxfehler im fremden QRCode-JS-Block in `src/prezero/ui.py` behoben (literale `{`/`}` in `document_html`-f-String verdoppelt), damit `py_compile` und pytest wieder durchlaufen.

**Belege:**
- `PYTHONPATH=src python3 -m pytest tests/ -q` → 134 passed
- `python3 Projek-Management/proof/verify_pitch_numbers.py` → RESULT: ALL MATCH
- `ui_2026-04-15.html` enthält `view-location-planning`, Banner „simulierten Koordinaten“ und Adoptions-Timeline.
- Commit `911d38e`, gepusht nach `origin/master`.

**Fails/Lernregeln:**
1. Fremde uncommittete Änderungen können Syntaxfehler enthalten, die die eigene Testausführung blockieren. Minimale Reparatur erlaubt, um den Baum wieder lauffähig zu machen, aber nicht deren Semantik ändern.
2. `pd.to_numeric(df.get(col))` ist gefährlich, wenn `col` fehlt: es entsteht ein numpy-Skalar. Besser einen leeren Series als Default übergeben.
3. Plotly-`include_plotlyjs=True` im Outer-HTML nach dem letzten `<iframe>` verletzt die „kein fetch() außerhalb von iframes“-Policy des Projekts.

**Nächster Schritt:**
- HAI-Mission `M-20261114T202446-e69c362d` war beim Close-Versuch nicht mehr aktiv (Status zeigt neue Mission `M-20261114T204635-499f4773`); Ergebnisse sind aber committed und gepusht.

**Fremde Änderungen im Baum (nicht committet):**
- modified: `src/prezero/tour.py`
- modified: `tests/test_tour.py`
- untracked: `docs/EXPORT_RECHERCHE.md`
