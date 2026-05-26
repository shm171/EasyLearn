from pathlib import Path


def test_reader_web_files_exist() -> None:
    required_files = [
        "reader_web/package.json",
        "reader_web/src/App.jsx",
        "reader_web/src/components/PdfReader.jsx",
        "reader_web/src/components/ContextMenu.jsx",
        "reader_web/src/components/PageRangeTool.jsx",
        "reader_web/src/components/QuizAnswerModule.jsx",
        "reader_web/src/components/FloatingToolbox.jsx",
        "reader_web/src/components/ReaderPageManager.jsx",
        "reader_web/src/components/ReaderAnnotationLayer.jsx",
        "reader_web/src/components/ReaderAnnotationTool.jsx",
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
    assert "codeExtensionCache" in quiz_module
    assert "memo(function QuestionCard" in quiz_module


def test_reader_supports_markdown_materials() -> None:
    app = Path("reader_web/src/App.jsx").read_text(encoding="utf-8")
    reader = Path("reader_web/src/components/PdfReader.jsx").read_text(encoding="utf-8")
    dialog = Path("reader_web/src/components/ImportPdfDialog.jsx").read_text(encoding="utf-8")
    client = Path("reader_web/src/api/client.js").read_text(encoding="utf-8")
    styles = Path("reader_web/src/styles.css").read_text(encoding="utf-8")

    assert "activeMaterial" in app
    assert "getMarkdownIndex" in client
    assert "getMarkdownPage" in client
    assert "updateMarkdownPage" in client
    assert "importLocalMaterial" in client
    assert "XMLHttpRequest" in client
    assert "onProgress" in client
    assert ".md,.markdown" in dialog
    assert "importProgress" in dialog
    assert "资料导入进度" in dialog
    assert "MarkdownThumbnail" in reader
    assert "renderMarkdown" in reader
    assert "markdownPageCache" in reader
    assert "markdownEditing" in reader
    assert "markdown-editor" in reader
    assert "saveMarkdownEdit" in reader
    assert "requestMarkdownPage" in reader
    assert "正在加载当前页" in reader
    assert "markdown-page" in styles
    assert "markdown-editor" in styles


def test_reader_layout_and_ai_panel_are_adjustable() -> None:
    app = Path("reader_web/src/App.jsx").read_text(encoding="utf-8")
    panel = Path("reader_web/src/components/AiSidePanel.jsx").read_text(encoding="utf-8")
    styles = Path("reader_web/src/styles.css").read_text(encoding="utf-8")

    assert "quick-start" not in app
    assert "reader-toolbar-meta" in styles
    assert "sidePanelWidth" in app
    assert "sidePanelExpanded" in app
    assert "startSidePanelResize" in app
    assert "onResizeStart" in panel
    assert "onToggleExpanded" in panel
    assert "ai-resize-handle" in styles
    assert "workspace.ai-expanded" in styles


def test_reader_can_close_imported_materials() -> None:
    app = Path("reader_web/src/App.jsx").read_text(encoding="utf-8")
    selector = Path("reader_web/src/components/CourseSelector.jsx").read_text(encoding="utf-8")
    client = Path("reader_web/src/api/client.js").read_text(encoding="utf-8")
    styles = Path("reader_web/src/styles.css").read_text(encoding="utf-8")

    assert "closeMaterial" in client
    assert 'method: "DELETE"' in client
    assert "getMaterialIndexStatus" in client
    assert "handleCloseSelectedMaterial" in app
    assert "removeSavedAnnotations" in app
    assert "onCloseSelected" in selector
    assert "close-material-button" in styles


def test_ai_side_panel_collapses_sources_by_default() -> None:
    panel = Path("reader_web/src/components/AiSidePanel.jsx").read_text(encoding="utf-8")
    styles = Path("reader_web/src/styles.css").read_text(encoding="utf-8")

    assert "useState(false)" in panel
    assert "setSourcesOpen(false)" in panel
    assert "source-toggle" in panel
    assert "aria-expanded={sourcesOpen}" in panel
    assert "source-toggle.open" in styles
    assert "max-height: 210px" in styles


def test_reader_supports_body_page_and_bookmark_navigation() -> None:
    app = Path("reader_web/src/App.jsx").read_text(encoding="utf-8")
    reader = Path("reader_web/src/components/PdfReader.jsx").read_text(encoding="utf-8")
    toolbox = Path("reader_web/src/components/FloatingToolbox.jsx").read_text(encoding="utf-8")
    manager = Path("reader_web/src/components/ReaderPageManager.jsx").read_text(encoding="utf-8")
    styles = Path("reader_web/src/styles.css").read_text(encoding="utf-8")

    assert "FloatingToolbox" in app
    assert "ReaderPageManager" in toolbox
    assert "PageRangeTool" in toolbox
    assert "READER_MARKS_STORAGE_PREFIX" in manager
    assert "标为正文首页" in manager
    assert "回正文首页" in manager
    assert "添加当前页为书签" in manager
    assert "跳转到指定书签" in manager
    assert 'event.key === "Tab"' in manager
    assert "event.altKey" in manager
    assert "readerMarks.bookmarks[Number(event.key) - 1]" in manager
    assert "isEditableShortcutTarget" in manager
    assert "reader-page-manager" in styles
    assert "floating-toolbox" in styles
    assert "toolbox-panel" in styles
    assert "body-jump-form" in styles
    assert "ReaderPageManager" not in reader


def test_reader_supports_page_annotations() -> None:
    app = Path("reader_web/src/App.jsx").read_text(encoding="utf-8")
    reader = Path("reader_web/src/components/PdfReader.jsx").read_text(encoding="utf-8")
    toolbox = Path("reader_web/src/components/FloatingToolbox.jsx").read_text(encoding="utf-8")
    annotation_tool = Path("reader_web/src/components/ReaderAnnotationTool.jsx").read_text(encoding="utf-8")
    annotation_layer = Path("reader_web/src/components/ReaderAnnotationLayer.jsx").read_text(encoding="utf-8")
    styles = Path("reader_web/src/styles.css").read_text(encoding="utf-8")

    assert "ANNOTATION_STORAGE_PREFIX" in app
    assert "event.ctrlKey || !event.altKey" in app
    assert 'key === "a"' in app
    assert 'key === "z" || key === "backspace"' in app
    assert "ReaderAnnotationTool" in toolbox
    assert "ReaderAnnotationLayer" in reader
    assert "annotation-surface" in reader
    assert "tool: settings.tool" in annotation_layer
    assert "destination-out" in annotation_layer
    assert "requestAnimationFrame" in annotation_layer
    assert "MAX_ANNOTATIONS_PER_PAGE" in annotation_layer
    assert "drawArrow" in annotation_layer
    assert "drawRect" in annotation_layer
    assert "drawText" in annotation_layer
    assert "createTextOperation" in annotation_layer
    assert "画笔" in annotation_tool
    assert "擦除" in annotation_tool
    assert "文字" in annotation_tool
    assert "矩形" in annotation_tool
    assert "保存" in annotation_tool
    assert "annotation-canvas" in styles
