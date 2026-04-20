"""Normalize optional WFDB datasets into staged records, windows, and annotations."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_config import load_pipeline_config, resolve_data_path, resolve_repo_path, to_repo_relative_path


@dataclass
class RecordContext:
    dataset_name: str
    record_id: int
    subject_id: str
    session_id: int
    session_name: str
    signal_channel: str
    file_name: str
    file_type: str
    source_url: str
    download_path: str
    content_sha256: str
    sample_rate_hz: float
    record_start_ts_utc: pd.Timestamp
    record_end_ts_utc: pd.Timestamp
    sample_count: int
    has_non_monotonic_timestamps: bool
    has_duplicate_timestamps: bool


def require_wfdb():
    try:
        import wfdb  # type: ignore
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "wfdb is required for LUDB and MIT-BIH parsing. Add it to the environment before running these optional dataset pipelines."
        ) from error
    return wfdb


def calculate_flatline_ratio(sample_values: pd.Series) -> float:
    valid_values = sample_values.dropna().reset_index(drop=True)
    if len(valid_values) <= 1:
        return 1.0
    adjacent_differences = valid_values.diff().iloc[1:]
    return float(adjacent_differences.eq(0).mean())


def calculate_mad(sample_values: pd.Series) -> float:
    valid_values = sample_values.dropna()
    if valid_values.empty:
        return 0.0
    median_value = float(valid_values.median())
    return float((valid_values - median_value).abs().median())


def build_window_frame(sample_values: pd.Series, record_context: RecordContext, window_seconds: int) -> pd.DataFrame:
    expected_sample_count = max(int(round(record_context.sample_rate_hz * window_seconds)), 1)
    sample_frame = pd.DataFrame({"sample_index": range(len(sample_values)), "sample_value": sample_values})
    sample_frame["window_offset"] = sample_frame["sample_index"] // expected_sample_count
    window_group = sample_frame.groupby("window_offset")["sample_value"]
    window_frame = window_group.agg(
        sample_count="count",
        window_mean="mean",
        window_std="std",
        window_min="min",
        window_max="max",
    ).reset_index()
    window_frame["window_iqr"] = window_group.quantile(0.75).reset_index(drop=True) - window_group.quantile(0.25).reset_index(drop=True)
    window_frame["window_mad"] = window_group.apply(calculate_mad).reset_index(drop=True)
    window_frame["flatline_ratio"] = window_group.apply(calculate_flatline_ratio).reset_index(drop=True)
    window_frame["window_std"] = window_frame["window_std"].fillna(0.0)
    window_frame["window_range"] = window_frame["window_max"] - window_frame["window_min"]
    window_frame["expected_sample_count"] = expected_sample_count
    window_frame["missing_value_ratio"] = (
        (expected_sample_count - window_frame["sample_count"]).clip(lower=0) / expected_sample_count
    )
    window_frame["window_coverage_ratio"] = (
        window_frame["sample_count"] / expected_sample_count
    ).clip(upper=1.0)
    window_frame["window_id"] = [f"{record_context.record_id}_{int(window_offset)}" for window_offset in window_frame["window_offset"]]
    window_frame["dataset_name"] = record_context.dataset_name
    window_frame["record_id"] = record_context.record_id
    window_frame["subject_id"] = record_context.subject_id
    window_frame["session_id"] = record_context.session_id
    window_frame["session_name"] = record_context.session_name
    window_frame["signal_channel"] = record_context.signal_channel
    window_frame["window_seconds"] = window_seconds
    window_frame["window_start_ts_utc"] = window_frame["window_offset"].apply(
        lambda window_offset: record_context.record_start_ts_utc + pd.Timedelta(seconds=int(window_offset) * window_seconds)
    )
    window_frame["window_end_ts_utc"] = window_frame["window_start_ts_utc"] + pd.Timedelta(seconds=window_seconds)
    return window_frame[
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
        ]
    ].copy()


def load_manifest(dataset_name: str) -> pd.DataFrame:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    manifest_path = resolve_repo_path(pipeline_config.paths.bronze_manifest_parquet)
    raw_manifest = pd.read_parquet(manifest_path)
    selected_manifest = raw_manifest.loc[raw_manifest["selected_for_download"] == True].copy()  # noqa: E712
    return selected_manifest


def build_annotation_rows(dataset_name: str, record_id: str, record_base_path: Path, annotation_extensions: list[str]) -> list[dict]:
    wfdb = require_wfdb()
    annotation_rows: list[dict] = []
    for annotation_suffix in annotation_extensions:
        annotation_extension = annotation_suffix.lstrip(".")
        annotation = wfdb.rdann(str(record_base_path), extension=annotation_extension)
        unique_symbols = sorted(set(annotation.symbol)) if annotation.symbol else []
        annotation_rows.append(
            {
                "annotation_id": f"{dataset_name}_{record_id}_{annotation_extension}_count",
                "dataset_name": dataset_name,
                "subject_id": record_id,
                "session_id": 0,
                "session_name": "",
                "source_file_name": f"{record_id}.{annotation_extension}",
                "label_name": f"{annotation_extension}_annotation_count",
                "label_value_text": "",
                "label_value_numeric": float(len(annotation.sample)),
                "label_value_boolean": pd.NA,
            }
        )
        annotation_rows.append(
            {
                "annotation_id": f"{dataset_name}_{record_id}_{annotation_extension}_symbols",
                "dataset_name": dataset_name,
                "subject_id": record_id,
                "session_id": 0,
                "session_name": "",
                "source_file_name": f"{record_id}.{annotation_extension}",
                "label_name": f"{annotation_extension}_annotation_symbols",
                "label_value_text": ",".join(unique_symbols),
                "label_value_numeric": pd.NA,
                "label_value_boolean": pd.NA,
            }
        )
    return annotation_rows


def normalize_wfdb_dataset(dataset_name: str) -> None:
    wfdb = require_wfdb()
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    manifest_frame = load_manifest(dataset_name)
    record_contexts: list[RecordContext] = []
    window_frames: list[pd.DataFrame] = []
    annotation_rows: list[dict] = []
    next_record_id = 1

    grouped_manifest = manifest_frame.groupby("record_group_id", sort=True)
    for record_group_id, record_manifest in grouped_manifest:
        header_row = record_manifest.loc[record_manifest["file_name"].str.endswith(".hea")].iloc[0]
        record_base_path = resolve_data_path(str(header_row["download_path"])).with_suffix("")
        record = wfdb.rdrecord(str(record_base_path))
        signal_frame = pd.DataFrame(record.p_signal, columns=[signal_name.lower() for signal_name in record.sig_name])
        record_start_ts_utc = pd.Timestamp("1970-01-01T00:00:00Z")
        record_duration_seconds = len(signal_frame) / float(record.fs)
        record_end_ts_utc = record_start_ts_utc + pd.to_timedelta(record_duration_seconds, unit="s")

        for signal_channel in signal_frame.columns:
            record_context = RecordContext(
                dataset_name=dataset_name,
                record_id=next_record_id,
                subject_id=str(record_group_id),
                session_id=0,
                session_name="",
                signal_channel=signal_channel,
                file_name=str(header_row["file_name"]),
                file_type="wfdb_record",
                source_url=str(header_row["source_url"]),
                download_path=to_repo_relative_path(record_base_path),
                content_sha256=str(header_row["content_sha256"]),
                sample_rate_hz=float(record.fs),
                record_start_ts_utc=record_start_ts_utc,
                record_end_ts_utc=record_end_ts_utc,
                sample_count=int(signal_frame[signal_channel].notna().sum()),
                has_non_monotonic_timestamps=False,
                has_duplicate_timestamps=False,
            )
            record_contexts.append(record_context)
            window_frames.append(
                build_window_frame(signal_frame[signal_channel], record_context, pipeline_config.windowing.window_seconds)
            )
            next_record_id += 1

        annotation_rows.extend(
            build_annotation_rows(
                dataset_name,
                str(record_group_id),
                record_base_path,
                pipeline_config.bounded_pull.required_annotation_suffixes,
            )
        )

    staging_directory = resolve_repo_path(pipeline_config.paths.staging_directory)
    staging_directory.mkdir(parents=True, exist_ok=True)

    staged_records = pd.DataFrame([record_context.__dict__ for record_context in record_contexts])
    staged_windows = pd.concat(window_frames, ignore_index=True)
    staged_annotations = pd.DataFrame(annotation_rows)

    staged_records.to_csv(staging_directory / "stg_signal_records.csv", index=False)
    staged_records.to_parquet(staging_directory / "stg_signal_records.parquet", index=False)
    staged_windows.to_csv(staging_directory / "stg_signal_windows.csv", index=False)
    staged_windows.to_parquet(staging_directory / "stg_signal_windows.parquet", index=False)
    staged_annotations.to_csv(staging_directory / "stg_annotations_or_labels.csv", index=False)
    staged_annotations.to_parquet(staging_directory / "stg_annotations_or_labels.parquet", index=False)

    print(f"wrote staged signal records, windows, and annotations for {dataset_name}")
