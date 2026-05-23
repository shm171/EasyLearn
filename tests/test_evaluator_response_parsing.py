from __future__ import annotations

import json

import pytest

from ai_core.agents.base_agent import BaseLearningAgent
from ai_core.agents.evaluator_agent import LearningEvaluatorAgent
from ai_core.schemas import EvaluationReport, Question, Quiz


class DummyStructuredAgent:
    def invoke(self, payload, config=None):
        return {
            "messages": [{"role": "assistant", "content": "ignored"}],
            "structured_response": {"ok": True},
        }


def _quiz() -> Quiz:
    return Quiz(
        quiz_id="quiz_test",
        course_id="python_001",
        chapter_title="Python basics",
        programming_language="python",
        difficulty="easy",
        questions=[
            Question(
                question_id="q1",
                question_type="true_false",
                stem="Python is dynamically typed.",
                answer="true",
                explanation="Python variables do not require declared static types.",
                difficulty="easy",
                knowledge_points=["typing"],
                reference_chunks=["chunk_1"],
            )
        ],
    )


def _payload() -> dict:
    return {
        "total_score": 100,
        "question_results": [
            {
                "question_id": "q1",
                "is_correct": True,
                "score": 100,
                "user_answer": "true",
                "feedback": "Correct.",
                "correct_answer": "true",
                "explanation": "The answer matches the reference.",
                "knowledge_points": ["typing"],
                "recommended_review_chunks": ["chunk_1"],
            }
        ],
        "wrong_knowledge_points": [],
        "weakness_summary": "No obvious weakness.",
        "next_study_plan": ["Continue practicing."],
        "recommended_review_chunks": ["chunk_1"],
    }


def _agent_without_init() -> LearningEvaluatorAgent:
    return LearningEvaluatorAgent.__new__(LearningEvaluatorAgent)


def test_empty_evaluator_response_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent_without_init()
    monkeypatch.setattr(agent, "invoke", lambda prompt: "")

    with pytest.raises(ValueError, match="Evaluator agent returned empty response"):
        agent.evaluate(_quiz(), [{"question_id": "q1", "answer": "true"}])


def test_json_string_evaluator_response_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent_without_init()
    monkeypatch.setattr(agent, "invoke", lambda prompt: json.dumps(_payload()))

    report = agent.evaluate(_quiz(), [{"question_id": "q1", "answer": "true"}])

    assert isinstance(report, EvaluationReport)
    assert report.total_score == 100


def test_markdown_json_evaluator_response_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent_without_init()
    monkeypatch.setattr(agent, "invoke", lambda prompt: f"```json\n{json.dumps(_payload())}\n```")

    report = agent.evaluate(_quiz(), [{"question_id": "q1", "answer": "true"}])

    assert report.question_results[0].correct_answer == "true"


def test_base_agent_prefers_structured_response() -> None:
    agent = BaseLearningAgent.__new__(BaseLearningAgent)
    agent.agent = DummyStructuredAgent()
    agent.thread_id = "thread_test"

    assert BaseLearningAgent.invoke(agent, "hello") == {"ok": True}
