from __future__ import annotations

from ai_core.agents.reading_agent import PDFReadingAgent
from ai_core.schemas import PDFQueryRequest, SourceChunk


class DummyModel:
    def invoke(self, prompt: str):
        return type("Message", (), {"content": "变量用于给数据命名，便于后续读取和操作。来源：chunk_1"})()


class StreamingDummyModel(DummyModel):
    def stream(self, prompt: str):
        yield type("Chunk", (), {"content": "变量用于"})()
        yield type("Chunk", (), {"content": "给数据命名"})()


class DummyRetriever:
    def retrieve(self, query: str, course_id: str, chapter_title: str | None, top_k: int):
        return [
            SourceChunk(
                chunk_id="chunk_1",
                content="在本章中，你学习了如何使用变量。",
                course_id=course_id,
                chapter_title=chapter_title,
                page_number=49,
            )
        ]


class EmptyRetriever:
    def retrieve(self, query: str, course_id: str, chapter_title: str | None, top_k: int):
        return []


def test_pdf_reading_agent_returns_model_answer_with_sources() -> None:
    agent = PDFReadingAgent.__new__(PDFReadingAgent)
    agent.model = DummyModel()
    agent.retriever = DummyRetriever()

    result = agent.answer(PDFQueryRequest(course_id="python_001", question="变量的作用是什么？"))

    assert "变量用于给数据命名" in result.answer
    assert result.source_chunks[0].chunk_id == "chunk_1"


def test_pdf_reading_agent_streams_model_answer_with_sources() -> None:
    agent = PDFReadingAgent.__new__(PDFReadingAgent)
    agent.model = StreamingDummyModel()
    agent.retriever = DummyRetriever()

    chunks, stream = agent.stream_answer(PDFQueryRequest(course_id="python_001", question="变量的作用是什么？"))

    assert chunks[0].chunk_id == "chunk_1"
    assert "".join(stream) == "变量用于给数据命名"


def test_pdf_reading_agent_short_circuits_without_sources() -> None:
    agent = PDFReadingAgent.__new__(PDFReadingAgent)
    agent.model = DummyModel()
    agent.retriever = EmptyRetriever()

    result = agent.answer(PDFQueryRequest(course_id="python_001", question="没有资料的问题"))

    assert result.answer == "资料中未找到明确依据"
    assert result.source_chunks == []
