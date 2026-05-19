from __future__ import annotations

"""Unified service API for CLI, FastAPI, and future GUI/Web clients."""

from typing import Any

from ai_core.agents.evaluator_agent import LearningEvaluatorAgent
from ai_core.agents.quiz_agent import ProgrammingQuizGenerationAgent
from ai_core.agents.reading_agent import PDFReadingAgent
from ai_core.agents.summary_agent import ChapterSummaryAgent
from ai_core.agents.tutor_agent import ProgrammingTutorAgent
from ai_core.config import get_settings
from ai_core.memory import create_memory_checkpointer
from ai_core.model_factory import get_chat_model
from ai_core.rag.pdf_loader import PDFLoaderManager
from ai_core.rag.retriever import PDFRetriever
from ai_core.rag.text_splitter import PDFTextSplitter
from ai_core.rag.vector_store import DocumentKnowledgeBase
from ai_core.schemas import (
    ChapterSummary,
    ChapterSummaryRequest,
    EvaluationReport,
    PDFIngestResult,
    PDFQueryRequest,
    PDFQueryResult,
    Quiz,
    QuizGenerationRequest,
    TutorChatRequest,
    TutorChatResponse,
    UserAnswer,
)


class LearningAIService:
    """Facade for the programming learning AI core."""

    def __init__(self) -> None:
        """Create the service with lazy model and vector-store initialization."""

        self.settings = get_settings()
        self.pdf_loader = PDFLoaderManager()
        self.text_splitter = PDFTextSplitter()
        self._knowledge_base: DocumentKnowledgeBase | None = None
        self._retriever: PDFRetriever | None = None
        self._model: Any | None = None
        self._checkpointer: Any | None = None

    @property
    def knowledge_base(self) -> DocumentKnowledgeBase:
        """Return the lazily initialized document knowledge base."""

        if self._knowledge_base is None:
            self._knowledge_base = DocumentKnowledgeBase()
        return self._knowledge_base

    @property
    def retriever(self) -> PDFRetriever:
        """Return the lazily initialized PDF retriever."""

        if self._retriever is None:
            self._retriever = PDFRetriever(self.knowledge_base)
        return self._retriever

    @property
    def model(self) -> Any:
        """Return the lazily initialized chat model."""

        if self._model is None:
            self._model = get_chat_model()
        return self._model

    @property
    def checkpointer(self) -> Any | None:
        """Return the lazily initialized memory checkpointer."""

        if self._checkpointer is None:
            self._checkpointer = create_memory_checkpointer()
        return self._checkpointer

    def ingest_pdf(self, course_id: str, file_path: str, chapter_title: str | None = None) -> PDFIngestResult:
        """Read, chunk, and store a PDF in the local vector database."""

        documents = self.pdf_loader.load_pdf(file_path=file_path, course_id=course_id, chapter_title=chapter_title)
        chunks = self.text_splitter.split_documents(documents)
        self.knowledge_base.add_documents(chunks)
        first_meta = documents[0].metadata
        return PDFIngestResult(
            course_id=course_id,
            file_path=file_path,
            file_name=str(first_meta.get("file_name", "")),
            chapter_title=chapter_title,
            page_count=len(documents),
            chunk_count=len(chunks),
            message="PDF imported successfully.",
        )

    def ask_pdf(self, course_id: str, question: str, chapter_title: str | None = None) -> PDFQueryResult:
        """Ask a question over imported PDF materials."""

        request = PDFQueryRequest(
            course_id=course_id,
            question=question,
            chapter_title=chapter_title,
            top_k=self.settings.top_k,
        )
        agent = PDFReadingAgent(self.model, self.retriever, self.checkpointer)
        return agent.answer(request)

    def summarize_chapter(self, course_id: str, chapter_title: str) -> ChapterSummary:
        """Generate a structured summary for a course chapter."""

        agent = ChapterSummaryAgent(self.model, self.retriever, self.checkpointer)
        return agent.summarize(ChapterSummaryRequest(course_id=course_id, chapter_title=chapter_title))

    def generate_programming_quiz(
        self,
        course_id: str,
        chapter_title: str,
        programming_language: str,
        difficulty: str,
        question_types: list[str],
        question_count: int,
    ) -> Quiz:
        """Generate programming learning questions for a chapter."""

        request = QuizGenerationRequest(
            course_id=course_id,
            chapter_title=chapter_title,
            programming_language=programming_language,
            difficulty=difficulty,  # type: ignore[arg-type]
            question_types=question_types,  # type: ignore[arg-type]
            question_count=question_count,
        )
        agent = ProgrammingQuizGenerationAgent(self.model, self.retriever, self.checkpointer)
        return agent.generate(request)

    def evaluate_answers(self, quiz: Quiz | dict[str, Any], user_answers: list[UserAnswer | dict[str, Any]]) -> EvaluationReport:
        """Evaluate a quiz submission."""

        parsed_quiz = quiz if isinstance(quiz, Quiz) else Quiz.model_validate(quiz)
        parsed_answers = [
            answer if isinstance(answer, UserAnswer) else UserAnswer.model_validate(answer)
            for answer in user_answers
        ]
        agent = LearningEvaluatorAgent(self.model, self.checkpointer)
        return agent.evaluate(parsed_quiz, parsed_answers)

    def chat_with_tutor(
        self,
        user_message: str,
        course_id: str | None = None,
        thread_id: str | None = None,
    ) -> TutorChatResponse:
        """Chat with the programming tutor agent."""

        request = TutorChatRequest(user_message=user_message, course_id=course_id, thread_id=thread_id)
        agent = ProgrammingTutorAgent(self.model, self.retriever, self.checkpointer)
        return agent.chat(request)


