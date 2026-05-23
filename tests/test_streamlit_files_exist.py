from pathlib import Path


def test_streamlit_files_exist() -> None:
    required_files = [
        "web_ui/app.py",
        "web_ui/state.py",
        "web_ui/ui_utils.py",
        "web_ui/pages/home.py",
        "web_ui/pages/ingest_pdf.py",
        "web_ui/pages/ask_pdf.py",
        "web_ui/pages/summary.py",
        "web_ui/pages/quiz.py",
        "web_ui/pages/evaluation.py",
    ]

    for file in required_files:
        assert Path(file).exists(), f"Missing file: {file}"
