"""Emptying policies a–h (docs/MODEL_SPEC.md §5, §9.4/§9.5).

Every policy only sees ``DayContext`` (walk-forward r̂, age since last emptying, calendar)
and ``Static`` (geometry, calendar, real visit dates). Estimated fill = r̂_c(d) × age_c.
Target = 100 − buffer_pct (default 80 %). Co-empty at a stop (``bundle_threshold``) is
applied by the engine after ``decide``; default None = only DUE containers of a stop are
emptied (MODEL_SPEC §10, today's behaviour). Only (g) switches it on.

(a) a_zero_overflow  — Timer: on an operating day empty c if its estimated fill on the NEXT
    operating day would be ≥ target  (r̂·(age + gap) ≥ target). Looks one operating day ahead,
    so it empties at ≈ target − r̂·gap ("just before the target").
(b) b_min_km         — As late as possible, no buffer: same look-ahead rule with 100 %
    instead of the target (r̂·(age + gap) ≥ 100). Fewer emptyings, more overflow risk.
(c) c_max_fill       — Cadence: T_c = floor(target / r̂_c(d)) days (≥ 1, re-estimated daily),
    empty on the first operating day with age ≥ T_c. Difference to (a): no look-ahead; it
    empties once the estimated fill TODAY has reached ≈ target (rounded to whole days), i.e.
    one operating gap later than (a) → fuller containers, slightly more overflow risk.
(d) d_status_quo     — Replay of the real visit dates (all readings after the first one,
    incl. Saturdays); no bundling. Reproduces W1's status quo (6,943.50 t, 10,363 emptyings).
(e) e_mentor         — Status-quo visit dates as the plan. A planned visit with estimated fill
    ≤ skip_pct (20 %) is skipped and the container goes into a 14-day rhythm: further planned
    visits within 14 days of that skip are skipped as well. Rescue: on an operating day,
    any container whose estimated fill on the next operating day would be ≥ target and whose
    next (non-skipped) planned visit lies after that day is emptied today (the time saved by
    skipping goes to critical sites). ``skipped_ever`` marks the 14-day containers.
(g) g_co_empty       — Policy (a) + co-empty: when a stop (physical lat/lon point) is visited,
    every other active container there with estimated fill ≥ X (default 50 %; also run with
    30 / 70) is emptied as well. In truck_mode=per_colour only within the same colour.
(f) f_fixed_areas    — 5 geographic areas (k-means on container lat/lon, numpy, seed 0),
    ordered west→east by centroid longitude = Mon..Fri. Area days = that weekday every week;
    a holiday shifts it to the next operating day. On an area day empty c if its estimated
    fill on the area's NEXT area day would be ≥ target.
(h) h_area_week_rhythm — Dispatcher's week rhythm on the areas of (f); see ``AreaWeekRhythm``.
"""

from __future__ import annotations

import numpy as np

from prezero.sim.engine import DayContext, Static

INF_DAY = 10**9


class _Base:
    id = "base"
    label = ""

    def __init__(self, buffer_pct: float = 20.0, bundle_threshold: float | None = None):
        self.buffer_pct = float(buffer_pct)
        self.bundle_threshold = bundle_threshold

    @property
    def target(self) -> float:
        return 100.0 - self.buffer_pct

    def setup(self, static: Static) -> None:
        self.static = static

    def decide(self, ctx: DayContext) -> np.ndarray:  # pragma: no cover - abstract
        raise NotImplementedError


class ZeroOverflow(_Base):
    id = "a_zero_overflow"
    label = "(a) 0 % Überlauf: Timer mit Puffer, leert vor dem Ziel am nächsten Betriebstag"

    def __init__(self, *args, id: str | None = None, **kw):
        super().__init__(*args, **kw)
        if id:
            self.id = id

    def decide(self, ctx: DayContext) -> np.ndarray:
        if not ctx.is_op:
            return np.zeros(ctx.active.size, dtype=bool)
        return ctx.active & (ctx.est_rate * (ctx.age + ctx.gap) >= self.target)


class MinKm(_Base):
    id = "b_min_km"
    label = "(b) min km: so spät wie möglich, leert vor 100 % am nächsten Betriebstag"

    def __init__(self, *args, limit_pct: float = 100.0, **kw):
        super().__init__(*args, **kw)
        self.limit_pct = float(limit_pct)

    def decide(self, ctx: DayContext) -> np.ndarray:
        if not ctx.is_op:
            return np.zeros(ctx.active.size, dtype=bool)
        return ctx.active & (ctx.est_rate * (ctx.age + ctx.gap) >= self.limit_pct)


class MaxFill(_Base):
    id = "c_max_fill"
    label = "(c) max Füllung: Takt T = floor((100 − Puffer)/r̂), leert wenn Alter ≥ T"

    def cadence(self, est_rate: np.ndarray) -> np.ndarray:
        with np.errstate(divide="ignore"):
            t = np.floor(self.target / np.maximum(est_rate, 1e-9))
        return np.maximum(t, 1).astype(np.int64)

    def decide(self, ctx: DayContext) -> np.ndarray:
        if not ctx.is_op:
            return np.zeros(ctx.active.size, dtype=bool)
        return ctx.active & (ctx.age >= self.cadence(ctx.est_rate))


def _planned_matrix(static: Static) -> np.ndarray:
    planned = np.zeros((static.n, len(static.dates)), dtype=bool)
    for c, days in enumerate(static.visit_days):
        planned[c, days] = True
    return planned


def _next_true(mask: np.ndarray) -> np.ndarray:
    """nxt[r, d] = smallest d' ≥ d with mask[r, d'] (INF_DAY if none)."""
    rows, n_days = mask.shape
    nxt = np.full((rows, n_days + 1), INF_DAY, dtype=np.int64)
    for d in range(n_days - 1, -1, -1):
        nxt[:, d] = np.where(mask[:, d], d, nxt[:, d + 1])
    return nxt


class StatusQuo(_Base):
    id = "d_status_quo"
    label = "(d) Status quo: reale Leerungstage"

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

    def setup(self, static: Static) -> None:
        super().setup(static)
        self.planned = _planned_matrix(static)

    def decide(self, ctx: DayContext) -> np.ndarray:
        return ctx.active & self.planned[:, ctx.day]


class Mentor(_Base):
    id = "e_mentor"
    label = "(e) Mentor: Status quo, ≤ 20 % überspringen → 14-Tage-Rhythmus, kritische dazu"

    def __init__(self, *args, skip_pct: float = 20.0, rhythm_days: int = 14, **kw):
        super().__init__(*args, **kw)
        self.skip_pct = float(skip_pct)
        self.rhythm_days = int(rhythm_days)

    def setup(self, static: Static) -> None:
        super().setup(static)
        self.planned = _planned_matrix(static)
        self.next_planned = _next_true(self.planned)
        self.blocked_until = np.full(static.n, -1, dtype=np.int64)
        self.skipped_ever = np.zeros(static.n, dtype=bool)
        self.n_skipped = 0
        self.n_rescued = 0

    def decide(self, ctx: DayContext) -> np.ndarray:
        di = ctx.day
        est_fill = ctx.est_fill
        planned = ctx.active & self.planned[:, di]
        blocked = planned & (di < self.blocked_until)
        low = planned & ~blocked & (est_fill <= self.skip_pct)
        self.blocked_until[low] = di + self.rhythm_days
        self.skipped_ever |= low
        self.n_skipped += int(blocked.sum() + low.sum())
        empty = planned & ~blocked & ~low
        if ctx.is_op:
            n_days = self.planned.shape[1]
            start = np.clip(np.maximum(di + 1, self.blocked_until), 0, n_days)
            nxt = self.next_planned[np.arange(ctx.active.size), start]
            next_op = di + ctx.gap
            rescue = (
                ctx.active
                & ~empty
                & (nxt > next_op)
                & (ctx.est_rate * (ctx.age + ctx.gap) >= self.target)
            )
            self.n_rescued += int(rescue.sum())
            empty |= rescue
        return empty


def kmeans(points: np.ndarray, k: int, seed: int = 0, iters: int = 100) -> tuple[np.ndarray, np.ndarray]:
    """Plain Lloyd k-means with deterministic k-means++ init (numpy only)."""
    rng = np.random.default_rng(seed)
    centers = [points[rng.integers(len(points))]]
    for _ in range(1, k):
        d2 = np.min(((points[:, None, :] - np.array(centers)[None]) ** 2).sum(-1), axis=1)
        centers.append(points[rng.choice(len(points), p=d2 / d2.sum())])
    cent = np.array(centers, dtype=float)
    labels = np.zeros(len(points), dtype=int)
    for _ in range(iters):
        labels = np.argmin(((points[:, None, :] - cent[None]) ** 2).sum(-1), axis=1)
        new = np.array([points[labels == j].mean(0) if (labels == j).any() else cent[j] for j in range(k)])
        if np.allclose(new, cent):
            break
        cent = new
    return labels, cent


class FixedAreas(_Base):
    id = "f_fixed_areas"
    label = "(f) feste Gebiete: 5 Gebiete = Mo–Fr, leert am Gebietstag vor dem Ziel am nächsten Gebietstag"

    def __init__(self, *args, n_areas: int = 5, seed: int = 0, **kw):
        super().__init__(*args, **kw)
        self.n_areas = int(n_areas)
        self.seed = int(seed)

    def setup(self, static: Static) -> None:
        super().setup(static)
        # cluster on (lat, lon·cos(lat)) so distances are roughly isotropic
        scale = np.cos(np.deg2rad(float(np.mean(static.lat))))
        pts = np.column_stack([static.lat, static.lon * scale])
        labels, cent = kmeans(pts, self.n_areas, seed=self.seed)
        order = np.argsort(cent[:, 1])  # west → east = Mon → Fri
        remap = np.empty(self.n_areas, dtype=int)
        remap[order] = np.arange(self.n_areas)
        self.area = remap[labels]  # area id == weekday (0 = Mon)
        n_days = len(static.dates)
        self.area_day = np.zeros((self.n_areas, n_days), dtype=bool)
        for di, d in enumerate(static.dates):
            if d.weekday() >= self.n_areas:
                continue
            j = di
            while j < n_days and not static.is_op[j]:
                j += 1
            if j < n_days:
                self.area_day[d.weekday(), j] = True
        nxt = _next_true(self.area_day)
        self.next_area_day = nxt  # (areas, days + 1)

    def decide(self, ctx: DayContext) -> np.ndarray:
        di = ctx.day
        today = self.area_day[self.area, di]
        if not today.any():
            return np.zeros(ctx.active.size, dtype=bool)
        n_days = self.area_day.shape[1]
        nxt = self.next_area_day[self.area, min(di + 1, n_days)]
        horizon = np.where(nxt >= INF_DAY, 7, nxt - di)
        return ctx.active & today & (ctx.est_rate * (ctx.age + horizon) >= self.target)


class AreaWeekRhythm(FixedAreas):
    """(h) Week rhythm per container on the 5 fixed areas of (f) (same k-means, same area days).

    Owner persona: containers that are regularly half empty get a longer rhythm, the freed
    time goes to the critical ones, the rhythm adapts after every new measurement.

    Rule (buffer = ``buffer_pct``, default 20; also run with 10 / 30):
      * rhythm k_c ∈ {1, 2, 3, 4} weeks = clamp(floor((100 − buffer) / (r̂_c · 7)), 1, 4),
        r̂_c = walk-forward estimate of the day of emptying (ratio of sums, readings with
        date < d only). k_c is recomputed after every emptying of c (``on_emptied``);
        before c's first emptying k_c follows the current r̂_c daily.
      * On c's area day empty c if age_c ≥ 7·k_c days since its last emptying/activation,
        OR (safety) its estimated fill on the area's next area day would be ≥ 100 − buffer/2:
        r̂_c · (age_c + days to next area day) ≥ 100 − buffer/2.
      * Never off its area day (holiday shift as in (f)). Co-empty at a stop is OFF.
    ``rhythm`` holds the current k per container (at the end of the run: the recommendation).
    """

    id = "h_area_week_rhythm"
    label = "(h) Wochenrhythmus: feste Gebiete, Takt k = 1–4 Wochen aus r̂, Sicherheit bei 100 − Puffer/2"

    def __init__(self, *args, id: str | None = None, **kw):
        super().__init__(*args, **kw)
        if id:
            self.id = id
        self.label = f"{AreaWeekRhythm.label} (Puffer {self.buffer_pct:g} %)"

    def rhythm_of(self, est_rate: np.ndarray) -> np.ndarray:
        with np.errstate(divide="ignore"):
            k = np.floor(self.target / (np.maximum(est_rate, 1e-9) * 7.0))
        return np.clip(k, 1, 4).astype(np.int64)

    def setup(self, static: Static) -> None:
        super().setup(static)
        self.rhythm = np.zeros(static.n, dtype=np.int64)  # 0 = not yet emptied
        self.fixed = np.zeros(static.n, dtype=bool)

    def decide(self, ctx: DayContext) -> np.ndarray:
        # containers never emptied yet follow the current estimate
        self.rhythm[~self.fixed] = self.rhythm_of(ctx.est_rate)[~self.fixed]
        di = ctx.day
        today = self.area_day[self.area, di]
        if not today.any():
            return np.zeros(ctx.active.size, dtype=bool)
        n_days = self.area_day.shape[1]
        nxt = self.next_area_day[self.area, min(di + 1, n_days)]
        horizon = np.where(nxt >= INF_DAY, 7, nxt - di)
        due = ctx.age >= 7 * self.rhythm
        safety = ctx.est_rate * (ctx.age + horizon) >= 100.0 - self.buffer_pct / 2.0
        return ctx.active & today & (due | safety)

    def on_emptied(self, ctx: DayContext, sel: np.ndarray) -> None:
        self.rhythm[sel] = self.rhythm_of(ctx.est_rate)[sel]
        self.fixed |= sel


class CoEmpty(ZeroOverflow):
    id = "g_co_empty"
    label = "(g) co-empty: (a) + am angefahrenen Halt alle Container mit Schätzung ≥ X mitleeren"

    def __init__(self, x_pct: float = 50.0, id: str | None = None, **kw):
        super().__init__(bundle_threshold=float(x_pct), id=id, **kw)
        self.label = f"{CoEmpty.label} (X = {x_pct:g} %)"


def default_policies() -> list[_Base]:
    """All multi_chamber scenarios (MODEL_SPEC §5, §10)."""
    return [
        ZeroOverflow(),
        MinKm(),
        MaxFill(),
        StatusQuo(),
        Mentor(),
        FixedAreas(),
        AreaWeekRhythm(),
        AreaWeekRhythm(buffer_pct=10.0, id="h_area_week_rhythm_b10"),
        AreaWeekRhythm(buffer_pct=30.0, id="h_area_week_rhythm_b30"),
        CoEmpty(50.0),
        CoEmpty(30.0, id="g_co_empty_x30"),
        CoEmpty(70.0, id="g_co_empty_x70"),
    ]


def per_colour_policies() -> list[_Base]:
    """Scenarios additionally run with truck_mode=per_colour."""
    return [ZeroOverflow(), StatusQuo(), CoEmpty(50.0)]
