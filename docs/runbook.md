# Runbook: Biofeedback Signal Lab

## Purpose
This runbook documents the reproducible phase-1 pipeline for the bounded Wearable Exam Stress slice and the local DuckDB review workflow.

Optional LUDB and MIT-BIH support is also available behind dataset-specific scripts and runtime toggles.

## Inputs and Bounds
- dataset: Wearable Exam Stress v1.0.0
- subjects: `S1`-`S6`
- sessions: `midterm_1`, `midterm_2`
- required files per session: `ACC.csv`, `BVP.csv`, `EDA.csv`, `HR.csv`, `IBI.csv`, `TEMP.csv`, `tags.csv`, `info.txt`
- single-file limit: 250 MB
- total bounded pull target: 250 MB

All bounds are configured in [config/dataset_slice.yaml](../config/dataset_slice.yaml).

Runtime delivery options are configured separately in [.config.json](../.config.json).
- keep `cloud.snowflake.enabled` set to `false` to disable Snowflake manually
- keep `dbt.enabled` set to `true` for the local DuckDB `dbt run` and `dbt test` flow
- keep `cloud.snowflake.dbt_enabled` set to `false` until a real Snowflake load path is added
- adjust `max_sync_file_size_mb` and `max_sync_total_size_mb` there if you later add optional warehouse sync behavior
- use `datasets.ludb.enabled` and `datasets.mitdb.enabled` to control whether those datasets are included in combined warehouse views

## Pipeline Steps
1. Run HEAD preflight checks against the dataset page, file listing, data listing, and zip endpoint.
2. Traverse the PhysioNet `/data/` tree for the configured subject and session slice.
3. Download only the bounded session files and write a bronze manifest.
4. Parse dense sensor files into staged records and fixed windows.
5. Parse `IBI.csv`, `tags.csv`, and `info.txt` into staged annotation summaries.
6. Build curated record, window, and session features plus interpretation guardrails.
7. Build deterministic train and validation split metadata.
8. Build the local DuckDB warehouse views from staged and curated outputs.
   `dbt run` builds both the core review models and the combined `_all` views the Streamlit app reads.
9. Run `dbt test`, validations, and pytest.
10. Launch Streamlit for review.

Optional LUDB and MIT-BIH steps:
1. Ingest the bounded record slice with `scripts/ingest_ludb.py` or `scripts/ingest_mitdb.py`.
2. Normalize the WFDB files with `scripts/normalize_ludb.py` or `scripts/normalize_mitdb.py`.
3. Extract curated features and reproducible splits for that dataset.
4. Rebuild the local warehouse so the `_all` combined views pick up any enabled dataset outputs.

## Commands
```bash
python scripts/head_preflight.py
python scripts/ingest_wearable_exam_stress.py
python scripts/normalize_signals.py
python scripts/extract_features.py
python scripts/build_reproducible_split.py
dbt run --project-dir . --profiles-dir dbt --target local_duckdb
dbt test --project-dir . --profiles-dir dbt --target local_duckdb
python scripts/run_validations.py
pytest -q
streamlit run app/streamlit_app.py
```

`python scripts/build_local_warehouse.py` remains available as a convenience wrapper if you prefer one command for the local dbt warehouse build.

## Output Paths
- bronze manifest: `data/bronze/wearable_exam_stress/raw_metadata_manifest.csv` and `.parquet`
- staged tables: `data/staging/wearable_exam_stress/`
- curated tables: `data/curated/wearable_exam_stress/`
- DuckDB warehouse: `outputs/warehouse/biofeedback_signal_lab.duckdb`
- preflight manifest: `outputs/manifests/head_preflight_manifest.json`

## Validation Expectations
- every selected subject-session should have the full required session file set
- staged records should expose `acc_x`, `acc_y`, `acc_z`, `acc_magnitude`, `bvp`, `eda`, `hr`, and `temp`
- window coverage and missingness ratios should remain within `[0, 1]`
- deterministic split should contain only `train` and `validation`
- DuckDB views should build and return rows

## Failure Modes
- empty `tags.csv` files are valid and should result in zero-count annotations
- if download resumes after interruption, existing files are reused when size matches the manifest
- if a required source file is missing for a selected session, ingest should fail fast
- if the DuckDB warehouse is missing, Streamlit should instruct the user to build it first
- if `wfdb` is not installed, LUDB and MIT-BIH normalization should fail fast with a dependency message while the default Wearable Exam Stress path remains unaffected
- if `dbt run` and `dbt test` are launched at the same time against the same DuckDB file, DuckDB will reject the second writer with a file-lock error
