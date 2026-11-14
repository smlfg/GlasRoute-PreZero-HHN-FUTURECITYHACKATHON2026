"""Domain model dataclasses and loader for GlasRoute."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SEASON_FACTORS: dict[int, float] = {
    1: 1.0,  # Annahme, von PreZero zu ersetzen
    2: 1.0,  # Annahme, von PreZero zu ersetzen
    3: 1.0,  # Annahme, von PreZero zu ersetzen
    4: 1.0,  # Annahme, von PreZero zu ersetzen
    5: 0.7,  # Annahme, von PreZero zu ersetzen
    6: 0.5,  # Annahme, von PreZero zu ersetzen
    7: 0.5,  # Annahme, von PreZero zu ersetzen
    8: 0.5,  # Annahme, von PreZero zu ersetzen
    9: 0.5,  # Annahme, von PreZero zu ersetzen
    10: 0.5,  # Annahme, von PreZero zu ersetzen
    11: 0.5,  # Annahme, von PreZero zu ersetzen
    12: 0.7,  # Annahme, von PreZero zu ersetzen
}


@dataclass(frozen=True)
class WasteStream:
    """Waste category and physical/seasonal assumptions."""

    name: str  # e.g. "glass_white", "paper", "bio"
    density_kg_per_m3: float = 400.0  # Annahme, von PreZero zu ersetzen
    container_volume_m3: float = 2.5  # Annahme, von PreZero zu ersetzen
    fill_speed: float = 1.0  # relative speed factor for synthetic generation
    season_factor: dict[int, float] = field(
        default_factory=lambda: dict(DEFAULT_SEASON_FACTORS)  # Annahme, von PreZero zu ersetzen
    )
    overfull_value: float = 110.0  # Annahme, von PreZero zu ersetzen
    display_name: str = ""
    synthetic: bool = False  # True for streams without real PreZero data

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "display_name", self.display_name or self.name.replace("_", " ").title()
        )

    def season_factor_for_month(self, month: int) -> float:
        """Return seasonal factor for a calendar month (1..12)."""
        return float(self.season_factor.get(int(month), 0.5))


# Glass streams (real PreZero data).
GLASS_WHITE = WasteStream(name="glass_white", display_name="Weißglas")
GLASS_GREEN = WasteStream(name="glass_green", display_name="Grünglas")
GLASS_BROWN = WasteStream(name="glass_brown", display_name="Braunglas")

# Synthetic waste streams used to demonstrate transferability of the pipeline.
PAPER = WasteStream(
    name="paper",
    density_kg_per_m3=80.0,
    container_volume_m3=3.0,
    fill_speed=1.3,
    season_factor={
        1: 1.2,
        2: 0.9,
        3: 0.8,
        4: 0.8,
        5: 0.8,
        6: 0.7,
        7: 0.7,
        8: 0.8,
        9: 0.9,
        10: 1.0,
        11: 1.3,
        12: 1.4,
    },
    display_name="Papier",
    synthetic=True,
)
BIO = WasteStream(
    name="bio",
    density_kg_per_m3=600.0,
    container_volume_m3=2.4,
    fill_speed=1.1,
    season_factor={
        1: 0.5,
        2: 0.6,
        3: 0.9,
        4: 1.2,
        5: 1.4,
        6: 1.5,
        7: 1.5,
        8: 1.4,
        9: 1.1,
        10: 0.9,
        11: 0.6,
        12: 0.5,
    },
    display_name="Bio",
    synthetic=True,
)
GASTRONOMIE = WasteStream(
    name="gastro",
    density_kg_per_m3=350.0,
    container_volume_m3=1.5,
    fill_speed=1.6,
    season_factor={
        1: 1.0,
        2: 1.0,
        3: 1.1,
        4: 1.1,
        5: 1.2,
        6: 1.3,
        7: 1.3,
        8: 1.2,
        9: 1.1,
        10: 1.1,
        11: 1.0,
        12: 1.1,
    },
    display_name="Gastronomie",
    synthetic=True,
)
PLASTIK = WasteStream(
    name="plastik",
    density_kg_per_m3=50.0,
    container_volume_m3=2.8,
    fill_speed=0.9,
    season_factor={
        1: 0.9,
        2: 0.9,
        3: 1.0,
        4: 1.1,
        5: 1.2,
        6: 1.2,
        7: 1.2,
        8: 1.1,
        9: 1.0,
        10: 1.0,
        11: 0.9,
        12: 0.9,
    },
    display_name="Plastik",
    synthetic=True,
)

WASTE_STREAMS: dict[str, WasteStream] = {
    "white": GLASS_WHITE,
    "green": GLASS_GREEN,
    "brown": GLASS_BROWN,
    "glass_white": GLASS_WHITE,
    "glass_green": GLASS_GREEN,
    "glass_brown": GLASS_BROWN,
    "paper": PAPER,
    "bio": BIO,
    "gastro": GASTRONOMIE,
    "plastik": PLASTIK,
}


def stream_for_material(material_name: str) -> WasteStream:
    """Return the WasteStream for a material_type value."""
    key = str(material_name).strip().lower()
    return WASTE_STREAMS.get(key, GLASS_WHITE)


@dataclass(frozen=True)
class Measurement:
    """One fill-level reading estimated by the driver at a container."""

    location_id: str
    timestamp: pd.Timestamp
    fill_pct: float
    estimated: bool = True  # Annahme, von PreZero zu ersetzen
    is_overfull: bool = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", pd.Timestamp(self.timestamp))
        object.__setattr__(self, "fill_pct", float(self.fill_pct))
        object.__setattr__(self, "is_overfull", float(self.fill_pct) >= 110.0)


@dataclass
class Container:
    """One physical recycling container identified by a chip Location_id at a Site."""

    location_id: str
    site_id: str
    waste_stream: WasteStream
    volume_m3: float = 2.5  # Annahme, von PreZero zu ersetzen
    measurements: list[Measurement] = field(default_factory=list)
    reference_date: pd.Timestamp | None = None

    def __post_init__(self) -> None:
        # Default volume comes from the waste stream if not explicitly supplied.
        if self.volume_m3 == 2.5 and self.waste_stream.container_volume_m3 != 2.5:
            object.__setattr__(self, "volume_m3", float(self.waste_stream.container_volume_m3))

    def last_fill(self) -> float:
        """Return latest recorded fill percentage (0.0 if no measurements)."""
        if not self.measurements:
            return 0.0
        latest = max(self.measurements, key=lambda m: m.timestamp)
        return float(latest.fill_pct)

    def days_since_last(self, reference_date: str | pd.Timestamp | None = None) -> int:
        """Return whole days elapsed since the latest measurement."""
        if not self.measurements:
            return 0
        latest_ts = max(m.timestamp for m in self.measurements)
        ref_ts = (
            pd.Timestamp(reference_date)
            if reference_date is not None
            else (self.reference_date if self.reference_date is not None else latest_ts)
        )
        return int((ref_ts - latest_ts).days)

    def avg_daily_increase(self) -> float:
        """Mean daily fill rate: level found at a visit / days since the previous (emptying) visit."""
        from prezero.features import fill_rates_after_emptying

        if len(self.measurements) < 2:
            return 0.0
        ordered = sorted(self.measurements, key=lambda m: m.timestamp)
        rates = fill_rates_after_emptying(
            [m.timestamp for m in ordered], [m.fill_pct for m in ordered]
        )
        return float(sum(rates) / len(rates)) if rates else 0.0

    def est_fill(self, reference_date: str | pd.Timestamp | None = None) -> float:
        """Estimated current level: emptied at the last visit, refilled at the average rate."""
        from prezero.features import elapsed_days, estimate_fill

        if not self.measurements:
            return 0.0
        latest_ts = max(m.timestamp for m in self.measurements)
        days = self.days_since_last(reference_date)
        return estimate_fill(
            self.avg_daily_increase(),
            elapsed_days(latest_ts, latest_ts + pd.Timedelta(days=days)),
        )

    def overfull_rate(self) -> float:
        """Return fraction of measurements at or above overfull threshold."""
        if not self.measurements:
            return 0.0
        overfull_count = sum(
            1 for m in self.measurements if m.fill_pct >= self.waste_stream.overfull_value
        )
        return float(overfull_count / len(self.measurements))

    def expected_mass_kg(self, fill: float | None = None) -> float:
        """Return expected waste mass in kg for a given fill percentage (defaults to est_fill)."""
        pct = self.est_fill() if fill is None else float(fill)
        return float(self.volume_m3) * (pct / 100.0) * float(self.waste_stream.density_kg_per_m3)


@dataclass
class Site:
    """A physical collection site holding one or more containers."""

    site_id: str
    lat: float
    lon: float
    source: str  # "prezero" | "osm_assigned" | "synthetic"
    confidence: str
    containers: list[Container] = field(default_factory=list)


@dataclass(frozen=True)
class Vehicle:
    """Collection truck specifications."""

    max_weight_kg: float = 11000.0  # Annahme, von PreZero zu ersetzen
    max_volume_m3: float = 26.0  # Annahme, von PreZero zu ersetzen
    avg_speed_kmh: float = 25.0  # Annahme, von PreZero zu ersetzen


@dataclass(frozen=True)
class Depot:
    """Yard and disposal depot coordinates and unloading duration."""

    yard_depot: tuple[float, float] = (49.1427, 9.2109)  # Annahme, von PreZero zu ersetzen
    disposal_depot: tuple[float, float] = (49.1780, 9.2085)  # Annahme, von PreZero zu ersetzen
    unload_time_min: float = 20.0  # Annahme, von PreZero zu ersetzen


@dataclass(frozen=True)
class ShiftConfig:
    """Driver shift duration, handling times, and road detour factor."""

    max_shift_hours: float = 8.0  # Annahme, von PreZero zu ersetzen
    stop_setup_min: float = 2.0  # Annahme, von PreZero zu ersetzen
    lift_time_per_bin_min: float = 3.0  # Annahme, von PreZero zu ersetzen
    road_detour_factor: float = 1.35  # Annahme, von PreZero zu ersetzen


def _resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute() or path.exists():
        return path
    return PROJECT_ROOT / path


def _normalize_source(raw_source: object) -> str:
    value = str(raw_source).strip().lower()
    if value in {"prezero", "prezero_supplied"}:
        return "prezero"
    if value in {"osm_assigned", "osm_heuristic"}:
        return "osm_assigned"
    if value in {"synthetic", "synthetic_placeholder"}:
        return "synthetic"
    return value


def _normalize_fill(value: object) -> float:
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned == "overfull":
            return 110.0
        return float(cleaned)
    return float(value)


def build_model(
    readings_df: pd.DataFrame | str | Path = "data/processed/cleaned_readings.csv",
    locations_df: pd.DataFrame | str | Path = "data/external/locations.csv",
) -> list[Site]:
    """Build the complete Site/Container/Measurement object graph from readings and locations."""
    if isinstance(readings_df, (str, Path)):
        readings = pd.read_csv(
            _resolve_path(readings_df),
            parse_dates=["date"],
            dtype={"Location_id": str, "material_type": str},
        )
    else:
        readings = readings_df.copy()

    if isinstance(locations_df, (str, Path)):
        locations = pd.read_csv(_resolve_path(locations_df), dtype={"Location_id": str})
    else:
        locations = locations_df.copy()

    readings = readings.copy()
    readings["Location_id"] = readings["Location_id"].astype(str).str.strip()
    readings["material_type"] = readings["material_type"].astype(str).str.strip().str.lower()
    readings["date"] = pd.to_datetime(readings["date"])
    if "fill_level_numeric" not in readings.columns:
        readings["fill_level_numeric"] = readings["fill_level_perc"].map(_normalize_fill)
    else:
        readings["fill_level_numeric"] = pd.to_numeric(readings["fill_level_numeric"], errors="raise")

    readings = readings.sort_values(["Location_id", "material_type", "date"]).reset_index(drop=True)
    max_dataset_date = pd.Timestamp(readings["date"].max()) if not readings.empty else None

    readings_by_series: dict[tuple[str, str], pd.DataFrame] = {
        (str(loc_id), str(material)): group
        for (loc_id, material), group in readings.groupby(
            ["Location_id", "material_type"], sort=False
        )
    }

    locs = locations.copy()
    locs["Location_id"] = locs["Location_id"].astype(str).str.strip()
    locs["lat"] = pd.to_numeric(locs["lat"], errors="raise")
    locs["lon"] = pd.to_numeric(locs["lon"], errors="raise")
    sites_by_location: dict[str, Site] = {}
    sites: list[Site] = []

    for row in locs.sort_values("Location_id").itertuples(index=False):
        site_id = f"site_{len(sites) + 1:03d}"
        location_id = str(row.Location_id)
        site = Site(
            site_id=site_id,
            lat=float(row.lat),
            lon=float(row.lon),
            source=_normalize_source(getattr(row, "source", "synthetic")),
            confidence=str(getattr(row, "confidence", "synthetic")).strip().lower(),
        )
        sites_by_location[location_id] = site
        sites.append(site)

    for row in locs.sort_values("Location_id").itertuples(index=False):
        loc_id = str(row.Location_id)
        site = sites_by_location[loc_id]
        material_names = sorted(
            material
            for (location_key, material) in readings_by_series
            if location_key == loc_id
        ) or ["white"]
        for material_name in material_names:
            mat_readings = readings_by_series.get((loc_id, material_name))
            if mat_readings is None:
                measurements: list[Measurement] = []
            else:
                mat_readings = mat_readings.sort_values("date")
                measurements = [
                    Measurement(
                        location_id=loc_id,
                        timestamp=pd.Timestamp(r.date),
                        fill_pct=float(r.fill_level_numeric),
                    )
                    for r in mat_readings.itertuples(index=False)
                ]
            stream = stream_for_material(material_name)
            container = Container(
                location_id=loc_id,
                site_id=site.site_id,
                waste_stream=stream,
                measurements=measurements,
                reference_date=max_dataset_date,
            )
            site.containers.append(container)

    return sites
