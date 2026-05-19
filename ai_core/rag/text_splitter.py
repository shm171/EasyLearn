from __future__ import annotations

"""Text splitting for PDF documents."""

from langchain_core.documents import Document

from ai_core.config import get_settings


class PDFTextSplitter:
    """Split PDF page documents into retrievable chunks."""

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None) -> None:
        """Create a splitter using explicit values or settings defaults."""

        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """Split documents and attach stable chunk metadata."""

        if not documents:
            return []
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError as exc:
            raise RuntimeError("Install langchain-text-splitters or langchain to split documents.") from exc

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""],
        )
        chunks = splitter.split_documents(documents)
        for index, chunk in enumerate(chunks, start=1):
            course_id = chunk.metadata.get("course_id", "course")
            page = chunk.metadata.get("page_number", "p")
            chunk.metadata["chunk_id"] = f"{course_id}:{page}:{index}"
        return chunks


