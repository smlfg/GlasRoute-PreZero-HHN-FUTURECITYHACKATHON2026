"""Generate seeded synthetic fill-level CSVs for non-glass waste streams.

The output schema matches the real glass CSV exactly:
    Location_id, material_type, date, fill_level_perc

Each stream uses stream-specific assumptions from prezero_config.json
(density, container volume, fill speed, seasonality). The generated data
respects the measure-and-empty semantics used by the rest of the pipeline:
after a visit the container is empty, so the next visit finds a low level
and the level rises until the following emptying.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "prezero_config.json"
LOCATIONS_PATH = ROOT / "data" / "external" / "locations.csv"
OUTPUT_DIR = ROOT / "data" / "synthetic"

# Same overall date range as the real glass data.
START_DATE = date(2025, 10, 31)
END_DATE = date(2026, 9, 30)

STREAM_KEYS = ("paper", "bio", "gastro", "plastik")


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_location_ids(path: Path = LOCATIONS_PATH) -> list[str]:
    df = pd.read_csv(path, dtype={"Location_id": str})
    return sorted(df["Location_id"].astype(str).str.strip().unique().tolist())


def _weekend_factor(d: date) -> float:
    """Gastro peaks on weekends and around public holidays/events."""
    weekday = d.weekday()
    if weekday >= 5:  # Saturday / Sunday
        return 1.5
    return 1.0


def _event_factor(d: date, rng: random.Random) -> float:
    """Occasional event spikes for gastro (Heilbronner Weindorf etc.)."""
    # A handful of random long-weekend events across the year.
    if (d.month, d.day) in ((9, 10), (9, 11), (9, 12), (9, 19), (9, 20)):
        return 1.8
    if rng.random() < 0.015 and d.weekday() >= 3:  # Thu-Sun event
        return 1.6
    return 1.0


def _season_factor(config: dict[str, Any], d: date) -> float:
    factors = config.get("season_factor", {})
    return float(factors.get(str(d.month), factors.get(d.month, 1.0)))


def generate_location_series(
    location_id: str,
    stream_key: str,
    config: dict[str, Any],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """Generate one synthetic reading series for a single location/stream."""
    fill_speed = float(config.get("fill_speed", 1.0))
    base_rate_pp_per_day = 1.5 * fill_speed

    rows: list[dict[str, Any]] = []
    current = START_DATE

    # Stagger start dates a bit so not all containers are in sync.
    current += timedelta(days=rng.randint(0, 21))

    last_level: float | None = None
    while current <= END_DATE:
        season = _season_factor(config, current)

        if stream_key == "gastro":
            weekend = _weekend_factor(current)
            event = _event_factor(current, rng)
            daily_rate = base_rate_pp_per_day * season * weekend * event
        else:
            daily_rate = base_rate_pp_per_day * season

        # Interval between visits varies per stream and season.
        if stream_key == "gastro":
            interval_days = rng.randint(7, 14)
        elif stream_key == "bio":
            interval_days = rng.randint(10, 25)
        elif stream_key == "paper":
            interval_days = rng.randint(14, 35)
        else:  # plastik
            interval_days = rng.randint(12, 30)

        # In peak season visits can be a bit more frequent.
        if season >= 1.3:
            interval_days = max(5, interval_days - rng.randint(0, 5))

        # Level found at this visit (container was emptied at previous visit).
        if last_level is None:
            level = rng.uniform(20.0, 90.0)
        else:
            # Refill from ~0 after emptying.
            refill = daily_rate * interval_days
            noise = rng.uniform(-8.0, 10.0)
            level = max(5.0, min(110.0, refill + noise))

        # Encode extreme values as "overfull" occasionally.
        if level >= 110.0 and rng.random() < 0.7:
            fill_level = "overfull"
        else:
            fill_level = str(round(level))

        rows.append(
            {
                "Location_id": location_id,
                "material_type": stream_key,
                "date": current.isoformat(),
                "fill_level_perc": fill_level,
            }
        )

        last_level = float(level)
        current += timedelta(days=interval_days)

    return rows


def generate_stream(
    stream_key: str,
    config: dict[str, Any],
    location_ids: list[str],
    seed: int,
) -> pd.DataFrame:
    """Generate a complete synthetic CSV for one waste stream."""
    rng = random.Random(seed + hash(stream_key) % 10000)
    rows: list[dict[str, Any]] = []
    for loc_id in location_ids:
        rows.extend(generate_location_series(loc_id, stream_key, config, rng))
    df = pd.DataFrame(rows, columns=["Location_id", "material_type", "date", "fill_level_perc"])
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    return df.sort_values(["Location_id", "date"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate seeded synthetic fill-level CSVs for non-glass waste streams."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Random seed for reproducible generation.",
    )
    parser.add_argument(
        "--streams",
        nargs="+",
        choices=STREAM_KEYS,
        default=STREAM_KEYS,
        help="Which streams to generate (default: all).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory for generated CSVs.",
    )
    args = parser.parse_args()

    full_config = load_config()
    stream_configs = full_config.get("streams", {})
    location_ids = load_location_ids()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for stream_key in args.streams:
        if stream_key not in stream_configs:
            raise ValueError(f"No config for stream '{stream_key}' in {CONFIG_PATH}")
        df = generate_stream(stream_key, stream_configs[stream_key], location_ids, args.seed)
        output_path = args.output_dir / f"{stream_key}_fill_levels.csv"
        df.to_csv(output_path, index=False)
        print(
            f"Generated {stream_key}: {len(df)} readings for "
            f"{df['Location_id'].nunique()} locations -> {output_path}"
        )


if __name__ == "__main__":
    main()
