import pandas as pd


def test_window_generation_respects_expected_duration_and_coverage() -> None:
    staged_windows = pd.read_parquet("data/staging/wearable_exam_stress/stg_signal_windows.parquet")
    assert set(staged_windows["dataset_name"].unique()) == {"wearable_exam_stress"}
    assert set(staged_windows["window_seconds"].unique()) == {60}
    assert (staged_windows["expected_sample_count"] > 0).all()
    assert (staged_windows["sample_count"] <= staged_windows["expected_sample_count"]).all()
    assert ((staged_windows["window_coverage_ratio"] >= 0) & (staged_windows["window_coverage_ratio"] <= 1)).all()


def test_staged_records_capture_real_channel_inventory() -> None:
    staged_records = pd.read_parquet("data/staging/wearable_exam_stress/stg_signal_records.parquet")
    expected_channels = {"acc_x", "acc_y", "acc_z", "acc_magnitude", "bvp", "eda", "hr", "temp"}
    assert set(staged_records["signal_channel"].unique()) == expected_channels
    assert set(staged_records["dataset_name"].unique()) == {"wearable_exam_stress"}
