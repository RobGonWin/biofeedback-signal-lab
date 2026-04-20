import pandas as pd


def test_reproducible_split_has_allowed_buckets() -> None:
    split_table = pd.read_parquet("data/curated/wearable_exam_stress/dim_reproducible_record_split.parquet")
    allowed_split_buckets = {"train", "validation"}
    assert set(split_table["split_bucket"].unique()).issubset(allowed_split_buckets)
    assert set(split_table["dataset_name"].unique()) == {"wearable_exam_stress"}


def test_reproducible_split_seed_populated() -> None:
    split_table = pd.read_parquet("data/curated/wearable_exam_stress/dim_reproducible_record_split.parquet")
    assert not split_table["split_seed"].isna().any()


def test_reproducible_split_matches_record_features() -> None:
    split_table = pd.read_parquet("data/curated/wearable_exam_stress/dim_reproducible_record_split.parquet")
    record_features = pd.read_parquet("data/curated/wearable_exam_stress/fct_record_features.parquet")
    assert set(split_table["record_id"]) == set(record_features["record_id"])
