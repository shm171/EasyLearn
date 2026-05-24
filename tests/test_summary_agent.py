from __future__ import annotations

import json

from ai_core.agents.summary_agent import ChapterSummaryAgent
from ai_core.schemas import ChapterSummaryRequest, SourceChunk


class DummyModel:
    def invoke(self, prompt: str):
        payload = {
            "chapter_title": "Python basics",
            "learning_goals": ["Understand variables"],
            "key_concepts": ["Variables store values"],
            "important_terms": ["variable"],
            "code_examples": ["name = 'Ada'"],
            "typical_question_types": ["Fill in missing assignment syntax"],
            "common_mistakes": ["Forgetting quotes around strings"],
            "study_suggestions": ["Practice small assignments"],
            "source_chunks": ["chunk_1"],
        }
        return type("Message", (), {"content": json.dumps(payload)})()


class DummyRetriever:
    def retrieve(self, query: str, course_id: str, chapter_title: str | None, top_k: int):
        self.top_k = top_k
        return [
            SourceChunk(
                chunk_id="chunk_1",
                content="Variables store values and are created by assignment.",
                course_id=course_id,
                chapter_title=chapter_title,
                page_number=12,
            )
        ]


def test_summary_agent_generates_summary_without_langchain_agent() -> None:
    retriever = DummyRetriever()
    agent = ChapterSummaryAgent(DummyModel(), retriever)
    events: list[tuple[float, str]] = []

    summary = agent.summarize(
        ChapterSummaryRequest(course_id="python_001", chapter_title="Python basics"),
        progress_callback=lambda value, message: events.append((value, message)),
    )

    assert summary.chapter_title == "Python basics"
    assert summary.source_chunks == ["chunk_1"]
    assert retriever.top_k == 8
    assert events[0][0] == 0.18
    assert events[-1][0] == 1.00
