-- raw_signal_files
-- grain: one row per discovered remote artifact in the bronze manifest.

select
  cast(dataset_name as varchar) as dataset_name,
  cast(source_url as varchar) as source_url,
  cast(file_name as varchar) as file_name,
  cast(subject_id as varchar) as subject_id,
  cast(session_name as varchar) as session_name,
  cast(record_group_id as varchar) as record_group_id,
  cast(record_id as varchar) as record_id,
  cast(file_type as varchar) as file_type,
  cast(file_role as varchar) as file_role,
  cast(selection_group as varchar) as selection_group,
  cast(discovered_at_utc as timestamp) as discovered_at_utc,
  cast(content_sha256 as varchar) as content_sha256,
  cast(content_length_bytes as bigint) as content_length_bytes,
  cast(selected_for_download as boolean) as selected_for_download,
  cast(download_path as varchar) as download_path,
  cast(is_within_limit as boolean) as is_within_limit
from read_parquet('data/bronze/wearable_exam_stress/raw_metadata_manifest.parquet')
