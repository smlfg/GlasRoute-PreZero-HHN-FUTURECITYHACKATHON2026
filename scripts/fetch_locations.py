#!/usr/bin/env python3
"""Fetch real Heilbronn glass sites and assign anonymized IDs transparently."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import ssl
import sys
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode, urlsplit

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from prezero.locations import (  # noqa: E402
    DEFAULT_REAL,
    assign_osm_sites,
    complete_locations,
    load_locations,
    location_stats,
    match_osm_locations,
    materials_from_tags,
    write_sanity_map,
)

OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
CANDIDATE_COLUMNS = ["osm_id", "lat", "lon", "material_tags", "source", "address"]
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 90
Transport = Callable[[str, bytes, dict[str, str], int, int], bytes]


class OverpassError(RuntimeError):
    """An Overpass transport, HTTP, or response error."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def overpass_query(admin_level: int) -> str:
    return (
        f'[out:json][timeout:90];\n'
        f'area["name"="Heilbronn"]["boundary"="administrative"]["admin_level"]="{admin_level}"]->.a;\n'
        f'( nwr["amenity"="recycling"]["recycling:glass_bottles"="yes"](area.a);\n'
        f'  nwr["amenity"="recycling"]["recycling:glass"="yes"](area.a); );\n'
        f'out center;'
    )


def _post_overpass(
    endpoint: str,
    body: bytes,
    headers: dict[str, str],
    connect_timeout: int,
    read_timeout: int,
) -> bytes:
    """POST with separate connect/read timeouts and no external dependency."""
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise OverpassError(f"Unsupported Overpass URL: {endpoint}")
    connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    kwargs = {"context": ssl.create_default_context()} if parsed.scheme == "https" else {}
    connection = connection_class(parsed.hostname, parsed.port, timeout=connect_timeout, **kwargs)
    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"
    try:
        connection.connect()
        if connection.sock is not None:
            connection.sock.settimeout(read_timeout)
        connection.request("POST", target, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read(10_000_001)
        if len(payload) > 10_000_000:
            raise OverpassError("Overpass response exceeds 10 MB safety limit")
        if response.status != 200:
            detail = payload[:500].decode("utf-8", errors="replace")
            raise OverpassError(f"Overpass HTTP {response.status}: {detail}", status=response.status)
        return payload
    except OverpassError:
        raise
    except (OSError, TimeoutError, http.client.HTTPException) as exc:
        raise OverpassError(f"Overpass transport failed: {exc}") from exc
    finally:
        connection.close()


def parse_overpass_payload(payload: bytes) -> pd.DataFrame:
    """Normalize real glass sites and area centers from Overpass JSON."""
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OverpassError(f"Invalid Overpass JSON: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("elements"), list):
        raise OverpassError("Overpass JSON has no elements list")

    rows: list[dict[str, object]] = []
    for element in document["elements"]:
        if not isinstance(element, dict) or element.get("type") not in {"node", "way", "relation"}:
            continue
        tags = element.get("tags", {})
        if not isinstance(tags, dict):
            continue
        materials, _, positive_tags = materials_from_tags(tags)
        if not materials:
            continue
        lat, lon = element.get("lat"), element.get("lon")
        if lat is None or lon is None:
            center = element.get("center", {})
            if isinstance(center, dict):
                lat, lon = center.get("lat"), center.get("lon")
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if not ((-90 <= lat <= 90) and (-180 <= lon <= 180)):
            continue
        encoded_tags = []
        for key in positive_tags:
            value = str(tags.get(key, "yes")).replace(";", "|")
            encoded_tags.append(f"{key}={value}" if key == "recycling:glass_bottles:colour" else key)
        address_parts = [
            " ".join(filter(None, [str(tags.get("addr:street", "")).strip(), str(tags.get("addr:housenumber", "")).strip()])),
            " ".join(filter(None, [str(tags.get("addr:postcode", "")).strip(), str(tags.get("addr:city", "")).strip()])),
        ]
        address = ", ".join(part for part in address_parts if part)
        if not address:
            address = str(tags.get("name") or tags.get("operator") or "")
        rows.append({
            "osm_id": f"{element['type']}/{element.get('id', 'unknown')}",
            "lat": lat,
            "lon": lon,
            "material_tags": ";".join(encoded_tags),
            "source": "openstreetmap",
            "address": address,
        })
    result = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    return result.drop_duplicates(subset="osm_id").sort_values("osm_id").reset_index(drop=True)


def _element_count(payload: bytes) -> int:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 0
    elements = document.get("elements", []) if isinstance(document, dict) else []
    return len(elements) if isinstance(elements, list) else 0


def fetch_real_candidates(
    mirrors: tuple[str, ...] = OVERPASS_MIRRORS,
    transport: Transport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[pd.DataFrame, bytes | None, list[str]]:
    """Try admin levels 6 then 8 and mirrors in the required order."""
    transport = transport or _post_overpass
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        "User-Agent": "prezero-routing-hackathon/0.1 (one-off Heilbronn research)",
        "Accept": "application/json",
    }
    errors: list[str] = []
    for admin_level in (6, 8):
        for mirror_number, endpoint in enumerate(mirrors, start=1):
            body = urlencode({"data": overpass_query(admin_level)}).encode("utf-8")
            try:
                payload = transport(endpoint, body, headers, CONNECT_TIMEOUT, READ_TIMEOUT)
                count = _element_count(payload)
                if count:
                    return parse_overpass_payload(payload), payload, errors
                errors.append(f"admin_level={admin_level}, mirror {mirror_number} {endpoint}: 0 elements")
            except (OverpassError, TimeoutError, OSError, ValueError) as exc:
                errors.append(f"admin_level={admin_level}, mirror {mirror_number} {endpoint}: {exc}")
            if mirror_number < len(mirrors):
                sleep(1.0)
    return pd.DataFrame(columns=CANDIDATE_COLUMNS), None, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default=ROOT / "data/raw/glass_fill_levels_anonymized_f.csv", type=Path)
    parser.add_argument("--output", default=ROOT / "data/external/locations_real_attempt.csv", type=Path)
    parser.add_argument("--raw-output", default=ROOT / "data/external/osm_glass_raw.json", type=Path)
    parser.add_argument("--matched-output", default=ROOT / "data/external/locations_matched.csv", type=Path)
    parser.add_argument("--locations-output", default=ROOT / "data/external/locations.csv", type=Path)
    parser.add_argument("--map-output", default=ROOT / "data/external/location_sanity_check.html", type=Path)
    return parser


def main(argv: list[str] | None = None, transport: Transport | None = None) -> dict[str, int]:
    args = build_parser().parse_args(argv)
    candidates, raw_payload, errors = fetch_real_candidates(transport=transport)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(args.output, index=False)
    for error in errors:
        print(f"WARNING: {error}", file=sys.stderr)

    if raw_payload is None:
        print("No OSM glass sites returned; leaving existing locations.csv unchanged")
        return {"total": 0, "provider_direct": 0, "osm_assigned": 0, "synthetic": 0}

    args.raw_output.write_bytes(raw_payload)
    raw = pd.read_csv(args.raw, dtype={"Location_id": "string"})
    resolved = match_osm_locations(raw, candidates)
    provider = load_locations(DEFAULT_REAL) if DEFAULT_REAL.is_file() else None
    resolved = complete_locations(raw, baseline=resolved, provider=provider)
    resolved.to_csv(args.matched_output, index=False)
    resolved.to_csv(args.locations_output, index=False)
    write_sanity_map(resolved, args.map_output)
    stats = location_stats(resolved)
    print(f"Real OSM glass sites: {len(candidates)}")
    print("Location statistics: " + ", ".join(f"{key}={value}" for key, value in stats.items()))
    print(f"Wrote {args.locations_output} and {args.map_output}")
    return stats


if __name__ == "__main__":
    main()
