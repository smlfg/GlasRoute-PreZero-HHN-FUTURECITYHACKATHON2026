# Upstream Research — GlasRoute (PreZero Glass Container Collection)

Context: GlasRoute models a **measure+empty** workflow (driver estimates fill level at emptying, `fill_rate = level / days_since_last_visit`), selects due containers, and routes multiple vehicles under dual capacity (`11 t` and `26 m³`, colour-specific glass density), an `8 h` shift limit, and intermediate unloading at a disposal site (NN / 2-opt / OR-Tools).

All links below were verified via HTTP `200` on 2026-11-15.

---

## 1. IRP, WCVRP-IF & Multi-Compartment / Dual Capacity

### 1. The multi-compartment vehicle routing problem with flexible compartment sizes
- **Authors & Year:** Tino Henke, M. Grazia Speranza, Gerhard Wäscher (2015)
- **Link:** https://doi.org/10.1016/j.ejor.2015.05.020
- **What it does:** Formulates and solves a multi-compartment VRP specifically motivated by colour-separated glass recycling, allowing flexible compartment sizes per vehicle.
- **Relation to GlasRoute:** **Better / we could cite it** — handles colour-specific glass compartments directly, whereas GlasRoute aggregates colour-specific densities into a joint `11 t` + `26 m³` vehicle capacity without compartment-partition constraints.

### 2. vrp-trash-collection (Open-Source, Google OR-Tools)
- **Authors & Year:** Celia V. Vergara (`cvvergara`), 2018–2023
- **Link:** https://github.com/cvvergara/vrp-trash-collection
- **What it does:** Implements a Capacitated, Multi-Trip VRPTW in Google OR-Tools following the exact `Deposit -> Containers -> Dump -> [Containers -> Dump] -> Deposit` cycle with shift time windows.
- **Relation to GlasRoute:** **Same** — models the identical intermediate-disposal multi-trip structure in OR-Tools, though with 1D capacity rather than GlasRoute's dual weight+volume (`11 t` / `26 m³`) constraint.

### 3. Urban-Waste-Collection (Open-Source, Groningen Case Study)
- **Authors & Year:** Niels Wouda (`N-Wouda`), 2021–2024
- **Link:** https://github.com/N-Wouda/Urban-Waste-Collection
- **What it does:** Provides a full simulation, forecasting, and routing pipeline (with OSRM matrices) evaluating container selection and routing policies on real municipal underground-container data from Groningen.
- **Relation to GlasRoute:** **Better** — couples forecasting and routing inside a rolling-horizon simulation loop, whereas GlasRoute runs a single-shot select-then-route pipeline.

---

## 2. Fill-Level Forecasting Without Continuous Sensors

### 4. Data analytics approach to create waste generation profiles for waste management and collection
- **Authors & Year:** Harri Niska, Ari Serkkola (2018)
- **Link:** https://doi.org/10.1016/j.wasman.2018.04.033
- **What it does:** Uses Self-Organizing Maps (SOM) and k-means clustering on container-level collection/weighing logs plus geospatial covariates to build waste-generation profiles without continuous IoT bin sensors.
- **Relation to GlasRoute:** **Better / we could cite it** — shows how sparse collection-event records can be clustered into container profiles, whereas GlasRoute uses a per-container deterministic rate (`level / days_since_last_visit`) from driver estimates.

---

## 3. Selection vs. Order: Threshold Policies & Overflow–Distance Trade-off

### 5. The effect of dynamic scheduling and routing in a solid waste management system
- **Authors & Year:** Ola M. Johansson (2006)
- **Link:** https://doi.org/10.1016/j.wasman.2005.09.004
- **What it does:** Evaluates dynamic container selection using `MustGo` / `MayGo` fill-level thresholds against static schedules, demonstrating significant distance and cost reductions.
- **Relation to GlasRoute:** **We could cite it** — foundational reference for threshold-based selective collection, whereas GlasRoute currently uses a single due-threshold (`MustGo`) without opportunistic `MayGo` insertion along the route.

### 6. Inventory routing for dynamic waste collection
- **Authors & Year:** Martijn Mes, Marco Schutten, Arturo Pérez Rivera (2014)
- **Link:** https://doi.org/10.1016/j.wasman.2014.05.011
- **What it does:** Solves a stochastic dynamic Inventory Routing Problem for waste containers using tunable `MustGo`/`MayGo` thresholds to balance driving distance against overflow penalties.
- **Relation to GlasRoute:** **Better** — jointly optimizes which `MayGo` containers to add based on route proximity and stochastic fill variance, whereas GlasRoute decouples selection from routing.

### 7. The smart waste collection routing problem: Alternative operational management approaches
- **Authors & Year:** Tânia Rodrigues Pereira Ramos, Carolina Soares de Morais, Ana Paula Barbosa-Póvoa (2018)
- **Link:** https://doi.org/10.1016/j.eswa.2018.03.001
- **What it does:** Compares static routes, simple threshold-based selective collection, and full dynamic IRP optimization, quantifying the trade-off between travelled kilometres, profit, and container overflows.
- **Relation to GlasRoute:** **We could cite it** — directly validates GlasRoute's threshold-selection paradigm against static routes while quantifying the remaining gap to joint selection-and-routing optimization.

---

## 4. Known Benchmarks & Datasets

### 8. Waste collection vehicle routing problem with time windows
- **Authors & Year:** Byung-In Kim, Seongbae Kim, Surya Sahoo (2006)
- **Link:** https://doi.org/10.1016/j.cor.2005.02.045
- **What it does:** Defines the canonical WCVRP-IF problem with multiple disposal trips and driver lunch breaks, and publishes standard real-world benchmark instances (up to 2,092 stops).
- **Relation to GlasRoute:** **Same / we could cite it** — established the standard WCVRP-IF benchmark formulation that matches GlasRoute's intermediate unloading and shift constraints.

### 9. Metaheuristics for the waste collection vehicle routing problem with time windows, driver rest period and multiple disposal facilities
- **Authors & Year:** A. M. Benjamin, J. E. Beasley (2010)
- **Link:** https://doi.org/10.1016/j.cor.2010.03.019
- **What it does:** Applies tabu search and variable neighborhood search to the Kim et al. (2006) WCVRP-IF benchmark instances with multiple disposal facilities and driver rest periods.
- **Relation to GlasRoute:** **Better** — provides metaheuristic baselines on the standard WCVRP-IF benchmarks that outperform simple NN + 2-opt construction/local search.

### 10. A variable neighborhood search for the multi-period collection of recyclable materials
- **Authors & Year:** Maria Elbek, Sanne Wøhlk (2016)
- **Link:** https://doi.org/10.1016/j.ejor.2015.08.035
- **What it does:** Solves a multi-period recyclable/glass collection IRP with stochastic fill levels and realistic Danish municipal benchmark instances using variable neighborhood search.
- **Relation to GlasRoute:** **Better** — models multi-period glass collection directly over a planning horizon with uncertainty, rather than GlasRoute's single-day deterministic snapshot.

---

## Synthesis

Our **routing** stack (threshold selection + dual-capacity WCVRP-IF with intermediate unloading and OR-Tools/2-opt) is **standard** OR practice, while our **measure+empty** fill-rate (`level / days_since_last_visit`) is **pragmatic yet slightly naive** because it omits stochastic safety buffers and opportunistic `MayGo` insertion—yet **practically smart** for a sensorless fleet by turning routine driver estimates into a zero-hardware soft sensor.
**Cite this one paper in the pitch:** **Ramos, Morais, & Barbosa-Póvoa (2018)** (*Expert Systems with Applications*, `10.1016/j.eswa.2018.03.001`), because it directly proves that threshold-based selective collection cuts kilometres and overflows compared to static schedules.
