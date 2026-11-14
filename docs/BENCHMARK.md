# Fair route benchmark

Generated from the same readings and coordinates for four dates (`2026-01-15, 2026-04-15, 2026-07-15, 2026-09-15`) and
three reproducible ID-to-coordinate mapping seeds (`7, 42, 1337`).

## Physical planning unit

Coordinates are rounded to 6 decimals and grouped before routing. At one point, all IDs and
material bins are one stop and their masses are summed. On 2026-04-15 / seed 42 this leaves
**121 real stops** overall and **95 critical stops**,
from **169 critical IDs**. Every route uses `OperationalConfig`:
11 t vehicle capacity, 8 h shift, yard start/end, and unloading at `disposal_depot`.

## 2026-04-15 table (seed 42)

| variant                   |   stops |      km |   vehicles |   rounds |      h |     t |   runtime_s |
|:--------------------------|--------:|--------:|-----------:|---------:|-------:|------:|------------:|
| B0 status quo             |     121 | 1838.75 |        102 |      102 | 175.03 | 892.7 |       0.004 |
| B1 status quo optimized   |     121 | 1736.53 |        103 |      103 | 171.28 | 892.7 |       0.17  |
| B2 demand-driven NN       |      95 |  508.36 |         24 |       24 |  42.15 | 232.4 |       0.098 |
| B3 demand-driven + 2-opt  |      95 |  508.36 |         24 |       24 |  42.15 | 232.4 |       0.215 |
| B4 demand-driven + solver |      95 |  475.43 |         22 |       22 |  40.17 | 232.4 |       5.116 |

Runtime is measured per route calculation; solver time is capped at 30 seconds. B0 is the
paper-list order (ID sort), B1 is all-site nearest neighbor, B2 is critical-only nearest
neighbor, B3 adds 2-opt, and B4 uses OR-Tools CVRP capacity constraints. Each round is packed
under 11 t and includes a disposal-depot unload and return.

## Effects

* **Routing effect:** B2 → the best of B3/B4 saves **6.5%** of B2 distance with the same critical stops.
* **Demand effect:** B1 → B2 saves **70.7%** by removing non-critical physical sites while keeping nearest neighbor.
* **Overall effect:** B0 → the best variant saves **74.1%**.

## Robustness (all dates × seeds)

Mean and min–max spread are shown for distance, hours, and runtime:

| variant                   |   km_mean |   km_min |   km_max |   h_mean |   runtime_mean |   km_spread |
|:--------------------------|----------:|---------:|---------:|---------:|---------------:|------------:|
| B0 status quo             |  1721.23  |  1655.08 |  1838.75 | 167.06   |       0.00475  |      183.67 |
| B1 status quo optimized   |  1565.58  |  1440.54 |  1736.53 | 161.447  |       0.154083 |      295.99 |
| B2 demand-driven NN       |   208.602 |    32.99 |   532.3  |  16.2142 |       0.02775  |      499.31 |
| B3 demand-driven + 2-opt  |   204.255 |    32.63 |   523.25 |  15.9858 |       0.0625   |      490.62 |
| B4 demand-driven + solver |   190.571 |    32.63 |   475.43 |  15.245  |       5.03592  |      442.8  |

## Assumptions

* Coordinates are the supplied synthetic/OSM-assigned mapping; ID seeds test mapping sensitivity,
  not alternative real-world locations.
* Mass is `2.5 m³ × fill level × 400 kg/m³`; route distance is Haversine × 1.35 and speed is 25 km/h.
* A round ends at the disposal depot after collection and returns to the yard. This conservative
  model makes the 11 t and 8 h limits explicit.
* B4 uses OR-Tools when installed; otherwise the documented fallback is B3 (2-opt).
