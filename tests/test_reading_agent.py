from __future__ import annotations

from ai_core.agents.reading_agent import PDFReadingAgent
from ai_core.schemas import PDFQueryRequest, SourceChunk


class DummyModel:
    def invoke(self, prompt: str):
        return type("Message", (), {"content": "A Python class is defined with class Name:. Source: chunk_1"})()


class StreamingDummyModel(DummyModel):
    def stream(self, prompt: str):
        yield type("Chunk", (), {"content": "A Python class "})()
        yield type("Chunk", (), {"content": "uses class Name:."})()


class DummyRetriever:
    def retrieve(self, query: str, course_id: str, chapter_title: str | None, top_k: int):
        return [
            SourceChunk(
                chunk_id="chunk_1",
                content="Classes are defined with the class keyword and can include methods.",
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

    result = agent.answer(PDFQueryRequest(course_id="python_001", question="How do I define a Python class?"))

    assert "class Name" in result.answer
    assert result.source_chunks[0].chunk_id == "chunk_1"


def test_pdf_reading_agent_streams_model_answer_with_sources() -> None:
    agent = PDFReadingAgent.__new__(PDFReadingAgent)
    agent.model = StreamingDummyModel()
    agent.retriever = DummyRetriever()

    chunks, stream = agent.stream_answer(PDFQueryRequest(course_id="python_001", question="How do classes work?"))

    assert chunks[0].chunk_id == "chunk_1"
    assert "".join(stream) == "A Python class uses class Name:."


def test_pdf_reading_agent_uses_general_answer_without_sources() -> None:
    agent = PDFReadingAgent.__new__(PDFReadingAgent)
    agent.model = DummyModel()
    agent.retriever = EmptyRetriever()

    result = agent.answer(PDFQueryRequest(course_id="python_001", question="What is a class structure?"))

    assert "class Name" in result.answer
    assert result.source_chunks == []

