from __future__ import annotations

"""Unified service API for CLI, FastAPI, and future GUI/Web clients."""

from collections.abc import Iterator
from dataclasses import dataclass
from threading import RLock, Thread
from time import perf_counter
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
    SourceChunk,
    TutorChatRequest,
    TutorChatResponse,
    UserAnswer,
)


@dataclass(frozen=True)
class PDFAnswerStream:
    """Prepared streaming answer plus the source chunks already retrieved."""

    source_chunks: list[SourceChunk]
    text_stream: Iterator[str]


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
        self._init_lock = RLock()
        self._warm_up_lock = RLock()
        self._warm_up_thread: Thread | None = None
        self._warm_up_status: dict[str, Any] = {"state": "not_started"}

    @property
    def knowledge_base(self) -> DocumentKnowledgeBase:
        """Return the lazily initialized document knowledge base."""

        with self._init_lock:
            if self._knowledge_base is None:
                self._knowledge_base = DocumentKnowledgeBase()
            return self._knowledge_base

    @property
    def retriever(self) -> PDFRetriever:
        """Return the lazily initialized PDF retriever."""

        with self._init_lock:
            if self._retriever is None:
                self._retriever = PDFRetriever(self.knowledge_base)
            return self._retriever

    @property
    def model(self) -> Any:
        """Return the lazily initialized chat model."""

        with self._init_lock:
            if self._model is None:
                self._model = get_chat_model()
            return self._model

    @property
    def checkpointer(self) -> Any | None:
        """Return the lazily initialized memory checkpointer."""

        with self._init_lock:
            if self._checkpointer is None:
                self._checkpointer = create_memory_checkpointer()
            return self._checkpointer

    @property
    def warm_up_status(self) -> dict[str, Any]:
        """Return the latest warm-up status snapshot."""

        return dict(self._warm_up_status)

    def warm_up(self, include_model: bool = True) -> dict[str, Any]:
        """Eagerly initialize slow resources before the first user question."""

        with self._warm_up_lock:
            self._warm_up_status = {"state": "running"}
            timings: dict[str, float] = {}
            started_at = perf_counter()
            try:
                step_started = perf_counter()
                knowledge_base = self.knowledge_base
                timings["knowledge_base_seconds"] = perf_counter() - step_started

                if self.settings.embedding_provider.lower() == "huggingface":
                    step_started = perf_counter()
                    knowledge_base.embedding_model.embed_query("warmup")
                    timings["embedding_query_seconds"] = perf_counter() - step_started

                if include_model:
                    step_started = perf_counter()
                    _ = self.model
                    timings["chat_model_seconds"] = perf_counter() - step_started

                self._warm_up_status = {
                    "state": "ready",
                    "total_seconds": perf_counter() - started_at,
                    **timings,
                }
            except Exception as exc:
                self._warm_up_status = {
                    "state": "failed",
                    "error": str(exc),
                    "total_seconds": perf_counter() - started_at,
                    **timings,
                }
            return dict(self._warm_up_status)

    def warm_up_async(self, include_model: bool = True) -> None:
        """Start one background warm-up thread if no warm-up is running."""

        with self._warm_up_lock:
            if self._warm_up_thread is not None and self._warm_up_thread.is_alive():
                return
            if self._warm_up_status.get("state") == "ready":
                return
            self._warm_up_status = {"state": "running"}
            self._warm_up_thread = Thread(
                target=self.warm_up,
                kwargs={"include_model": include_model},
                daemon=True,
            )
            self._warm_up_thread.start()

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
        agent = PDFReadingAgent(self.model, self.retriever)
        return agent.answer(request)

    def stream_pdf_answer(
        self,
        course_id: str,
        question: str,
        chapter_title: str | None = None,
    ) -> PDFAnswerStream:
        """Prepare a streaming PDF answer for Web clients."""

        request = PDFQueryRequest(
            course_id=course_id,
            question=question,
            chapter_title=chapter_title,
            top_k=self.settings.top_k,
        )
        agent = PDFReadingAgent(self.model, self.retriever)
        source_chunks, text_stream = agent.stream_answer(request)
        return PDFAnswerStream(source_chunks=source_chunks, text_stream=text_stream)

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


