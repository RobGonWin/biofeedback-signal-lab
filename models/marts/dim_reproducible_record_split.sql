-- dim_reproducible_record_split
-- grain: one row per record_id split assignment.

select
  cast(dataset_name as varchar) as dataset_name,
  cast(record_id as bigint) as record_id,
  cast(subject_id as varchar) as subject_id,
  cast(session_id as bigint) as session_id,
  cast(session_name as varchar) as session_name,
  cast(signal_channel as varchar) as signal_channel,
  cast(split_seed as varchar) as split_seed,
  cast(split_bucket as varchar) as split_bucket
from read_parquet('data/curated/wearable_exam_stress/dim_reproducible_record_split.parquet')
