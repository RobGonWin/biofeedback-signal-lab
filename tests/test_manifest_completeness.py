from pathlib import Path

import pandas as pd


EXPECTED_SIGNAL_FILES = {"ACC.csv", "BVP.csv", "EDA.csv", "HR.csv", "IBI.csv", "TEMP.csv", "info.txt", "tags.csv"}
EXPECTED_SUBJECT_IDS = {"S1", "S2", "S3", "S4", "S5", "S6"}
EXPECTED_SESSION_NAMES = {"midterm_1", "midterm_2"}


def test_manifest_selection_uses_subject_and_session_limits() -> None:
    manifest_path = Path("data/bronze/wearable_exam_stress/raw_metadata_manifest.parquet")
    assert manifest_path.exists(), "raw metadata manifest should exist"

    manifest_frame = pd.read_parquet(manifest_path)
    selected_manifest = manifest_frame.loc[manifest_frame["selected_for_download"] == True].copy()  # noqa: E712

    assert set(selected_manifest["dataset_name"].unique()) == {"wearable_exam_stress"}
    assert set(selected_manifest["subject_id"].unique()) == EXPECTED_SUBJECT_IDS
    assert set(selected_manifest["session_name"].unique()) == EXPECTED_SESSION_NAMES


def test_download_manifest_contains_required_exam_sensor_files() -> None:
    manifest_frame = pd.read_parquet("data/bronze/wearable_exam_stress/raw_metadata_manifest.parquet")
    selected_manifest = manifest_frame.loc[manifest_frame["selected_for_download"] == True].copy()  # noqa: E712
    grouped_manifest = (
        selected_manifest.groupby(["subject_id", "session_name"])["file_name"]
        .apply(lambda file_names: set(file_names))
        .to_dict()
    )

    assert grouped_manifest, "expected selected manifest groups"
    for file_names in grouped_manifest.values():
        assert file_names == EXPECTED_SIGNAL_FILES


def test_manifest_has_dataset_aware_fields() -> None:
    manifest_frame = pd.read_parquet("data/bronze/wearable_exam_stress/raw_metadata_manifest.parquet")
    expected_columns = {
        "dataset_name",
        "record_group_id",
        "record_id",
        "file_role",
        "selection_group",
    }
    assert expected_columns.issubset(set(manifest_frame.columns))
