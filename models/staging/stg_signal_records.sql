-- stg_signal_records
-- grain: one row per staged subject-session-channel record parsed from dense sensor files.

select
  cast(dataset_name as varchar) as dataset_name,
  cast(record_id as bigint) as record_id,
  cast(subject_id as varchar) as subject_id,
  cast(session_id as bigint) as session_id,
  cast(session_name as varchar) as session_name,
  cast(signal_channel as varchar) as signal_channel,
  cast(file_name as varchar) as file_name,
  cast(file_type as varchar) as file_type,
  cast(source_url as varchar) as source_url,
  cast(download_path as varchar) as download_path,
  cast(content_sha256 as varchar) as content_sha256,
  cast(sample_rate_hz as double) as sample_rate_hz,
  cast(record_start_ts_utc as timestamp) as record_start_ts_utc,
  cast(record_end_ts_utc as timestamp) as record_end_ts_utc,
  cast(sample_count as bigint) as sample_count,
  cast(has_non_monotonic_timestamps as boolean) as has_non_monotonic_timestamps,
  cast(has_duplicate_timestamps as boolean) as has_duplicate_timestamps
from read_parquet('data/staging/wearable_exam_stress/stg_signal_records.parquet')
