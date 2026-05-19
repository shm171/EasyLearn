from __future__ import annotations

import json

import pytest

from ai_core.agents.evaluator_agent import LearningEvaluatorAgent
from ai_core.schemas import EvaluationReport, Quiz, Question


def _quiz() -> Quiz:
    return Quiz(
        quiz_id="quiz_test",
        course_id="python_001",
        chapter_title="Python basics",
        programming_language="python",
        difficulty="medium",
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


def _evaluation_payload() -> dict:
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


def test_evaluator_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent_without_init()
    monkeypatch.setattr(agent, "invoke", lambda prompt: "")

    with pytest.raises(ValueError, match="Evaluator agent returned empty response"):
        agent.evaluate(_quiz(), [{"question_id": "q1", "answer": "true"}])


def test_evaluator_json_string_response(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent_without_init()
    monkeypatch.setattr(agent, "invoke", lambda prompt: json.dumps(_evaluation_payload()))

    report = agent.evaluate(_quiz(), [{"question_id": "q1", "answer": "true"}])

    assert isinstance(report, EvaluationReport)
    assert report.total_score == 100
    assert report.question_results[0].user_answer == "true"


def test_evaluator_markdown_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _agent_without_init()
    raw = "```json\n" + json.dumps(_evaluation_payload()) + "\n```"
    monkeypatch.setattr(agent, "invoke", lambda prompt: raw)

    report = agent.evaluate(_quiz(), [{"question_id": "q1", "answer": "true"}])

    assert isinstance(report, EvaluationReport)
    assert report.question_results[0].explanation == "The answer matches the reference."

