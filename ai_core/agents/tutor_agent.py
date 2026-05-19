from __future__ import annotations

"""High-level programming tutor agent."""

from ai_core.agents.base_agent import BaseLearningAgent
from ai_core.rag.retriever import PDFRetriever
from ai_core.schemas import TutorChatRequest, TutorChatResponse


TUTOR_SYSTEM_PROMPT = """You are a programming learning tutor controller.
Help identify whether the student wants material lookup, summaries, quizzes, evaluation, or general guidance.
If PDF evidence is insufficient, tell the student to import PDF materials first."""


class ProgrammingTutorAgent(BaseLearningAgent):
    """General tutor agent for programming learning conversations."""

    def __init__(self, model, retriever: PDFRetriever, checkpointer=None) -> None:
        """Create a tutor agent."""

        self.retriever = retriever
        super().__init__(
            model=model,
            tools=[],
            system_prompt=TUTOR_SYSTEM_PROMPT,
            checkpointer=checkpointer,
            response_format=TutorChatResponse,
        )

    def chat(self, request: TutorChatRequest) -> TutorChatResponse:
        """Chat with the tutor, optionally grounding the answer in course materials."""

        chunks = []
        if request.course_id:
            chunks = self.retriever.retrieve(request.user_message, request.course_id, top_k=5)
        context = "\n\n".join(f"[{chunk.chunk_id} | page {chunk.page_number}]\n{chunk.content[:1200]}" for chunk in chunks)
        prompt = f"""Student message: {request.user_message}
Course ID: {request.course_id or "not specified"}

Retrieved evidence:
{context or "No evidence retrieved."}

Return a helpful TutorChatResponse. If evidence is needed but absent, ask the student to import PDF materials first."""
        result = self.invoke(prompt, thread_id=request.thread_id)
        if isinstance(result, TutorChatResponse):
            result.thread_id = request.thread_id or self.thread_id
            result.source_chunks = result.source_chunks or chunks
            return result
        parsed = TutorChatResponse.model_validate(result)
        parsed.thread_id = request.thread_id or self.thread_id
        parsed.source_chunks = parsed.source_chunks or chunks
        return parsed


