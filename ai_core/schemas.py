from __future__ import annotations

"""Pydantic schemas for the programming learning AI core."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


QuestionType = Literal["true_false", "fill_blank", "programming", "short_answer"]
Difficulty = Literal["easy", "medium", "hard", "mixed"]
ConcreteDifficulty = Literal["easy", "medium", "hard"]


class SourceChunk(BaseModel):
    """A retrieved text chunk with source metadata."""

    chunk_id: str
    content: str
    course_id: str
    chapter_title: str | None = None
    file_name: str | None = None
    page_number: int | None = None
    score: float | None = None


class PDFIngestRequest(BaseModel):
    """Request for importing a PDF into the knowledge base."""

    course_id: str
    file_path: str
    chapter_title: str | None = None


class PDFIngestResult(BaseModel):
    """Result returned after PDF ingestion."""

    course_id: str
    file_path: str
    file_name: str
    file_type: Literal["pdf", "markdown"] = "pdf"
    chapter_title: str | None = None
    page_count: int
    chunk_count: int
    message: str


class PDFQueryRequest(BaseModel):
    """Request for asking questions over an imported PDF."""

    course_id: str
    question: str
    chapter_title: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class PDFQueryResult(BaseModel):
    """Answer and sources for a PDF question."""

    answer: str
    source_chunks: list[SourceChunk] = Field(default_factory=list)


class PageRange(BaseModel):
    """A 1-based inclusive PDF page range."""

    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)


class RangeAskRequest(BaseModel):
    """Request for asking AI within a page range."""

    course_id: str
    question: str
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    chapter_title: str | None = None


class RangeSummaryRequest(BaseModel):
    """Request for summarizing a page range."""

    course_id: str
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    chapter_title: str | None = None


class RangeQuizRequest(BaseModel):
    """Request for generating quiz questions from a page range."""

    course_id: str
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    programming_language: str = "python"
    difficulty: Difficulty = "easy"
    question_types: list[QuestionType]
    question_count: int = Field(default=5, ge=1, le=50)
    chapter_title: str | None = None

    @field_validator("question_types")
    @classmethod
    def validate_question_types(cls, value: list[QuestionType]) -> list[QuestionType]:
        """Ensure at least one question type is provided."""

        if not value:
            raise ValueError("question_types cannot be empty")
        return value


class CurrentPageAskRequest(BaseModel):
    """Request for asking AI about the current PDF page."""

    course_id: str
    page_number: int = Field(..., ge=1)
    question: str
    chapter_title: str | None = None


class SelectionAskRequest(BaseModel):
    """Request for AI actions on selected PDF text."""

    course_id: str
    selected_text: str = Field(..., min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    action: Literal["explain", "summarize", "ask", "generate_quiz"] = "explain"
    question: str | None = None
    chapter_title: str | None = None


class CodeSelectionExplainRequest(BaseModel):
    """Request for explaining selected code from a PDF page."""

    course_id: str
    selected_text: str = Field(..., min_length=1)
    page_number: int | None = Field(default=None, ge=1)
    programming_language: str = "python"
    chapter_title: str | None = None


class ChapterSummaryRequest(BaseModel):
    """Request for generating a chapter summary."""

    course_id: str
    chapter_title: str


class ChapterSummary(BaseModel):
    """Structured summary for a programming chapter."""

    chapter_title: str
    learning_goals: list[str] = Field(default_factory=list)
    key_concepts: list[str] = Field(default_factory=list)
    important_terms: list[str] = Field(default_factory=list)
    code_examples: list[str] = Field(default_factory=list)
    typical_question_types: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    study_suggestions: list[str] = Field(default_factory=list)
    source_chunks: list[str] = Field(default_factory=list)


class QuizGenerationRequest(BaseModel):
    """Request for generating programming practice questions."""

    course_id: str
    chapter_title: str
    programming_language: str = "cpp"
    difficulty: Difficulty = "medium"
    question_types: list[QuestionType]
    question_count: int = Field(default=5, ge=1, le=50)

    @field_validator("question_types")
    @classmethod
    def validate_question_types(cls, value: list[QuestionType]) -> list[QuestionType]:
        """Ensure at least one question type is provided."""

        if not value:
            raise ValueError("question_types cannot be empty")
        return value


class Question(BaseModel):
    """A single generated programming learning question."""

    question_id: str
    question_type: QuestionType
    stem: str
    options: list[str] | None = None
    code_snippet: str | None = None
    answer: str
    explanation: str
    difficulty: ConcreteDifficulty
    knowledge_points: list[str] = Field(default_factory=list)
    reference_chunks: list[str] = Field(default_factory=list)


class Quiz(BaseModel):
    """Structured quiz generated from a chapter."""

    quiz_id: str
    course_id: str
    chapter_title: str
    programming_language: str
    difficulty: Difficulty
    questions: list[Question]


class UserAnswer(BaseModel):
    """A user's answer to one quiz question."""

    question_id: str
    answer: str


class QuestionEvaluation(BaseModel):
    """Evaluation result for a single question."""

    question_id: str
    is_correct: bool
    score: float = Field(ge=0, le=100)
    user_answer: str = ""
    feedback: str
    correct_answer: str
    explanation: str = ""
    knowledge_points: list[str] = Field(default_factory=list)
    recommended_review_chunks: list[str] = Field(default_factory=list)


class EvaluationReport(BaseModel):
    """Structured learning evaluation report."""

    total_score: float = Field(ge=0, le=100)
    question_results: list[QuestionEvaluation]
    wrong_knowledge_points: list[str] = Field(default_factory=list)
    weakness_summary: str
    next_study_plan: list[str] = Field(default_factory=list)
    recommended_review_chunks: list[str] = Field(default_factory=list)


class EvaluationRequest(BaseModel):
    """Request for evaluating quiz answers."""

    quiz_id: str
    questions: list[Question]
    user_answers: list[UserAnswer]


class TutorChatRequest(BaseModel):
    """Request for chatting with the tutor agent."""

    user_message: str
    course_id: str | None = None
    thread_id: str | None = None


class TutorChatResponse(BaseModel):
    """Tutor chat response."""

    answer: str
    thread_id: str | None = None
    source_chunks: list[SourceChunk] = Field(default_factory=list)


