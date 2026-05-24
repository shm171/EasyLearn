from __future__ import annotations

"""Page-range retrieval helpers for imported PDF chunks."""

import logging
from typing import Any

from langchain_core.documents import Document

from ai_core.rag.vector_store import DocumentKnowledgeBase
from ai_core.schemas import SourceChunk


NO_RANGE_CONTENT_MESSAGE = "指定页码范围内未找到可用内容。"

logger = logging.getLogger(__name__)


class RangeRetriever:
    """Retrieve PDF chunks by course_id and page range."""

    def __init__(self, knowledge_base: DocumentKnowledgeBase) -> None:
        self.knowledge_base = knowledge_base
        self.warnings: list[str] = []

    def validate_page_range(self, page_start: int, page_end: int) -> tuple[int, int]:
        """Validate 1-based user-visible page numbers."""

        if page_start < 1 or page_end < 1:
            raise ValueError("page_start and page_end must be greater than or equal to 1.")
        if page_start > page_end:
            raise ValueError("page_start cannot be greater than page_end.")
        return page_start, page_end

    def get_chunks_by_page_range(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None = None,
        limit: int | None = None,
    ) -> list[SourceChunk]:
        """Return chunks whose metadata page number is inside the requested range."""

        self._reset_warnings()
        page_start, page_end = self.validate_page_range(page_start, page_end)
        try:
            results = self.knowledge_base.store.get(
                where=self._build_range_filter(course_id, page_start, page_end, chapter_title),
                include=["documents", "metadatas"],
            )
            chunks = self._chunks_from_get_results(results, course_id, page_start, page_end)
        except Exception as exc:
            self._warn(
                "Chroma metadata range filtering is unavailable; falling back to Python page_number filtering."
            )
            logger.debug("Chroma range get failed; using fallback filtering.", exc_info=exc)
            chunks = self._fallback_get_chunks(course_id, page_start, page_end, chapter_title)

        chunks = self._sort_chunks(chunks)
        if limit is not None:
            chunks = chunks[:limit]
        return chunks

    def search_in_range(
        self,
        course_id: str,
        query: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None = None,
        top_k: int = 5,
    ) -> list[SourceChunk]:
        """Run semantic search while restricting candidates to a page range."""

        self._reset_warnings()
        if not query.strip():
            raise ValueError("query cannot be empty")
        page_start, page_end = self.validate_page_range(page_start, page_end)
        fetch_k = max(top_k * 8, top_k + 20)

        try:
            matches = self.knowledge_base.store.similarity_search_with_score(
                query=query,
                k=fetch_k,
                filter=self._build_range_filter(course_id, page_start, page_end, chapter_title),
            )
            chunks = [
                self._document_to_source_chunk(document, course_id, score)
                for document, score in matches
                if self._document_in_range(document, page_start, page_end)
            ]
        except Exception as exc:
            self._warn(
                "Chroma metadata range filtering is unavailable; falling back to global search plus Python page_number filtering."
            )
            logger.debug("Chroma range search failed; using fallback filtering.", exc_info=exc)
            matches = self.knowledge_base.search(query, course_id, chapter_title, fetch_k)
            chunks = [
                self._document_to_source_chunk(document, course_id, score)
                for document, score in matches
                if self._document_in_range(document, page_start, page_end)
            ]

        return self._sort_chunks(chunks)[:top_k]

    def build_context_from_range(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None = None,
        max_chars: int = 12000,
    ) -> str:
        """Build a clipped context string from all chunks in a page range."""

        chunks = self.get_chunks_by_page_range(
            course_id=course_id,
            page_start=page_start,
            page_end=page_end,
            chapter_title=chapter_title,
        )
        if not chunks:
            return NO_RANGE_CONTENT_MESSAGE

        sections: list[str] = []
        used_chars = 0
        for chunk in chunks:
            header = f"[{chunk.chunk_id} | page {chunk.page_number}]"
            section = f"{header}\n{chunk.content.strip()}"
            remaining = max_chars - used_chars
            if remaining <= 0:
                break
            if len(section) > remaining:
                section = section[: max(0, remaining - 4)].rstrip() + "\n..."
            sections.append(section)
            used_chars += len(section) + 2
        return "\n\n".join(sections) if sections else NO_RANGE_CONTENT_MESSAGE

    def _build_range_filter(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None,
    ) -> dict[str, Any]:
        clauses: list[dict[str, Any]] = [
            {"course_id": course_id},
            {"page_number": {"$gte": page_start}},
            {"page_number": {"$lte": page_end}},
        ]
        if chapter_title:
            clauses.append({"chapter_title": chapter_title})
        return {"$and": clauses}

    def _fallback_get_chunks(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None,
    ) -> list[SourceChunk]:
        where: dict[str, Any] = {"course_id": course_id}
        if chapter_title:
            where = {"$and": [{"course_id": course_id}, {"chapter_title": chapter_title}]}
        results = self.knowledge_base.store.get(where=where, include=["documents", "metadatas"])
        return self._chunks_from_get_results(results, course_id, page_start, page_end)

    def _chunks_from_get_results(
        self,
        results: dict[str, Any],
        course_id: str,
        page_start: int,
        page_end: int,
    ) -> list[SourceChunk]:
        ids = results.get("ids") or []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        chunks: list[SourceChunk] = []

        for index, content in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
            page_number = self._metadata_page_number(metadata)
            if page_number is None:
                self._warn("Skipped a chunk without metadata.page_number.")
                continue
            if not page_start <= page_number <= page_end:
                continue
            chunk_id = str(metadata.get("chunk_id") or (ids[index] if index < len(ids) else ""))
            chunks.append(
                SourceChunk(
                    chunk_id=chunk_id,
                    content=str(content or ""),
                    course_id=str(metadata.get("course_id") or course_id),
                    chapter_title=metadata.get("chapter_title"),
                    file_name=metadata.get("file_name"),
                    page_number=page_number,
                    score=None,
                )
            )
        return chunks

    def _document_to_source_chunk(
        self,
        document: Document,
        course_id: str,
        score: float | None = None,
    ) -> SourceChunk:
        metadata = document.metadata
        return SourceChunk(
            chunk_id=str(metadata.get("chunk_id", "")),
            content=document.page_content,
            course_id=str(metadata.get("course_id") or course_id),
            chapter_title=metadata.get("chapter_title"),
            file_name=metadata.get("file_name"),
            page_number=self._metadata_page_number(metadata),
            score=float(score) if score is not None else None,
        )

    def _document_in_range(self, document: Document, page_start: int, page_end: int) -> bool:
        page_number = self._metadata_page_number(document.metadata)
        if page_number is None:
            self._warn("Skipped a chunk without metadata.page_number.")
            return False
        return page_start <= page_number <= page_end

    def _metadata_page_number(self, metadata: dict[str, Any]) -> int | None:
        value = metadata.get("page_number")
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            self._warn(f"Skipped a chunk with invalid metadata.page_number: {value}")
            return None

    def _sort_chunks(self, chunks: list[SourceChunk]) -> list[SourceChunk]:
        return sorted(chunks, key=lambda chunk: (chunk.page_number or 0, chunk.chunk_id))

    def _reset_warnings(self) -> None:
        self.warnings = []

    def _warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)
        logger.warning(message)
