from __future__ import annotations

"""Agent for generating structured chapter summaries."""

import json
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from ai_core.agents.evaluator_agent import extract_json_from_text
from ai_core.agents.reading_agent import _extract_response_text
from ai_core.config import get_settings
from ai_core.rag.retriever import PDFRetriever
from ai_core.schemas import ChapterSummary, ChapterSummaryRequest, SourceChunk


ProgressCallback = Callable[[float, str], None]


SUMMARY_SYSTEM_PROMPT = """You are a programming course chapter summary assistant.
Use PDF evidence as course context, but build a complete student-facing programming summary.
PDF extraction can be noisy, so ignore table-of-contents, preface, copyright, and unrelated overview text.
When evidence is partial, use reliable programming knowledge to fill the teaching scaffold.
Do not cite source chunks for claims that are not supported by those chunks."""


class ChapterSummaryAgent:
    """Generate structured chapter summaries from PDF chunks."""

    def __init__(self, model: Any, retriever: PDFRetriever, checkpointer: Any | None = None) -> None:
        """Create a lightweight chapter summary generator."""

        self.model = model
        self.retriever = retriever
        self.checkpointer = checkpointer

    def summarize(
        self,
        request: ChapterSummaryRequest,
        progress_callback: ProgressCallback | None = None,
    ) -> ChapterSummary:
        """Generate a structured summary for a chapter."""

        _report(progress_callback, 0.18, "检索章节重点")
        summary_query = (
            f"{request.chapter_title} core concepts syntax structure code examples "
            "common mistakes practice questions"
        )
        chunks = self.retriever.retrieve(
            query=summary_query,
            course_id=request.course_id,
            chapter_title=request.chapter_title,
            top_k=8,
        )

        _report(progress_callback, 0.36, "压缩章节上下文")
        prompt = _build_summary_prompt(request, chunks)

        _report(progress_callback, 0.52, "生成章节总结")
        result = self.model.invoke(prompt)

        _report(progress_callback, 0.92, "整理总结结构")
        parsed = _parse_summary_result(result)
        parsed.source_chunks = parsed.source_chunks or [chunk.chunk_id for chunk in chunks]
        _report(progress_callback, 1.00, "章节总结完成")
        return parsed


def _build_summary_prompt(request: ChapterSummaryRequest, chunks: list[SourceChunk]) -> str:
    return f"""{SUMMARY_SYSTEM_PROMPT}

Output JSON only. Do not output Markdown.
JSON shape:
{{
  "chapter_title": "{request.chapter_title}",
  "learning_goals": ["..."],
  "key_concepts": ["..."],
  "important_terms": ["..."],
  "code_examples": ["..."],
  "typical_question_types": ["..."],
  "common_mistakes": ["..."],
  "study_suggestions": ["..."],
  "source_chunks": ["chunk_id"]
}}

Course ID: {request.course_id}
Chapter title: {request.chapter_title}

PDF evidence:
{_format_summary_chunks(chunks) or "No reliable retrieved evidence was found."}

Rules:
- Keep every list concise: 3-5 items each.
- code_examples should be short, review-friendly snippets, not long programs.
- source_chunks must use only chunk IDs from the evidence.
- If evidence is weak, still provide a useful teaching scaffold, but leave source_chunks empty for unsupported items."""


def _format_summary_chunks(chunks: list[SourceChunk]) -> str:
    settings = get_settings()
    per_chunk_limit = max(500, min(settings.rag_chunk_max_chars, 900))
    total_limit = max(2500, min(settings.rag_context_max_chars, 4200))
    sections: list[str] = []
    used_chars = 0

    for chunk in chunks:
        header = f"[{chunk.chunk_id} | page {chunk.page_number}]"
        content = _clip_text(chunk.content.strip(), per_chunk_limit)
        section = f"{header}\n{content}"
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


def _parse_summary_result(result: Any) -> ChapterSummary:
    if isinstance(result, ChapterSummary):
        return result
    if isinstance(result, dict):
        return ChapterSummary.model_validate(result)

    raw_text = _extract_response_text(result)
    if not raw_text:
        raise ValueError("Summary generation returned an empty response.")
    try:
        parsed_json = extract_json_from_text(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Summary generation returned invalid JSON.") from exc
    try:
        return ChapterSummary.model_validate(parsed_json)
    except ValidationError as exc:
        raise ValueError("Summary generation returned JSON that does not match ChapterSummary schema.") from exc


def _report(progress_callback: ProgressCallback | None, value: float, message: str) -> None:
    if progress_callback is not None:
        progress_callback(value, message)
