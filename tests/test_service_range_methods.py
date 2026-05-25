from __future__ import annotations

from ai_core.service import LearningAIService


def test_learning_service_exposes_reader_and_range_methods() -> None:
    service = LearningAIService()

    for method_name in [
        "list_materials",
        "get_material",
        "ingest_markdown",
        "get_markdown_pages",
        "get_markdown_index",
        "get_markdown_page",
        "_get_range_context_memory",
        "_remember_range_context",
        "ask_pdf_in_range",
        "summarize_range",
        "generate_quiz_from_range",
        "ask_current_page",
        "explain_selected_text",
        "explain_code_selection",
    ]:
        assert callable(getattr(service, method_name))
