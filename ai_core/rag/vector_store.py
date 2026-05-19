from __future__ import annotations

"""Local Chroma vector store wrapper."""

from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from ai_core.config import get_settings
from ai_core.model_factory import get_embedding_model


class DocumentKnowledgeBase:
    """Manage a local Chroma knowledge base for PDF chunks."""

    def __init__(self, persist_directory: str | None = None, embedding_model: Any | None = None) -> None:
        """Create or load the local vector store."""

        settings = get_settings()
        self.persist_directory = str(Path(persist_directory or settings.vector_db_dir))
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        self.embedding_model = embedding_model or get_embedding_model()
        self.store = self._create_store()

    def _create_store(self) -> Any:
        try:
            from langchain_chroma import Chroma
        except ImportError as exc:
            raise RuntimeError("Install langchain-chroma to use the local vector store.") from exc
        return Chroma(
            collection_name="programming_learning_pdf",
            embedding_function=self.embedding_model,
            persist_directory=self.persist_directory,
        )

    def add_documents(self, documents: list[Document]) -> list[str]:
        """Add chunked documents to Chroma and return stored IDs."""

        if not documents:
            return []
        ids: list[str] = []
        for index, document in enumerate(documents, start=1):
            metadata = document.metadata
            for key, value in list(metadata.items()):
                if value is None:
                    metadata[key] = ""
            metadata.setdefault("chunk_id", f"{metadata.get('course_id', 'course')}:chunk:{index}")
            ids.append(str(metadata["chunk_id"]))
        return self.store.add_documents(documents=documents, ids=ids)

    def search(
        self,
        query: str,
        course_id: str,
        chapter_title: str | None = None,
        top_k: int | None = None,
    ) -> list[tuple[Document, float]]:
        """Search chunks by query and course filters."""

        if not query.strip():
            raise ValueError("query cannot be empty")
        settings = get_settings()
        filters: dict[str, Any] = {"course_id": course_id}
        if chapter_title:
            filters = {"$and": [{"course_id": course_id}, {"chapter_title": chapter_title}]}
        return self.store.similarity_search_with_score(query=query, k=top_k or settings.top_k, filter=filters)

    def delete_course(self, course_id: str) -> int:
        """Delete all chunks for a course and return the deleted count."""

        results = self.store.get(where={"course_id": course_id}, include=["metadatas"])
        ids = results.get("ids", [])
        if ids:
            self.store.delete(ids=ids)
        return len(ids)

    def list_courses(self) -> list[str]:
        """List known course IDs in the vector store."""

        results = self.store.get(include=["metadatas"])
        courses = {
            metadata.get("course_id")
            for metadata in results.get("metadatas", [])
            if metadata and metadata.get("course_id")
        }
        return sorted(courses)

