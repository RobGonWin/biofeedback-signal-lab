-- stg_annotations_or_labels
-- grain: one row per subject-session label summary derived from sparse source files.

select
  cast(dataset_name as varchar) as dataset_name,
  cast(annotation_id as varchar) as annotation_id,
  cast(subject_id as varchar) as subject_id,
  cast(session_id as bigint) as session_id,
  cast(session_name as varchar) as session_name,
  cast(source_file_name as varchar) as source_file_name,
  cast(label_name as varchar) as label_name,
  cast(label_value_text as varchar) as label_value_text,
  cast(label_value_numeric as double) as label_value_numeric,
  cast(label_value_boolean as boolean) as label_value_boolean
from read_parquet('data/staging/wearable_exam_stress/stg_annotations_or_labels.parquet')
