from __future__ import annotations

"""Agent for generating structured chapter summaries."""

from ai_core.agents.base_agent import BaseLearningAgent
from ai_core.rag.retriever import PDFRetriever
from ai_core.schemas import ChapterSummary, ChapterSummaryRequest


SUMMARY_SYSTEM_PROMPT = """You are a programming course chapter summary assistant.
Use PDF evidence as course context, but build a complete student-facing programming summary.
PDF extraction can be noisy, so ignore table-of-contents, preface, copyright, and unrelated overview text.
When evidence is partial, use reliable programming knowledge to fill the teaching scaffold.
Do not cite source chunks for claims that are not supported by those chunks."""


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

        summary_query = (
            f"{request.chapter_title} core concepts syntax structure code examples "
            "common mistakes practice questions"
        )
        chunks = self.retriever.retrieve(
            query=summary_query,
            course_id=request.course_id,
            chapter_title=request.chapter_title,
            top_k=14,
        )

        context = "\n\n".join(f"[{chunk.chunk_id} | page {chunk.page_number}]\n{chunk.content[:1800]}" for chunk in chunks)
        prompt = f"""Course ID: {request.course_id}
Chapter title: {request.chapter_title}

PDF evidence:
{context or "No reliable retrieved evidence was found."}

Return a ChapterSummary.
Rules:
- learning_goals should explain what the student should be able to do.
- key_concepts and important_terms should be complete enough for review, not just copied fragments.
- code_examples should include concise examples when the chapter topic naturally requires syntax.
- common_mistakes should be practical programming mistakes.
- source_chunks must contain only chunk IDs that directly informed the summary. Use an empty list if no reliable chunks were found."""
        result = self.invoke(prompt)
        if isinstance(result, ChapterSummary):
            result.source_chunks = result.source_chunks or [chunk.chunk_id for chunk in chunks]
            return result
        parsed = ChapterSummary.model_validate(result)
        parsed.source_chunks = parsed.source_chunks or [chunk.chunk_id for chunk in chunks]
        return parsed


