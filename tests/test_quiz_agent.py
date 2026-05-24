from __future__ import annotations

import json

from ai_core.agents.quiz_agent import ProgrammingQuizGenerationAgent
from ai_core.schemas import QuizGenerationRequest, SourceChunk


class DummyModel:
    def invoke(self, prompt: str):
        payload = {
            "quiz_id": "quiz_test",
            "course_id": "python_001",
            "chapter_title": "Python basics",
            "programming_language": "python",
            "difficulty": "easy",
            "questions": [
                {
                    "question_id": "q1",
                    "question_type": "true_false",
                    "stem": "Python classes are defined with the class keyword.",
                    "options": None,
                    "code_snippet": None,
                    "answer": "true",
                    "explanation": "The evidence states that classes use the class keyword.",
                    "difficulty": "easy",
                    "knowledge_points": ["class"],
                    "reference_chunks": ["chunk_1"],
                }
            ],
        }
        return type("Message", (), {"content": json.dumps(payload)})()


class DummyRetriever:
    def retrieve(self, query: str, course_id: str, chapter_title: str | None, top_k: int):
        self.top_k = top_k
        return [
            SourceChunk(
                chunk_id="chunk_1",
                content="Classes are defined with the class keyword.",
                course_id=course_id,
                chapter_title=chapter_title,
                page_number=49,
            )
        ]


def test_quiz_agent_generates_quiz_without_langchain_agent() -> None:
    retriever = DummyRetriever()
    agent = ProgrammingQuizGenerationAgent(DummyModel(), retriever)
    events: list[tuple[float, str]] = []

    quiz = agent.generate(
        QuizGenerationRequest(
            course_id="python_001",
            chapter_title="Python basics",
            programming_language="python",
            difficulty="easy",
            question_types=["true_false"],
            question_count=1,
        ),
        progress_callback=lambda value, message: events.append((value, message)),
    )

    assert quiz.quiz_id == "quiz_test"
    assert quiz.questions[0].question_id == "q1"
    assert retriever.top_k == 4
    assert events[0][0] == 0.10
    assert events[-1][0] == 1.00
