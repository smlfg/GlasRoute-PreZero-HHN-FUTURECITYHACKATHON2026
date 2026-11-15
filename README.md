# PreZero Route — Dynamic Glass Collection Routing for Heilbronn

Prototype for the PreZero Challenge at Future City Hackathon 2026.

## Problem

PreZero empties glass containers in Heilbronn on fixed routes. Trucks visit half-empty bins while others overflow. For the demo day (2026-04-15) the data shows **106 critical physical sites** with **509 critical containers**, **488 of them estimated ≥ 110 % full**.

## Solution in 4 steps

1. **Daten** — Ingest the real PreZero fill-level CSV (**11,701 measurements, 449 containers**).
2. **Auswahl** — Score containers by fill rate, overfull frequency and seasonality; pick the 25 most critical stops for the day.
3. **Tour** — OR-Tools builds a capacity-constrained route for the selected stops.
4. **Entscheidung** — The dispatcher approves or rejects the proposal; nothing is dispatched without approval.

## Demo result (2026-04-15)

Numbers from `Pitch/demo_facts.txt` / `route_2026-04-15.json`:

| | |
|---|---|
| Critical physical sites (containers) | 127 (509) |
| Containers estimated ≥ 110 % full | 488 |
| Stops in tour | 25 |
| Planned tour | 227.23 km |
| Full round, same rules, all 142 sites | 1,368.78 km |
| Saved vs. full round | 1,141.55 km (83.4 %) |
| Vehicles / rounds | 3 / 16 |
| Vehicle hours / longest shift | 19.85 h / 7.96 h (limit 8.0 h) |
| Collected | 116.18 t |

## What is real vs. simulated

- **Real:** 11,701 fill-level measurements from PreZero.
- **Simulated:** The mapping from anonymised PreZero IDs to coordinates. All locations are real OpenStreetMap glass-container points in Heilbronn, but the ID-to-point assignment is a deterministic simulation (`seed = 2026`, `source = osm_assigned`, `confidence = simulated_mapping`). Replace it by putting real `Location_id, lat, lon` data into `data/external/locations_real.csv` and running `scripts/refresh_locations.py --real ...` — no code changes required.

## Run it

```bash
prezero-route run --date 2026-04-15
```

Creates `route_2026-04-15.json`, `map_2026-04-15.html` and `trends.png`.

## Tech choices

- **OR-Tools** — Solves the capacitated vehicle-routing problem with vehicle, shift and transfer limits.
- **Measure+empty model** — Estimates the next due date from the last measured fill level and days since empty; uses existing data only, no ML forecast.
- **Python CLI** — Reproducible pipeline: ingest → features → score → route → visualise.
- **Haversine distance** — Placeholder until real street distances are available.
- **Folium + Matplotlib** — Static maps and trend charts; no dashboard overhead.

## Limits & next steps

- Coordinates use a simulated ID-to-OSM mapping; the swap path to real PreZero coordinates is ready.
- Distances are straight-line with a detour factor, not street routing.
- Operational variables (vehicle capacity, glass density, shift length) are assumptions in `prezero_config.json`.
- No multi-day fleet optimisation yet.

Next: real PreZero coordinates, real operational variables, street-routing integration.
