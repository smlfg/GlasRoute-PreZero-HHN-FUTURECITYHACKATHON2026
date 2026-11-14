"""Backtest: can the level found at a visit be predicted from the visits before it?

Stakeholder question: "es kann auch sein, dass alle Werte wirklich komplett random ist".

Walk-forward per container (Location_id x glass colour), no look-ahead:
for every visit i that has at least one earlier interval, predict the level the driver
will find at visit i using only visits 0..i-1, then compare with the real reading.

Model (measure-and-empty, same as prezero.features):
    rate = mean(level found / days since previous emptying) over earlier intervals
    prediction = min(110, rate x days since the previous visit)
Variant kept for comparison:
    model_season = same, but days weighted with the old fixed season factor (Jan-Apr 1.0, else 0.5-0.7)
Baselines (no model):
    mean_past  = mean of the levels found at earlier visits ("wie immer")
    last_value = level found at the previous visit ("wie letztes Mal")

Writes backtest_results.csv (one row per predicted visit), backtest_summary.json and
docs/BACKTEST.md.  Run:  python scripts/backtest.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from prezero.features import (
    DUE_FILL_PCT,
    MAX_FILL_PCT,
    elapsed_days,
    fill_rates_after_emptying,
    get_season_factor,
)

def _season_days(start: pd.Timestamp, end: pd.Timestamp) -> float:
    """Days weighted with the old fixed season factor (only for the comparison column)."""
    days = pd.date_range(start.normalize() + pd.Timedelta(days=1), end.normalize(), freq="D")
    return float(sum(get_season_factor(day) for day in days))

ROOT = Path(__file__).resolve().parents[1]
METHODS = {
    "model": "Timer-Modell (Füllrate x Tage)",
    "model_season": "Timer mit altem Saisonfaktor",
    "mean_past": "Basis: Durchschnitt bisher",
    "last_value": "Basis: wie letztes Mal",
}


def walk_forward(readings: pd.DataFrame) -> pd.DataFrame:
    """One row per visit that can be predicted from earlier visits of the same container."""
    rows: list[dict] = []
    work = readings.sort_values(["Location_id", "material_type", "date"])
    for (loc, mat), group in work.groupby(["Location_id", "material_type"], sort=False):
        dates = list(pd.to_datetime(group["date"]))
        levels = [float(v) for v in group["fill_level_numeric"]]
        for i in range(2, len(levels)):
            past_rates = fill_rates_after_emptying(dates[:i], levels[:i])
            if not past_rates:
                continue
            gap = (dates[i] - dates[i - 1]).days
            if gap <= 0:
                continue
            rate = float(np.mean(past_rates))
            rows.append(
                {
                    "Location_id": loc,
                    "material_type": mat,
                    "date": dates[i].date().isoformat(),
                    "days_since_prev_visit": gap,
                    "history_visits": i,
                    "actual": levels[i],
                    "model": min(MAX_FILL_PCT, rate * elapsed_days(dates[i - 1], dates[i])),
                    "model_season": min(MAX_FILL_PCT, rate * _season_days(dates[i - 1], dates[i])),
                    "mean_past": float(np.mean(levels[:i])),
                    "last_value": levels[i - 1],
                }
            )
    return pd.DataFrame(rows)


def _metrics(actual: pd.Series, pred: pd.Series) -> dict[str, float]:
    err = (pred - actual).abs()
    full_true = actual >= DUE_FILL_PCT
    full_pred = pred >= DUE_FILL_PCT
    tp = int((full_true & full_pred).sum())
    precision = tp / int(full_pred.sum()) if full_pred.any() else 0.0
    recall = tp / int(full_true.sum()) if full_true.any() else 0.0
    return {
        "mae_pp": round(float(err.mean()), 1),
        "within_20pp_pct": round(float((err <= 20).mean() * 100), 1),
        "full_precision_pct": round(precision * 100, 1),
        "full_recall_pct": round(recall * 100, 1),
        "spearman": round(float(actual.corr(pred, method="spearman")), 3),
    }


MATERIAL_DE = {"brown": "Braunglas", "green": "Grünglas", "white": "Weißglas"}


def rhythm_analysis(readings: pd.DataFrame) -> dict:
    """How well does today's emptying rhythm fit each container's fill rate?

    Per container: ideal interval = 80 % / mean fill rate; actual = median days between visits.
    'too often' = actual < 0.8 x ideal, 'too rarely' = actual > 1.2 x ideal.
    """
    work = readings.sort_values(["Location_id", "material_type", "date"]).copy()
    work["gap"] = work.groupby(["Location_id", "material_type"])["date"].diff().dt.days
    visits = work.dropna(subset=["gap"])
    visits = visits[visits["gap"] > 0].copy()
    level = visits["fill_level_numeric"].astype(float)
    visits["rate"] = level / visits["gap"]
    per = visits.groupby(["Location_id", "material_type"]).agg(
        rate=("rate", "mean"), gap=("gap", "median")
    )
    per = per[per["rate"] > 0].copy()
    per["ideal"] = DUE_FILL_PCT / per["rate"]

    def block(frame: pd.DataFrame) -> dict:
        return {
            "containers": int(len(frame)),
            "ideal_days_median": round(float(frame["ideal"].median()), 1),
            "actual_days_median": round(float(frame["gap"].median()), 1),
            "too_often_pct": round(float((frame["gap"] < 0.8 * frame["ideal"]).mean() * 100), 1),
            "too_rarely_pct": round(float((frame["gap"] > 1.2 * frame["ideal"]).mean() * 100), 1),
        }

    return {
        "visits": int(len(visits)),
        "found_below_50_pct": round(float((level < 50).mean() * 100), 1),
        "found_due_pct": round(float((level >= DUE_FILL_PCT).mean() * 100), 1),
        "found_overfull_pct": round(float((level >= MAX_FILL_PCT).mean() * 100), 1),
        "all": block(per),
        "by_material": {mat: block(g) for mat, g in per.groupby(level="material_type")},
    }


def summarize(results: pd.DataFrame) -> dict:
    overall = {m: _metrics(results["actual"], results[m]) for m in METHODS}
    by_material = {
        mat: {m: _metrics(g["actual"], g[m]) for m in METHODS}
        for mat, g in results.groupby("material_type")
    }
    per_container = (
        results.assign(err=(results["model"] - results["actual"]).abs())
        .groupby(["Location_id", "material_type"])["err"]
        .mean()
    )
    return {
        "predicted_visits": int(len(results)),
        "containers": int(per_container.shape[0]),
        "full_share_pct": round(float((results["actual"] >= DUE_FILL_PCT).mean() * 100), 1),
        "due_level_pct": DUE_FILL_PCT,
        "methods": METHODS,
        "overall": overall,
        "by_material": by_material,
        "container_mae_quartiles_pp": [
            round(float(q), 1) for q in per_container.quantile([0.25, 0.5, 0.75])
        ],
    }


def _markdown(summary: dict) -> str:
    o = summary["overall"]

    def row(name: str, m: dict) -> str:
        return (
            f"| {name} | {m['mae_pp']} | {m['within_20pp_pct']} % | {m['full_precision_pct']} % | "
            f"{m['full_recall_pct']} % | {m['spearman']} |"
        )

    table = "\n".join(row(METHODS[k], o[k]) for k in METHODS)
    mat_rows = "\n".join(
        f"| {mat} | {v['model']['mae_pp']} | {v['mean_past']['mae_pp']} | {v['last_value']['mae_pp']} | "
        f"{v['model']['full_recall_pct']} % |"
        for mat, v in summary["by_material"].items()
    )
    q = summary["container_mae_quartiles_pp"]
    rh = summary.get("rhythm")
    rhythm_md = ""
    if rh:
        rows_rh = "\n".join(
            f"| {MATERIAL_DE.get(mat, mat)} | {b['ideal_days_median']} | {b['actual_days_median']} | "
            f"{b['too_often_pct']} % | {b['too_rarely_pct']} % |"
            for mat, b in rh["by_material"].items()
        )
        a = rh["all"]
        rhythm_md = f"""
## Passt der heutige Leerungsrhythmus?

Je Container: idealer Abstand = 80 % ÷ Füllrate; tatsächlicher Abstand = Median der Tage zwischen
zwei Besuchen. „zu oft“ = tatsächlich < 0,8 × ideal, „zu selten“ = > 1,2 × ideal.

| Glasfarbe | idealer Abstand (Tage) | tatsächlich (Tage) | zu oft geleert | zu selten geleert |
|---|---|---|---|---|
{rows_rh}
| **alle** | {a['ideal_days_median']} | {a['actual_days_median']} | {a['too_often_pct']} % | {a['too_rarely_pct']} % |

Bei {rh['found_below_50_pct']} % aller {rh['visits']} Besuche war der Container unter 50 % voll (Fahrt zu früh),
bei {rh['found_overfull_pct']} % lief er über. **Braunglas wird viel zu oft geleert**, Weißglas teils zu selten.
"""
    m, base = o["model"], o["mean_past"]
    better = m["mae_pp"] < base["mae_pp"]
    verdict = (
        f"**Nicht zufällig.** Das Timer-Modell sagt den vorgefundenen Füllstand mit {m['mae_pp']} pp "
        f"Fehler voraus, „Durchschnitt bisher“ mit {base['mae_pp']} pp. "
        f"Wenn das Modell „voll“ sagt, stimmt es in {m['full_precision_pct']} % der Fälle "
        f"(Basis {base['full_precision_pct']} %). Die Zeit seit der letzten Leerung trägt also Information."
        if better
        else f"Das Timer-Modell ({m['mae_pp']} pp) ist nicht besser als „Durchschnitt bisher“ "
        f"({base['mae_pp']} pp). Für die Planung reicht der Mittelwert."
    )
    return f"""# Backtest: Ist der Füllstand vorhersagbar?

Frage des Stakeholders: „es kann auch sein, dass alle Werte wirklich komplett random ist“.

**Vorgehen (walk-forward, ohne Blick in die Zukunft):** Für jeden Besuch eines Containers
(Standort × Glasfarbe), vor dem es schon mindestens ein Intervall gab, wird der Füllstand, den
der Fahrer vorfinden wird, **nur aus den Besuchen davor** vorhergesagt und mit der echten
Messung verglichen. {summary['predicted_visits']} Besuche in {summary['containers']} Containern.
{summary['full_share_pct']} % der Besuche fanden den Container ≥ {summary['due_level_pct']:.0f} % voll vor.

## Kurzantwort

{verdict}

## Ergebnis

| Methode | Fehler Ø (Prozentpunkte) | Treffer ±20 pp | „voll“ korrekt vorhergesagt (Precision) | volle erkannt (Recall) | Rangkorrelation |
|---|---|---|---|---|---|
{table}

„voll“ = ≥ {summary['due_level_pct']:.0f} %. Die Messwerte sind Schätzungen des Fahrers in 10-%-Stufen;
`overfull` ist als 110 % kodiert (wahre Höhe unbekannt). Ein Fehler unter ca. 10 pp ist deshalb
nicht erreichbar.

## Je Glasfarbe (Fehler Ø in pp)

| Glasfarbe | Timer-Modell | Durchschnitt bisher | wie letztes Mal | volle erkannt (Modell) |
|---|---|---|---|---|
{mat_rows}

**Streuung über Container:** Fehler Ø des Modells je Container, Quartile 25 / 50 / 75 %:
{q[0]} / {q[1]} / {q[2]} pp. Manche Container sind gut vorhersagbar, andere kaum.

{rhythm_md}
## Einordnung

- Ist das Modell besser als „Durchschnitt bisher“, steckt in der Füllrate (Zeit seit der letzten
  Leerung) echte Information. Ist es nicht besser, reicht für die Planung der Mittelwert.
- Ein ML-Modell (z. B. Gradient Boosting mit Wochentag, Ferien, Standortgruppe) ist der nächste
  Schritt, aber erst sinnvoll, wenn diese Basis steht. Bewusst nicht im Hackathon-Scope.

Erzeugt mit `python scripts/backtest.py` aus `data/processed/cleaned_readings.csv`.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readings", type=Path, default=ROOT / "data/processed/cleaned_readings.csv")
    parser.add_argument("--output", type=Path, default=ROOT)
    args = parser.parse_args()
    readings = pd.read_csv(args.readings, parse_dates=["date"])
    results = walk_forward(readings)
    summary = summarize(results)
    summary["rhythm"] = rhythm_analysis(readings)
    results.round(2).to_csv(args.output / "backtest_results.csv", index=False)
    (args.output / "backtest_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (args.output / "docs").mkdir(exist_ok=True)
    (args.output / "docs/BACKTEST.md").write_text(_markdown(summary), encoding="utf-8")
    o = summary["overall"]
    for key, label in METHODS.items():
        print(f"{label:34s} MAE {o[key]['mae_pp']:5.1f} pp | ±20pp {o[key]['within_20pp_pct']:5.1f} % | "
              f"voll P/R {o[key]['full_precision_pct']}/{o[key]['full_recall_pct']} % | rho {o[key]['spearman']}")


if __name__ == "__main__":
    main()
