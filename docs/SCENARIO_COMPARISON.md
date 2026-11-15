# Szenario-Vergleich (gleiche Glasmenge)

Erzeugt von `scripts/scenario_comparison.py` aus `data/outputs/scenarios/summary.json` (generated_at 2026-11-15T12:20:46+00:00), `km_decomposition.json`, `skip_savings.json`. Keine Zahl ist von Hand eingetragen. Modell: `docs/MODEL_SPEC.md`.

**Zeitraum:** 2025-10-17 bis 2026-09-30 (349 Tage). **Produziertes Glas: 7.613,95 t in jedem Szenario** (Massenbilanz `gesammelt + Endbestand = produziert` geprüft je Szenario, `mass_balance_ok` = True).

Spalten: *Überlauf-Tage* = Container-Tage mit Füllstand ≥ 110 %; *übervoll bei Leerung* = Leerungen bei ≥ 110 %; *Halte* = angefahrene Punkte (lat/lon). Kosten (Annahme) = Fahrzeugtage × 500 € + Crew-h × 64 € + km × 0,65 €. „günstigste“ / „wenigste Überläufe“ gelten je Zeitmodell. `_per_colour` = ein LKW je Glasfarbe (`truck_mode`), sonst Mehrkammer-Annahme.

## Szenarien

### Zeitmodell Mentor (7/15 min Fahrt, 5 min/Halt, Depot)

| Szenario | gesammelt t | Endbestand t | Überlauf-Tage | übervoll bei Leerung | Ø Füllstand % | Leerungen | Halte | Fahrzeugtage | Stunden | km | Kosten € | Δ Kosten |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `d_status_quo` | 6.943,5 | 670,5 | 19.047 | 1.196 | 67,0 | 10.363 | 3.714 | 271 | 1.335,0 | 19.008 | 233.295 | 0,0 % |
| `a_zero_overflow` | 7.095,3 | 518,7 | 2.237 | 259 | 68,0 | 10.427 | 7.797 | 391 | 2.256,4 | 25.266 | 356.333 | +52,7 % |
| `b_min_km` | 6.963,9 | 650,1 | 7.079 | 923 | 86,0 | 8.094 | 6.425 | 339 | 1.930,8 | 22.959 | 307.994 | +32,0 % |
| `c_max_fill` | 7.099,8 | 514,2 | 2.502 | 300 | 71,6 | 9.912 | 7.569 | 379 | 2.202,2 | 24.673 | 346.478 | +48,5 % |
| `e_mentor` | 7.206,1 | 407,8 | 485 | 101 | 52,7 | 13.676 | 7.278 | 404 | 2.130,6 | 25.185 | 354.729 | +52,1 % |
| `f_fixed_areas` | 7.143,1 | 470,8 | 1.958 | 216 | 60,3 | 11.842 | 4.668 | 317 | 1.539,9 | 14.898 | 266.738 | +14,3 % |
| `g_co_empty_x70` | 7.121,0 | 492,9 | 1.636 | 223 | 66,6 | 10.695 | 5.736 | 331 | 1.779,9 | 22.238 | 293.869 | +26,0 % |
| `g_co_empty` | 7.196,6 | 417,3 | 581 | 105 | 57,2 | 12.584 | 3.069 | 286 | 1.208,8 | 17.482 | 231.726 | -0,7 % |
| `g_co_empty_x30` **günstigste**, **wenigste Überläufe** | 7.290,2 | 323,7 | 159 | 45 | 45,6 | 15.976 | 2.228 | 275 | 1.055,3 | 15.398 | 215.048 | -7,8 % |
| `d_status_quo_per_colour` | 6.943,5 | 670,5 | 19.047 | 1.196 | 67,0 | 10.363 | 9.640 | 672 | 2.677,8 | 39.292 | 532.919 | +128,4 % |
| `a_zero_overflow_per_colour` | 7.095,3 | 518,7 | 2.237 | 259 | 68,0 | 10.427 | 9.454 | 766 | 2.626,8 | 38.029 | 575.834 | +146,8 % |
| `g_co_empty_per_colour` | 7.173,5 | 440,4 | 1.034 | 155 | 60,8 | 11.800 | 5.461 | 698 | 1.694,9 | 27.844 | 475.572 | +103,9 % |

### km-Modell (25 km/h, Rüst-/Hubzeit aus Config)

| Szenario | gesammelt t | Endbestand t | Überlauf-Tage | übervoll bei Leerung | Ø Füllstand % | Leerungen | Halte | Fahrzeugtage | Stunden | km | Kosten € | Δ Kosten |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `d_status_quo` | 6.943,5 | 670,5 | 19.047 | 1.196 | 67,0 | 10.363 | 3.714 | 317 | 1.593,3 | 19.008 | 272.826 | 0,0 % |
| `a_zero_overflow` | 7.095,3 | 518,7 | 2.237 | 259 | 68,0 | 10.427 | 7.797 | 344 | 1.968,5 | 25.266 | 314.407 | +15,2 % |
| `b_min_km` | 6.963,9 | 650,1 | 7.079 | 923 | 86,0 | 8.094 | 6.425 | 301 | 1.721,3 | 22.959 | 275.586 | +1,0 % |
| `c_max_fill` | 7.099,8 | 514,2 | 2.502 | 300 | 71,6 | 9.912 | 7.569 | 328 | 1.915,9 | 24.673 | 302.655 | +10,9 % |
| `e_mentor` | 7.206,1 | 407,8 | 485 | 101 | 52,7 | 13.676 | 7.278 | 404 | 2.104,8 | 25.185 | 353.078 | +29,4 % |
| `f_fixed_areas` **günstigste** | 7.143,1 | 470,8 | 1.958 | 216 | 60,3 | 11.842 | 4.668 | 315 | 1.534,3 | 14.898 | 265.379 | -2,7 % |
| `g_co_empty_x70` | 7.121,0 | 492,9 | 1.636 | 223 | 66,6 | 10.695 | 5.736 | 329 | 1.799,1 | 22.238 | 294.097 | +7,8 % |
| `g_co_empty` | 7.196,6 | 417,3 | 581 | 105 | 57,2 | 12.584 | 3.069 | 315 | 1.633,4 | 17.482 | 273.401 | +0,2 % |
| `g_co_empty_x30` **wenigste Überläufe** | 7.290,2 | 323,7 | 159 | 45 | 45,6 | 15.976 | 2.228 | 341 | 1.700,3 | 15.398 | 289.328 | +6,0 % |
| `d_status_quo_per_colour` | 6.943,5 | 670,5 | 19.047 | 1.196 | 67,0 | 10.363 | 9.640 | 658 | 2.541,3 | 39.292 | 517.183 | +89,6 % |
| `a_zero_overflow_per_colour` | 7.095,3 | 518,7 | 2.237 | 259 | 68,0 | 10.427 | 9.454 | 738 | 2.471,2 | 38.029 | 551.876 | +102,3 % |
| `g_co_empty_per_colour` | 7.173,5 | 440,4 | 1.034 | 155 | 60,8 | 11.800 | 5.461 | 710 | 2.012,8 | 27.844 | 501.918 | +84,0 % |

### Normierte Distanz: jeder Sprung 5 min

| Szenario | gesammelt t | Endbestand t | Überlauf-Tage | übervoll bei Leerung | Ø Füllstand % | Leerungen | Halte | Fahrzeugtage | Stunden | km | Kosten € | Δ Kosten |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `d_status_quo` | 6.943,5 | 670,5 | 19.047 | 1.196 | 67,0 | 10.363 | 3.714 | 233 | 893,0 | 19.008 | 186.007 | 0,0 % |
| `a_zero_overflow` | 7.095,3 | 518,7 | 2.237 | 259 | 68,0 | 10.427 | 7.797 | 290 | 1.551,6 | 25.266 | 260.725 | +40,2 % |
| `b_min_km` | 6.963,9 | 650,1 | 7.079 | 923 | 86,0 | 8.094 | 6.425 | 282 | 1.326,8 | 22.959 | 240.838 | +29,5 % |
| `c_max_fill` | 7.099,8 | 514,2 | 2.502 | 300 | 71,6 | 9.912 | 7.569 | 286 | 1.515,3 | 24.673 | 256.017 | +37,6 % |
| `e_mentor` | 7.206,1 | 407,8 | 485 | 101 | 52,7 | 13.676 | 7.278 | 295 | 1.474,2 | 25.185 | 258.219 | +38,8 % |
| `f_fixed_areas` | 7.143,1 | 470,8 | 1.958 | 216 | 60,3 | 11.842 | 4.668 | 236 | 1.051,8 | 14.898 | 194.999 | +4,8 % |
| `g_co_empty_x70` | 7.121,0 | 492,9 | 1.636 | 223 | 66,6 | 10.695 | 5.736 | 280 | 1.216,9 | 22.238 | 232.337 | +24,9 % |
| `g_co_empty` | 7.196,6 | 417,3 | 581 | 105 | 57,2 | 12.584 | 3.069 | 248 | 799,8 | 17.482 | 186.550 | +0,3 % |
| `g_co_empty_x30` **günstigste**, **wenigste Überläufe** | 7.290,2 | 323,7 | 159 | 45 | 45,6 | 15.976 | 2.228 | 248 | 679,5 | 15.398 | 177.496 | -4,6 % |
| `d_status_quo_per_colour` | 6.943,5 | 670,5 | 19.047 | 1.196 | 67,0 | 10.363 | 9.640 | 645 | 1.823,3 | 39.292 | 464.731 | +149,8 % |
| `a_zero_overflow_per_colour` | 7.095,3 | 518,7 | 2.237 | 259 | 68,0 | 10.427 | 9.454 | 695 | 1.781,5 | 38.029 | 486.235 | +161,4 % |
| `g_co_empty_per_colour` | 7.173,5 | 440,4 | 1.034 | 155 | 60,8 | 11.800 | 5.461 | 672 | 1.129,0 | 27.844 | 426.354 | +129,2 % |

### Normierte Distanz: jeder Sprung 10 min

| Szenario | gesammelt t | Endbestand t | Überlauf-Tage | übervoll bei Leerung | Ø Füllstand % | Leerungen | Halte | Fahrzeugtage | Stunden | km | Kosten € | Δ Kosten |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `d_status_quo` | 6.943,5 | 670,5 | 19.047 | 1.196 | 67,0 | 10.363 | 3.714 | 249 | 1.271,6 | 19.008 | 218.237 | 0,0 % |
| `a_zero_overflow` | 7.095,3 | 518,7 | 2.237 | 259 | 68,0 | 10.427 | 7.797 | 390 | 2.263,9 | 25.266 | 356.313 | +63,3 % |
| `b_min_km` | 6.963,9 | 650,1 | 7.079 | 923 | 86,0 | 8.094 | 6.425 | 332 | 1.925,5 | 22.959 | 304.155 | +39,4 % |
| `c_max_fill` | 7.099,8 | 514,2 | 2.502 | 300 | 71,6 | 9.912 | 7.569 | 381 | 2.211,9 | 24.673 | 348.099 | +59,5 % |
| `e_mentor` | 7.206,1 | 407,8 | 485 | 101 | 52,7 | 13.676 | 7.278 | 400 | 2.135,6 | 25.185 | 353.049 | +61,8 % |
| `f_fixed_areas` | 7.143,1 | 470,8 | 1.958 | 216 | 60,3 | 11.842 | 4.668 | 321 | 1.501,7 | 14.898 | 266.293 | +22,0 % |
| `g_co_empty_x70` | 7.121,0 | 492,9 | 1.636 | 223 | 66,6 | 10.695 | 5.736 | 323 | 1.763,2 | 22.238 | 288.800 | +32,3 % |
| `g_co_empty` | 7.196,6 | 417,3 | 581 | 105 | 57,2 | 12.584 | 3.069 | 279 | 1.125,2 | 17.482 | 222.876 | +2,1 % |
| `g_co_empty_x30` **günstigste**, **wenigste Überläufe** | 7.290,2 | 323,7 | 159 | 45 | 45,6 | 15.976 | 2.228 | 268 | 939,2 | 15.398 | 204.117 | -6,5 % |
| `d_status_quo_per_colour` | 6.943,5 | 670,5 | 19.047 | 1.196 | 67,0 | 10.363 | 9.640 | 671 | 2.711,7 | 39.292 | 534.588 | +145,0 % |
| `a_zero_overflow_per_colour` | 7.095,3 | 518,7 | 2.237 | 259 | 68,0 | 10.427 | 9.454 | 767 | 2.650,7 | 38.029 | 577.864 | +164,8 % |
| `g_co_empty_per_colour` | 7.173,5 | 440,4 | 1.034 | 155 | 60,8 | 11.800 | 5.461 | 697 | 1.670,9 | 27.844 | 473.536 | +117,0 % |

## Warum der reine Timer mehr km fährt (km-Modell, gegenüber Status quo)

Methode und Rohwerte: `data/outputs/scenarios/km_decomposition.json` (sequenzielle Zerlegung, keine eindeutige Zuordnung).

| Politik | Δ km gesamt | (1) mehr Leerungen | (2) Tages-Streuung / Sprunglänge | (3) Fahrzeuge Depot hin/zurück | (4) Entladefahrten | (5) Farben getrennt | Container je Halt (Status quo) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `a_zero_overflow` | 6.259 | 70 | -5.440 | 285 | -1.103 | 12.447 | 1,34 (2,79) |
| `e_mentor` | 6.178 | 3.598 | -4.135 | 873 | -1.362 | 7.203 | 1,88 (2,79) |
| `f_fixed_areas` | -4.109 | 1.624 | -7.142 | 19 | 91 | 1.299 | 2,54 (2,79) |
| `g_co_empty` | -1.526 | 2.555 | 491 | -509 | 563 | -4.626 | 4,10 (2,79) |

Lesart: (2) ist negativ, wenn mehr Halte pro Tag die Sprünge kürzer machen; die Streuung der Fälligkeiten zeigt sich daher vor allem in (5), nicht in der Sprunglänge.

## Einsparung durch Auslassen von Leerungen ≤ 20 % (Status quo, Mentor 15.11.)

Quelle: `data/outputs/scenarios/skip_savings.json`.

```json
{
  "question": "Zeitersparnis im Status quo, wenn Container mit Fuellstand <= 20 % nicht geleert werden (Mentor 15.11.)",
  "primary_world_consistent_replay": {
    "n_visits": 10363,
    "n_visits_le_20pct": 753,
    "share_pct": 7.27,
    "tonnage_in_those_visits_t": 106.013,
    "tonnage_note": "Glas bleibt im Container stehen und wird beim naechsten Besuch geholt - nicht verloren.",
    "lower_bound_service_only": {
      "saved_service_h": 62.75,
      "saved_drive_h": 0.0,
      "saved_total_h": 62.75,
      "saved_truck_days": 7.84,
      "saved_cost_eur": 7937.88
    },
    "site_aware_service_plus_hop_if_whole_site_skipped": {
      "saved_service_h": 62.75,
      "saved_drive_h": 14.05,
      "saved_total_h": 76.8,
      "saved_truck_days": 9.6,
      "saved_cost_eur": 9715.2
    },
    "upper_bound_service_plus_hop": {
      "saved_service_h": 62.75,
      "saved_drive_h": 105.32,
      "saved_total_h": 168.07,
      "saved_truck_days": 21.01,
      "saved_cost_eur": 21260.43
    }
  },
  "cross_check_raw_measured_readings": {
    "label": "Kreuzprobe mit gemessenen Fuellstaenden (level <= 20), nicht weltkonsistent",
    "n_visits": 10363,
    "n_visits_le_20pct": 1286,
    "share_pct": 12.41,
    "tonnage_in_those_visits_t": 220.3,
    "tonnage_note": "Glas bleibt im Container stehen und wird beim naechsten Besuch geholt - nicht verloren.",
    "lower_bound_service_only": {
      "saved_service_h": 107.17,
      "saved_drive_h": 0.0,
      "saved_total_h": 107.17,
      "saved_truck_days": 13.4,
      "saved_cost_eur": 13556.58
    },
    "site_aware_service_plus_hop_if_whole_site_skipped": {
      "saved_service_h": 107.17,
      "saved_drive_h": 19.35,
      "saved_total_h": 126.52,
      "saved_truck_days": 15.81,
      "saved_cost_eur": 16004.36
    },
    "upper_bound_service_plus_hop": {
      "saved_service_h": 107.17,
      "saved_drive_h": 179.63,
      "saved_total_h": 286.8,
      "saved_truck_days": 35.85,
      "saved_cost_eur": 36280.2
    }
  },
  "reference_status_quo_emptyings_w1": 10363,
  "assumptions": {
    "service_min_per_stop": 5.0,
    "hop_urban_min": 7.0,
    "hop_rural_min": 15.0,
    "rural_rule": "Annahme: Abstand zum Zentrum Heilbronn (49.1427, 9.2109) > 6.0 km = laendlich (W4 besitzt die verbindliche Regel)",
    "shift_h": 8.0,
    "rates": {
      "vehicle_day_eur": 500.0,
      "crew_hour_eur": 64.0,
      "km_eur": 0.65
    },
    "rates_label": "Annahme",
    "km_note": "km unbekannt -> 0 angesetzt; Kosten = Fahrzeugtage + Crew-h",
    "bounds": "lower = nur 5 min Service (andere Container am Standort werden ohnehin geleert); upper = Service + Fahrzeit-Hop je uebersprungenem Stopp; site_aware = Hop nur, wenn alle Container des Standorts am Tag <= 20 %."
  }
}
```

## Grenzen (ehrlich)

- **Standorte simuliert:** 449 IDs liegen zufällig auf 121 OSM-Punkten (`MODEL_SPEC.md` §10). Bündelung am Halt (Szenario g) ist dadurch in der Simulation leichter als in der Realität; absolute km/Halte sind illustrativ.
- **Mehrkammer oder ein LKW je Farbe ist unbekannt** → beide Varianten stehen in der Tabelle.
- **Kostensätze sind Annahmen**, keine PreZero-Preise.
- **Füllraten** aus gekappten Messungen (overfull = 110 %) unterschätzen stark überlaufende Container.
