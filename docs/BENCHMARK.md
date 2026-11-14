# Fair route benchmark

Generated from the same readings and coordinates for four dates (`2026-01-15, 2026-04-15, 2026-07-15, 2026-09-15`) and
three reproducible ID-to-coordinate mapping seeds (`7, 42, 1337`).

## Physical planning unit

Coordinates are rounded to 6 decimals and grouped before routing. At one point, all IDs and
material bins are one stop and their masses are summed. On 2026-04-15 / seed 42 this leaves
**121 real stops** overall and **73 critical stops**,
from **108 critical IDs**. Every route uses `OperationalConfig`:
11 t vehicle capacity, 8 h shift, yard start/end, and unloading at `disposal_depot`.

## 2026-04-15 table (seed 42)

| variant                   |   stops |      km |   vehicles |   rounds |      h |      t | nn_kept   |   runtime_s |
|:--------------------------|--------:|--------:|-----------:|---------:|-------:|-------:|:----------|------------:|
| B0 status quo             |     121 | 1768.84 |         94 |       94 | 169.57 | 808.22 | False     |       0.005 |
| B1 status quo optimized   |     121 | 1584.92 |         93 |       93 | 161.88 | 808.22 | False     |       0.142 |
| B2 demand-driven NN       |      73 |  297.3  |         13 |       13 |  24.56 | 125.12 | False     |       0.058 |
| B3 demand-driven + 2-opt  |      73 |  297.3  |         13 |       13 |  24.56 | 125.12 | True      |       0.166 |
| B4 demand-driven + solver |      73 |  292.84 |         12 |       12 |  24.05 | 125.12 | False     |       5.073 |

Runtime is measured per route calculation; solver time is capped at 30 seconds. B0 is the
paper-list order (ID sort), B1 is all-site nearest neighbor, B2 is critical-only nearest
neighbor, B3 adds 2-opt, and B4 uses OR-Tools CVRP capacity constraints. Each round is packed
under 11 t and includes a disposal-depot unload and return.

## Effects

* **Routing effect:** B2 → the best of B3/B4 saves **1.5%** of B2 distance with the same critical stops.
* **Demand effect:** B1 → B2 saves **81.2%** by removing non-critical physical sites while keeping nearest neighbor.
* **Overall effect:** B0 → the best variant saves **83.4%**.

## Robustness (all dates × seeds)

Mean and min–max spread are shown for distance, hours, and runtime:

| variant                   |   km_mean |   km_min |   km_max |   h_mean |   runtime_mean |   nn_kept_cases |   cases |   km_spread |
|:--------------------------|----------:|---------:|---------:|---------:|---------------:|----------------:|--------:|------------:|
| B0 status quo             |  1402.13  |  1125.95 |  1776.81 | 143.463  |     0.00683333 |               0 |      12 |      650.86 |
| B1 status quo optimized   |  1037.52  |   628.85 |  1584.92 | 128.907  |     0.145167   |               0 |      12 |      956.07 |
| B2 demand-driven NN       |   155.423 |    18.8  |   330.92 |  12.0592 |     0.0255     |               0 |      12 |      312.12 |
| B3 demand-driven + 2-opt  |   147.981 |    18.8  |   313.41 |  11.735  |     0.0695     |               2 |      12 |      294.61 |
| B4 demand-driven + solver |   146.313 |    18.8  |   298.55 |  11.5842 |     5.03425    |               1 |      12 |      279.75 |

## Assumptions

* Coordinates are the supplied synthetic/OSM-assigned mapping; ID seeds test mapping sensitivity,
  not alternative real-world locations.
* Mass is `2.5 m³ × fill level × 400 kg/m³`; route distance is Haversine × 1.35 and speed is 25 km/h.
* A round ends at the disposal depot after collection and returns to the yard. This conservative
  model makes the 11 t and 8 h limits explicit.
* B4 uses OR-Tools when installed; otherwise the documented fallback is B3 (2-opt).
* `nn_kept = True` means the 2-opt (B3) or solver (B4) order packed into legal rounds was longer
  than plain nearest neighbor, so the NN order was kept for that row. Its km then equal B2.
  `nn_kept_cases` in the robustness table counts how often that happened per variant.
