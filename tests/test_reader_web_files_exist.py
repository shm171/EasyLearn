from pathlib import Path


def test_reader_web_files_exist() -> None:
    required_files = [
        "reader_web/package.json",
        "reader_web/src/App.jsx",
        "reader_web/src/components/PdfReader.jsx",
        "reader_web/src/components/ContextMenu.jsx",
        "reader_web/src/components/PageRangeTool.jsx",
    ]

    for file in required_files:
        assert Path(file).exists(), f"Missing file: {file}"
