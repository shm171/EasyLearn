from __future__ import annotations

"""Agent for generating programming learning quizzes."""

from uuid import uuid4

from ai_core.agents.base_agent import BaseLearningAgent
from ai_core.rag.retriever import PDFRetriever
from ai_core.schemas import Quiz, QuizGenerationRequest
from ai_core.tools.quiz_tools import allocate_question_counts, allocate_question_counts_tool


QUIZ_SYSTEM_PROMPT = """You are a programming learning quiz generation assistant.
Questions must come from the current chapter evidence. Match question_types, difficulty, and exact question_count.
For programming questions, include clear input/output or function requirements when code is expected.
Answers and explanations must be accurate. Do not generate questions unrelated to the PDF chapter."""


class ProgrammingQuizGenerationAgent(BaseLearningAgent):
    """Generate structured programming quizzes from chapter evidence."""

    def __init__(self, model, retriever: PDFRetriever, checkpointer=None) -> None:
        """Create a quiz generation agent."""

        self.retriever = retriever
        super().__init__(
            model=model,
            tools=[allocate_question_counts_tool],
            system_prompt=QUIZ_SYSTEM_PROMPT,
            checkpointer=checkpointer,
            response_format=Quiz,
        )

    def generate(self, request: QuizGenerationRequest) -> Quiz:
        """Generate a quiz with an exact number of questions."""

        chunks = self.retriever.retrieve(
            query=f"{request.chapter_title} programming syntax concepts practice questions",
            course_id=request.course_id,
            chapter_title=request.chapter_title,
            top_k=14,
        )
        if not chunks:
            raise ValueError("\u8d44\u6599\u4e2d\u672a\u627e\u5230\u660e\u786e\u4f9d\u636e. Please import this chapter PDF first.")

        allocation = allocate_question_counts(request.question_types, request.question_count)
        difficulty_plan = _build_difficulty_plan(request.difficulty, request.question_count)
        context = "\n\n".join(f"[{chunk.chunk_id} | page {chunk.page_number}]\n{chunk.content[:1600]}" for chunk in chunks)
        prompt = f"""Generate a structured Quiz.

quiz_id: generate a stable-looking ID beginning with quiz_
course_id: {request.course_id}
chapter_title: {request.chapter_title}
programming_language: {request.programming_language}
difficulty parameter: {request.difficulty}
exact question_count: {request.question_count}
question type allocation: {allocation}
difficulty plan in order: {difficulty_plan}

PDF evidence:
{context}

Rules:
- The final questions length must be exactly {request.question_count}.
- question_id values should be q1, q2, q3...
- true_false answers must be exactly "true" or "false".
- fill_blank stems must contain ____.
- reference_chunks must use chunk IDs from the evidence."""
        result = self.invoke(prompt)
        quiz = result if isinstance(result, Quiz) else Quiz.model_validate(result)
        if not quiz.quiz_id:
            quiz.quiz_id = f"quiz_{uuid4().hex[:12]}"
        if len(quiz.questions) != request.question_count:
            raise ValueError(
                f"Quiz generation returned {len(quiz.questions)} questions; expected {request.question_count}."
            )
        return quiz


def _build_difficulty_plan(difficulty: str, count: int) -> list[str]:
    if difficulty in {"easy", "medium", "hard"}:
        return [difficulty] * count
    plan = ["medium"] * count
    for index in range(count):
        if index % 5 == 0:
            plan[index] = "easy"
        elif index % 5 == 4:
            plan[index] = "hard"
    return plan


