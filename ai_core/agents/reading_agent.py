from __future__ import annotations

"""Agent for answering questions over PDF materials."""

from ai_core.agents.base_agent import BaseLearningAgent
from ai_core.rag.retriever import PDFRetriever
from ai_core.schemas import PDFQueryRequest, PDFQueryResult, SourceChunk
from ai_core.tools.pdf_tools import create_query_pdf_tool


READING_SYSTEM_PROMPT = """You are a rigorous programming learning PDF Q&A assistant.
Answer only from retrieved PDF content. If there is no evidence, say "璧勬枡涓湭鎵惧埌鏄庣‘渚濇嵁".
Include source chunk IDs and page numbers when possible. Do not invent content not present in the PDF."""


class PDFReadingAgent(BaseLearningAgent):
    """Answer questions based on retrieved PDF chunks."""

    def __init__(self, model, retriever: PDFRetriever, checkpointer=None) -> None:
        """Create a PDF reading agent."""

        self.retriever = retriever
        super().__init__(
            model=model,
            tools=[create_query_pdf_tool(retriever)],
            system_prompt=READING_SYSTEM_PROMPT,
            checkpointer=checkpointer,
            response_format=PDFQueryResult,
        )

    def answer(self, request: PDFQueryRequest) -> PDFQueryResult:
        """Answer a PDF question using retrieved evidence."""

        chunks = self.retriever.retrieve(
            request.question,
            request.course_id,
            request.chapter_title,
            request.top_k,
        )
        if not chunks:
            return PDFQueryResult(answer="璧勬枡涓湭鎵惧埌鏄庣‘渚濇嵁", source_chunks=[])

        context = _format_chunks(chunks)
        prompt = f"""Course ID: {request.course_id}
Chapter: {request.chapter_title or "not specified"}
Question: {request.question}

Retrieved evidence:
{context}

Return a concise answer grounded in the evidence and include source chunk IDs."""
        result = self.invoke(prompt)
        if isinstance(result, PDFQueryResult):
            result.source_chunks = result.source_chunks or chunks
            return result
        if isinstance(result, dict):
            parsed = PDFQueryResult.model_validate(result)
            parsed.source_chunks = parsed.source_chunks or chunks
            return parsed
        return PDFQueryResult(answer=str(result), source_chunks=chunks)


def _format_chunks(chunks: list[SourceChunk]) -> str:
    return "\n\n".join(
        f"[{chunk.chunk_id} | page {chunk.page_number}]\n{chunk.content[:1800]}" for chunk in chunks
    )


