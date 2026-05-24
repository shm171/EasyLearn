from pathlib import Path


def test_reader_web_files_exist() -> None:
    required_files = [
        "reader_web/package.json",
        "reader_web/src/App.jsx",
        "reader_web/src/components/PdfReader.jsx",
        "reader_web/src/components/ContextMenu.jsx",
        "reader_web/src/components/PageRangeTool.jsx",
        "reader_web/src/components/QuizAnswerModule.jsx",
    ]

    for file in required_files:
        assert Path(file).exists(), f"Missing file: {file}"


def test_reader_quiz_module_supports_grading_without_snippet_templates() -> None:
    module = Path("reader_web/src/components/QuizAnswerModule.jsx").read_text(encoding="utf-8")
    client = Path("reader_web/src/api/client.js").read_text(encoding="utf-8")

    assert "evaluateQuiz" in client
    assert "批改" in module
    assert "codeSnippets" not in module
    assert "snippet-bar" not in module
