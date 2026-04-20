import duckdb


def test_duckdb_marts_build_and_return_rows() -> None:
    connection = duckdb.connect("outputs/warehouse/biofeedback_signal_lab.duckdb", read_only=True)
    try:
        record_row_count = connection.execute("select count(*) from fct_record_features").fetchone()[0]
        window_row_count = connection.execute("select count(*) from fct_window_features").fetchone()[0]
        session_row_count = connection.execute("select count(*) from mart_subject_or_session_summary").fetchone()[0]
        combined_record_row_count = connection.execute("select count(*) from fct_record_features_all").fetchone()[0]
    finally:
        connection.close()

    assert record_row_count > 0
    assert window_row_count > 0
    assert session_row_count > 0
    assert combined_record_row_count >= record_row_count
