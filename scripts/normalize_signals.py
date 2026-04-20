"""Normalize downloaded sensor files into staged records, windows, and annotations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd
from pandas.errors import EmptyDataError

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_config import get_session_id, load_pipeline_config, resolve_data_path, resolve_repo_path


REQUIRED_MANIFEST_COLUMNS = {
    "dataset_name",
    "source_url",
    "file_name",
    "subject_id",
    "session_name",
    "record_group_id",
    "record_id",
    "file_type",
    "file_role",
    "selection_group",
    "discovered_at_utc",
    "content_sha256",
    "content_length_bytes",
    "selected_for_download",
    "download_path",
    "is_within_limit",
}

DENSE_SIGNAL_FILE_TYPES = {"acc", "bvp", "eda", "hr", "temp"}


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


def load_raw_manifest(manifest_path: Path) -> pd.DataFrame:
    """Load the bronze manifest from Parquet."""
    raw_manifest = pd.read_parquet(manifest_path)
    return raw_manifest


def validate_manifest_schema(raw_manifest: pd.DataFrame) -> None:
    """Validate the manifest schema before downstream transforms."""
    actual_columns = set(raw_manifest.columns)
    missing_columns = REQUIRED_MANIFEST_COLUMNS - actual_columns
    if missing_columns:
        raise ValueError(f"missing required manifest columns: {sorted(missing_columns)}")


def filter_selected_downloads(raw_manifest: pd.DataFrame) -> pd.DataFrame:
    """Return only the files downloaded for signal normalization."""
    selected_manifest = raw_manifest.loc[raw_manifest["selected_for_download"] == True].copy()  # noqa: E712
    selected_manifest["dataset_name"] = selected_manifest["dataset_name"].astype(str)
    selected_manifest["file_type"] = selected_manifest["file_type"].str.lower()
    selected_manifest["subject_id"] = selected_manifest["subject_id"].astype(str)
    selected_manifest["session_name"] = selected_manifest["session_name"].astype(str)
    selected_manifest = selected_manifest.sort_values(["subject_id", "session_name", "file_name"]).reset_index(drop=True)
    return selected_manifest


def parse_scalar_signal_file(file_path: Path) -> tuple[float, float, pd.Series]:
    """Parse a scalar CSV file with start timestamp, sample rate, and one value column."""
    raw_frame = pd.read_csv(file_path, header=None)
    start_epoch_seconds = float(str(raw_frame.iloc[0, 0]).strip())
    sample_rate_hz = float(str(raw_frame.iloc[1, 0]).strip())
    sample_values = pd.to_numeric(raw_frame.iloc[2:, 0], errors="coerce").reset_index(drop=True)
    return start_epoch_seconds, sample_rate_hz, sample_values


def parse_acc_signal_file(file_path: Path) -> tuple[float, float, pd.DataFrame]:
    """Parse the three-axis ACC file and derive a magnitude column."""
    raw_frame = pd.read_csv(file_path, header=None)
    start_epoch_seconds = float(str(raw_frame.iloc[0, 0]).strip())
    sample_rate_hz = float(str(raw_frame.iloc[1, 0]).strip())
    acc_axis_frame = raw_frame.iloc[2:, :3].apply(pd.to_numeric, errors="coerce").reset_index(drop=True)
    acc_axis_frame.columns = ["acc_x", "acc_y", "acc_z"]
    acc_axis_frame["acc_magnitude"] = acc_axis_frame.pow(2).sum(axis=1).pow(0.5)
    return start_epoch_seconds, sample_rate_hz, acc_axis_frame


def calculate_flatline_ratio(sample_values: pd.Series) -> float:
    """Estimate the share of adjacent values that do not change."""
    valid_values = sample_values.dropna().reset_index(drop=True)
    if len(valid_values) <= 1:
        return 1.0

    adjacent_differences = valid_values.diff().iloc[1:]
    flatline_ratio = float(adjacent_differences.eq(0).mean())
    return flatline_ratio


def calculate_mad(sample_values: pd.Series) -> float:
    """Compute median absolute deviation for one sample series."""
    valid_values = sample_values.dropna()
    if valid_values.empty:
        return 0.0

    median_value = float(valid_values.median())
    mad_value = float((valid_values - median_value).abs().median())
    return mad_value


def build_window_frame(
    sample_values: pd.Series,
    record_context: RecordContext,
    window_seconds: int,
) -> pd.DataFrame:
    """Aggregate dense samples into fixed windows with feature scaffolding."""
    expected_sample_count = max(int(round(record_context.sample_rate_hz * window_seconds)), 1)
    sample_frame = pd.DataFrame(
        {
            "sample_index": range(len(sample_values)),
            "sample_value": sample_values,
        }
    )
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
    ordered_window_frame = window_frame[
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
    return ordered_window_frame


def build_record_frame(record_contexts: list[RecordContext]) -> pd.DataFrame:
    """Convert record contexts to a staged records DataFrame."""
    record_frame = pd.DataFrame([record_context.__dict__ for record_context in record_contexts])
    return record_frame


def build_annotation_rows_for_ibi(
    subject_id: str,
    session_name: str,
    file_name: str,
    file_path: Path,
) -> list[dict]:
    """Build annotation summaries from IBI offsets and intervals."""
    try:
        raw_frame = pd.read_csv(file_path, header=None)
        start_epoch_seconds = float(str(raw_frame.iloc[0, 0]).strip())
        ibi_offsets = pd.to_numeric(raw_frame.iloc[1:, 0], errors="coerce").dropna().reset_index(drop=True)
        ibi_values = pd.to_numeric(raw_frame.iloc[1:, 1], errors="coerce").dropna().reset_index(drop=True)
        ibi_event_epochs = start_epoch_seconds + ibi_offsets
    except EmptyDataError:
        ibi_values = pd.Series(dtype="float64")
        ibi_event_epochs = pd.Series(dtype="float64")

    annotation_rows = [
        {
            "annotation_id": f"{subject_id}_{session_name}_{file_name}_ibi_count",
            "dataset_name": "wearable_exam_stress",
            "subject_id": subject_id,
            "session_id": get_session_id(session_name),
            "session_name": session_name,
            "source_file_name": file_name,
            "label_name": "ibi_interval_count",
            "label_value_text": "",
            "label_value_numeric": float(len(ibi_values)),
            "label_value_boolean": pd.NA,
        },
        {
            "annotation_id": f"{subject_id}_{session_name}_{file_name}_ibi_mean_seconds",
            "dataset_name": "wearable_exam_stress",
            "subject_id": subject_id,
            "session_id": get_session_id(session_name),
            "session_name": session_name,
            "source_file_name": file_name,
            "label_name": "ibi_mean_seconds",
            "label_value_text": "",
            "label_value_numeric": float(ibi_values.mean()) if not ibi_values.empty else 0.0,
            "label_value_boolean": pd.NA,
        },
        {
            "annotation_id": f"{subject_id}_{session_name}_{file_name}_ibi_times_are_monotonic",
            "dataset_name": "wearable_exam_stress",
            "subject_id": subject_id,
            "session_id": get_session_id(session_name),
            "session_name": session_name,
            "source_file_name": file_name,
            "label_name": "ibi_times_are_monotonic",
            "label_value_text": "",
            "label_value_numeric": pd.NA,
            "label_value_boolean": bool(ibi_event_epochs.is_monotonic_increasing),
        },
    ]
    return annotation_rows


def build_annotation_rows_for_tags(
    subject_id: str,
    session_name: str,
    file_name: str,
    file_path: Path,
) -> list[dict]:
    """Build annotation summaries from tag event timestamps."""
    try:
        tag_frame = pd.read_csv(file_path, header=None)
        tag_epochs = pd.to_numeric(tag_frame.iloc[:, 0], errors="coerce").dropna().reset_index(drop=True)
    except EmptyDataError:
        tag_epochs = pd.Series(dtype="float64")
    annotation_rows = [
        {
            "annotation_id": f"{subject_id}_{session_name}_{file_name}_tag_count",
            "dataset_name": "wearable_exam_stress",
            "subject_id": subject_id,
            "session_id": get_session_id(session_name),
            "session_name": session_name,
            "source_file_name": file_name,
            "label_name": "tag_event_count",
            "label_value_text": "",
            "label_value_numeric": float(len(tag_epochs)),
            "label_value_boolean": pd.NA,
        },
        {
            "annotation_id": f"{subject_id}_{session_name}_{file_name}_tag_times_are_monotonic",
            "dataset_name": "wearable_exam_stress",
            "subject_id": subject_id,
            "session_id": get_session_id(session_name),
            "session_name": session_name,
            "source_file_name": file_name,
            "label_name": "tag_times_are_monotonic",
            "label_value_text": "",
            "label_value_numeric": pd.NA,
            "label_value_boolean": bool(tag_epochs.is_monotonic_increasing),
        },
    ]
    return annotation_rows


def build_annotation_rows_for_info(
    subject_id: str,
    session_name: str,
    file_name: str,
    file_path: Path,
) -> list[dict]:
    """Build annotation summaries from info.txt metadata."""
    info_lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    excerpt_text = " ".join(line.strip() for line in info_lines[:3]).strip()
    annotation_rows = [
        {
            "annotation_id": f"{subject_id}_{session_name}_{file_name}_info_present",
            "dataset_name": "wearable_exam_stress",
            "subject_id": subject_id,
            "session_id": get_session_id(session_name),
            "session_name": session_name,
            "source_file_name": file_name,
            "label_name": "info_present",
            "label_value_text": "",
            "label_value_numeric": pd.NA,
            "label_value_boolean": True,
        },
        {
            "annotation_id": f"{subject_id}_{session_name}_{file_name}_info_excerpt",
            "dataset_name": "wearable_exam_stress",
            "subject_id": subject_id,
            "session_id": get_session_id(session_name),
            "session_name": session_name,
            "source_file_name": file_name,
            "label_name": "info_excerpt",
            "label_value_text": excerpt_text,
            "label_value_numeric": pd.NA,
            "label_value_boolean": pd.NA,
        },
    ]
    return annotation_rows


def parse_dense_signal_rows(
    manifest_row: pd.Series,
    next_record_id: int,
    window_seconds: int,
) -> tuple[list[RecordContext], list[pd.DataFrame], int]:
    """Parse one dense sensor file into staged record contexts and window frames."""
    file_path = resolve_data_path(str(manifest_row["download_path"]))
    file_type = str(manifest_row["file_type"]).lower()
    subject_id = str(manifest_row["subject_id"])
    session_name = str(manifest_row["session_name"])
    dataset_name = str(manifest_row["dataset_name"])
    session_id = get_session_id(session_name)

    if file_type == "acc":
        start_epoch_seconds, sample_rate_hz, channel_frame = parse_acc_signal_file(file_path)
    else:
        start_epoch_seconds, sample_rate_hz, sample_values = parse_scalar_signal_file(file_path)
        channel_frame = pd.DataFrame({file_type: sample_values})

    record_start_ts_utc = pd.to_datetime(start_epoch_seconds, unit="s", utc=True)
    record_duration_seconds = len(channel_frame) / sample_rate_hz if sample_rate_hz else 0.0
    record_end_ts_utc = record_start_ts_utc + pd.to_timedelta(record_duration_seconds, unit="s")

    record_contexts: list[RecordContext] = []
    window_frames: list[pd.DataFrame] = []

    for signal_channel in channel_frame.columns:
        record_context = RecordContext(
            dataset_name=dataset_name,
            record_id=next_record_id,
            subject_id=subject_id,
            session_id=session_id,
            session_name=session_name,
            signal_channel=signal_channel,
            file_name=str(manifest_row["file_name"]),
            file_type=file_type,
            source_url=str(manifest_row["source_url"]),
            download_path=str(manifest_row["download_path"]),
            content_sha256=str(manifest_row["content_sha256"]),
            sample_rate_hz=float(sample_rate_hz),
            record_start_ts_utc=record_start_ts_utc,
            record_end_ts_utc=record_end_ts_utc,
            sample_count=int(channel_frame[signal_channel].notna().sum()),
            has_non_monotonic_timestamps=False,
            has_duplicate_timestamps=False,
        )
        record_contexts.append(record_context)
        window_frames.append(
            build_window_frame(
                channel_frame[signal_channel],
                record_context,
                window_seconds,
            )
        )
        next_record_id += 1

    return record_contexts, window_frames, next_record_id


def build_staged_outputs(selected_manifest: pd.DataFrame, window_seconds: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build staged records, windows, and annotations from the downloaded slice."""
    record_contexts: list[RecordContext] = []
    window_frames: list[pd.DataFrame] = []
    annotation_rows: list[dict] = []
    next_record_id = 1

    for _, manifest_row in selected_manifest.iterrows():
        file_type = str(manifest_row["file_type"]).lower()
        file_path = resolve_data_path(str(manifest_row["download_path"]))
        subject_id = str(manifest_row["subject_id"])
        session_name = str(manifest_row["session_name"])
        file_name = str(manifest_row["file_name"])

        if file_type in DENSE_SIGNAL_FILE_TYPES:
            parsed_record_contexts, parsed_window_frames, next_record_id = parse_dense_signal_rows(
                manifest_row,
                next_record_id,
                window_seconds,
            )
            record_contexts.extend(parsed_record_contexts)
            window_frames.extend(parsed_window_frames)
            continue

        if file_type == "ibi":
            annotation_rows.extend(
                build_annotation_rows_for_ibi(subject_id, session_name, file_name, file_path)
            )
            continue

        if file_type == "tags":
            annotation_rows.extend(
                build_annotation_rows_for_tags(subject_id, session_name, file_name, file_path)
            )
            continue

        if file_type == "info":
            annotation_rows.extend(
                build_annotation_rows_for_info(subject_id, session_name, file_name, file_path)
            )

    staged_records = build_record_frame(record_contexts)
    staged_windows = pd.concat(window_frames, ignore_index=True)
    staged_annotations_or_labels = pd.DataFrame(annotation_rows)

    return staged_records, staged_windows, staged_annotations_or_labels


def write_staged_outputs(
    staged_records: pd.DataFrame,
    staged_windows: pd.DataFrame,
    staged_annotations_or_labels: pd.DataFrame,
) -> None:
    """Persist staged outputs as both CSV and Parquet."""
    pipeline_config = load_pipeline_config()
    output_directory = resolve_repo_path(pipeline_config.paths.staging_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    staged_records.to_csv(output_directory / "stg_signal_records.csv", index=False)
    staged_records.to_parquet(output_directory / "stg_signal_records.parquet", index=False)

    staged_windows.to_csv(output_directory / "stg_signal_windows.csv", index=False)
    staged_windows.to_parquet(output_directory / "stg_signal_windows.parquet", index=False)

    staged_annotations_or_labels.to_csv(
        output_directory / "stg_annotations_or_labels.csv", index=False
    )
    staged_annotations_or_labels.to_parquet(
        output_directory / "stg_annotations_or_labels.parquet", index=False
    )


def main() -> None:
    pipeline_config = load_pipeline_config()
    manifest_path = resolve_repo_path(pipeline_config.paths.bronze_manifest_parquet)
    raw_manifest = load_raw_manifest(manifest_path)
    validate_manifest_schema(raw_manifest)
    selected_manifest = filter_selected_downloads(raw_manifest)

    staged_records, staged_windows, staged_annotations_or_labels = build_staged_outputs(
        selected_manifest,
        pipeline_config.windowing.window_seconds,
    )
    write_staged_outputs(
        staged_records,
        staged_windows,
        staged_annotations_or_labels,
    )

    print("wrote staged signal records, windows, and annotations")


if __name__ == "__main__":
    main()
