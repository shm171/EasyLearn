from __future__ import annotations

"""Evaluation helper tools."""

try:
    from langchain_core.tools import tool
except ImportError:  # pragma: no cover
    tool = None


def _normalize_answer(answer: str) -> str:
    return " ".join(answer.strip().lower().split())


if tool:
    @tool("compare_answer")
    def compare_answer_tool(reference_answer: str, user_answer: str) -> bool:
        """Compare simple factual answers after whitespace and case normalization."""

        return _normalize_answer(reference_answer) == _normalize_answer(user_answer)
else:  # pragma: no cover
    def compare_answer_tool(reference_answer: str, user_answer: str) -> bool:
        """Compare simple factual answers after whitespace and case normalization."""

        return _normalize_answer(reference_answer) == _normalize_answer(user_answer)


