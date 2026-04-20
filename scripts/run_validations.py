"""Run file, schema, feature, and DuckDB warehouse validations."""

from __future__ import annotations

from pathlib import Path
import sys

import duckdb
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_config import load_pipeline_config, resolve_repo_path


CRITICAL_CURATED_FILES = [
    "fct_record_features.parquet",
    "fct_window_features.parquet",
    "mart_subject_or_session_summary.parquet",
    "mart_feature_distribution_summary.parquet",
    "mart_interpretation_guardrails.parquet",
    "dim_reproducible_record_split.parquet",
]

EXPECTED_SIGNAL_FILES = {"ACC.csv", "BVP.csv", "EDA.csv", "HR.csv", "IBI.csv", "TEMP.csv", "info.txt", "tags.csv"}
EXPECTED_CHANNELS = {"acc_x", "acc_y", "acc_z", "acc_magnitude", "bvp", "eda", "hr", "temp"}
EXPECTED_WAREHOUSE_VIEWS = {
    "raw_signal_files",
    "raw_signal_files_all",
    "stg_signal_records",
    "stg_signal_records_all",
    "stg_signal_windows",
    "stg_signal_windows_all",
    "stg_annotations_or_labels",
    "stg_annotations_or_labels_all",
    "fct_record_features",
    "fct_record_features_all",
    "fct_window_features",
    "fct_window_features_all",
    "dim_reproducible_record_split",
    "dim_reproducible_record_split_all",
    "mart_subject_or_session_summary",
    "mart_subject_or_session_summary_all",
    "mart_feature_distribution_summary",
    "mart_feature_distribution_summary_all",
    "mart_interpretation_guardrails",
    "mart_interpretation_guardrails_all",
}


def validate_file_completeness(curated_directory: Path) -> None:
    """Validate required curated outputs exist."""
    missing_files = [
        str(curated_directory / required_file)
        for required_file in CRITICAL_CURATED_FILES
        if not (curated_directory / required_file).exists()
    ]
    if missing_files:
        raise FileNotFoundError(f"missing curated files: {missing_files}")


def validate_manifest_selection(raw_manifest: pd.DataFrame) -> None:
    """Validate subject/session completeness for the selected slice."""
    selected_manifest = raw_manifest.loc[raw_manifest["selected_for_download"] == True].copy()  # noqa: E712
    grouped_files = (
        selected_manifest.groupby(["subject_id", "session_name"])["file_name"]
        .apply(lambda file_names: set(file_names))
        .to_dict()
    )
    for group_key, file_names in grouped_files.items():
        if file_names != EXPECTED_SIGNAL_FILES:
            raise ValueError(f"incomplete file set for {group_key}: {sorted(file_names)}")
    if not raw_manifest["dataset_name"].eq("wearable_exam_stress").all():
        raise ValueError("default manifest should be tagged with wearable_exam_stress")


def validate_staged_channel_inventory(staged_records: pd.DataFrame) -> None:
    """Validate the staged record channels match the expected parsed inventory."""
    actual_channels = set(staged_records["signal_channel"].unique())
    if actual_channels != EXPECTED_CHANNELS:
        raise ValueError(f"unexpected staged signal channels: {sorted(actual_channels)}")
    if not staged_records["dataset_name"].eq("wearable_exam_stress").all():
        raise ValueError("default staged records should be tagged with wearable_exam_stress")


def validate_window_integrity(staged_windows: pd.DataFrame) -> None:
    """Validate window-level coverage and sample expectations."""
    has_invalid_coverage_ratio = (
        (staged_windows["window_coverage_ratio"] < 0)
        | (staged_windows["window_coverage_ratio"] > 1)
    ).any()
    if has_invalid_coverage_ratio:
        raise ValueError("window_coverage_ratio must be in [0, 1]")

    has_invalid_expected_sample_count = (staged_windows["expected_sample_count"] <= 0).any()
    if has_invalid_expected_sample_count:
        raise ValueError("expected_sample_count must be positive")

    has_excess_sample_count = (
        staged_windows["sample_count"] > staged_windows["expected_sample_count"]
    ).any()
    if has_excess_sample_count:
        raise ValueError("sample_count cannot exceed expected_sample_count")


def validate_record_timestamp_flags(record_features: pd.DataFrame) -> None:
    """Validate record timestamp quality flags stay false for dense parsed files."""
    if record_features["has_non_monotonic_timestamps"].fillna(False).any():
        raise ValueError("dense records should not have non-monotonic timestamp flags")
    if record_features["has_duplicate_timestamps"].fillna(False).any():
        raise ValueError("dense records should not have duplicate timestamp flags")


def validate_window_feature_sanity(window_features: pd.DataFrame) -> None:
    """Validate key window feature ranges."""
    has_negative_std = (window_features["window_std"] < 0).any()
    if has_negative_std:
        raise ValueError("window_std contains negative values")

    has_invalid_missing_ratio = (
        (window_features["missing_value_ratio"] < 0)
        | (window_features["missing_value_ratio"] > 1)
    ).any()
    if has_invalid_missing_ratio:
        raise ValueError("missing_value_ratio must be in [0, 1]")

    has_invalid_flatline_ratio = (
        (window_features["flatline_ratio"] < 0)
        | (window_features["flatline_ratio"] > 1)
    ).any()
    if has_invalid_flatline_ratio:
        raise ValueError("flatline_ratio must be in [0, 1]")


def validate_record_key_uniqueness(record_features: pd.DataFrame) -> None:
    """Validate record_id uniqueness in record feature table."""
    duplicate_record_count = int(record_features["record_id"].duplicated().sum())
    if duplicate_record_count > 0:
        raise ValueError(f"record_id has duplicates: {duplicate_record_count}")


def validate_reproducible_split_integrity(split_table: pd.DataFrame) -> None:
    """Validate split integrity and expected bucket values."""
    allowed_split_buckets = {"train", "validation"}
    actual_split_buckets = set(split_table["split_bucket"].unique())
    if not actual_split_buckets.issubset(allowed_split_buckets):
        raise ValueError(f"invalid split buckets: {sorted(actual_split_buckets)}")

    if split_table["split_seed"].isna().any():
        raise ValueError("split_seed should be populated for all rows")
    if not split_table["dataset_name"].eq("wearable_exam_stress").all():
        raise ValueError("default split table should be tagged with wearable_exam_stress")


def validate_operational_state_flags(window_features: pd.DataFrame) -> None:
    """Validate state flags remain non-diagnostic booleans."""
    flag_columns = [
        "is_low_coverage_window",
        "is_flatline_like_window",
        "is_high_motion_window",
        "is_higher_relative_variability_window",
    ]
    for flag_column in flag_columns:
        if not window_features[flag_column].isin([True, False]).all():
            raise ValueError(f"{flag_column} must contain only boolean values")


def validate_duckdb_warehouse(warehouse_path: Path) -> None:
    """Validate warehouse views exist and return rows when expected."""
    if not warehouse_path.exists():
        raise FileNotFoundError(f"missing DuckDB warehouse: {warehouse_path}")

    connection = duckdb.connect(str(warehouse_path), read_only=True)
    try:
        available_view_names = {
            row[0]
            for row in connection.execute("select table_name from information_schema.views").fetchall()
        }
        missing_view_names = sorted(EXPECTED_WAREHOUSE_VIEWS - available_view_names)
        if missing_view_names:
            raise ValueError(f"missing DuckDB views: {missing_view_names}")

        non_empty_core_views = [
            "stg_signal_records",
            "stg_signal_windows",
            "fct_record_features",
            "fct_window_features",
            "mart_subject_or_session_summary",
        ]
        for view_name in non_empty_core_views:
            row_count = connection.execute(f"select count(*) from {view_name}").fetchone()[0]
            if row_count <= 0:
                raise ValueError(f"DuckDB view is empty: {view_name}")
    finally:
        connection.close()


def main() -> None:
    pipeline_config = load_pipeline_config()
    curated_directory = resolve_repo_path(pipeline_config.paths.curated_directory)
    staging_directory = resolve_repo_path(pipeline_config.paths.staging_directory)
    manifest_path = resolve_repo_path(pipeline_config.paths.bronze_manifest_parquet)
    warehouse_path = resolve_repo_path(pipeline_config.paths.warehouse_database_path)

    validate_file_completeness(curated_directory)

    raw_manifest = pd.read_parquet(manifest_path)
    staged_records = pd.read_parquet(staging_directory / "stg_signal_records.parquet")
    staged_windows = pd.read_parquet(staging_directory / "stg_signal_windows.parquet")
    record_features = pd.read_parquet(curated_directory / "fct_record_features.parquet")
    window_features = pd.read_parquet(curated_directory / "fct_window_features.parquet")
    split_table = pd.read_parquet(curated_directory / "dim_reproducible_record_split.parquet")

    validate_manifest_selection(raw_manifest)
    validate_staged_channel_inventory(staged_records)
    validate_window_integrity(staged_windows)
    validate_record_timestamp_flags(record_features)
    validate_record_key_uniqueness(record_features)
    validate_window_feature_sanity(window_features)
    validate_operational_state_flags(window_features)
    validate_reproducible_split_integrity(split_table)
    validate_duckdb_warehouse(warehouse_path)

    print("all validations passed")


if __name__ == "__main__":
    main()
