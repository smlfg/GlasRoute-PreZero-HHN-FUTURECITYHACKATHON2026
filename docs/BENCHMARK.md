# Fair route benchmark

Generated from the same readings and coordinates for four dates (`2026-01-15, 2026-04-15, 2026-07-15, 2026-09-15`) and
three reproducible ID-to-coordinate mapping seeds (`7, 42, 1337`).

## Physical planning unit

Coordinates are rounded to 6 decimals and grouped before routing. At one point, all IDs and
material bins are one stop and their masses are summed. On 2026-04-15 / seed 42 this leaves
**121 real stops** overall and **112 critical stops**,
from **276 critical IDs**. Every route uses `OperationalConfig`:
11 t and 26 m³ vehicle capacity, 8 h shift, yard start/end, and unloading at `disposal_depot`.

## 2026-04-15 table (seed 42)

| variant                   |   stops |      km |   vehicles |   rounds |      h |      t | nn_kept   |   runtime_s |
|:--------------------------|--------:|--------:|-----------:|---------:|-------:|-------:|:----------|------------:|
| B0 status quo             |     121 | 1795.91 |         95 |       95 | 170.99 | 808.54 | False     |       0.005 |
| B1 status quo optimized   |     121 | 1662.7  |         98 |       98 | 166.66 | 808.54 | False     |       0.146 |
| B2 demand-driven NN       |     112 | 1165.9  |         67 |       67 |  98.15 | 529.43 | False     |       0.126 |
| B3 demand-driven + 2-opt  |     112 | 1165.9  |         67 |       67 |  98.15 | 529.43 | True      |       0.305 |
| B4 demand-driven + solver |     112 | 1053.29 |         55 |       55 |  89.65 | 529.43 | False     |       0.314 |

Runtime is measured per route calculation; the OR-Tools solver stops deterministically after a fixed limit of 25 solutions (`solution_limit = 25`) for reproducible results. B0 is the
paper-list order (ID sort), B1 is all-site nearest neighbor, B2 is critical-only nearest
neighbor, B3 adds 2-opt, and B4 uses OR-Tools CVRP capacity constraints. Each round is packed
under 11 t and includes a disposal-depot unload and return.

## Effects

* **Routing effect:** B2 → the best of B3/B4 saves **9.7%** of B2 distance with the same critical stops.
* **Demand effect:** B1 → B2 saves **29.9%** by removing non-critical physical sites while keeping nearest neighbor.
* **Overall effect:** B0 → the best variant saves **41.4%**.

## Robustness (all dates × seeds)

Mean and min–max spread are shown for distance, hours, and runtime:

| variant                   |   km_mean |   km_min |   km_max |   h_mean |   runtime_mean |   nn_kept_cases |   cases |   km_spread |
|:--------------------------|----------:|---------:|---------:|---------:|---------------:|----------------:|--------:|------------:|
| B0 status quo             |  1605.26  |  1446.99 |  1809.88 | 158.533  |     0.00583333 |               0 |      12 |      362.89 |
| B1 status quo optimized   |  1352.65  |  1095.19 |  1662.7  | 148.317  |     0.146917   |               0 |      12 |      567.51 |
| B2 demand-driven NN       |   691.509 |   380.47 |  1165.9  |  57.39   |     0.0844167  |               0 |      12 |      785.43 |
| B3 demand-driven + 2-opt  |   684.87  |   364.68 |  1165.9  |  57.0692 |     0.196833   |               4 |      12 |      801.22 |
| B4 demand-driven + solver |   643.165 |   333.73 |  1074.69 |  53.5958 |     0.203583   |               2 |      12 |      740.96 |

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
