#!/usr/bin/env python3
"""Refresh the canonical 449-location file and its source-coloured sanity map."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from prezero.locations import (  # noqa: E402
    DEFAULT_MATCHED,
    DEFAULT_REAL,
    assign_osm_sites,
    complete_locations,
    load_locations,
    location_stats,
    write_sanity_map,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default=ROOT / "data/raw/glass_fill_levels_anonymized_f.csv", type=Path)
    parser.add_argument("--real", type=Path, help="Direct provider CSV: Location_id,lat,lon[,source,confidence]")
    parser.add_argument("--synthetic", type=Path, help="Optional baseline instead of fresh OSM matching")
    parser.add_argument("--candidates", default=ROOT / "data/external/locations_real_attempt.csv", type=Path)
    parser.add_argument("--matched-output", default=ROOT / "data/external/locations_matched.csv", type=Path)
    parser.add_argument("--output", default=ROOT / "data/external/locations.csv", type=Path)
    parser.add_argument("--map-output", default=ROOT / "data/external/location_sanity_check.html", type=Path)
    return parser


def main(argv: list[str] | None = None) -> dict[str, int]:
    args = build_parser().parse_args(argv)
    raw = pd.read_csv(args.raw, dtype={"Location_id": "string"})

    real_path = args.real if args.real is not None else DEFAULT_REAL
    provider = load_locations(real_path) if real_path.is_file() else None
    if args.real is not None and provider is None:
        raise FileNotFoundError(f"Real provider file does not exist: {real_path}")

    real_candidates = 0
    if args.synthetic is not None:
        baseline = load_locations(args.synthetic)
    elif args.candidates.is_file():
        candidates = pd.read_csv(args.candidates)
        real_candidates = len(candidates)
        baseline = assign_osm_sites(raw, candidates)
    elif DEFAULT_MATCHED.is_file():
        baseline = load_locations(DEFAULT_MATCHED)
    else:
        baseline = None

    resolved = complete_locations(raw, baseline=baseline, provider=provider)
    args.matched_output.parent.mkdir(parents=True, exist_ok=True)
    resolved.to_csv(args.matched_output, index=False)
    resolved.to_csv(args.output, index=False)
    write_sanity_map(resolved, args.map_output)

    stats = location_stats(resolved)
    print(f"Real OSM glass candidates used: {real_candidates}")
    print("Location statistics: " + ", ".join(f"{key}={value}" for key, value in stats.items()))
    print(f"Wrote {args.output} and {args.map_output}")
    return stats


if __name__ == "__main__":
    main()
