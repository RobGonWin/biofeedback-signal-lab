"""Shared configuration helpers for the Biofeedback Signal Lab pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "dataset_slice.yaml"
DEFAULT_RUNTIME_CONFIG_PATH = REPO_ROOT / ".config.json"


@dataclass(frozen=True)
class DatasetSettings:
    dataset_name: str
    version: str
    dataset_page_url: str
    file_listing_url: str
    data_listing_url: str
    zip_url: str
    parser_type: str


@dataclass(frozen=True)
class BoundedPullSettings:
    max_single_file_mb: int
    max_total_pull_mb: int
    selected_subject_ids: list[str]
    selected_session_names: list[str]
    selected_record_ids: list[str]
    required_signal_files: list[str]
    include_metadata_files: list[str]
    required_record_suffixes: list[str]
    required_annotation_suffixes: list[str]
    ignore_file_suffixes: list[str]
    metadata_index_file: str
    prefer_file_listing_over_zip: bool


@dataclass(frozen=True)
class WindowingSettings:
    window_seconds: int
    min_window_coverage_ratio: float
    higher_relative_variability_quantile: float
    high_motion_quantile: float


@dataclass(frozen=True)
class ReproducibilitySettings:
    random_seed: int
    split_seed: str
    snapshot_date_utc: str


@dataclass(frozen=True)
class PathSettings:
    raw_root_directory: str
    bronze_manifest_csv: str
    bronze_manifest_parquet: str
    preflight_manifest_json: str
    staging_directory: str
    curated_directory: str
    warehouse_directory: str
    warehouse_database_path: str


@dataclass(frozen=True)
class RuntimeSettings:
    default_query_engine: str
    default_delivery_target: str
    allow_optional_cloud_targets: bool
    default_dataset_name: str


@dataclass(frozen=True)
class DatasetRuntimeSettings:
    enabled: bool
    include_in_combined_views: bool


@dataclass(frozen=True)
class DuckDbRuntimeSettings:
    enabled: bool
    warehouse_path: str


@dataclass(frozen=True)
class SnowflakeRuntimeSettings:
    enabled: bool
    dbt_enabled: bool
    sync_mode: str
    max_sync_file_size_mb: int
    max_sync_total_size_mb: int
    source_directory: str
    allowed_file_formats: list[str]
    target_profile_name: str
    target_database_env_var: str
    target_schema_env_var: str
    target_warehouse_env_var: str
    target_role_env_var: str


@dataclass(frozen=True)
class DbtRuntimeSettings:
    enabled: bool
    project_file: str
    profiles_dir: str
    target_name: str


@dataclass(frozen=True)
class RuntimeConfig:
    runtime: RuntimeSettings
    datasets: dict[str, DatasetRuntimeSettings]
    duckdb: DuckDbRuntimeSettings
    snowflake: SnowflakeRuntimeSettings
    dbt: DbtRuntimeSettings


@dataclass(frozen=True)
class PipelineConfig:
    default_dataset_name: str
    dataset: DatasetSettings
    bounded_pull: BoundedPullSettings
    windowing: WindowingSettings
    reproducibility: ReproducibilitySettings
    paths: PathSettings


def _read_yaml_file(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as config_file:
        loaded_config = yaml.safe_load(config_file)
    return loaded_config


def _read_json_file(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as config_file:
        loaded_config = json.load(config_file)
    return loaded_config


def resolve_repo_path(relative_path: str) -> Path:
    resolved_path = REPO_ROOT / relative_path
    return resolved_path


def to_repo_relative_path(path_value: Path | str) -> str:
    candidate_path = Path(path_value)
    if candidate_path.is_absolute():
        relative_path = candidate_path.resolve().relative_to(REPO_ROOT.resolve())
    else:
        relative_path = candidate_path
    return relative_path.as_posix()


def resolve_data_path(path_value: str) -> Path:
    candidate_path = Path(path_value)
    if candidate_path.is_absolute():
        return candidate_path
    return resolve_repo_path(path_value)


def _load_dataset_catalog(loaded_config: dict, dataset_name: str | None) -> tuple[str, dict]:
    if "datasets" not in loaded_config:
        active_dataset_name = dataset_name or loaded_config["dataset"]["dataset_name"]
        return active_dataset_name, loaded_config

    default_dataset_name = loaded_config["default_dataset_name"]
    active_dataset_name = dataset_name or default_dataset_name
    dataset_catalog = loaded_config["datasets"]
    if active_dataset_name not in dataset_catalog:
        raise KeyError(f"unknown dataset_name: {active_dataset_name}")

    dataset_config = dataset_catalog[active_dataset_name]
    flattened_dataset_config = {
        "default_dataset_name": default_dataset_name,
        "dataset": dataset_config["dataset"],
        "bounded_pull": dataset_config["bounded_pull"],
        "windowing": dataset_config["windowing"],
        "reproducibility": dataset_config["reproducibility"],
        "paths": dataset_config["paths"],
    }
    return active_dataset_name, flattened_dataset_config


def load_pipeline_config(
    config_path: Path | None = None,
    dataset_name: str | None = None,
) -> PipelineConfig:
    active_config_path = config_path or DEFAULT_CONFIG_PATH
    loaded_config = _read_yaml_file(active_config_path)
    active_dataset_name, flattened_config = _load_dataset_catalog(loaded_config, dataset_name)

    pipeline_config = PipelineConfig(
        default_dataset_name=flattened_config.get("default_dataset_name", active_dataset_name),
        dataset=DatasetSettings(**flattened_config["dataset"]),
        bounded_pull=BoundedPullSettings(**flattened_config["bounded_pull"]),
        windowing=WindowingSettings(**flattened_config["windowing"]),
        reproducibility=ReproducibilitySettings(**flattened_config["reproducibility"]),
        paths=PathSettings(**flattened_config["paths"]),
    )
    return pipeline_config


def load_runtime_config(config_path: Path | None = None) -> RuntimeConfig:
    active_config_path = config_path or DEFAULT_RUNTIME_CONFIG_PATH
    loaded_config = _read_json_file(active_config_path)

    runtime_config = RuntimeConfig(
        runtime=RuntimeSettings(**loaded_config["runtime"]),
        datasets={
            dataset_name: DatasetRuntimeSettings(**dataset_settings)
            for dataset_name, dataset_settings in loaded_config["datasets"].items()
        },
        duckdb=DuckDbRuntimeSettings(**loaded_config["local"]["duckdb"]),
        snowflake=SnowflakeRuntimeSettings(**loaded_config["cloud"]["snowflake"]),
        dbt=DbtRuntimeSettings(**loaded_config["dbt"]),
    )
    return runtime_config


def get_enabled_dataset_names(runtime_config: RuntimeConfig) -> list[str]:
    enabled_dataset_names = [
        dataset_name
        for dataset_name, dataset_settings in runtime_config.datasets.items()
        if dataset_settings.enabled
    ]
    return enabled_dataset_names


def get_combined_view_dataset_names(runtime_config: RuntimeConfig) -> list[str]:
    combined_view_dataset_names = [
        dataset_name
        for dataset_name, dataset_settings in runtime_config.datasets.items()
        if dataset_settings.enabled and dataset_settings.include_in_combined_views
    ]
    return combined_view_dataset_names


def get_session_id(session_name: str) -> int:
    session_lookup = {
        "midterm_1": 1,
        "midterm_2": 2,
        "final": 3,
    }
    normalized_session_name = session_name.lower()
    session_id = session_lookup.get(normalized_session_name)
    if session_id is None:
        raise ValueError(f"unsupported session_name: {session_name}")
    return session_id
