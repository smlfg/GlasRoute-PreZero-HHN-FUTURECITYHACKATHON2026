# PreZero Route – Dynamic Glass Collection Routing for Heilbronn

Prototype for the **PreZero Challenge** at Future City Hackathon 2026 (HHN TechCampus Heilbronn).

Turns fill-level data from glass recycling containers into a prioritized, human-approved collection route.

## Problem

Glass containers in Heilbronn are emptied on a fixed schedule, regardless of how full they actually are. Trucks drive to half-empty containers while others overflow. That wastes fuel, time, and CO₂.

## Solution

A CLI tool that:

1. Ingests fill-level CSV data.
2. Analyzes patterns (material, season, overfull frequency).
3. Scores container criticality for a target day.
4. Builds a route for one collection vehicle.
5. Presents the route for dispatcher approval (Human-Agent Interface).

## Quick start

```bash
# Install
pip install -e .

# Resolve container coordinates (OpenStreetMap attempt + deterministic fallback)
python scripts/fetch_locations.py

# Refresh from the best available source / apply PreZero coordinates later
python scripts/refresh_locations.py

# Run full demo
python scripts/01_ingest.py
python scripts/02_analyze.py
python scripts/03_score.py
python scripts/04_route.py
python scripts/05_visualize.py

# Or use the CLI
prezero-route ingest
prezero-route analyze
prezero-route score --date 2026-04-15
prezero-route route --date 2026-04-15
prezero-route visualize
```

## Data

- `data/raw/glass_fill_levels_anonymized_f.csv` – provided by PreZero (11.701 readings, 449 containers).
- `data/external/locations_real_attempt.csv` – real candidate glass containers fetched from open data (Overpass/OSM) with `osm_id/provider_id`, coordinates, material tags, source and address where available.
- `data/external/locations_matched.csv` – per-`Location_id` resolution before final override: heuristic OSM assignments (`confidence=low`, explicitly unverified without a PreZero key) or deterministic synthetic placeholders.
- `data/external/locations.csv` – **canonical** pipeline input with exactly 449 rows (`Location_id, lat, lon, source, confidence, match_reason`).
- `data/external/location_sanity_check.html` – sanity map colored by source.
- `data/external/locations_synthetic.csv` – legacy placeholder file; prefer `locations.csv` / `refresh_locations.py`.

## Geo coordinates / PreZero swap

The location resolver is source-agnostic and labels every coordinate. OSM points are real places, but assigning them to anonymized IDs is heuristic unless PreZero supplies the mapping.

To replace synthetic or heuristic coordinates with real ones:

1. Place real coordinates in `data/external/locations_real.csv` (minimum columns: `Location_id, lat, lon`).
2. Run `python scripts/refresh_locations.py --real data/external/locations_real.csv`.
3. The pipeline automatically uses the real data (`locations_real.csv` is preferred and written into `locations.csv`; no code changes required).

Programmatic use:

```python
from prezero.locations import load_locations, resolve_locations

df = load_locations()  # reads data/external/locations.csv by default
# or resolve from raw readings with an explicit provider file:
# df = resolve_locations(raw_df, real_path="data/external/locations_real.csv")
```

`fetch_locations.py` fails gracefully: if Overpass is unavailable it records the error, writes an empty candidate file and still produces complete, labeled synthetic coordinates and the sanity map.

## Docs

- `docs/ANFORDERUNGEN.md` – challenge requirements
- `docs/ARCHITEKTUR.md` – technical architecture and geo swap path
- `docs/GEO_DATENQUELLEN.md` – checked open-data sources, limits, licenses/attribution
- `docs/PITCH.md` – Sunday pitch structure
- `PLAN.md` – hackathon plan with checkpoints
