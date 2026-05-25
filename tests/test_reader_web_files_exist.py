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
    assert "String(question.question_id" in module
    assert "codeSnippets" not in module
    assert "snippet-bar" not in module


def test_reader_context_menu_supports_copy_and_paste_completion() -> None:
    context_menu = Path("reader_web/src/components/ContextMenu.jsx").read_text(encoding="utf-8")
    pdf_reader = Path("reader_web/src/components/PdfReader.jsx").read_text(encoding="utf-8")
    quiz_module = Path("reader_web/src/components/QuizAnswerModule.jsx").read_text(encoding="utf-8")

    assert "copy_selection" in context_menu
    assert "复制选中文字" in context_menu
    assert "copyTextToClipboard" in pdf_reader
    assert "input.paste" in quiz_module
    assert "startCompletion" in quiz_module
    assert "inferCodeLanguage" in quiz_module


def test_ai_side_panel_collapses_sources_by_default() -> None:
    panel = Path("reader_web/src/components/AiSidePanel.jsx").read_text(encoding="utf-8")
    styles = Path("reader_web/src/styles.css").read_text(encoding="utf-8")

    assert "useState(false)" in panel
    assert "setSourcesOpen(false)" in panel
    assert "source-toggle" in panel
    assert "aria-expanded={sourcesOpen}" in panel
    assert "source-toggle.open" in styles
    assert "max-height: 210px" in styles
