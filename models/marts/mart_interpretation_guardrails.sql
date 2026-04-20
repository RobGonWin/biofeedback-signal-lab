-- mart_interpretation_guardrails
-- grain: one row per interpretation guardrail statement.

select
  cast(dataset_name as varchar) as dataset_name,
  cast(guardrail_id as bigint) as guardrail_id,
  cast(what_features_may_suggest as varchar) as what_features_may_suggest,
  cast(what_features_do_not_prove as varchar) as what_features_do_not_prove
from read_parquet('data/curated/wearable_exam_stress/mart_interpretation_guardrails.parquet')
order by guardrail_id
