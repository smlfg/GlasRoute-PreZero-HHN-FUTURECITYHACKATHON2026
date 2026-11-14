import pandas as pd

from prezero.scoring import score_containers


def feature_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("A", "white", 110, 0.5, 1.0),
            ("B", "brown", 40, 0.0, 1.0),
            ("C", "green", 90, 1.0, 0.7),
        ],
        columns=[
            "Location_id",
            "material_type",
            "last_level",
            "overfull_rate",
            "season_factor",
        ],
    )


def test_score_is_normalized_and_uses_weights() -> None:
    scored = score_containers(feature_rows())
    assert scored["score"].between(0, 1).all()
    assert scored.loc[0, "score"] == 0.5 + 0.15 + 0.2


def test_white_material_gets_higher_material_factor() -> None:
    scored = score_containers(feature_rows()).set_index("Location_id")
    assert scored.loc["A", "score"] > scored.loc["C", "score"]


def test_critical_flag_uses_point_seven_threshold() -> None:
    scored = score_containers(feature_rows()).set_index("Location_id")
    assert scored.loc["A", "critical"]
    assert not scored.loc["B", "critical"]
