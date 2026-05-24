from __future__ import annotations

"""Retriever facade over the document knowledge base."""

from ai_core.rag.vector_store import DocumentKnowledgeBase
from ai_core.rag.source_validator import SourceQualityValidator
from ai_core.schemas import SourceChunk


class PDFRetriever:
    """Retrieve source chunks for a PDF question."""

    def __init__(self, knowledge_base: DocumentKnowledgeBase) -> None:
        """Create a retriever from a knowledge base."""

        self.knowledge_base = knowledge_base
        self.validator = SourceQualityValidator()

    def retrieve(
        self,
        query: str,
        course_id: str,
        chapter_title: str | None = None,
        top_k: int | None = None,
    ) -> list[SourceChunk]:
        """Return source chunks matching the query."""

        limit = top_k or 5
        fetch_k = max(limit * 3, limit + 8)
        seen: set[str] = set()
        chunks: list[SourceChunk] = []

        for query_variant in self.validator.build_query_variants(query):
            matches = self.knowledge_base.search(query_variant, course_id, chapter_title, fetch_k)
            for document, score in matches:
                metadata = document.metadata
                chunk_id = str(metadata.get("chunk_id", ""))
                if chunk_id in seen:
                    continue
                seen.add(chunk_id)
                chunks.append(
                    SourceChunk(
                        chunk_id=chunk_id,
                        content=document.page_content,
                        course_id=str(metadata.get("course_id", course_id)),
                        chapter_title=metadata.get("chapter_title"),
                        file_name=metadata.get("file_name"),
                        page_number=metadata.get("page_number"),
                        score=float(score),
                    )
                )

        if not chunks and chapter_title:
            for query_variant in self.validator.build_query_variants(query):
                matches = self.knowledge_base.search(query_variant, course_id, None, fetch_k)
                for document, score in matches:
                    metadata = document.metadata
                    chunk_id = str(metadata.get("chunk_id", ""))
                    if chunk_id in seen:
                        continue
                    seen.add(chunk_id)
                    chunks.append(
                        SourceChunk(
                            chunk_id=chunk_id,
                            content=document.page_content,
                            course_id=str(metadata.get("course_id", course_id)),
                            chapter_title=metadata.get("chapter_title"),
                            file_name=metadata.get("file_name"),
                            page_number=metadata.get("page_number"),
                            score=float(score),
                        )
                    )

        return self.validator.rerank(chunks, query, limit)


