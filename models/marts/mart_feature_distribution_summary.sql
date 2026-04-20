-- mart_feature_distribution_summary
-- grain: one row per signal_channel x feature_name summary statistic set.

select
  cast(dataset_name as varchar) as dataset_name,
  cast(signal_channel as varchar) as signal_channel,
  cast(feature_name as varchar) as feature_name,
  cast(feature_mean as double) as feature_mean,
  cast(feature_median as double) as feature_median,
  cast(feature_p90 as double) as feature_p90
from read_parquet('data/curated/wearable_exam_stress/mart_feature_distribution_summary.parquet')
