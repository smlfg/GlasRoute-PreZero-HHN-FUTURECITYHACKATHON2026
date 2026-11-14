# Fair route benchmark

Generated from the same readings and coordinates for four dates (`2026-01-15, 2026-04-15, 2026-07-15, 2026-09-15`) and
three reproducible ID-to-coordinate mapping seeds (`7, 42, 1337`).

## Physical planning unit

Coordinates are rounded to 6 decimals and grouped before routing. At one point, all IDs and
material bins are one stop and their masses are summed. On 2026-04-15 / seed 42 this leaves
**121 real stops** overall and **73 critical stops**,
from **108 critical IDs**. Every route uses `OperationalConfig`:
11 t and 26 m³ vehicle capacity, 8 h shift, yard start/end, and unloading at `disposal_depot`.

## 2026-04-15 table (seed 42)

| variant                   |   stops |      km |   vehicles |   rounds |      h |      t | nn_kept   |   runtime_s |
|:--------------------------|--------:|--------:|-----------:|---------:|-------:|-------:|:----------|------------:|
| B0 status quo             |     121 | 1795.91 |         95 |       95 | 170.99 | 808.22 | False     |       0.005 |
| B1 status quo optimized   |     121 | 1662.7  |         98 |       98 | 166.66 | 808.22 | False     |       0.142 |
| B2 demand-driven NN       |      73 |  316.31 |         14 |       14 |  25.65 | 125.12 | False     |       0.056 |
| B3 demand-driven + 2-opt  |      73 |  299.65 |         14 |       14 |  24.99 | 125.12 | False     |       0.158 |
| B4 demand-driven + solver |      73 |  285.79 |         13 |       13 |  24.1  | 125.12 | False     |       5.072 |

Runtime is measured per route calculation; solver time is capped at 30 seconds. B0 is the
paper-list order (ID sort), B1 is all-site nearest neighbor, B2 is critical-only nearest
neighbor, B3 adds 2-opt, and B4 uses OR-Tools CVRP capacity constraints. Each round is packed
under 11 t and includes a disposal-depot unload and return.

## Effects

* **Routing effect:** B2 → the best of B3/B4 saves **9.6%** of B2 distance with the same critical stops.
* **Demand effect:** B1 → B2 saves **81.0%** by removing non-critical physical sites while keeping nearest neighbor.
* **Overall effect:** B0 → the best variant saves **84.1%**.

## Robustness (all dates × seeds)

Mean and min–max spread are shown for distance, hours, and runtime:

| variant                   |   km_mean |   km_min |   km_max |   h_mean |   runtime_mean |   nn_kept_cases |   cases |   km_spread |
|:--------------------------|----------:|---------:|---------:|---------:|---------------:|----------------:|--------:|------------:|
| B0 status quo             |  1426.15  |  1159.7  |  1809.88 | 145.202  |        0.00725 |               0 |      12 |      650.18 |
| B1 status quo optimized   |  1078.32  |   667.16 |  1662.7  | 131.372  |        0.144   |               0 |      12 |      995.54 |
| B2 demand-driven NN       |   158.03  |    18.8  |   334.18 |  12.3025 |        0.02475 |               0 |      12 |      315.38 |
| B3 demand-driven + 2-opt  |   154.677 |    18.8  |   334.18 |  12.1692 |        0.0675  |               3 |      12 |      315.38 |
| B4 demand-driven + solver |   149.166 |    18.8  |   303.18 |  11.865  |        5.03375 |               2 |      12 |      284.38 |

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
