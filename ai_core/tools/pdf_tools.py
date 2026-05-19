from __future__ import annotations

"""PDF RAG tools."""

from langchain_core.tools import tool

from ai_core.rag.retriever import PDFRetriever


def create_query_pdf_tool(retriever: PDFRetriever):
    """Create a query_pdf tool bound to a retriever instance."""

    @tool("query_pdf")
    def query_pdf(course_id: str, question: str, chapter_title: str | None = None, top_k: int = 5) -> str:
        """Search imported PDF chunks for evidence related to a programming learning question."""

        chunks = retriever.retrieve(question, course_id, chapter_title, top_k)
        if not chunks:
            return "璧勬枡涓湭鎵惧埌鏄庣‘渚濇嵁"
        lines: list[str] = []
        for chunk in chunks:
            lines.append(
                f"[chunk_id={chunk.chunk_id}, page={chunk.page_number}, score={chunk.score}] "
                f"{chunk.content[:1200]}"
            )
        return "\n\n".join(lines)

    return query_pdf


