from __future__ import annotations

import pytest

from ai_core.rag.range_retriever import RangeRetriever


class DummyKnowledgeBase:
    pass


def test_validate_page_range_accepts_valid_range() -> None:
    retriever = RangeRetriever(DummyKnowledgeBase())  # type: ignore[arg-type]

    assert retriever.validate_page_range(1, 5) == (1, 5)


def test_validate_page_range_rejects_reversed_range() -> None:
    retriever = RangeRetriever(DummyKnowledgeBase())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="page_start cannot be greater"):
        retriever.validate_page_range(5, 1)


def test_validate_page_range_rejects_zero_page() -> None:
    retriever = RangeRetriever(DummyKnowledgeBase())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="greater than or equal to 1"):
        retriever.validate_page_range(0, 5)
