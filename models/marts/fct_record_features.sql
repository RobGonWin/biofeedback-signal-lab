-- fct_record_features
-- grain: one row per staged record_id at the subject-session-channel level.

select
  cast(dataset_name as varchar) as dataset_name,
  cast(record_id as bigint) as record_id,
  cast(subject_id as varchar) as subject_id,
  cast(session_id as bigint) as session_id,
  cast(session_name as varchar) as session_name,
  cast(signal_channel as varchar) as signal_channel,
  cast(file_name as varchar) as file_name,
  cast(file_type as varchar) as file_type,
  cast(sample_rate_hz as double) as sample_rate_hz,
  cast(sample_count as bigint) as sample_count,
  cast(window_count as bigint) as window_count,
  cast(record_missing_value_ratio as double) as record_missing_value_ratio,
  cast(record_flatline_ratio as double) as record_flatline_ratio,
  cast(avg_window_coverage_ratio as double) as avg_window_coverage_ratio,
  cast(avg_window_std as double) as avg_window_std,
  cast(low_coverage_window_count as bigint) as low_coverage_window_count,
  cast(flatline_window_count as bigint) as flatline_window_count,
  cast(high_motion_window_count as bigint) as high_motion_window_count,
  cast(higher_relative_variability_window_count as bigint) as higher_relative_variability_window_count,
  cast(record_signal_quality_score as double) as record_signal_quality_score,
  cast(has_non_monotonic_timestamps as boolean) as has_non_monotonic_timestamps,
  cast(has_duplicate_timestamps as boolean) as has_duplicate_timestamps
from read_parquet('data/curated/wearable_exam_stress/fct_record_features.parquet')
