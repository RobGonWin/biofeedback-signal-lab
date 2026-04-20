# Configuration Guide: Biofeedback Signal Lab

This document explains how configuration works in the repo, what `.config.json` actually controls today, and which settings are safe to tweak for demos, app review, and optional dataset expansion.

## Configuration Files

There are two main config surfaces:

- `.config.json`
  Runtime toggles for enabled datasets, dbt, DuckDB, and optional Snowflake scaffolding.

- `config/dataset_slice.yaml`
  Dataset catalog, bounded pull settings, windowing rules, reproducibility settings, and output paths.

Use them for different jobs:
- use `.config.json` to control runtime behavior
- use `config/dataset_slice.yaml` to control dataset-specific pull scope and storage layout

## What `.config.json` Controls

Current file:

```json
{
  "runtime": {
    "default_query_engine": "duckdb",
    "default_delivery_target": "local",
    "allow_optional_cloud_targets": false,
    "default_dataset_name": "wearable_exam_stress"
  },
  "datasets": {
    "wearable_exam_stress": {
      "enabled": true,
      "include_in_combined_views": true
    },
    "ludb": {
      "enabled": true,
      "include_in_combined_views": true
    },
    "mitdb": {
      "enabled": true,
      "include_in_combined_views": true
    }
  },
  "local": {
    "duckdb": {
      "enabled": true,
      "warehouse_path": "outputs/warehouse/biofeedback_signal_lab.duckdb"
    }
  },
  "cloud": {
    "snowflake": {
      "enabled": false,
      "dbt_enabled": false,
      "sync_mode": "manual_curated_outputs",
      "max_sync_file_size_mb": 250,
      "max_sync_total_size_mb": 250,
      "source_directory": "data/curated",
      "allowed_file_formats": ["csv", "parquet"],
      "target_profile_name": "biofeedback_signal_lab",
      "target_database_env_var": "SNOWFLAKE_DATABASE",
      "target_schema_env_var": "SNOWFLAKE_SCHEMA",
      "target_warehouse_env_var": "SNOWFLAKE_WAREHOUSE",
      "target_role_env_var": "SNOWFLAKE_ROLE"
    }
  },
  "dbt": {
    "enabled": true,
    "project_file": "dbt_project.yml",
    "profiles_dir": "dbt",
    "target_name": "local_duckdb"
  }
}
```

## How The Current Implementation Uses `.config.json`

The runtime config is loaded in `scripts/pipeline_config.py` through `load_runtime_config()`.

Today, the most important code paths that read it are:

- `app/streamlit_app.py`
  Uses `runtime.default_dataset_name` to choose the app’s default dataset in the selector.

- `scripts/build_local_warehouse.py`
  Uses the dbt block to decide whether to run the local dbt build path.

- `macros/combined_views.sql`
  Reads dataset toggles from `.config.json` so dbt can build the `_all` views only for enabled datasets.

That means `.config.json` affects:
- which datasets show up in the app
- which datasets are included in `_all` warehouse views
- whether dbt is the active local warehouse build path
- whether optional Snowflake scaffolding is considered enabled

## Field-by-Field Guide

### `runtime`

- `default_query_engine`
  Current expected value: `duckdb`
  This is descriptive for the current local-first build. The working demo path assumes DuckDB.

- `default_delivery_target`
  Current expected value: `local`
  Signals that the main delivery path is local rather than cloud.

- `allow_optional_cloud_targets`
  Current expected value: `false`
  Keeps the project centered on the local demo path.

- `default_dataset_name`
  Current expected value: `wearable_exam_stress`
  Controls the default dataset in the Streamlit selector and the default dataset used by several helper scripts.

### `datasets`

Each dataset has:
- `enabled`
- `include_in_combined_views`

Meaning:
- `enabled=true`
  The dataset is considered active for runtime use.

- `include_in_combined_views=true`
  The dataset is eligible for dbt-built `_all` views such as `fct_record_features_all` and `raw_signal_files_all`.

Practical behavior:
- if both are `true`, the dataset can appear in the app once its parquet outputs exist
- if `enabled=false`, the dataset is treated as off
- if `enabled=true` but `include_in_combined_views=false`, the dataset can still exist on disk but will not be unioned into `_all` views

### `local.duckdb`

- `enabled`
  Current expected value: `true`
  The project’s canonical demo path expects DuckDB to be enabled.

- `warehouse_path`
  Points to the DuckDB file used by dbt, validations, and Streamlit.

### `cloud.snowflake`

These values are scaffolding for a later optional cloud publishing path. They do not drive the core demo workflow today.

- `enabled`
  Leave `false` for the default demo path.

- `dbt_enabled`
  Leave `false` unless a real Snowflake dbt path is added.

- `sync_mode`
  Describes the intended sync style. Current value: `manual_curated_outputs`.

- `max_sync_file_size_mb`
- `max_sync_total_size_mb`
  Guardrails for future sync scope.

- `source_directory`
- `allowed_file_formats`
  Define what the future sync path would consider valid local outputs.

- `target_*_env_var`
  These point to environment variable names rather than hardcoded secrets.

### `dbt`

- `enabled`
  Current expected value: `true`
  When true, the local warehouse build path uses dbt.

- `project_file`
  Current expected value: `dbt_project.yml`

- `profiles_dir`
  Current expected value: `dbt`

- `target_name`
  Current expected value: `local_duckdb`
  This should stay aligned with `dbt/profiles.yml`.

## Safe Tweaks

These are the lowest-risk config edits for normal portfolio use.

### 1. Change the app’s default dataset

```json
"runtime": {
  "default_dataset_name": "ludb"
}
```

Use this if you want the Streamlit app to open on LUDB or MIT-BIH instead of Wearable Exam Stress.

### 2. Hide optional datasets from the app and `_all` views

```json
"datasets": {
  "wearable_exam_stress": {
    "enabled": true,
    "include_in_combined_views": true
  },
  "ludb": {
    "enabled": false,
    "include_in_combined_views": false
  },
  "mitdb": {
    "enabled": false,
    "include_in_combined_views": false
  }
}
```

Use this if you want the repo to present only the default wearable story.

### 3. Keep multiple datasets enabled in the app

```json
"datasets": {
  "wearable_exam_stress": {
    "enabled": true,
    "include_in_combined_views": true
  },
  "ludb": {
    "enabled": true,
    "include_in_combined_views": true
  },
  "mitdb": {
    "enabled": true,
    "include_in_combined_views": true
  }
}
```

Use this if you want the app selector to show all datasets that have been materialized locally.

### 4. Keep Snowflake scaffolding off

```json
"cloud": {
  "snowflake": {
    "enabled": false,
    "dbt_enabled": false
  }
}
```

This is still the recommended default for demo use.

## When To Edit `config/dataset_slice.yaml` Instead

Do not use `.config.json` for dataset pull scope.

Edit `config/dataset_slice.yaml` when you want to change:
- selected subject IDs
- selected session names
- selected WFDB record IDs
- required file suffixes
- bounded pull limits
- window lengths
- output folder layout

Examples:
- narrowing the wearable slice from `S1-S6` to `S1-S3`
- expanding LUDB from 5 records to 10
- changing MIT-BIH window size from 30 seconds to something else

## Recommended Setup Patterns

### Demo-Only Wearable Setup

Best when you want the cleanest project story:

- `default_dataset_name = wearable_exam_stress`
- `wearable_exam_stress.enabled = true`
- `ludb.enabled = false`
- `mitdb.enabled = false`

### Multi-Dataset Review Setup

Best when you want to show extensibility:

- `default_dataset_name = wearable_exam_stress`
- all three datasets enabled
- all three `include_in_combined_views = true`

### Future Snowflake Setup

Best when you only want scaffolding present:

- keep Snowflake `enabled = false`
- keep `dbt_enabled = false`
- set env vars separately in `.env` or your shell

## Rebuild Steps After Config Changes

If you change dataset toggles in `.config.json`, rebuild the warehouse:

```bash
dbt run --project-dir . --profiles-dir dbt --target local_duckdb
dbt test --project-dir . --profiles-dir dbt --target local_duckdb
python scripts/run_validations.py
streamlit run app/streamlit_app.py
```

If you change pull scope or path settings in `config/dataset_slice.yaml`, rerun the affected ingestion and transform steps before rebuilding dbt.

## Practical Notes

- Do not run `dbt run` and `dbt test` at the same time against the same DuckDB file.
- `.config.json` affects runtime behavior, not raw file parsing rules.
- `config/dataset_slice.yaml` affects data scope and storage layout.
- The current demo path is still local-first: Python + Parquet + DuckDB + dbt + Streamlit.
