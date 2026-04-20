{% macro get_runtime_dataset_toggle(dataset_name, toggle_name) %}
  {% if not execute %}
    {{ return(false) }}
  {% endif %}

  {% set toggle_sql %}
    select
      case '{{ dataset_name }}'
        when 'wearable_exam_stress' then datasets.wearable_exam_stress.{{ toggle_name }}
        when 'ludb' then datasets.ludb.{{ toggle_name }}
        when 'mitdb' then datasets.mitdb.{{ toggle_name }}
      end as toggle_value
    from read_json_auto('.config.json')
  {% endset %}

  {% set toggle_result = run_query(toggle_sql) %}
  {% if toggle_result is none %}
    {{ return(false) }}
  {% endif %}

  {% set toggle_value = toggle_result.columns[0].values()[0] %}
  {{ return(toggle_value) }}
{% endmacro %}

{% macro get_combined_view_file_name(combined_view_name) %}
  {% set combined_view_file_names = {
    'raw_signal_files_all': 'raw_metadata_manifest.parquet',
    'stg_signal_records_all': 'stg_signal_records.parquet',
    'stg_signal_windows_all': 'stg_signal_windows.parquet',
    'stg_annotations_or_labels_all': 'stg_annotations_or_labels.parquet',
    'fct_record_features_all': 'fct_record_features.parquet',
    'fct_window_features_all': 'fct_window_features.parquet',
    'dim_reproducible_record_split_all': 'dim_reproducible_record_split.parquet',
    'mart_subject_or_session_summary_all': 'mart_subject_or_session_summary.parquet',
    'mart_feature_distribution_summary_all': 'mart_feature_distribution_summary.parquet',
    'mart_interpretation_guardrails_all': 'mart_interpretation_guardrails.parquet'
  } %}

  {{ return(combined_view_file_names[combined_view_name]) }}
{% endmacro %}

{% macro get_dataset_output_path(dataset_name, combined_view_name) %}
  {% set file_name = get_combined_view_file_name(combined_view_name) %}

  {% if combined_view_name == 'raw_signal_files_all' %}
    {% set dataset_paths = {
      'wearable_exam_stress': 'data/bronze/wearable_exam_stress/raw_metadata_manifest.parquet',
      'ludb': 'data/bronze/ludb/raw_metadata_manifest.parquet',
      'mitdb': 'data/bronze/mitdb/raw_metadata_manifest.parquet'
    } %}
    {{ return(dataset_paths[dataset_name]) }}
  {% endif %}

  {% if combined_view_name.startswith('stg_') %}
    {% set dataset_paths = {
      'wearable_exam_stress': 'data/staging/wearable_exam_stress/' ~ file_name,
      'ludb': 'data/staging/ludb/' ~ file_name,
      'mitdb': 'data/staging/mitdb/' ~ file_name
    } %}
    {{ return(dataset_paths[dataset_name]) }}
  {% endif %}

  {% set dataset_paths = {
    'wearable_exam_stress': 'data/curated/wearable_exam_stress/' ~ file_name,
    'ludb': 'data/curated/ludb/' ~ file_name,
    'mitdb': 'data/curated/mitdb/' ~ file_name
  } %}
  {{ return(dataset_paths[dataset_name]) }}
{% endmacro %}

{% macro parquet_file_exists(parquet_path) %}
  {% if not execute %}
    {{ return(false) }}
  {% endif %}

  {% set existence_sql %}
    select count(*) > 0 as parquet_exists
    from glob('{{ parquet_path }}')
  {% endset %}

  {% set existence_result = run_query(existence_sql) %}
  {% if existence_result is none %}
    {{ return(false) }}
  {% endif %}

  {% set parquet_exists = existence_result.columns[0].values()[0] %}
  {{ return(parquet_exists) }}
{% endmacro %}

{% macro build_combined_model_sql(combined_view_name) %}
  {% set candidate_datasets = ['wearable_exam_stress', 'ludb', 'mitdb'] %}
  {% set select_statements = [] %}

  {% for dataset_name in candidate_datasets %}
    {% set dataset_path = get_dataset_output_path(dataset_name, combined_view_name) %}
    {% set is_enabled = get_runtime_dataset_toggle(dataset_name, 'enabled') %}
    {% set is_included = get_runtime_dataset_toggle(dataset_name, 'include_in_combined_views') %}
    {% set parquet_exists = parquet_file_exists(dataset_path) %}

    {% if is_enabled and is_included and parquet_exists %}
      {% do select_statements.append("select * from read_parquet('" ~ dataset_path ~ "')") %}
    {% endif %}
  {% endfor %}

  {% if select_statements | length == 0 %}
    {{ return("select 1 as no_rows where false") }}
  {% endif %}

  {{ return(select_statements | join('\nunion all\n')) }}
{% endmacro %}
