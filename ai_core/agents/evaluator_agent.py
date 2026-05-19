from __future__ import annotations

"""Agent for evaluating quiz answers."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ai_core.agents.base_agent import BaseLearningAgent
from ai_core.schemas import EvaluationReport, EvaluationRequest, Quiz, UserAnswer
from ai_core.tools.evaluation_tools import compare_answer_tool


EVALUATOR_SYSTEM_PROMPT = """You are a strict but clear programming learning evaluator.
Grade true/false, fill-blank, short-answer, and programming questions with suitable criteria.
For programming answers, consider idea correctness, syntax, edge cases, and complexity.
Always identify causes of mistakes and give concrete next study steps.
Output JSON only. Do not output Markdown. Do not output explanatory natural language outside JSON.
The JSON must strictly match the EvaluationReport schema."""


DEBUG_DIR = Path("debug_outputs")
EVALUATION_PROMPT_PATH = DEBUG_DIR / "evaluation_prompt.txt"
RAW_EVALUATION_RESPONSE_PATH = DEBUG_DIR / "raw_evaluation_response.txt"


class LearningEvaluatorAgent(BaseLearningAgent):
    """Evaluate user quiz answers and produce a structured report."""

    def __init__(self, model, checkpointer=None) -> None:
        """Create an evaluator agent."""

        super().__init__(
            model=model,
            tools=[compare_answer_tool],
            system_prompt=EVALUATOR_SYSTEM_PROMPT,
            checkpointer=checkpointer,
            response_format=EvaluationReport,
        )

    def evaluate(self, quiz: Quiz, user_answers: list[UserAnswer]) -> EvaluationReport:
        """Evaluate user answers for a quiz."""

        request = EvaluationRequest(quiz_id=quiz.quiz_id, questions=quiz.questions, user_answers=user_answers)
        prompt = f"""Evaluate this quiz attempt and return EvaluationReport.

Output requirements:
- Output JSON only.
- Do not output Markdown.
- Do not output explanatory natural language outside JSON.
- The JSON must strictly conform to the EvaluationReport schema.
- total_score must be a number from 0 to 100.
- question_results must cover every question in the quiz.
- Every item in question_results must include:
  - question_id
  - is_correct
  - score
  - user_answer
  - feedback
  - correct_answer
  - explanation
  - knowledge_points
  - recommended_review_chunks

Quiz metadata:
course_id={quiz.course_id}
chapter_title={quiz.chapter_title}
programming_language={quiz.programming_language}

Evaluation payload JSON:
{request.model_dump_json(ensure_ascii=False)}

Scoring:
- total_score is 0 to 100.
- each question score is 0 to 100.
- recommend review chunks based on reference_chunks."""
        result: Any | None = None
        try:
            result = self.invoke(prompt)
            return self._parse_evaluation_result(result)
        except ValueError:
            self._write_debug_files(prompt, result)
            raise
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            self._write_debug_files(prompt, result)
            raise ValueError(
                "Evaluator agent returned an invalid EvaluationReport. "
                "Raw response was saved to debug_outputs/raw_evaluation_response.txt."
            ) from exc

    def _parse_evaluation_result(self, result: Any) -> EvaluationReport:
        """Safely parse the evaluator agent result into EvaluationReport."""

        if isinstance(result, EvaluationReport):
            return result
        if isinstance(result, dict):
            return EvaluationReport.model_validate(result)
        if isinstance(result, str):
            raw_text = result.strip()
            if not raw_text:
                raise ValueError(
                    "Evaluator agent returned empty response. Please check DeepSeek response, prompt, "
                    "or structured output configuration."
                )
            parsed_json = extract_json_from_text(raw_text)
            return EvaluationReport.model_validate(parsed_json)
        raise ValueError(
            f"Evaluator agent returned unsupported response type: {type(result).__name__}. "
            "Raw response was saved to debug_outputs/raw_evaluation_response.txt."
        )

    def _write_debug_files(self, prompt: str, raw_response: Any) -> None:
        """Save prompt and raw response for debugging failed evaluations."""

        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        EVALUATION_PROMPT_PATH.write_text(prompt, encoding="utf-8")
        if isinstance(raw_response, str):
            raw_text = raw_response
        else:
            raw_text = repr(raw_response)
        RAW_EVALUATION_RESPONSE_PATH.write_text(raw_text, encoding="utf-8")


def extract_json_from_text(text: str) -> dict[str, Any]:
    """Extract the first JSON object from plain text or a markdown JSON code block."""

    raw_text = text.strip()
    if not raw_text:
        raise ValueError("Cannot extract JSON from empty text.")

    candidates = [raw_text]
    fenced = _extract_fenced_json(raw_text)
    if fenced:
        candidates.insert(0, fenced)
    embedded = _extract_first_json_object(raw_text)
    if embedded:
        candidates.append(embedded)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if not isinstance(parsed, dict):
            raise ValueError("Extracted JSON is not an object.")
        return parsed

    raise ValueError("Failed to parse EvaluationReport JSON from evaluator response.") from last_error


def _extract_fenced_json(text: str) -> str | None:
    marker = "```"
    start = text.find(marker)
    while start != -1:
        content_start = start + len(marker)
        line_end = text.find("\n", content_start)
        if line_end == -1:
            return None
        language = text[content_start:line_end].strip().lower()
        end = text.find(marker, line_end + 1)
        if end == -1:
            return None
        block = text[line_end + 1 : end].strip()
        if language in {"json", ""} and block:
            return block
        start = text.find(marker, end + len(marker))
    return None


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


