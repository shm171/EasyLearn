from __future__ import annotations

"""Quiz generation helper tools."""

from ai_core.schemas import QuestionType

try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover - dependency is part of requirements
    tool = None


QUESTION_TYPE_PRIORITY: list[QuestionType] = ["programming", "fill_blank", "true_false", "short_answer"]


def allocate_question_counts(question_types: list[QuestionType], question_count: int) -> dict[str, int]:
    """Allocate the exact question count across selected question types."""

    if not question_types:
        raise ValueError("question_types cannot be empty")
    if question_count < 1 or question_count > 50:
        raise ValueError("question_count must be between 1 and 50")

    unique_types = list(dict.fromkeys(question_types))
    base = question_count // len(unique_types)
    remainder = question_count % len(unique_types)
    allocation = {question_type: base for question_type in unique_types}
    for question_type in QUESTION_TYPE_PRIORITY:
        if remainder <= 0:
            break
        if question_type in allocation:
            allocation[question_type] += 1
            remainder -= 1
    return allocation


if tool:
    @tool("allocate_question_counts")
    def allocate_question_counts_tool(question_types: list[str], question_count: int) -> dict[str, int]:
        """Allocate question counts evenly, prioritizing programming when there is a remainder."""

        return allocate_question_counts(question_types, question_count)  # type: ignore[arg-type]
else:  # pragma: no cover
    allocate_question_counts_tool = allocate_question_counts


