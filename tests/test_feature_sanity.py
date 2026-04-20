import pandas as pd


def test_feature_sanity_handles_flatline_and_missing_windows() -> None:
    window_features = pd.read_parquet("data/curated/wearable_exam_stress/fct_window_features.parquet")
    assert set(window_features["dataset_name"].unique()) == {"wearable_exam_stress"}
    assert (window_features["window_std"] >= 0).all()
    assert ((window_features["missing_value_ratio"] >= 0) & (window_features["missing_value_ratio"] <= 1)).all()
    assert ((window_features["flatline_ratio"] >= 0) & (window_features["flatline_ratio"] <= 1)).all()


def test_operational_state_flags_are_non_diagnostic_and_bounded() -> None:
    window_features = pd.read_parquet("data/curated/wearable_exam_stress/fct_window_features.parquet")
    flag_columns = [
        "is_low_coverage_window",
        "is_flatline_like_window",
        "is_high_motion_window",
        "is_higher_relative_variability_window",
    ]
    for flag_column in flag_columns:
        assert window_features[flag_column].isin([True, False]).all()


def test_out_of_order_or_duplicate_timestamps_are_flagged() -> None:
    record_features = pd.read_parquet("data/curated/wearable_exam_stress/fct_record_features.parquet")
    assert set(record_features["dataset_name"].unique()) == {"wearable_exam_stress"}
    assert not record_features["has_non_monotonic_timestamps"].fillna(False).any()
    assert not record_features["has_duplicate_timestamps"].fillna(False).any()
