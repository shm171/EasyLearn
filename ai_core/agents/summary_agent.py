from __future__ import annotations

"""Agent for generating structured chapter summaries."""

from ai_core.agents.base_agent import BaseLearningAgent
from ai_core.rag.retriever import PDFRetriever
from ai_core.schemas import ChapterSummary, ChapterSummaryRequest


SUMMARY_SYSTEM_PROMPT = """You are a programming course chapter summary assistant.
Create exam/interview/practice oriented summaries for students. Focus on concepts, terms, code patterns,
common mistakes, typical question types, and study suggestions. Do not invent content outside the evidence."""


class ChapterSummaryAgent(BaseLearningAgent):
    """Generate structured chapter summaries from PDF chunks."""

    def __init__(self, model, retriever: PDFRetriever, checkpointer=None) -> None:
        """Create a chapter summary agent."""

        self.retriever = retriever
        super().__init__(
            model=model,
            tools=[],
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            checkpointer=checkpointer,
            response_format=ChapterSummary,
        )

    def summarize(self, request: ChapterSummaryRequest) -> ChapterSummary:
        """Generate a structured summary for a chapter."""

        chunks = self.retriever.retrieve(
            query=f"{request.chapter_title} core concepts code examples common mistakes",
            course_id=request.course_id,
            chapter_title=request.chapter_title,
            top_k=12,
        )
        if not chunks:
            raise ValueError("\u8d44\u6599\u4e2d\u672a\u627e\u5230\u660e\u786e\u4f9d\u636e. Please import this chapter PDF first.")

        context = "\n\n".join(f"[{chunk.chunk_id} | page {chunk.page_number}]\n{chunk.content[:1800]}" for chunk in chunks)
        prompt = f"""Course ID: {request.course_id}
Chapter title: {request.chapter_title}

PDF evidence:
{context}

Return a ChapterSummary. source_chunks must contain the chunk IDs you used."""
        result = self.invoke(prompt)
        if isinstance(result, ChapterSummary):
            result.source_chunks = result.source_chunks or [chunk.chunk_id for chunk in chunks]
            return result
        parsed = ChapterSummary.model_validate(result)
        parsed.source_chunks = parsed.source_chunks or [chunk.chunk_id for chunk in chunks]
        return parsed


