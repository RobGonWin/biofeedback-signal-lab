"""Extract record, window, and session-level features for one dataset."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_config import load_pipeline_config, resolve_repo_path


def load_staged_tables(dataset_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    staging_directory = resolve_repo_path(pipeline_config.paths.staging_directory)
    staged_records = pd.read_parquet(staging_directory / "stg_signal_records.parquet")
    staged_windows = pd.read_parquet(staging_directory / "stg_signal_windows.parquet")
    return staged_records, staged_windows


def build_window_features(staged_windows: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    window_features = staged_windows.copy()
    channel_variability_thresholds = (
        window_features.groupby("signal_channel")["window_std"]
        .quantile(pipeline_config.windowing.higher_relative_variability_quantile)
        .to_dict()
    )
    acc_motion_threshold = channel_variability_thresholds.get("acc_magnitude", float("inf"))
    window_features["is_low_coverage_window"] = (
        window_features["window_coverage_ratio"] < pipeline_config.windowing.min_window_coverage_ratio
    )
    window_features["is_flatline_like_window"] = (
        (window_features["flatline_ratio"] >= 0.98) | (window_features["window_std"] <= 0)
    )
    window_features["is_higher_relative_variability_window"] = window_features.apply(
        lambda row: row["window_std"] >= channel_variability_thresholds.get(row["signal_channel"], float("inf")),
        axis=1,
    )
    window_features["is_high_motion_window"] = (
        (window_features["signal_channel"] == "acc_magnitude")
        & (window_features["window_std"] >= acc_motion_threshold)
    )
    ordered_window_features = window_features[
        [
            "dataset_name",
            "window_id",
            "record_id",
            "subject_id",
            "session_id",
            "session_name",
            "signal_channel",
            "window_start_ts_utc",
            "window_end_ts_utc",
            "window_seconds",
            "expected_sample_count",
            "sample_count",
            "window_coverage_ratio",
            "missing_value_ratio",
            "flatline_ratio",
            "window_mean",
            "window_std",
            "window_min",
            "window_max",
            "window_iqr",
            "window_mad",
            "window_range",
            "is_low_coverage_window",
            "is_flatline_like_window",
            "is_high_motion_window",
            "is_higher_relative_variability_window",
        ]
    ].copy()
    return ordered_window_features


def build_record_features(staged_records: pd.DataFrame, window_features: pd.DataFrame) -> pd.DataFrame:
    record_rollup = (
        window_features.groupby("record_id", as_index=False)
        .agg(
            window_count=("window_id", "count"),
            record_missing_value_ratio=("missing_value_ratio", "mean"),
            record_flatline_ratio=("flatline_ratio", "mean"),
            avg_window_coverage_ratio=("window_coverage_ratio", "mean"),
            low_coverage_window_count=("is_low_coverage_window", "sum"),
            flatline_window_count=("is_flatline_like_window", "sum"),
            high_motion_window_count=("is_high_motion_window", "sum"),
            higher_relative_variability_window_count=("is_higher_relative_variability_window", "sum"),
            avg_window_std=("window_std", "mean"),
        )
    )
    record_features = staged_records.merge(record_rollup, on="record_id", how="left")
    record_features["record_signal_quality_score"] = (
        record_features["avg_window_coverage_ratio"].fillna(0.0)
        * (1 - record_features["record_missing_value_ratio"].fillna(0.0))
        * (1 - record_features["record_flatline_ratio"].fillna(0.0))
    ).clip(lower=0.0, upper=1.0)
    return record_features[
        [
            "dataset_name",
            "record_id",
            "subject_id",
            "session_id",
            "session_name",
            "signal_channel",
            "file_name",
            "file_type",
            "sample_rate_hz",
            "sample_count",
            "window_count",
            "record_missing_value_ratio",
            "record_flatline_ratio",
            "avg_window_coverage_ratio",
            "avg_window_std",
            "low_coverage_window_count",
            "flatline_window_count",
            "high_motion_window_count",
            "higher_relative_variability_window_count",
            "record_signal_quality_score",
            "has_non_monotonic_timestamps",
            "has_duplicate_timestamps",
        ]
    ].copy()


def build_session_summary(window_features: pd.DataFrame) -> pd.DataFrame:
    return (
        window_features.groupby(
            ["dataset_name", "subject_id", "session_id", "session_name", "signal_channel"],
            as_index=False,
        )
        .agg(
            window_count=("window_id", "count"),
            avg_window_std=("window_std", "mean"),
            avg_window_coverage_ratio=("window_coverage_ratio", "mean"),
            avg_missing_value_ratio=("missing_value_ratio", "mean"),
            low_coverage_window_count=("is_low_coverage_window", "sum"),
            flatline_window_count=("is_flatline_like_window", "sum"),
            high_motion_window_count=("is_high_motion_window", "sum"),
            higher_relative_variability_window_count=("is_higher_relative_variability_window", "sum"),
        )
        .sort_values(["dataset_name", "subject_id", "session_id", "signal_channel"])
    )


def build_feature_distribution_summary(window_features: pd.DataFrame) -> pd.DataFrame:
    summary_rows: list[dict] = []
    summarized_feature_names = [
        "window_std",
        "window_range",
        "window_coverage_ratio",
        "missing_value_ratio",
        "flatline_ratio",
    ]
    for (dataset_name, signal_channel), channel_frame in window_features.groupby(["dataset_name", "signal_channel"]):
        for feature_name in summarized_feature_names:
            feature_series = channel_frame[feature_name]
            summary_rows.append(
                {
                    "dataset_name": dataset_name,
                    "signal_channel": signal_channel,
                    "feature_name": feature_name,
                    "feature_mean": float(feature_series.mean()),
                    "feature_median": float(feature_series.median()),
                    "feature_p90": float(feature_series.quantile(0.9)),
                }
            )
    return pd.DataFrame(summary_rows)


def build_interpretation_guardrails(dataset_name: str) -> pd.DataFrame:
    if dataset_name == "wearable_exam_stress":
        may_suggest = [
            "capture consistency differences across sessions and channels",
            "relative variability changes across fixed windows",
            "motion-heavy periods when accelerometer magnitude variability is elevated",
            "records that may deserve closer data-quality review",
        ]
        do_not_prove = [
            "clinical diagnosis",
            "cognitive state certainty",
            "medical treatment need",
            "stress level as a definitive outcome",
        ]
    else:
        may_suggest = [
            "waveform quality differences across records and leads",
            "relative lead-level variability changes across fixed windows",
            "annotation density differences across records",
            "records that may deserve closer waveform or label review",
        ]
        do_not_prove = [
            "clinical diagnosis",
            "definitive rhythm interpretation without specialist review",
            "treatment need",
            "medical certainty from summary metrics alone",
        ]

    return pd.DataFrame(
        {
            "dataset_name": [dataset_name] * 4,
            "guardrail_id": [1, 2, 3, 4],
            "what_features_may_suggest": may_suggest,
            "what_features_do_not_prove": do_not_prove,
        }
    )


def write_curated_outputs(
    dataset_name: str,
    record_features: pd.DataFrame,
    window_features: pd.DataFrame,
    session_summary: pd.DataFrame,
    distribution_summary: pd.DataFrame,
    interpretation_guardrails: pd.DataFrame,
) -> None:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    curated_directory = resolve_repo_path(pipeline_config.paths.curated_directory)
    curated_directory.mkdir(parents=True, exist_ok=True)
    output_tables = {
        "fct_record_features": record_features,
        "fct_window_features": window_features,
        "mart_subject_or_session_summary": session_summary,
        "mart_feature_distribution_summary": distribution_summary,
        "mart_interpretation_guardrails": interpretation_guardrails,
    }
    for table_name, output_table in output_tables.items():
        output_table.to_csv(curated_directory / f"{table_name}.csv", index=False)
        output_table.to_parquet(curated_directory / f"{table_name}.parquet", index=False)


def extract_dataset_features(dataset_name: str) -> None:
    staged_records, staged_windows = load_staged_tables(dataset_name)
    window_features = build_window_features(staged_windows, dataset_name)
    record_features = build_record_features(staged_records, window_features)
    session_summary = build_session_summary(window_features)
    distribution_summary = build_feature_distribution_summary(window_features)
    interpretation_guardrails = build_interpretation_guardrails(dataset_name)
    write_curated_outputs(
        dataset_name,
        record_features,
        window_features,
        session_summary,
        distribution_summary,
        interpretation_guardrails,
    )
    print(f"wrote curated feature tables for {dataset_name}")
