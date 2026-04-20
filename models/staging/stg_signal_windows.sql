-- stg_signal_windows
-- grain: one row per staged subject-session-channel fixed window.

select
  cast(dataset_name as varchar) as dataset_name,
  cast(window_id as varchar) as window_id,
  cast(record_id as bigint) as record_id,
  cast(subject_id as varchar) as subject_id,
  cast(session_id as bigint) as session_id,
  cast(session_name as varchar) as session_name,
  cast(signal_channel as varchar) as signal_channel,
  cast(window_start_ts_utc as timestamp) as window_start_ts_utc,
  cast(window_end_ts_utc as timestamp) as window_end_ts_utc,
  cast(window_seconds as bigint) as window_seconds,
  cast(expected_sample_count as bigint) as expected_sample_count,
  cast(sample_count as bigint) as sample_count,
  cast(window_coverage_ratio as double) as window_coverage_ratio,
  cast(missing_value_ratio as double) as missing_value_ratio,
  cast(flatline_ratio as double) as flatline_ratio,
  cast(window_mean as double) as window_mean,
  cast(window_std as double) as window_std,
  cast(window_min as double) as window_min,
  cast(window_max as double) as window_max,
  cast(window_iqr as double) as window_iqr,
  cast(window_mad as double) as window_mad,
  cast(window_range as double) as window_range
from read_parquet('data/staging/wearable_exam_stress/stg_signal_windows.parquet')
