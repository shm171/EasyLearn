from __future__ import annotations

"""Retriever facade over the document knowledge base."""

from ai_core.rag.vector_store import DocumentKnowledgeBase
from ai_core.schemas import SourceChunk


class PDFRetriever:
    """Retrieve source chunks for a PDF question."""

    def __init__(self, knowledge_base: DocumentKnowledgeBase) -> None:
        """Create a retriever from a knowledge base."""

        self.knowledge_base = knowledge_base

    def retrieve(
        self,
        query: str,
        course_id: str,
        chapter_title: str | None = None,
        top_k: int | None = None,
    ) -> list[SourceChunk]:
        """Return source chunks matching the query."""

        matches = self.knowledge_base.search(query, course_id, chapter_title, top_k)
        chunks: list[SourceChunk] = []
        for document, score in matches:
            metadata = document.metadata
            chunks.append(
                SourceChunk(
                    chunk_id=str(metadata.get("chunk_id", "")),
                    content=document.page_content,
                    course_id=str(metadata.get("course_id", course_id)),
                    chapter_title=metadata.get("chapter_title"),
                    file_name=metadata.get("file_name"),
                    page_number=metadata.get("page_number"),
                    score=float(score),
                )
            )
        return chunks


