from streamlit.testing.v1 import AppTest


def test_streamlit_app_renders_without_exceptions() -> None:
    app_test = AppTest.from_file("app/streamlit_app.py")
    app_test.run(timeout=10)

    assert len(app_test.exception) == 0
    assert len(app_test.selectbox) == 1
    assert app_test.selectbox[0].value == "wearable_exam_stress"
