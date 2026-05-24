from __future__ import annotations

"""Fast quiz generation from retrieved PDF evidence."""

import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from ai_core.agents.evaluator_agent import extract_json_from_text
from ai_core.config import get_settings
from ai_core.rag.retriever import PDFRetriever
from ai_core.schemas import Quiz, QuizGenerationRequest, SourceChunk
from ai_core.tools.quiz_tools import allocate_question_counts


ProgressCallback = Callable[[float, str], None]


QUIZ_SYSTEM_PROMPT = """You are a programming learning quiz generation assistant.
Questions must come from the current chapter evidence. Match question_types, difficulty, and exact question_count.
For programming questions, include clear input/output or function requirements when code is expected.
Answers and explanations must be accurate. Do not generate questions unrelated to the PDF chapter."""


class ProgrammingQuizGenerationAgent:
    """Generate structured programming quizzes from chapter evidence."""

    def __init__(self, model: Any, retriever: PDFRetriever, checkpointer: Any | None = None) -> None:
        """Create a lightweight quiz generator."""

        self.model = model
        self.retriever = retriever
        self.checkpointer = checkpointer

    def generate(self, request: QuizGenerationRequest, progress_callback: ProgressCallback | None = None) -> Quiz:
        """Generate a quiz with an exact number of questions."""

        _report(progress_callback, 0.10, "检索出题依据")
        chunks = self.retriever.retrieve(
            query=f"{request.chapter_title} programming syntax concepts practice questions",
            course_id=request.course_id,
            chapter_title=request.chapter_title,
            top_k=_quiz_top_k(request.question_count),
        )
        if not chunks:
            raise ValueError("资料中未找到明确依据. Please import this chapter PDF first.")

        _report(progress_callback, 0.30, "压缩上下文")
        allocation = allocate_question_counts(request.question_types, request.question_count)
        difficulty_plan = _build_difficulty_plan(request.difficulty, request.question_count)
        prompt = _build_quiz_prompt(request, chunks, allocation, difficulty_plan)

        _report(progress_callback, 0.45, "调用模型生成题目")
        result = self.model.invoke(prompt)

        _report(progress_callback, 0.92, "解析生成结果")
        quiz = _parse_quiz_result(result)
        if not quiz.quiz_id:
            quiz.quiz_id = f"quiz_{uuid4().hex[:12]}"
        if len(quiz.questions) != request.question_count:
            raise ValueError(
                f"Quiz generation returned {len(quiz.questions)} questions; expected {request.question_count}."
            )
        _report(progress_callback, 1.00, "题目生成完成")
        return quiz


def _build_difficulty_plan(difficulty: str, count: int) -> list[str]:
    if difficulty in {"easy", "medium", "hard"}:
        return [difficulty] * count
    plan = ["medium"] * count
    for index in range(count):
        if index % 5 == 0:
            plan[index] = "easy"
        elif index % 5 == 4:
            plan[index] = "hard"
    return plan


def _quiz_top_k(question_count: int) -> int:
    return min(8, max(4, question_count + 1))


def _build_quiz_prompt(
    request: QuizGenerationRequest,
    chunks: list[SourceChunk],
    allocation: dict[str, int],
    difficulty_plan: list[str],
) -> str:
    context = _format_quiz_chunks(chunks)
    return f"""{QUIZ_SYSTEM_PROMPT}

Output JSON only. Do not output Markdown.
The JSON must strictly match this shape:
{{
  "quiz_id": "quiz_xxx",
  "course_id": "{request.course_id}",
  "chapter_title": "{request.chapter_title}",
  "programming_language": "{request.programming_language}",
  "difficulty": "{request.difficulty}",
  "questions": [
    {{
      "question_id": "q1",
      "question_type": "true_false|fill_blank|programming|short_answer",
      "stem": "...",
      "options": null,
      "code_snippet": null,
      "answer": "...",
      "explanation": "...",
      "difficulty": "easy|medium|hard",
      "knowledge_points": ["..."],
      "reference_chunks": ["chunk_id"]
    }}
  ]
}}

Generation parameters:
- exact question_count: {request.question_count}
- question type allocation: {allocation}
- difficulty plan in order: {difficulty_plan}
- question_id values must be q1, q2, q3...
- true_false answers must be exactly "true" or "false".
- fill_blank stems must contain ____.
- reference_chunks must use chunk IDs from the evidence.
- Keep stems and explanations concise to reduce latency; explanation should be one short sentence.

PDF evidence:
{context}"""


def _format_quiz_chunks(chunks: list[SourceChunk]) -> str:
    settings = get_settings()
    per_chunk_limit = max(500, min(settings.rag_chunk_max_chars, 1000))
    total_limit = max(2500, min(settings.rag_context_max_chars, 4200))
    sections: list[str] = []
    used_chars = 0

    for chunk in chunks:
        header = f"[{chunk.chunk_id} | page {chunk.page_number}]"
        content = chunk.content.strip()
        section = f"{header}\n{_clip_text(content, per_chunk_limit)}"
        remaining = total_limit - used_chars
        if remaining <= 0:
            break
        if len(section) > remaining:
            section = _clip_text(section, remaining)
        sections.append(section)
        used_chars += len(section) + 2

    return "\n\n".join(sections)


def _clip_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 4)].rstrip() + "\n..."


def _parse_quiz_result(result: Any) -> Quiz:
    if isinstance(result, Quiz):
        return result
    if isinstance(result, dict):
        return Quiz.model_validate(result)

    raw_text = _extract_response_text(result)
    if not raw_text:
        raise ValueError("Quiz generation returned an empty response.")
    try:
        parsed_json = extract_json_from_text(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Quiz generation returned invalid JSON.") from exc
    try:
        return Quiz.model_validate(parsed_json)
    except ValidationError as exc:
        raise ValueError("Quiz generation returned JSON that does not match Quiz schema.") from exc


def _extract_response_text(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "\n".join(part.strip() for part in parts if part and part.strip())
    return str(content).strip()


def _report(progress_callback: ProgressCallback | None, value: float, message: str) -> None:
    if progress_callback is not None:
        progress_callback(value, message)
