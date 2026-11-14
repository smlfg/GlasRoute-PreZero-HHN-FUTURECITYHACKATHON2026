"""Offline, frozen dispatch experiment; separate from interactive annual replay."""

import json
from pathlib import Path


def comparison_panel(path=None):
    path = path or Path(__file__).resolve().parents[2] / "data/dispatch_experiment.json"
    if not path.is_file():
        return "<p>Der Quartalsvergleich ist für diesen Datenstand nicht verfügbar.</p>"
    report = json.loads(path.read_text())
    final = report["checkpoints"][report["end"]]
    stress = report["inflow_plus_20_percent"]

    def fmt(value, digits=0):
        return (
            f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")
        )

    def row(label, s):
        return (
            "<tr><th>"
            + label
            + "</th>"
            + "".join(
                "<td>" + fmt(s[key], digits) + "</td>"
                for key, digits in [
                    ("driving_days", 0),
                    ("vehicle_days", 0),
                    ("km", 0),
                    ("collected_kg", 0),
                    ("cost", 0),
                ]
            )
            + "</tr>"
        )

    rows = "".join(
        [
            row("A · Messbesuche", report["measured_A"]),
            row("A · Fahrplan bei Modellzufluss", final["A"]),
            row("B · Sofortabholung", final["B"]),
            row("C · Gebündelte Abholung", final["C"]),
        ]
    )
    delta = final["C"]["cost"] - final["A"]["cost"]
    stress_delta = stress["C"]["cost"] - stress["A"]["cost"]
    return f"""<article id="dispatch-quarter"><h2>Gebündelte Abholung · Juli–September 2026</h2>
    <p>Modellierte Kostendifferenz C minus A bei identischem Zufluss: <strong>{fmt(delta)} €</strong>.
    Bei 20 % mehr Zufluss: <strong>{fmt(stress_delta)} €</strong> (Mehrkosten).</p>
    <table><thead><tr><th>Strategie</th><th>Fahrtage</th><th>Fahrzeugtage</th><th>km</th>
    <th>Gesammelt (kg)</th><th>Periodenkosten (€)</th></tr></thead><tbody>{rows}</tbody></table>
    <p>Behältertage über Nennvolumen: A {fmt(final["A"]["risk_bin_days"])} · C {fmt(final["C"]["risk_bin_days"])}.
    Restbestand: A {fmt(final["A"]["ending_kg"] / 1000, 1)} t · C {fmt(final["C"]["ending_kg"] / 1000, 1)} t.
    Am Quartalsende sind bei C {final["C"]["overdue_bins"]} Behälter über Nennvolumen.
    Historisch wurden im Vergleichsbestand {report["observed_overfull"]} Übervoll-Meldungen erfasst.</p>
    <p>Fester Quartalsversuch: simulierte Standorte und tägliche Sensorwerte, Raten aus früheren Besuchen,
    Montag bis Freitag, gemeinsame Ladekapazität. Getrennte Glaskammern und Sensorkosten sind offen.
    500 €/Fahrzeugtag, zwei Personen zu 32 €/h, 0,65 €/km. Die folgenden Regler gelten für den separaten Langzeit-Replay.</p></article>"""
