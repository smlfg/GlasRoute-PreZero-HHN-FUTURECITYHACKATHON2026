import pandas as pd

from prezero.features import build_features


def readings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("A", "white", "2026-01-01", 50),
            ("A", "white", "2026-01-11", 70),
            ("A", "white", "2026-01-21", "overfull"),
            ("B", "brown", "2026-03-01", 40),
            ("B", "brown", "2026-04-01", 60),
            ("B", "brown", "2026-05-01", 70),
        ],
        columns=["Location_id", "material_type", "date", "fill_level_perc"],
    )


def test_builds_one_row_per_location_and_material() -> None:
    features = build_features(readings(), "2026-04-15")
    assert set(zip(features["Location_id"], features["material_type"])) == {
        ("A", "white"),
        ("B", "brown"),
    }


def test_uses_only_readings_up_to_target_date() -> None:
    features = build_features(readings(), "2026-04-15").set_index("Location_id")
    assert features.loc["B", "last_level"] == 60
    assert features.loc["B", "days_since_measurement"] == 14


def test_calculates_rates_and_season_factor() -> None:
    features = build_features(readings(), "2026-04-15").set_index("Location_id")
    assert features.loc["A", "overfull_rate"] == 1 / 3
    assert features.loc["A", "avg_daily_increase"] == 3
    assert features.loc["A", "season_factor"] == 1.0
    assert features.loc["B", "season_factor"] == 1.0
    assert build_features(readings(), "2026-05-01")["season_factor"].iloc[0] == 0.7
