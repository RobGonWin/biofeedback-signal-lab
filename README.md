# Biofeedback Signal Lab

Biofeedback Signal Lab is a local-first analytics engineering project built on public PhysioNet data. It takes bounded physiological signal files, turns them into reproducible staged and curated tables, models them in DuckDB with dbt, and exposes a narrow Streamlit review surface for cautious signal analysis.

This project demonstrates bounded physiological data ingestion, reproducible feature extraction, validation-aware modeling, and careful non-diagnostic interpretation.

## Why a Team Would Care

A data platform, analytics, or health-tech-adjacent team could use this pattern to turn messy physiological files into reviewable tables, monitor data quality issues early, and support cautious operational decisions without overstating what the signals mean.

## Stack

Python, DuckDB, dbt, Streamlit, PhysioNet bounded public data, CSV/Parquet artifacts, and validation-focused tests.

## What This Project Proves

- bounded, reproducible physiological data ingestion
- validation-aware feature extraction and modeling
- explicit interpretation guardrails for ambiguous source data
- a narrow stakeholder-facing review surface rather than dashboard sprawl
- clear documentation around what the analysis does and does not support

## Current Demo State

The current demo includes:
- bounded public demo data committed for reviewability
- runnable ingestion, normalization, feature extraction, and warehouse build scripts
- staged and curated CSV/Parquet outputs
- dbt models and validation checks
- a cautious non-diagnostic Streamlit review surface

## Hiring Signal

This project demonstrates systems-minded analytics engineering for ambiguous, sensitive-feeling data: bounded ingestion, reproducible transformation layers, validation before interpretation, and clear explanation of what the outputs do and do not support.

## Screenshots
![Image of Streamlit app preview](https://github.com/user-attachments/assets/1df7a640-850f-41c4-9d59-94545891887b "Image of Streamlit app preview")


## What Data This Uses

- Primary source: PhysioNet Wearable Exam Stress v1.0.0
- Bounded demo slice: subjects `S1` to `S6`, sessions `midterm_1` and `midterm_2`
- Required files per session: `ACC.csv`, `BVP.csv`, `EDA.csv`, `HR.csv`, `IBI.csv`, `TEMP.csv`, `tags.csv`, `info.txt`
- Scope rules live in `config/dataset_slice.yaml`

## Data Sources and Attribution

This repo uses bounded public data from PhysioNet. The committed demo files and derived outputs are based on these sources:

- Wearable Exam Stress: https://physionet.org/content/wearable-exam-stress/
- Lobachevsky University Electrocardiography Database (LUDB): https://physionet.org/content/ludb/
- MIT-BIH Arrhythmia Database: https://physionet.org/content/mitdb/

PhysioNet lists these datasets as open access and provides the file license as Open Data Commons Attribution License v1.0:

- ODC-By v1.0: https://physionet.org/about/licenses/open-data-commons-attribution-license-v10/

Please cite the original dataset pages and authors when reusing the raw data or substantial derived artifacts.
> Code in this repository is MIT-licensed; included dataset files remain subject to their original PhysioNet/ODC-By terms.

## Business Question

Across comparable exam sessions, how do compact physiological and signal-quality features vary by subject, session, and fixed window, and which operational states are observable without making medical or cognitive claims?

> This is intentionally framed as an analytics and data-quality question, not a diagnosis question.

## Decision Supported

A reviewer or team can use this project to decide whether a bounded physiological data pipeline is stable enough for downstream review, which sessions or channels deserve closer data-quality inspection, and whether cautious operational summaries can be produced without overclaiming what the signals mean.

## What This Project Does

- downloads a bounded slice of real public physiological data
- normalizes raw sensor files into reproducible bronze, staging, and curated outputs
- computes reviewable signal-quality and variability features at record, window, and session grain
- builds DuckDB + dbt models, including combined `_all` views for enabled datasets
- exposes a narrow Streamlit surface for reviewing outputs and interpretation guardrails
- validates completeness, schema shape, feature sanity, and warehouse health before review

## For Non-Technical Reviewers

If you are not reading this as a data engineer, the simplest way to think about the project is:

1. It pulls a real public dataset rather than using fake demo data.
2. It organizes messy biosignal files into structured tables that are easier to inspect.
3. It summarizes quality and variability patterns across sessions and windows.
4. It makes the interpretation limits explicit: the outputs may suggest capture or variability differences, but they do not prove stress level, diagnosis, or treatment need.

What should stand out is not "medical insight." It is disciplined data work:
- bounded ingestion
- reproducible transforms
- validation before interpretation
- clear documentation and reviewability

## Technical Architecture

The current default path is:

`PhysioNet files -> Python ingestion and normalization -> Parquet outputs -> dbt models on DuckDB -> Streamlit review app`

Core implementation pieces:
- ingestion: `scripts/ingest_wearable_exam_stress.py`
- wearable normalization: `scripts/normalize_signals.py`
- feature extraction: `scripts/extract_features.py` and `scripts/extract_dataset_features.py`
- reproducible split: `scripts/build_reproducible_split.py`
- warehouse build: `dbt run` / `dbt test` against `local_duckdb`
- app: `app/streamlit_app.py`

Optional secondary dataset implementations:
- LUDB: `scripts/ingest_ludb.py`, `scripts/normalize_ludb.py`, `scripts/extract_ludb_features.py`
- MIT-BIH: `scripts/ingest_mitdb.py`, `scripts/normalize_mitdb.py`, `scripts/extract_mitdb_features.py`

## Runtime Config Summary

Two config files drive the default workflow:
- `.config.json` controls runtime behavior
- `config/dataset_slice.yaml` controls dataset scope, pull bounds, windowing, reproducibility, and output paths

Most common tweaks:
- changing the default app dataset with `runtime.default_dataset_name`
- enabling or disabling datasets in the Streamlit selector and dbt `_all` views
- keeping Snowflake scaffolding off for the default local demo path

Highest-signal implementation touchpoints:
- `scripts/pipeline_config.py` loads `.config.json` and `config/dataset_slice.yaml`
- `app/streamlit_app.py` uses `.config.json` to choose the app’s default dataset
- `macros/combined_views.sql` uses `.config.json` to decide which datasets appear in dbt-built `_all` views
- `scripts/build_local_warehouse.py` uses the dbt block from `.config.json` to decide whether the dbt-backed local warehouse path is active

For setup instructions and safe examples, see [docs/configuration_guide.md](docs/configuration_guide.md).

## Data Products and Grain

Default wearable dataset outputs follow this model flow:
- `raw_signal_files`: one row per discovered remote artifact in the bronze manifest
- `stg_signal_records`: one row per parsed subject-session-channel record
- `stg_signal_windows`: one row per subject-session-channel fixed window
- `stg_annotations_or_labels`: one row per subject-session annotation summary
- `fct_record_features`: one row per record-level feature summary
- `fct_window_features`: one row per window-level feature set
- `mart_subject_or_session_summary`: one row per subject-session-channel summary
- `mart_feature_distribution_summary`: one row per signal-channel and feature summary
- `mart_interpretation_guardrails`: one row per guardrail statement

There is also a dbt-native combined layer:
- `raw_signal_files_all`
- `stg_signal_records_all`
- `stg_signal_windows_all`
- `stg_annotations_or_labels_all`
- `fct_record_features_all`
- `fct_window_features_all`
- `dim_reproducible_record_split_all`
- `mart_subject_or_session_summary_all`
- `mart_feature_distribution_summary_all`
- `mart_interpretation_guardrails_all`

Those `_all` views are what the Streamlit app uses when multiple datasets are enabled in `.config.json`.

## Feature Scope

Wearable dense parsed channels:
- `acc_x`
- `acc_y`
- `acc_z`
- `acc_magnitude`
- `bvp`
- `eda`
- `hr`
- `temp`

Key window features:
- `window_mean`
- `window_std`
- `window_min`
- `window_max`
- `window_iqr`
- `window_mad`
- `window_range`
- `missing_value_ratio`
- `flatline_ratio`
- `window_coverage_ratio`

Operational state flags:
- `is_low_coverage_window`
- `is_flatline_like_window`
- `is_high_motion_window`
- `is_higher_relative_variability_window`

These are intentionally operational and descriptive. They are not diagnostic labels.

## Repo Walkthrough

If you want to review the repo quickly, these are the most important places to look:

- `config/dataset_slice.yaml`
  What gets pulled, how big the bounded slice is, and where outputs are written.

- `scripts/ingest_wearable_exam_stress.py`
  Bounded source discovery, HEAD checks, manifest creation, and downloads.

- `scripts/extract_dataset_features.py`
  Feature engineering and interpretation guardrail tables.

- `app/streamlit_app.py`
  The review surface used to inspect dataset inventory, feature outputs, and guardrails.

- [docs/ethics_memo.md](docs/ethics_memo.md)
  The short limitations and interpretation memo.

- `tests/`
  Regression and sanity checks for manifest completeness, feature ranges, warehouse health, and app rendering.

## Output Layout

Default wearable paths:
- bronze manifest: `data/bronze/wearable_exam_stress/raw_metadata_manifest.csv` and `.parquet`
- staged outputs: `data/staging/wearable_exam_stress/`
- curated outputs: `data/curated/wearable_exam_stress/`

Optional dataset-specific paths:
- LUDB: `data/bronze/ludb/`, `data/staging/ludb/`, `data/curated/ludb/`
- MIT-BIH: `data/bronze/mitdb/`, `data/staging/mitdb/`, `data/curated/mitdb/`

Warehouse:
- DuckDB file: `outputs/warehouse/biofeedback_signal_lab.duckdb`

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

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

`python scripts/build_local_warehouse.py` remains available as a convenience wrapper around the local dbt build path.

## Optional Dataset Commands

LUDB:

```bash
python scripts/ingest_ludb.py
python scripts/normalize_ludb.py
python scripts/extract_ludb_features.py
python scripts/build_ludb_reproducible_split.py
```

MIT-BIH:

```bash
python scripts/ingest_mitdb.py
python scripts/normalize_mitdb.py
python scripts/extract_mitdb_features.py
python scripts/build_mitdb_reproducible_split.py
```

`wfdb` is only required when running the LUDB or MIT-BIH pipelines.

## Streamlit Review Surface

The app is intentionally narrow. It answers four questions:
- what data exists
- what features were extracted
- what those features might suggest
- what those features do not prove

The app is backed by the DuckDB warehouse and reads the dbt-built `_all` views, so it can switch datasets when multiple sources are enabled.


## Related Docs

- [Configuration Guide](docs/configuration_guide.md)
- [Ethics Memo](docs/ethics_memo.md)

## Validation Coverage

The repo includes checks for:
- source completeness by selected subject-session file set
- staged channel inventory
- window sample-count and coverage integrity
- feature range sanity
- deterministic split integrity
- DuckDB view existence and non-empty core marts
- Streamlit smoke rendering

## Interpretation Limits and Ethics

This project is intentionally non-diagnostic.

The outputs may suggest:
- capture consistency differences across sessions and channels
- relative variability changes across fixed windows
- motion-heavy periods when accelerometer variability is elevated
- records or windows that deserve closer data-quality review

The outputs do not prove:
- clinical diagnosis
- definitive stress state
- cognitive performance level
- treatment need

The short ethics note is in [docs/ethics_memo.md](docs/ethics_memo.md).

## Why This Stands Out

For technical reviewers, this repo demonstrates:
- bounded source ingestion with explicit guardrails
- reproducible multi-step transformation logic
- dbt + DuckDB local analytics workflow
- dataset-aware modeling and review surfaces
- tests and validation around a non-trivial data pipeline

For non-technical stakeholders, it demonstrates:
- the ability to turn ambiguous source files into usable business tables
- disciplined handling of sensitive-feeling subject matter
- clear explanation of what an analysis does and does not support
- a small but credible end-to-end analytics product

## Current Scope Limits

- The primary polished path is still Wearable Exam Stress.
- LUDB and MIT-BIH are additive optional datasets, not the headline story.
- Sparse `IBI.csv`, `tags.csv`, and `info.txt` inputs are treated as annotations, not definitive labels.
- Snowflake remains optional scaffolding rather than the canonical demo path.
