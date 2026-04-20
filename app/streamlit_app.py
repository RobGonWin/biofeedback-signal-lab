"""Streamlit review surface for Biofeedback Signal Lab."""

from __future__ import annotations

from pathlib import Path
import sys

import duckdb
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pipeline_config import load_runtime_config


st.set_page_config(page_title="Biofeedback Signal Lab", layout="wide")
st.title("Biofeedback Signal Lab")
st.caption("Cautious, non-diagnostic physiological feature review")

WAREHOUSE_PATH = Path("outputs/warehouse/biofeedback_signal_lab.duckdb")
DEFAULT_DATASET_NAME = load_runtime_config().runtime.default_dataset_name


def query_table(sql_query: str):
    """Run a read-only DuckDB query against the local warehouse."""
    if not WAREHOUSE_PATH.exists():
        raise FileNotFoundError(
            "local DuckDB warehouse not found. Run scripts/build_local_warehouse.py first."
        )

    connection = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        output_table = connection.execute(sql_query).fetchdf()
    finally:
        connection.close()
    return output_table


available_datasets = query_table(
    """
    select distinct dataset_name
    from raw_signal_files_all
    where selected_for_download = true
    order by dataset_name
    """
)
available_dataset_names = available_datasets["dataset_name"].tolist()
default_dataset_index = 0
if DEFAULT_DATASET_NAME in available_dataset_names:
    default_dataset_index = available_dataset_names.index(DEFAULT_DATASET_NAME)

selected_dataset_name = st.selectbox(
    "Dataset",
    available_dataset_names,
    index=default_dataset_index,
)

st.header("1) What data exists")
raw_signal_files = query_table(
    f"""
    select
      dataset_name,
      subject_id,
      session_name,
      file_name,
      file_type,
      content_length_bytes
    from raw_signal_files_all
    where selected_for_download = true
      and dataset_name = '{selected_dataset_name}'
    order by subject_id, session_name, file_name
    """
)
record_features = query_table(
    f"""
    select *
    from fct_record_features_all
    where dataset_name = '{selected_dataset_name}'
    order by subject_id, session_id, signal_channel
    """
)
window_features = query_table(
    f"""
    select *
    from fct_window_features_all
    where dataset_name = '{selected_dataset_name}'
    """
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Downloaded files", len(raw_signal_files))
col2.metric("Record rows", len(record_features))
col3.metric("Window rows", len(window_features))
col4.metric("Unique subjects", int(window_features["subject_id"].nunique()) if not window_features.empty else 0)

st.dataframe(raw_signal_files, width="stretch")

st.header("2) What features were extracted")
feature_distribution = query_table(
    f"""
    select *
    from mart_feature_distribution_summary_all
    where dataset_name = '{selected_dataset_name}'
    order by signal_channel, feature_name
    """
)
st.dataframe(feature_distribution, width="stretch")
if not feature_distribution.empty:
    st.bar_chart(
        feature_distribution.pivot(index="signal_channel", columns="feature_name", values="feature_mean"),
        width="stretch",
    )

st.header("3) What the features might suggest")
state_summary = query_table(
    f"""
    select
      dataset_name,
      signal_channel,
      sum(case when is_low_coverage_window then 1 else 0 end) as low_coverage_windows,
      sum(case when is_flatline_like_window then 1 else 0 end) as flatline_like_windows,
      sum(case when is_high_motion_window then 1 else 0 end) as high_motion_windows,
      sum(case when is_higher_relative_variability_window then 1 else 0 end) as higher_relative_variability_windows
    from fct_window_features_all
    where dataset_name = '{selected_dataset_name}'
    group by dataset_name, signal_channel
    order by signal_channel
    """
)
session_summary = query_table(
    f"""
    select *
    from mart_subject_or_session_summary_all
    where dataset_name = '{selected_dataset_name}'
    order by subject_id, session_id, signal_channel
    """
)
st.dataframe(state_summary, width="stretch")
st.dataframe(session_summary, width="stretch")

st.header("4) What the features do not prove")
guardrails = query_table(
    f"""
    select *
    from mart_interpretation_guardrails_all
    where dataset_name = '{selected_dataset_name}'
    order by guardrail_id
    """
)
st.dataframe(guardrails, width="stretch")

st.info(
    "This app is intentionally non-diagnostic. It supports reproducible signal analytics "
    "and quality-aware interpretation, not medical or cognitive conclusions."
)
