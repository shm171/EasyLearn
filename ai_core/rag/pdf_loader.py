from __future__ import annotations

"""PDF loading utilities."""

from pathlib import Path

from langchain_core.documents import Document


class PDFLoaderManager:
    """Read text-based PDF learning materials into LangChain documents."""

    def load_pdf(self, file_path: str, course_id: str, chapter_title: str | None = None) -> list[Document]:
        """Load a PDF file page by page.

        Raises:
            ValueError: If the file is not a PDF or appears to be scanned/OCR-only.
        """

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError("Only .pdf files are supported in this phase.")

        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("Install pymupdf to read PDF files.") from exc

        documents: list[Document] = []
        try:
            with fitz.open(path) as pdf:
                for index, page in enumerate(pdf, start=1):
                    text = page.get_text("text").strip()
                    if not text:
                        continue
                    documents.append(
                        Document(
                            page_content=text,
                            metadata={
                                "course_id": course_id,
                                "file_path": str(path),
                                "file_name": path.name,
                                "file_type": "pdf",
                                "chapter_title": chapter_title,
                                "page_number": index,
                            },
                        )
                    )
        except Exception as exc:
            raise RuntimeError(f"Failed to read PDF: {file_path}") from exc

        if not documents:
            raise ValueError("No extractable text found. Scanned PDF files are not supported yet.")
        return documents


