from __future__ import annotations

from ai_core.rag.source_validator import SourceQualityValidator
from ai_core.schemas import SourceChunk


def test_source_validator_expands_class_questions() -> None:
    validator = SourceQualityValidator()

    variants = validator.build_query_variants("Python class structure")

    assert any("__init__" in variant for variant in variants)
    assert any("attribute" in variant for variant in variants)


def test_source_validator_reranks_code_chunk_over_toc_noise() -> None:
    validator = SourceQualityValidator()
    toc = SourceChunk(
        chunk_id="toc",
        content="Table of Contents\nChapter 1 .... 1\nChapter 2 .... 20\nChapter 3 .... 40",
        course_id="python_001",
        page_number=1,
        score=0.1,
    )
    useful = SourceChunk(
        chunk_id="class",
        content="class Dog:\n    def __init__(self, name):\n        self.name = name\n\nA class includes attributes and methods.",
        course_id="python_001",
        page_number=120,
        score=0.4,
    )

    ranked = validator.rerank([toc, useful], "How is a Python class defined?", limit=2)

    assert ranked[0].chunk_id == "class"


def test_source_validator_drops_unrelated_iterator_chunks() -> None:
    validator = SourceQualityValidator()
    unrelated = SourceChunk(
        chunk_id="function",
        content="A function can return a value with the return statement.",
        course_id="cpp_001",
        page_number=10,
        score=0.3,
    )

    ranked = validator.rerank([unrelated], "C++ 的迭代器是什么？", limit=3)

    assert ranked == []
