from __future__ import annotations

from ai_core.service import LearningAIService


def test_learning_service_exposes_reader_and_range_methods() -> None:
    service = LearningAIService()

    for method_name in [
        "list_materials",
        "get_material",
        "ask_pdf_in_range",
        "summarize_range",
        "generate_quiz_from_range",
        "ask_current_page",
        "explain_selected_text",
        "explain_code_selection",
    ]:
        assert callable(getattr(service, method_name))
