"""Exercise the exact economics function embedded in the offline analysis page."""

import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def calc(h=None, o=None, **updates):
    r = json.loads((ROOT / "data/replay_comparison.json").read_text())
    r["historical"] = h or r["historical"]
    r["optimized"] = o or r["optimized"]
    p = json.loads((ROOT / "prezero_config.json").read_text())["economics"] | updates
    out = subprocess.run(
        [
            "node",
            "-e",
            "const f=require('./src/prezero/economics.js'); console.log(JSON.stringify(f(...JSON.parse(require('fs').readFileSync(0,'utf8')))))",
        ],
        cwd=ROOT,
        input=json.dumps([r, p]),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(out.stdout)


def test_components_discrete_days_unit_cost_and_identical_scenarios():
    h = json.loads((ROOT / "data/replay_comparison.json").read_text())["historical"]
    costs = calc(h, h)
    assert costs["difference"] == 0
    a = costs["historical"]
    assert a["vehicle"] == h["vehicle_days"] * 500
    assert a["total"] == pytest.approx(
        a["vehicle"] + 2 * h["hours"] * 32 + h["km"] * 0.65
    )
    assert a["perTonne"] == pytest.approx(
        a["total"] / (h["inventory"]["collected_kg"] / 1000)
    )
    assert calc(h, h | {"vehicle_days": h["vehicle_days"] + 1})[
        "difference"
    ] == pytest.approx(-500)
    for k, field, factor in [
        ("wage", "labor", 64),
        ("crew", "labor", 4),
        ("km_cost", "drive", 1.30),
        ("vehicle_day", "vehicle", 1000),
        ("annual_days", "annual", 500),
    ]:
        assert calc(h, h, **{k: factor})["historical"][field] == pytest.approx(
            a[field] * 2
        )


def test_sensitivity_is_explicit_recalculation():
    c = calc()
    defaults = json.loads((ROOT / "prezero_config.json").read_text())["economics"]
    for k, pair in c["sensitivity"].items():
        for v, factor in zip(pair, [0.8, 1.2]):
            varied = calc(**{k: defaults[k] * factor})
            assert v == pytest.approx(
                varied["historical"]["annual"] - varied["optimized"]["annual"]
            )


def test_pitch_matches_published_calculation():
    pitch = subprocess.check_output(
        ["node", "scripts/cfo.cjs", "--pitch"], cwd=ROOT, text=True
    ).strip()
    assert pitch in (ROOT / "docs/PITCH.md").read_text()
