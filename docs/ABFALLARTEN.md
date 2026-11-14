# Abfallarten & Synthetische Ströme (`WasteStream`)

Dieses Dokument beschreibt die Übertragbarkeit der GlasRoute-Pipeline auf weitere Abfallarten neben Altglas.

> [!IMPORTANT]
> **Daten-Wahrheit:** Nur Altglas (`glass_white`, `glass_green`, `glass_brown`) basiert auf echten PreZero-Messungen (`data/raw/glass_fill_levels_anonymized_f.csv`, 11.701 Messungen, 449 Standorte). Alle übrigen Ströme (`paper`, `bio`, `gastro`, `plastik`) sind **synthetische, deterministisch geseedete Simulationen** (`synthetic = True`) zum Nachweis der Pipeline-Übertragbarkeit.

---

## 1. Datenmodell (`WasteStream`)

In [`src/prezero/model.py`](../src/prezero/model.py) kapselt die Dataclass `WasteStream` die physikalischen und saisonalen Annahmen je Fraktion:

- `name`: Technischer Schlüssel (z. B. `glass_white`, `paper`, `bio`, `gastro`, `plastik`)
- `display_name`: Deutscher Anzeigename für UI/Berichte (`Weißglas`, `Papier`, `Bio`, `Gastronomie`, `Plastik`)
- `density_kg_per_m3`: Schüttdichte in $\text{kg/m}^3$ (steuert Gewichtsberechnung `Container.expected_mass_kg()` und Fahrzeugkapazität)
- `container_volume_m3`: Standard-Behältervolumen in $\text{m}^3$ (überschreibt in `Container.__post_init__` den Default `2.5` $\text{m}^3$, sofern nicht explizit abweichend gesetzt)
- `fill_speed`: Relativer Füllgeschwindigkeitsfaktor für den synthetischen Generator
- `season_factor`: Monatsfaktoren (`1`..`12`) für die saisonale Füllrate
- `overfull_value`: Numerischer Ersatzwert für `"overfull"` (Default `110.0`)
- `synthetic`: `False` für echte Altglas-Daten, `True` für synthetische Ströme

Über `WASTE_STREAMS` und `stream_for_material(material_name)` ordnet `build_model()` jede Messung automatisch dem passenden `WasteStream` zu.

---

## 2. Übersicht der Abfallarten

Alle Parameter sind in [`src/prezero/model.py`](../src/prezero/model.py) und [`prezero_config.json`](../prezero_config.json) (Sektion `"streams"`) hinterlegt:

| Stream-Key | Anzeigename | `synthetic` | Dichte ($\text{kg/m}^3$) | Volumen ($\text{m}^3$) | `fill_speed` | Saisonalität (Schwerpunkt) |
|---|---|---|---|---|---|---|
| `glass` (`white`, `green`, `brown`) | Weiß-/Grün-/Braunglas | `False` | `400.0` | `2.5` | `1.0` | Jan–Apr `1.0`, Mai/Dez `0.7`, Jun–Nov `0.5` |
| `paper` | Papier | `True` | `80.0` | `3.0` | `1.3` | Winter/Jahresende (`11`: `1.3`, `12`: `1.4`, `1`: `1.2`) |
| `bio` | Bio | `True` | `600.0` | `2.4` | `1.1` | Sommer (`6`–`7`: `1.5`, `5`/`8`: `1.4`, Winter `0.5`) |
| `gastro` | Gastronomie | `True` | `350.0` | `1.5` | `1.6` | Sommer (`6`–`7`: `1.3`) + Wochenend- (`1.5×`) & Event-Spitzen |
| `plastik` | Plastik | `True` | `50.0` | `2.8` | `0.9` | Leichtes Sommerhoch (`5`–`7`: `1.2`, Winter `0.9`) |

---

## 3. Synthetischer Datengenerator

Das Skript [`scripts/generate_synthetic_streams.py`](../scripts/generate_synthetic_streams.py) erzeugt reproduzierbare CSV-Dateien im identischen Schema der Rohdaten (`Location_id, material_type, date, fill_level_perc`) für alle 449 Standorte aus `data/external/locations.csv` im Zeitraum `2025-10-31` bis `2026-09-30` (Default-Seed: `2026`).

- **Measure-and-Empty-Semantik:** Nach jedem Besuch ist der Container geleert; der Füllstand beim nächsten Besuch ergibt sich aus `daily_rate * interval_days + noise`, begrenzt auf `[5.0, 110.0]` (bei `>= 110.0` mit 70 % Wahrscheinlichkeit als `"overfull"` codiert).
- **Gastro-Besonderheiten:** Wochenenden (`weekday >= 5`) erhalten Faktor `1.5`, definierte Event-Tage (z. B. September-Wochenenden) Faktor `1.8`, zufällige Do–So-Events Faktor `1.6`.
- **Erzeugte Dateien in `data/synthetic/`:**
  - `data/synthetic/paper_fill_levels.csv`
  - `data/synthetic/bio_fill_levels.csv`
  - `data/synthetic/gastro_fill_levels.csv`
  - `data/synthetic/plastik_fill_levels.csv`

Regenerieren per CLI:

```bash
python3 scripts/generate_synthetic_streams.py --seed 2026
```

---

## 4. CLI-Nutzung (`--stream`)

Die Pipeline-Befehle in [`src/prezero/cli.py`](../src/prezero/cli.py) akzeptieren `--stream` / `-s` (`glass`, `paper`, `bio`, `gastro`, `plastik`; Default `glass`) und routen Ein- und Ausgabepfade automatisch getrennt je Stream:

- **Rohdaten:** `data/raw/glass_fill_levels_anonymized_f.csv` bzw. `data/synthetic/<stream>_fill_levels.csv`
- **Cleaned:** `data/processed/cleaned_readings.csv` bzw. `data/processed/<stream>_cleaned_readings.csv`
- **Scored:** `data/processed/scored_<date>.csv` bzw. `data/processed/<stream>_scored_<date>.csv`
- **Outputs:** `<stream>_route_<date>.json`, `<stream>_ui_<date>.html`, `<stream>_map_<date>.html`, `<stream>_heatmap.html`, `<stream>_trends.png` (für `glass` ohne Präfix)

Beispiel für einen synthetischen Lauf:

```bash
prezero-route run --stream bio --date 2026-04-15
```

---

## 5. Offene UI-Integration (Hinweis)

`build_ui(..., stream=...)` in `src/prezero/ui.py` akzeptiert `stream` bereits als Parameter, zeigt jedoch aktuell noch keinen UI-Stream-Selector und kein Banner „Synthetische Daten“ an. Diese UI-Erweiterung wird separat über die UI/Website-Rolle integriert.
