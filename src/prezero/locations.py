"""Resolve anonymized container IDs to labelled, replaceable coordinates.

OSM coordinates describe real recycling sites. Assigning them to anonymized
PreZero IDs is only a material-aware heuristic and therefore always ``low``.
Only a direct provider mapping (``Location_id,lat,lon``) receives ``high``.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXTERNAL_DIR = PROJECT_ROOT / "data" / "external"
DEFAULT_LOCATIONS = EXTERNAL_DIR / "locations.csv"
DEFAULT_REAL = EXTERNAL_DIR / "locations_real.csv"
DEFAULT_MATCHED = EXTERNAL_DIR / "locations_matched.csv"

# south, west, north, east; intentionally a bbox, not an administrative polygon.
HEILBRONN_BBOX = (49.09, 9.13, 49.23, 9.28)
SYNTHETIC_SEED = 2026
MATERIALS = frozenset({"brown", "green", "white"})
COLUMNS = ["Location_id", "lat", "lon", "source", "confidence", "match_reason"]
GENERAL_GLASS_TAGS = {"recycling:glass", "recycling:glass_bottles"}
COLOUR_TAGS = {
    "brown": "recycling:glass_brown",
    "green": "recycling:glass_green",
    "white": "recycling:glass_white",
}


def _path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute() or path.exists():
        return path
    return PROJECT_ROOT / path


def _read_csv(path: str | Path) -> pd.DataFrame:
    source = _path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Location file does not exist: {source}")
    return pd.read_csv(source, dtype={"Location_id": "string"})


def _validate_location_frame(df: pd.DataFrame) -> pd.DataFrame:
    required = {"Location_id", "lat", "lon"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Location CSV is missing columns: {sorted(missing)}")
    result = df.copy()
    result["Location_id"] = result["Location_id"].astype("string").str.strip()
    if result["Location_id"].isna().any() or result["Location_id"].eq("").any():
        raise ValueError("Location_id must be non-empty")
    if result["Location_id"].duplicated().any():
        duplicates = result.loc[result["Location_id"].duplicated(), "Location_id"].tolist()
        raise ValueError(f"Duplicate Location_id values: {duplicates[:3]}")
    for column in ("lat", "lon"):
        result[column] = pd.to_numeric(result[column], errors="raise")
        if not result[column].map(pd.notna).all():
            raise ValueError(f"{column} contains missing values")
    if not result["lat"].between(-90, 90).all() or not result["lon"].between(-180, 180).all():
        raise ValueError("Coordinates must be valid WGS84 latitude/longitude")

    if "source" not in result:
        result["source"] = "prezero_supplied"
    if "confidence" not in result:
        result["confidence"] = result["source"].map(
            lambda source: "synthetic" if source == "synthetic_placeholder" else "high"
        )
    if "match_reason" not in result:
        result["match_reason"] = result["source"].map(
            lambda source: (
                "deterministic synthetic fallback"
                if source == "synthetic_placeholder"
                else "direct Location_id mapping from supplied CSV"
            )
        )
    result["source"] = result["source"].fillna("").astype(str).str.strip()
    result["confidence"] = result["confidence"].fillna("").astype(str).str.strip().str.lower()
    result["match_reason"] = result["match_reason"].fillna("").astype(str).str.strip()
    if result["source"].eq("").any() or result["match_reason"].eq("").any():
        raise ValueError("source and match_reason must be non-empty")
    if not result["confidence"].isin({"high", "medium", "low", "synthetic", "simulated_mapping"}).all():
        raise ValueError("confidence must be high, medium, low, synthetic, or simulated_mapping")
    synthetic = result["source"].eq("synthetic_placeholder") | result["confidence"].eq("synthetic")
    if not (result.loc[synthetic, "source"].eq("synthetic_placeholder").all()
            and result.loc[synthetic, "confidence"].eq("synthetic").all()):
        raise ValueError("Synthetic rows must use source=synthetic_placeholder and confidence=synthetic")
    return result[COLUMNS + [c for c in result.columns if c not in COLUMNS]]


def load_locations(path: str | Path = "data/external/locations.csv") -> pd.DataFrame:
    """Load and validate coordinates; relative paths also work outside the repo cwd."""
    return _validate_location_frame(_read_csv(path))


def material_sets(raw_df: pd.DataFrame) -> dict[str, frozenset[str]]:
    """Return the normalized set of recorded glass colours for each location."""
    required = {"Location_id", "material_type"}
    missing = required - set(raw_df.columns)
    if missing:
        raise ValueError(f"Raw data is missing columns: {sorted(missing)}")
    if raw_df[list(required)].isna().any().any():
        raise ValueError("Location_id and material_type must be non-empty")
    normalized = raw_df[["Location_id", "material_type"]].copy()
    normalized["Location_id"] = normalized["Location_id"].astype("string").str.strip()
    normalized["material_type"] = normalized["material_type"].str.lower().str.strip()
    unknown = set(normalized["material_type"]) - MATERIALS
    if unknown:
        raise ValueError(f"Unknown material_type values: {sorted(unknown)}")
    return {
        str(location): frozenset(group["material_type"])
        for location, group in normalized.groupby("Location_id", sort=True)
    }


def materials_from_tags(tags: dict[str, object]) -> tuple[frozenset[str], bool, list[str]]:
    """Extract accepted colours and whether only general glass tagging is present."""
    materials: set[str] = set()
    general = False
    positive_tags: list[str] = []
    for key, raw_value in tags.items():
        value = str(raw_value).strip().lower()
        if key in GENERAL_GLASS_TAGS and value in {"yes", "true", "1"}:
            general = True
            positive_tags.append(key)
        for colour, colour_key in COLOUR_TAGS.items():
            if key == colour_key and value in {"yes", "true", "1"}:
                materials.add(colour)
                positive_tags.append(key)
        if key == "recycling:glass_bottles:colour":
            values = set(re.split(r"[;,|]", value))
            if "clear" in values:
                materials.add("white")
            materials.update(values & {"brown", "green"})
            if "mixed" in values:
                general = True
            if values & {"clear", "brown", "green", "mixed"}:
                positive_tags.append(key)
    if general:
        materials.update(MATERIALS)
    return frozenset(materials), general, sorted(set(positive_tags))


def _tags_from_text(value: object) -> dict[str, str]:
    if pd.isna(value):
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, tuple, set)):
        return {str(item): "yes" for item in value}
    tags: dict[str, str] = {}
    for item in re.split(r"[;,|]", str(value)):
        if not item.strip():
            continue
        key, separator, val = item.partition("=")
        tags[key.strip()] = val.strip() if separator else "yes"
    return tags


def _candidate_table(candidates_df: pd.DataFrame) -> list[dict[str, object]]:
    if candidates_df.empty:
        return []
    id_column = "osm_id" if "osm_id" in candidates_df else "provider_id" if "provider_id" in candidates_df else None
    if id_column is None or not {"lat", "lon"} <= set(candidates_df.columns):
        raise ValueError("Candidates need osm_id/provider_id, lat and lon")
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    for _, row in candidates_df.iterrows():
        candidate_id = str(row[id_column])
        if candidate_id in seen:
            raise ValueError(f"Duplicate candidate ID: {candidate_id}")
        seen.add(candidate_id)
        lat, lon = float(row["lat"]), float(row["lon"])
        if not ((-90 <= lat <= 90) and (-180 <= lon <= 180)):
            raise ValueError(f"Invalid candidate coordinates: {candidate_id}")
        tags = _tags_from_text(row.get("material_tags", ""))
        materials, general, _ = materials_from_tags(tags)
        if not materials:
            continue
        candidates.append({
            "id": candidate_id, "lat": lat, "lon": lon,
            "materials": materials, "general": general,
        })
    return sorted(candidates, key=lambda candidate: str(candidate["id"]))


def _candidate_score(target: frozenset[str], candidate: dict[str, object]) -> int:
    materials = candidate["materials"]
    assert isinstance(materials, frozenset)
    if candidate["general"]:
        return 80 if len(target) == 1 else 60
    if target == materials:
        return 100
    if target < materials:
        return 75 - 5 * len(materials - target)
    overlap = len(target & materials)
    return 20 * overlap - 25 * len(target - materials) - len(materials - target)


def match_osm_locations(
    raw_df: pd.DataFrame,
    candidates_df: pd.DataFrame,
) -> pd.DataFrame:
    """Assign each ID a distinct OSM site, preferring material-compatible sites.

    The mapping is a heuristic, never a verified identity: anonymous PreZero IDs
    carry no geographic key. Every result is therefore labelled
    ``source=osm_heuristic``, ``confidence=low`` and an ``UNVERIFIED`` reason.
    """
    colours = material_sets(raw_df)
    candidates = _candidate_table(candidates_df)
    if not candidates:
        return complete_locations(raw_df)

    # Greedy assignment over the highest-scoring candidate per ID, keeping the
    # mapping one-to-one: a site is consumed once it has been assigned.
    ordered_ids = sorted(colours)
    remaining = list(candidates)
    rows: list[dict[str, object]] = []
    for location_id in ordered_ids:
        target = colours[location_id]
        if not remaining:
            break
        best_index = max(
            range(len(remaining)),
            key=lambda index: (
                _candidate_score(target, remaining[index]),
                -index,
            ),
        )
        candidate = remaining.pop(best_index)
        score = _candidate_score(target, candidate)
        tag_note = "general_glass_tag" if candidate["general"] else "colour_match"
        rows.append({
            "Location_id": location_id,
            "lat": candidate["lat"],
            "lon": candidate["lon"],
            "source": "osm_heuristic",
            "confidence": "low",
            "match_reason": (
                f"UNVERIFIED anonymous-ID assignment; OSM={candidate['id']}; "
                f"{tag_note}; score={score}; no geographic PreZero key"
            ),
        })

    assigned = pd.DataFrame(rows, columns=COLUMNS)
    return complete_locations(raw_df, baseline=assigned)


def assign_osm_sites(
    raw_df: pd.DataFrame,
    candidates_df: pd.DataFrame,
    seed: int = SYNTHETIC_SEED,
) -> pd.DataFrame:
    """Assign all IDs to real OSM sites using a deterministic simulated mapping."""
    colours = material_sets(raw_df)
    candidates = _candidate_table(candidates_df)
    if not candidates:
        return complete_locations(raw_df)

    ordered_ids = sorted(colours)
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    for location_id in ordered_ids:
        candidate = candidates[rng.randrange(len(candidates))]
        rows.append({
            "Location_id": location_id,
            "lat": candidate["lat"],
            "lon": candidate["lon"],
            "source": "osm_assigned",
            "confidence": "simulated_mapping",
            "match_reason": "real OSM site, ID assignment simulated",
        })
    return complete_locations(raw_df, pd.DataFrame(rows, columns=COLUMNS))


def synthetic_locations(location_ids: Iterable[str], seed: int = SYNTHETIC_SEED) -> pd.DataFrame:
    """Generate deterministic placeholders in the documented Heilbronn bbox."""
    rng = random.Random(seed)
    south, west, north, east = HEILBRONN_BBOX
    rows = []
    for location_id in sorted(set(location_ids)):
        rows.append({
            "Location_id": location_id,
            "lat": round(rng.uniform(south, north), 6),
            "lon": round(rng.uniform(west, east), 6),
            "source": "synthetic_placeholder",
            "confidence": "synthetic",
            "match_reason": f"deterministic seed={seed}; no verified real coordinate",
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def complete_locations(
    raw_df: pd.DataFrame,
    baseline: pd.DataFrame | None = None,
    provider: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Overlay baseline then direct provider rows on a complete synthetic base."""
    expected = set(material_sets(raw_df))
    result = synthetic_locations(expected).set_index("Location_id", drop=False)
    if baseline is not None and not baseline.empty:
        base = _validate_location_frame(baseline)
        base = base[base["Location_id"].isin(expected)]
        for row in base.itertuples(index=False):
            result.loc[row.Location_id, COLUMNS] = [getattr(row, column) for column in COLUMNS]
    if provider is not None and not provider.empty:
        direct = _validate_location_frame(provider)
        direct = direct[direct["Location_id"].isin(expected)]
        for row in direct.itertuples(index=False):
            result.loc[row.Location_id, COLUMNS] = [
                row.Location_id, row.lat, row.lon, "prezero_supplied", "high",
                "direct Location_id mapping supplied by PreZero/provider",
            ]
    return _validate_location_frame(result.reset_index(drop=True)[COLUMNS])


def resolve_locations(
    raw_df: pd.DataFrame,
    real_path: str | Path | None = None,
    synthetic_path: str | Path | None = None,
) -> pd.DataFrame:
    """Resolve with direct provider priority, then best baseline, then placeholders.

    Explicit ``real_path`` wins. Otherwise ``locations_real.csv`` is discovered
    automatically. A partial provider file overrides only the IDs it contains.
    """
    provider_path = _path(real_path) if real_path is not None else DEFAULT_REAL
    provider = load_locations(provider_path) if provider_path.is_file() else None
    if real_path is not None and provider is None:
        raise FileNotFoundError(f"Location file does not exist: {provider_path}")

    if synthetic_path is not None:
        baseline = load_locations(synthetic_path)
    elif DEFAULT_MATCHED.is_file():
        baseline = load_locations(DEFAULT_MATCHED)
    elif DEFAULT_LOCATIONS.is_file():
        baseline = load_locations(DEFAULT_LOCATIONS)
    else:
        baseline = None
    return complete_locations(raw_df, baseline=baseline, provider=provider)


def location_stats(df: pd.DataFrame) -> dict[str, int]:
    counts = df["source"].value_counts()
    return {
        "total": len(df),
        "provider_direct": int(counts.get("prezero_supplied", 0)),
        "osm_heuristic": int(counts.get("osm_heuristic", 0)),
        "osm_assigned": int(counts.get("osm_assigned", 0)),
        "synthetic": int((df["confidence"] == "synthetic").sum()),
    }


def write_sanity_map(df: pd.DataFrame, path: str | Path) -> None:
    """Write a source-coloured map, with a stdlib Leaflet fallback."""
    locations = _validate_location_frame(df)
    output = _path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        import folium
    except ImportError:
        _write_leaflet_fallback(locations, output)
        return
    center = [float(locations["lat"].mean()), float(locations["lon"].mean())]
    map_object = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")
    for row in locations.itertuples(index=False):
        folium.CircleMarker(
            location=[row.lat, row.lon], radius=4,
            color=_source_colour(row.source), fill=True, fill_opacity=0.65,
            tooltip=f"{row.Location_id} — {row.source}/{row.confidence}",
            popup=f"{row.match_reason}<br>© OpenStreetMap contributors, ODbL",
        ).add_to(map_object)
    map_object.save(str(output))


def _source_colour(source: str) -> str:
    return {
        "prezero_supplied": "#15803d",
        "osm_assigned": "#2563eb",
        "synthetic_placeholder": "#dc2626",
    }.get(source, "#ea580c")


def _write_leaflet_fallback(locations: pd.DataFrame, output: Path) -> None:
    records = [
        {
            "id": row.Location_id, "lat": row.lat, "lon": row.lon,
            "source": row.source, "confidence": row.confidence,
            "reason": row.match_reason, "colour": _source_colour(row.source),
        }
        for row in locations.itertuples(index=False)
    ]
    payload = json.dumps(records, ensure_ascii=False).replace("<", "\\u003c")
    center = [float(locations["lat"].mean()), float(locations["lon"].mean())]
    html = """<!doctype html><html><head><meta charset="utf-8"><title>Location sanity check</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>html,body,#map{height:100%;margin:0}.note{position:absolute;z-index:1000;background:white;padding:8px;right:8px;top:8px;max-width:360px}</style></head>
<body><div class="note">Blue: unverified OSM heuristic · Red: synthetic · Green: direct provider<br>OSM mappings are not verified PreZero identities.</div><div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
const points=__POINTS__;const map=L.map('map').setView(__CENTER__,11);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, ODbL'}).addTo(map);
for(const p of points){const marker=L.circleMarker([p.lat,p.lon],{radius:4,color:p.colour,fillOpacity:.65}).addTo(map);marker.bindTooltip(p.id+' — '+p.source+'/'+p.confidence);marker.bindPopup(p.reason);}
</script></body></html>"""
    output.write_text(html.replace("__POINTS__", payload).replace("__CENTER__", json.dumps(center)), encoding="utf-8")
