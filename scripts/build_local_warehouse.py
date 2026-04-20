"""Build the local DuckDB review warehouse from staged and curated outputs."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_config import (
    get_combined_view_dataset_names,
    load_pipeline_config,
    load_runtime_config,
    resolve_repo_path,
)


MODEL_PATHS_IN_BUILD_ORDER = [
    "models/staging/raw_signal_files.sql",
    "models/staging/stg_signal_records.sql",
    "models/staging/stg_signal_windows.sql",
    "models/staging/stg_annotations_or_labels.sql",
    "models/marts/fct_record_features.sql",
    "models/marts/fct_window_features.sql",
    "models/marts/dim_reproducible_record_split.sql",
    "models/marts/mart_subject_or_session_summary.sql",
    "models/marts/mart_feature_distribution_summary.sql",
    "models/marts/mart_interpretation_guardrails.sql",
]

COMBINED_VIEW_FILE_NAMES = {
    "raw_signal_files_all": "raw_metadata_manifest.parquet",
    "stg_signal_records_all": "stg_signal_records.parquet",
    "stg_signal_windows_all": "stg_signal_windows.parquet",
    "stg_annotations_or_labels_all": "stg_annotations_or_labels.parquet",
    "fct_record_features_all": "fct_record_features.parquet",
    "fct_window_features_all": "fct_window_features.parquet",
    "dim_reproducible_record_split_all": "dim_reproducible_record_split.parquet",
    "mart_subject_or_session_summary_all": "mart_subject_or_session_summary.parquet",
    "mart_feature_distribution_summary_all": "mart_feature_distribution_summary.parquet",
    "mart_interpretation_guardrails_all": "mart_interpretation_guardrails.parquet",
}


def get_dataset_output_path(dataset_name: str, combined_view_name: str) -> Path:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    if combined_view_name == "raw_signal_files_all":
        return resolve_repo_path(pipeline_config.paths.bronze_manifest_parquet)
    if combined_view_name.startswith("stg_"):
        return resolve_repo_path(pipeline_config.paths.staging_directory) / COMBINED_VIEW_FILE_NAMES[combined_view_name]
    return resolve_repo_path(pipeline_config.paths.curated_directory) / COMBINED_VIEW_FILE_NAMES[combined_view_name]


def build_combined_view_sql(combined_view_name: str, dataset_names: list[str]) -> str:
    select_statements: list[str] = []
    for dataset_name in dataset_names:
        dataset_output_path = get_dataset_output_path(dataset_name, combined_view_name)
        if not dataset_output_path.exists():
            continue
        select_statements.append(
            f"select * from read_parquet('{dataset_output_path.as_posix()}')"
        )

    if not select_statements:
        return "select 1 as no_rows where false"
    return " union all ".join(select_statements)


def load_model_sql(model_path: Path) -> str:
    """Read one SQL model file."""
    model_sql = model_path.read_text(encoding="utf-8").strip().rstrip(";")
    return model_sql


def run_dbt_local_build(runtime_config) -> None:
    """Run dbt against the local DuckDB target when enabled."""
    if not runtime_config.dbt.enabled:
        return

    dbt_executable = shutil.which("dbt")
    if dbt_executable is None:
        scripts_directory = Path(sys.executable).resolve().parent / "Scripts" / "dbt.exe"
        if scripts_directory.exists():
            dbt_executable = str(scripts_directory)
        else:
            raise FileNotFoundError("dbt executable not found in PATH or Python Scripts directory")

    dbt_profiles_dir = resolve_repo_path(runtime_config.dbt.profiles_dir)
    dbt_project_dir = resolve_repo_path(".")
    dbt_target_name = runtime_config.dbt.target_name
    dbt_commands = [
        [
            dbt_executable,
            "run",
            "--project-dir",
            str(dbt_project_dir),
            "--profiles-dir",
            str(dbt_profiles_dir),
            "--target",
            dbt_target_name,
        ],
        [
            dbt_executable,
            "test",
            "--project-dir",
            str(dbt_project_dir),
            "--profiles-dir",
            str(dbt_profiles_dir),
            "--target",
            dbt_target_name,
        ],
    ]
    for dbt_command in dbt_commands:
        subprocess.run(dbt_command, check=True, cwd=str(dbt_project_dir))


def build_local_warehouse() -> Path:
    """Create or replace DuckDB views for all review models."""
    runtime_config = load_runtime_config()
    pipeline_config = load_pipeline_config(dataset_name=runtime_config.runtime.default_dataset_name)
    warehouse_path = resolve_repo_path(pipeline_config.paths.warehouse_database_path)
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)

    run_dbt_local_build(runtime_config)

    if runtime_config.dbt.enabled:
        return warehouse_path

    connection = duckdb.connect(str(warehouse_path))
    try:
        for relative_model_path in MODEL_PATHS_IN_BUILD_ORDER:
            absolute_model_path = resolve_repo_path(relative_model_path)
            model_name = absolute_model_path.stem
            model_sql = load_model_sql(absolute_model_path)
            connection.execute(f"create or replace view {model_name} as {model_sql}")

        combined_view_dataset_names = get_combined_view_dataset_names(runtime_config)
        for combined_view_name in COMBINED_VIEW_FILE_NAMES:
            combined_view_sql = build_combined_view_sql(combined_view_name, combined_view_dataset_names)
            connection.execute(f"create or replace view {combined_view_name} as {combined_view_sql}")
    finally:
        connection.close()

    return warehouse_path


def main() -> None:
    warehouse_path = build_local_warehouse()
    print(f"built local DuckDB warehouse: {warehouse_path}")


if __name__ == "__main__":
    main()
