"""Build deterministic train/validation split metadata for one dataset."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_config import load_pipeline_config, resolve_repo_path


def assign_split_bucket(record_id: int, split_seed: str) -> str:
    raw_key = f"{split_seed}:{record_id}"
    hash_value = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    bucket_value = int(hash_value[:8], 16) % 100
    return "train" if bucket_value < 80 else "validation"


def build_reproducible_split_dataset(dataset_name: str) -> None:
    pipeline_config = load_pipeline_config(dataset_name=dataset_name)
    curated_directory = resolve_repo_path(pipeline_config.paths.curated_directory)
    record_features = pd.read_parquet(curated_directory / "fct_record_features.parquet")
    split_table = record_features[
        ["dataset_name", "record_id", "subject_id", "session_id", "session_name", "signal_channel"]
    ].copy()
    split_table["split_seed"] = pipeline_config.reproducibility.split_seed
    split_table["split_bucket"] = split_table["record_id"].apply(
        lambda record_id: assign_split_bucket(int(record_id), pipeline_config.reproducibility.split_seed)
    )
    split_table.to_csv(curated_directory / "dim_reproducible_record_split.csv", index=False)
    split_table.to_parquet(curated_directory / "dim_reproducible_record_split.parquet", index=False)
    print(f"wrote deterministic record split table for {dataset_name}")
