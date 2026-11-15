"""Scenario engine + policies a–f: one world, mass balance, no look-ahead (docs/MODEL_SPEC.md)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prezero.locations import load_locations
from prezero.routing import load_config
from prezero.sim.engine import WalkForwardEstimator, run_scenario, static_view
from prezero.sim.policies import AreaWeekRhythm, CoEmpty, FixedAreas, StatusQuo, ZeroOverflow, default_policies
from prezero.sim.world import build_world, simulate_daily

ROOT = Path(__file__).resolve().parents[1]


def _null_evaluator(sites_df, cfg):
    return {"stops": len(sites_df), "km": 0.0, "vehicles": 0, "hours": 0.0, "unloads": 0}


@pytest.fixture(scope="module")
def inputs():
    readings = pd.read_csv(ROOT / "data/processed/cleaned_readings.csv")
    locations = load_locations(ROOT / "data/external/locations.csv")
    cfg = load_config(ROOT / "prezero_config.json")
    return readings, locations, cfg


@pytest.fixture(scope="module")
def runs(inputs):
    readings, locations, cfg = inputs
    world = build_world(readings, locations, cfg)
    static = static_view(world)
    pols = default_policies()
    results = {p.id: run_scenario(p, cfg=cfg, world=world, static=static) for p in pols}
    return world, {p.id: p for p in pols}, results


def test_mass_balance_per_scenario(runs):
    _, _, results = runs
    for sid, res in results.items():
        lg = res.ledger
        assert lg["collected_t"] + lg["end_stock_t"] == pytest.approx(lg["produced_t"], abs=1e-6), sid
        assert res.daily["tonnage_t"].sum() == pytest.approx(lg["collected_t"], abs=0.5), sid


def test_produced_equal_across_scenarios(runs, inputs):
    readings, _, cfg = inputs
    _, _, results = runs
    produced = {res.ledger["produced_t"] for res in results.values()}
    assert max(produced) - min(produced) < 1e-9
    assert min(produced) == pytest.approx(simulate_daily().produced_total(readings, cfg), abs=1e-6)


def test_status_quo_reproduces_w1(runs):
    _, _, results = runs
    lg = results["d_status_quo"].ledger
    assert round(lg["collected_t"], 2) == 6943.50
    assert lg["n_emptyings"] == 10363
    assert lg["overflow_container_days"] == 19047
    assert lg["overfull_at_emptying"] == 1196


def test_all_policies_present(runs):
    _, _, results = runs
    assert set(results) == {
        "a_zero_overflow", "b_min_km", "c_max_fill", "d_status_quo", "e_mentor",
        "f_fixed_areas", "g_co_empty", "g_co_empty_x30", "g_co_empty_x70",
        "h_area_week_rhythm", "h_area_week_rhythm_b10", "h_area_week_rhythm_b30",
    }
    for sid, res in results.items():
        assert res.events["bundled"].any() == sid.startswith("g_"), sid


def test_estimator_ratio_of_sums_and_no_look_ahead(inputs):
    readings, locations, cfg = inputs
    world = build_world(readings, locations, cfg)
    day_of = {d: i for i, d in enumerate(world.dates)}
    cut = 120
    est = WalkForwardEstimator(world.readings, world.n, world.material, day_of)
    r_cut = est.advance(cut).copy()

    poisoned = readings.copy()
    late = pd.to_datetime(poisoned["date"]).dt.date >= world.dates[cut]
    poisoned.loc[late, "fill_level_numeric"] = 999.0
    world_p = build_world(poisoned, locations, cfg)
    est_p = WalkForwardEstimator(world_p.readings, world_p.n, world_p.material, day_of)
    np.testing.assert_array_equal(est_p.advance(cut), r_cut)

    # ratio of sums for one container with ≥ 2 visible readings
    rd = world.readings
    vis = rd[rd["date_only"] < world.dates[cut]]
    c = int(vis.groupby("c").size().idxmax())
    g = vis[vis["c"] == c].sort_values("date_only")
    span = (g["date_only"].iloc[-1] - g["date_only"].iloc[0]).days
    assert r_cut[c] == pytest.approx(g["fill_level_numeric"].iloc[1:].sum() / span)


def test_policy_decisions_ignore_future_readings(inputs):
    """Poisoning readings from day `cut` on must not change any emptying before `cut`."""
    readings, locations, cfg = inputs
    cut = 150
    base = run_scenario(ZeroOverflow(), readings, locations, cfg, evaluate_day=_null_evaluator)
    world = build_world(readings, locations, cfg)
    poisoned = readings.copy()
    late = pd.to_datetime(poisoned["date"]).dt.date >= world.dates[cut]
    poisoned.loc[late, "fill_level_numeric"] = 999.0
    pois = run_scenario(ZeroOverflow(), poisoned, locations, cfg, evaluate_day=_null_evaluator)
    a = base.events[base.events["day"] < cut][["day", "c", "bundled"]].reset_index(drop=True)
    b = pois.events[pois.events["day"] < cut][["day", "c", "bundled"]].reset_index(drop=True)
    assert len(a) > 1000
    pd.testing.assert_frame_equal(a, b)


def test_fixed_areas_only_on_area_days(runs):
    world, pols, results = runs
    pol: FixedAreas = pols["f_fixed_areas"]
    ev = results["f_fixed_areas"].events
    assert len(ev) > 0
    area = pol.area[ev["c"].to_numpy()]
    assert pol.area_day[area, ev["day"].to_numpy()].all()
    # an emptying off the area's weekday only happens when that weekday was a holiday
    # in the same week and the area day shifted forward to the next operating day
    from datetime import timedelta

    is_op = simulate_daily().is_operating_day
    wd = np.array([d.weekday() for d in ev["date"]])
    for d, w, a in zip(ev["date"], wd, area):
        if w != a:  # walk back to the area's weekday: every day in between was non-operating
            back = (w - a) % 7
            assert all(not is_op(d - timedelta(days=k)) for k in range(1, back + 1)), (d, a)
    assert (wd == area).mean() > 0.95
    assert sorted(set(pol.area)) == [0, 1, 2, 3, 4]
    # site bundling never crosses areas: every site lies in exactly one area
    assert (pd.Series(pol.area).groupby(world.site).nunique() == 1).all()


def test_co_empty_reduces_stops(runs):
    _, _, results = runs
    a, g = results["a_zero_overflow"], results["g_co_empty"]
    assert g.events["bundled"].any() and not a.events["bundled"].any()
    assert g.daily["stops"].sum() < a.daily["stops"].sum()
    # higher X -> fewer co-emptyings
    co = [results[k].events["bundled"].sum() for k in ("g_co_empty_x30", "g_co_empty", "g_co_empty_x70")]
    assert co[0] > co[1] > co[2]


def test_per_colour_truck_mode(runs, inputs):
    world, _, results = runs
    _, _, cfg = inputs
    static = static_view(world)
    sq = run_scenario(StatusQuo(), cfg=cfg, world=world, static=static, truck_mode="per_colour")
    g = run_scenario(CoEmpty(50.0), cfg=cfg, world=world, static=static, truck_mode="per_colour")
    for r in (sq, g):
        lg = r.ledger
        assert lg["collected_t"] + lg["end_stock_t"] == pytest.approx(lg["produced_t"], abs=1e-6)
    # same emptyings as multi_chamber status quo, but each colour at a point is its own stop
    assert sq.ledger["n_emptyings"] == results["d_status_quo"].ledger["n_emptyings"]
    assert sq.daily["stops"].sum() > results["d_status_quo"].daily["stops"].sum()
    # per_colour co-empty never mixes colours: every co-emptied container shares day + stop + colour
    ev = g.events
    key = pd.DataFrame({"day": ev["day"], "site": world.site[ev["c"]], "mat": world.material[ev["c"]]})
    trig = key[~ev["bundled"].to_numpy()].drop_duplicates()
    co = key[ev["bundled"].to_numpy()].drop_duplicates()
    assert len(co) > 0
    assert len(co.merge(trig, how="left", indicator=True).query("_merge == 'left_only'")) == 0


H_IDS = ("h_area_week_rhythm", "h_area_week_rhythm_b10", "h_area_week_rhythm_b30")


def test_week_rhythm_mass_balance_and_rhythm_range(runs):
    _, pols, results = runs
    for sid in H_IDS:
        lg = results[sid].ledger
        assert lg["collected_t"] + lg["end_stock_t"] == pytest.approx(lg["produced_t"], abs=1e-6), sid
        assert not results[sid].events["bundled"].any(), sid
        k = pols[sid].rhythm
        assert k.min() >= 1 and k.max() <= 8, sid
        assert len(set(k)) > 1, sid


def test_week_rhythm_only_on_area_days(runs):
    _, pols, results = runs
    f = pols["f_fixed_areas"]
    for sid in H_IDS:
        pol: AreaWeekRhythm = pols[sid]
        np.testing.assert_array_equal(pol.area, f.area)
        ev = results[sid].events
        assert len(ev) > 0
        # area_day already includes the holiday shift to the next operating day
        assert pol.area_day[pol.area[ev["c"].to_numpy()], ev["day"].to_numpy()].all(), sid


def test_week_rhythm_ignores_future_readings(inputs):
    readings, locations, cfg = inputs
    cut = 150
    base = run_scenario(AreaWeekRhythm(), readings, locations, cfg, evaluate_day=_null_evaluator)
    world = build_world(readings, locations, cfg)
    poisoned = readings.copy()
    late = pd.to_datetime(poisoned["date"]).dt.date >= world.dates[cut]
    poisoned.loc[late, "fill_level_numeric"] = 999.0
    pois = run_scenario(AreaWeekRhythm(), poisoned, locations, cfg, evaluate_day=_null_evaluator)
    a = base.events[base.events["day"] < cut][["day", "c", "bundled"]].reset_index(drop=True)
    b = pois.events[pois.events["day"] < cut][["day", "c", "bundled"]].reset_index(drop=True)
    assert len(a) > 500
    pd.testing.assert_frame_equal(a, b)


def test_containers_csv_rhythm_columns():
    path = ROOT / "data/outputs/scenarios/containers.csv"
    if not path.exists():
        pytest.skip("run scripts/run_scenarios.py first")
    df = pd.read_csv(path)
    for col in ("interval_status_quo_days", "rhythm_weeks_status_quo", "rhythm_weeks_new",
                "recommendation", "area_weekday", "area", "skip_14d"):
        assert col in df.columns, col
    assert set(df["recommendation"]) <= {"länger", "kürzer", "gleich"}
    assert set(df["area_weekday"]) <= {"Mo", "Di", "Mi", "Do", "Fr"}
    assert df["rhythm_weeks_new"].between(1, 8).all()
    assert df["rhythm_weeks_status_quo"].dropna().between(1, 8).all()
