-- mart_subject_or_session_summary
-- grain: one row per subject_id x session_id x signal_channel.

with session_summary as (
  select
    dataset_name,
    subject_id,
    session_id,
    session_name,
    signal_channel,
    count(*) as window_count,
    avg(window_std) as avg_window_std,
    avg(missing_value_ratio) as avg_missing_value_ratio,
    avg(window_coverage_ratio) as avg_window_coverage_ratio,
    sum(case when is_low_coverage_window then 1 else 0 end) as low_coverage_window_count,
    sum(case when is_flatline_like_window then 1 else 0 end) as flatline_window_count,
    sum(case when is_high_motion_window then 1 else 0 end) as high_motion_window_count,
    sum(case when is_higher_relative_variability_window then 1 else 0 end) as higher_relative_variability_window_count
  from read_parquet('data/curated/wearable_exam_stress/fct_window_features.parquet')
  group by
    dataset_name,
    subject_id,
    session_id,
    session_name,
    signal_channel
)
select
  dataset_name,
  subject_id,
  session_id,
  session_name,
  signal_channel,
  window_count,
  avg_window_std,
  avg_missing_value_ratio,
  avg_window_coverage_ratio,
  low_coverage_window_count,
  flatline_window_count,
  high_motion_window_count,
  higher_relative_variability_window_count
from session_summary
order by dataset_name, subject_id, session_id, signal_channel
