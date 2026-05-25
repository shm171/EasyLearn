from __future__ import annotations

"""Agent for answering questions over imported learning materials."""

import json
from collections.abc import Iterator
from typing import Any

from pydantic import ValidationError

from ai_core.agents.evaluator_agent import extract_json_from_text
from ai_core.config import get_settings
from ai_core.rag.retriever import PDFRetriever
from ai_core.schemas import PDFQueryRequest, PDFQueryResult, SourceChunk


READING_SYSTEM_PROMPT = """You are a programming learning tutor using imported material retrieval as the primary source.
First judge whether retrieved evidence actually supports the student's question.
When evidence is relevant, answer mainly from the material and cite chunk IDs for supported points.
When evidence is partial, you may add reliable programming knowledge, but clearly mark it as supplemental.
When evidence is missing or off-topic, do not pretend the answer came from the course material; say that the material did not provide a clear basis, then give only a brief general supplement.
Never cite a chunk for a claim that the chunk does not support. Keep answers concise and layered."""
NO_EVIDENCE_MESSAGE = "资料中未找到明确依据"


class PDFReadingAgent:
    """Answer questions based on retrieved material chunks."""

    def __init__(self, model: Any, retriever: PDFRetriever, checkpointer: Any | None = None) -> None:
        """Create a lightweight direct RAG reader.

        PDF Q&A already performs retrieval before generation, so creating a
        full tool-calling agent for every question adds latency without adding
        useful behavior on this path.
        """

        self.model = model
        self.retriever = retriever
        self.checkpointer = checkpointer

    def answer(self, request: PDFQueryRequest) -> PDFQueryResult:
        """Answer a material question using retrieved evidence."""

        chunks = self.retrieve_sources(request)
        prompt = _build_prompt(request, chunks)
        result = self.model.invoke(prompt)
        parsed = _parse_query_result(result)
        if parsed is not None:
            parsed.source_chunks = parsed.source_chunks or chunks
            return parsed
        answer_text = _extract_response_text(result)
        return PDFQueryResult(answer=answer_text or NO_EVIDENCE_MESSAGE, source_chunks=chunks)

    def retrieve_sources(self, request: PDFQueryRequest) -> list[SourceChunk]:
        """Retrieve source chunks for a material question."""

        return self.retriever.retrieve(
            request.question,
            request.course_id,
            request.chapter_title,
            request.top_k,
        )

    def stream_answer(self, request: PDFQueryRequest) -> tuple[list[SourceChunk], Iterator[str]]:
        """Return retrieved chunks and a token stream for the answer text."""

        chunks = self.retrieve_sources(request)
        return chunks, _stream_model_text(self.model, _build_prompt(request, chunks))


def _build_prompt(request: PDFQueryRequest, chunks: list[SourceChunk]) -> str:
    context = _format_chunks(chunks)
    return f"""{READING_SYSTEM_PROMPT}

Course ID: {request.course_id}
Chapter: {request.chapter_title or "not specified"}
Question: {request.question}

Retrieved evidence:
{context or "No reliable retrieved evidence was found."}

Answer requirements:
- Answer in the same language as the question when possible.
- Start with one short sentence describing the material status: "资料依据：已找到相关资料" or "资料依据：资料中未找到明确依据".
- If material evidence is relevant, use "## 结论 / ## 要点 / ## 示例" and keep the answer within 300-500 Chinese characters unless code is necessary.
- When the question asks for syntax, include one compact syntax template or minimal example.
- If no reliable evidence is provided, use exactly two short sections:
  1. "资料依据：资料中未找到明确依据"
  2. "通用补充：" followed by at most 4 short bullet points. Do not include code blocks unless the student explicitly asks for code.
- If the retrieved material is weak but relevant, say "资料中没有完整展开，下面给出通用补充" and keep the supplement concise. Do not make it look like a course-material answer.
- Include source chunk IDs only for points directly supported by retrieved evidence."""


def _format_chunks(chunks: list[SourceChunk]) -> str:
    settings = get_settings()
    chunk_char_limit = max(350, min(settings.rag_chunk_max_chars, 900))
    total_char_limit = max(chunk_char_limit, min(settings.rag_context_max_chars, 3600))
    sections: list[str] = []
    used_chars = 0

    for chunk in chunks:
        header = f"[{chunk.chunk_id} | page {chunk.page_number}]"
        content = chunk.content.strip()
        clipped_content = _clip_text(content, chunk_char_limit)
        section = f"{header}\n{clipped_content}"
        remaining = total_char_limit - used_chars
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


def _parse_query_dict(result: dict[str, Any]) -> PDFQueryResult | None:
    if "answer" not in result:
        return None
    try:
        return PDFQueryResult.model_validate(result)
    except ValidationError:
        return PDFQueryResult(answer=str(result.get("answer") or ""), source_chunks=[])


def _parse_query_text(text: str) -> PDFQueryResult | None:
    raw_text = text.strip()
    if not raw_text:
        return None
    try:
        parsed = extract_json_from_text(raw_text)
    except (ValueError, json.JSONDecodeError):
        return None
    return _parse_query_dict(parsed)


def _parse_query_result(result: Any) -> PDFQueryResult | None:
    if isinstance(result, PDFQueryResult):
        return result
    if isinstance(result, dict):
        parsed = _parse_query_dict(result)
        if parsed is not None:
            return parsed
        text = _extract_message_text(result)
    else:
        text = _extract_response_text(result)
    return _parse_query_text(text)


def _extract_message_text(result: dict[str, Any]) -> str:
    messages = result.get("messages") or []
    for message in reversed(messages):
        if isinstance(message, dict):
            content = message.get("content")
        else:
            content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if text:
                        parts.append(str(text))
            joined = "\n".join(part.strip() for part in parts if part and part.strip())
            if joined:
                return joined
    return ""


def _extract_response_text(result: Any, strip_text: bool = True) -> str:
    if isinstance(result, dict):
        return _extract_message_text(result)
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content.strip() if strip_text else content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        if strip_text:
            return "\n".join(part.strip() for part in parts if part and part.strip())
        return "".join(parts)
    text = str(content)
    return text.strip() if strip_text else text


def _stream_model_text(model: Any, prompt: str) -> Iterator[str]:
    stream = getattr(model, "stream", None)
    if not callable(stream):
        yield _extract_response_text(model.invoke(prompt))
        return

    emitted = False
    try:
        for chunk in stream(prompt):
            text = _extract_response_text(chunk, strip_text=False)
            if text:
                emitted = True
                yield text
    except Exception:
        if emitted:
            raise
        yield _extract_response_text(model.invoke(prompt))


