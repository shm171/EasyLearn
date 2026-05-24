from __future__ import annotations

"""Unified service API for CLI, FastAPI, and future GUI/Web clients."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import logging
from threading import RLock, Thread
from time import perf_counter
from typing import Any

from ai_core.agents.range_agent import RangeLearningAgent
from ai_core.agents.evaluator_agent import LearningEvaluatorAgent
from ai_core.agents.quiz_agent import ProgrammingQuizGenerationAgent
from ai_core.agents.reading_agent import PDFReadingAgent
from ai_core.agents.summary_agent import ChapterSummaryAgent
from ai_core.agents.tutor_agent import ProgrammingTutorAgent
from ai_core.config import get_settings, reset_settings_cache
from ai_core.materials_registry import MaterialsRegistry
from ai_core.memory import create_memory_checkpointer
from ai_core.model_factory import get_chat_model, reset_model_caches
from ai_core.rag.pdf_loader import PDFLoaderManager
from ai_core.rag.range_retriever import NO_RANGE_CONTENT_MESSAGE, RangeRetriever
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


logger = logging.getLogger(__name__)
ProgressCallback = Callable[[float, str], None]


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
        self._range_retriever: RangeRetriever | None = None
        self._materials_registry: MaterialsRegistry | None = None
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
    def range_retriever(self) -> RangeRetriever:
        """Return the lazily initialized page-range retriever."""

        with self._init_lock:
            if self._range_retriever is None:
                self._range_retriever = RangeRetriever(self.knowledge_base)
            return self._range_retriever

    @property
    def materials_registry(self) -> MaterialsRegistry:
        """Return the lazily initialized imported-materials registry."""

        with self._init_lock:
            if self._materials_registry is None:
                self._materials_registry = MaterialsRegistry()
            return self._materials_registry

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

    def reload_model_config(self) -> dict[str, Any]:
        """Reload local environment settings and clear cached chat models."""

        with self._init_lock:
            reset_settings_cache()
            reset_model_caches()
            self.settings = get_settings()
            self._model = None
            self._warm_up_status = {"state": "not_started"}
            return {
                "ai_provider": self.settings.ai_provider,
                "deepseek_model": self.settings.deepseek_model,
                "deepseek_api_key_set": bool(self.settings.deepseek_api_key),
            }

    def ingest_pdf(self, course_id: str, file_path: str, chapter_title: str | None = None) -> PDFIngestResult:
        """Read, chunk, and store a PDF in the local vector database."""

        documents = self.pdf_loader.load_pdf(file_path=file_path, course_id=course_id, chapter_title=chapter_title)
        chunks = self.text_splitter.split_documents(documents)
        self.knowledge_base.add_documents(chunks)
        first_meta = documents[0].metadata
        result = PDFIngestResult(
            course_id=course_id,
            file_path=file_path,
            file_name=str(first_meta.get("file_name", "")),
            chapter_title=chapter_title,
            page_count=len(documents),
            chunk_count=len(chunks),
            message="PDF imported successfully.",
        )
        try:
            self.materials_registry.register_pdf(
                course_id=course_id,
                file_path=file_path,
                chapter_title=chapter_title,
                page_count=result.page_count,
            )
        except Exception as exc:
            logger.warning("PDF imported but was not registered for the reader: %s", exc)
        return result

    def ask_pdf(self, course_id: str, question: str, chapter_title: str | None = None) -> PDFQueryResult:
        """Ask a question over imported PDF materials."""

        request = PDFQueryRequest(
            course_id=course_id,
            question=question,
            chapter_title=chapter_title,
            top_k=_fast_top_k(self.settings.top_k),
        )
        agent = PDFReadingAgent(self.model, self.retriever)
        return agent.answer(request)

    def stream_pdf_answer(
        self,
        course_id: str,
        question: str,
        chapter_title: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> PDFAnswerStream:
        """Prepare a streaming PDF answer for Web clients."""

        _report_progress(progress_callback, 0.08, "初始化检索器")
        retriever = self.retriever
        _report_progress(progress_callback, 0.18, "初始化模型")
        model = self.model
        request = PDFQueryRequest(
            course_id=course_id,
            question=question,
            chapter_title=chapter_title,
            top_k=_fast_top_k(self.settings.top_k),
        )
        _report_progress(progress_callback, 0.30, "检索资料")
        agent = PDFReadingAgent(model, retriever)
        source_chunks, text_stream = agent.stream_answer(request)
        _report_progress(progress_callback, 0.55, "开始生成回答")
        return PDFAnswerStream(source_chunks=source_chunks, text_stream=text_stream)

    def summarize_chapter(
        self,
        course_id: str,
        chapter_title: str,
        progress_callback: ProgressCallback | None = None,
    ) -> ChapterSummary:
        """Generate a structured summary for a course chapter."""

        _report_progress(progress_callback, 0.06, "初始化模型和检索器")
        agent = ChapterSummaryAgent(self.model, self.retriever)
        return agent.summarize(
            ChapterSummaryRequest(course_id=course_id, chapter_title=chapter_title),
            progress_callback=progress_callback,
        )

    def generate_programming_quiz(
        self,
        course_id: str,
        chapter_title: str,
        programming_language: str,
        difficulty: str,
        question_types: list[str],
        question_count: int,
        progress_callback: ProgressCallback | None = None,
    ) -> Quiz:
        """Generate programming learning questions for a chapter."""

        _report_progress(progress_callback, 0.05, "初始化模型和检索器")
        model = self.model
        retriever = self.retriever
        request = QuizGenerationRequest(
            course_id=course_id,
            chapter_title=chapter_title,
            programming_language=programming_language,
            difficulty=difficulty,  # type: ignore[arg-type]
            question_types=question_types,  # type: ignore[arg-type]
            question_count=question_count,
        )
        agent = ProgrammingQuizGenerationAgent(model, retriever)
        return agent.generate(request, progress_callback=progress_callback)

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

    def list_materials(self) -> list[dict[str, Any]]:
        """List imported PDF materials."""

        return self.materials_registry.list_materials()

    def get_material(self, course_id: str) -> dict[str, Any]:
        """Get PDF material metadata by course_id."""

        return self.materials_registry.get_material(course_id)

    def ask_pdf_in_range(
        self,
        course_id: str,
        question: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None = None,
    ) -> dict[str, Any]:
        """Ask AI using only chunks from a page range."""

        _validate_page_range_values(page_start, page_end)
        chunks = self.range_retriever.search_in_range(
            course_id=course_id,
            query=question,
            page_start=page_start,
            page_end=page_end,
            chapter_title=chapter_title,
            top_k=_fast_top_k(self.settings.top_k),
        )
        warnings = list(self.range_retriever.warnings)
        if chunks:
            context = _format_source_chunks(chunks, _context_limit(self.settings.rag_context_max_chars, 3600))
        else:
            context = self.range_retriever.build_context_from_range(
                course_id=course_id,
                page_start=page_start,
                page_end=page_end,
                chapter_title=chapter_title,
                max_chars=_context_limit(self.settings.rag_context_max_chars, 2600),
            )
            warnings.extend(_new_warnings(warnings, self.range_retriever.warnings))
            chunks = self.range_retriever.get_chunks_by_page_range(
                course_id=course_id,
                page_start=page_start,
                page_end=page_end,
                chapter_title=chapter_title,
                limit=_fast_top_k(self.settings.top_k),
            )
            warnings.extend(_new_warnings(warnings, self.range_retriever.warnings))

        if context == NO_RANGE_CONTENT_MESSAGE:
            answer = "当前页码范围内未找到明确依据。"
        else:
            answer = RangeLearningAgent(self.model).answer_range(
                course_id=course_id,
                question=question,
                page_start=page_start,
                page_end=page_end,
                context=context,
            )
        return {
            "answer": answer,
            "source_chunks": _dump_chunks(chunks),
            "page_range": {"page_start": page_start, "page_end": page_end},
            "warnings": warnings,
        }

    def summarize_range(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None = None,
    ) -> dict[str, Any]:
        """Summarize a specified page range."""

        _validate_page_range_values(page_start, page_end)
        chunks = self.range_retriever.search_in_range(
            course_id=course_id,
            query="核心概念 语法 示例 易错点 复习总结",
            page_start=page_start,
            page_end=page_end,
            chapter_title=chapter_title,
            top_k=_summary_top_k(self.settings.top_k),
        )
        warnings = list(self.range_retriever.warnings)
        if not chunks:
            chunks = self.range_retriever.get_chunks_by_page_range(
                course_id, page_start, page_end, chapter_title, limit=_summary_top_k(self.settings.top_k)
            )
            warnings.extend(_new_warnings(warnings, self.range_retriever.warnings))
        context = _format_source_chunks(chunks, _context_limit(self.settings.rag_context_max_chars, 4200))
        if not context:
            summary = "当前页码范围内未找到明确依据。"
        else:
            summary = RangeLearningAgent(self.model).summarize_range(course_id, page_start, page_end, context)
        return {
            "summary": summary,
            "source_chunks": _dump_chunks(chunks),
            "page_range": {"page_start": page_start, "page_end": page_end},
            "warnings": warnings,
        }

    def generate_quiz_from_range(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        programming_language: str,
        difficulty: str,
        question_types: list[str],
        question_count: int,
        chapter_title: str | None = None,
    ) -> dict[str, Any]:
        """Generate programming quiz from a page range."""

        _validate_page_range_values(page_start, page_end)
        chunks = self.range_retriever.search_in_range(
            course_id=course_id,
            query=f"{programming_language} syntax examples practice questions exercises",
            page_start=page_start,
            page_end=page_end,
            chapter_title=chapter_title,
            top_k=_quiz_range_top_k(question_count),
        )
        warnings = list(self.range_retriever.warnings)
        if not chunks:
            chunks = self.range_retriever.get_chunks_by_page_range(
                course_id, page_start, page_end, chapter_title, limit=_quiz_range_top_k(question_count)
            )
            warnings.extend(_new_warnings(warnings, self.range_retriever.warnings))
        context = _format_source_chunks(chunks, _quiz_context_limit(self.settings.rag_context_max_chars, question_count))
        if not context:
            quiz_text = '{"message":"当前页码范围内未找到明确依据。","questions":[]}'
        else:
            quiz_text = RangeLearningAgent(self.model).quiz_range(
                course_id=course_id,
                page_start=page_start,
                page_end=page_end,
                context=context,
                programming_language=programming_language,
                difficulty=difficulty,
                question_types=question_types,
                question_count=question_count,
            )
        return {
            "answer": quiz_text,
            "source_chunks": _dump_chunks(chunks),
            "page_range": {"page_start": page_start, "page_end": page_end},
            "warnings": warnings,
        }

    def ask_current_page(
        self,
        course_id: str,
        question: str,
        page_number: int,
        chapter_title: str | None = None,
    ) -> dict[str, Any]:
        """Ask AI using current page as primary context."""

        _validate_page_range_values(page_number, page_number)
        chunks = self.range_retriever.get_chunks_by_page_range(
            course_id=course_id,
            page_start=page_number,
            page_end=page_number,
            chapter_title=chapter_title,
            limit=3,
        )
        warnings = list(self.range_retriever.warnings)
        context = _format_source_chunks(chunks, max(1000, min(self.settings.rag_context_max_chars, 2200)))
        if not context:
            answer = "当前页码范围内未找到明确依据。"
        else:
            answer = RangeLearningAgent(self.model).answer_range(
                course_id=course_id,
                question=question,
                page_start=page_number,
                page_end=page_number,
                context=context,
            )
        return {
            "answer": answer,
            "source_chunks": _dump_chunks(chunks),
            "page_range": {"page_start": page_number, "page_end": page_number},
            "page_number": page_number,
            "warnings": warnings,
        }

    def explain_selected_text(
        self,
        course_id: str,
        selected_text: str,
        page_number: int | None = None,
        chapter_title: str | None = None,
        action: str = "explain",
        question: str | None = None,
    ) -> dict[str, Any]:
        """Explain, summarize, or analyze selected text."""

        page_context, chunks, warnings = self._selection_page_context(
            course_id,
            page_number,
            chapter_title,
            include_context=action == "ask" or len(selected_text.strip()) < 30,
        )
        answer = RangeLearningAgent(self.model).selection_action(
            selected_text=selected_text,
            action=action,
            page_context=page_context,
            question=question,
        )
        return {
            "answer": answer,
            "source_chunks": _dump_chunks(chunks),
            "page_number": page_number,
            "selected_text": selected_text,
            "warnings": warnings,
        }

    def explain_code_selection(
        self,
        course_id: str,
        selected_text: str,
        page_number: int | None = None,
        programming_language: str = "python",
        chapter_title: str | None = None,
    ) -> dict[str, Any]:
        """Explain selected code with optional page context."""

        page_context, chunks, warnings = self._selection_page_context(
            course_id,
            page_number,
            chapter_title,
            include_context=len(selected_text.strip()) < 30,
        )
        answer = RangeLearningAgent(self.model).explain_code(
            selected_text=selected_text,
            programming_language=programming_language,
            page_context=page_context,
        )
        return {
            "answer": answer,
            "source_chunks": _dump_chunks(chunks),
            "page_number": page_number,
            "selected_text": selected_text,
            "warnings": warnings,
        }

    def get_key_points_from_range(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None = None,
    ) -> dict[str, Any]:
        """Extract key points from a specified page range."""

        _validate_page_range_values(page_start, page_end)
        chunks = self.range_retriever.search_in_range(
            course_id=course_id,
            query="关键概念 语法 示例 易错点",
            page_start=page_start,
            page_end=page_end,
            chapter_title=chapter_title,
            top_k=_summary_top_k(self.settings.top_k),
        )
        warnings = list(self.range_retriever.warnings)
        if not chunks:
            chunks = self.range_retriever.get_chunks_by_page_range(
                course_id, page_start, page_end, chapter_title, limit=_summary_top_k(self.settings.top_k)
            )
            warnings.extend(_new_warnings(warnings, self.range_retriever.warnings))
        context = _format_source_chunks(chunks, _context_limit(self.settings.rag_context_max_chars, 3600))
        if not context:
            answer = "当前页码范围内未找到明确依据。"
        else:
            answer = RangeLearningAgent(self.model).key_points_range(course_id, page_start, page_end, context)
        return {
            "answer": answer,
            "source_chunks": _dump_chunks(chunks),
            "page_range": {"page_start": page_start, "page_end": page_end},
            "warnings": warnings,
        }

    def _selection_page_context(
        self,
        course_id: str,
        page_number: int | None,
        chapter_title: str | None,
        include_context: bool = True,
    ) -> tuple[str, list[SourceChunk], list[str]]:
        if page_number is None or not include_context:
            return "", [], []
        chunks = self.range_retriever.get_chunks_by_page_range(
            course_id=course_id,
            page_start=page_number,
            page_end=page_number,
            chapter_title=chapter_title,
            limit=3,
        )
        return (
            _format_source_chunks(chunks, max(900, min(self.settings.rag_context_max_chars, 1800))),
            chunks,
            list(self.range_retriever.warnings),
        )


def _dump_chunks(chunks: list[SourceChunk]) -> list[dict[str, Any]]:
    return [chunk.model_dump() for chunk in chunks]


def _validate_page_range_values(page_start: int, page_end: int) -> None:
    if page_start < 1 or page_end < 1:
        raise ValueError("page_start and page_end must be greater than or equal to 1.")
    if page_start > page_end:
        raise ValueError("page_start cannot be greater than page_end.")


def _format_source_chunks(chunks: list[SourceChunk], max_chars: int) -> str:
    sections: list[str] = []
    used_chars = 0
    for chunk in chunks:
        header = f"[{chunk.chunk_id} | page {chunk.page_number}]"
        section = f"{header}\n{chunk.content.strip()}"
        remaining = max_chars - used_chars
        if remaining <= 0:
            break
        if len(section) > remaining:
            section = section[: max(0, remaining - 4)].rstrip() + "\n..."
        sections.append(section)
        used_chars += len(section) + 2
    return "\n\n".join(sections)


def _fast_top_k(configured_top_k: int) -> int:
    return max(2, min(configured_top_k, 4))


def _summary_top_k(configured_top_k: int) -> int:
    return max(4, min(max(configured_top_k, 6), 8))


def _quiz_range_top_k(question_count: int) -> int:
    return max(4, min(question_count + 1, 8))


def _context_limit(configured_limit: int, hard_limit: int) -> int:
    return max(1200, min(configured_limit, hard_limit))


def _quiz_context_limit(configured_limit: int, question_count: int) -> int:
    desired = max(2400, min(4800, 2200 + question_count * 350))
    return _context_limit(configured_limit, desired)


def _new_warnings(existing: list[str], candidates: list[str]) -> list[str]:
    return [warning for warning in candidates if warning not in existing]


def _report_progress(progress_callback: ProgressCallback | None, value: float, message: str) -> None:
    if progress_callback is not None:
        progress_callback(value, message)


