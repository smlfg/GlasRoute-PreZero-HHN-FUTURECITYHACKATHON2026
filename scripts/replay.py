"""Reproduce paired replay and compare causal timer predictions with the backtest."""

import json
from pathlib import Path
import pandas as pd
from prezero.ingest import load_raw
from prezero.locations import load_locations
from prezero.routing import load_config
from prezero.replay import simulate

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = ROOT / "prezero_config.json"
    params = json.loads(config.read_text()).get("replay", {})
    raw = load_raw(ROOT / "data/raw/glass_fill_levels_anonymized_f.csv")
    daily, report = simulate(
        raw,
        load_locations(ROOT / "data/external/locations.csv"),
        load_config(config),
        **params,
    )
    backtest = pd.read_csv(ROOT / "backtest_results.csv")
    report["walk_forward"] = {
        m: round(float((backtest[m] - backtest.actual).abs().mean()), 1)
        for m in ("model", "mean_past", "last_value")
    }
    report["walk_forward"]["visits"] = len(backtest)
    n = int(daily.timer_predictions.sum())
    mae = round(float(daily.timer_absolute_error_pp.sum() / n), 1)
    if (n, mae) != (len(backtest), report["walk_forward"]["model"]):
        raise ValueError("Replay predictions differ from the walk-forward reference")
    history = pd.read_csv(ROOT / "data/history_tours.csv")
    # Mixed tours do not identify colour-specific km. Allocate each day's totals by lifts.
    for color, result in report["observed"]["colors"].items():
        shares = (
            history.material_breakdown.map(
                lambda v: json.loads(v).get(color, {}).get("containers", 0)
            )
            / history.containers_visited
        )
        result["allocated_by_lifts"] = {
            m: float((history[m] * shares).sum())
            for m in (
                "modeled_km",
                "modeled_vehicle_hours",
                "modeled_vehicle_days",
                "modeled_rounds",
            )
        }
    report["observed"]["routes"] = {
        m: float(history[m].sum()) for m in result["allocated_by_lifts"]
    }
    daily.to_csv(ROOT / "data/optimized_tours.csv", index=False)
    (ROOT / "data/replay_comparison.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
