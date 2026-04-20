from scripts.pipeline_config import (
    get_combined_view_dataset_names,
    get_enabled_dataset_names,
    load_pipeline_config,
    load_runtime_config,
)


def test_default_dataset_remains_wearable_exam_stress() -> None:
    pipeline_config = load_pipeline_config()
    runtime_config = load_runtime_config()
    assert pipeline_config.dataset.dataset_name == "wearable_exam_stress"
    assert runtime_config.runtime.default_dataset_name == "wearable_exam_stress"


def test_dataset_catalog_supports_secondary_optional_datasets() -> None:
    ludb_config = load_pipeline_config(dataset_name="ludb")
    mitdb_config = load_pipeline_config(dataset_name="mitdb")
    assert ludb_config.dataset.dataset_name == "ludb"
    assert mitdb_config.dataset.dataset_name == "mitdb"
    assert ludb_config.dataset.parser_type == "wfdb_ecg"
    assert mitdb_config.dataset.parser_type == "wfdb_ecg"


def test_secondary_datasets_follow_runtime_config() -> None:
    runtime_config = load_runtime_config()
    assert get_enabled_dataset_names(runtime_config) == [
        "wearable_exam_stress",
        "ludb",
        "mitdb",
    ]
    assert get_combined_view_dataset_names(runtime_config) == [
        "wearable_exam_stress",
        "ludb",
        "mitdb",
    ]
