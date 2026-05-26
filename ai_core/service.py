from __future__ import annotations

"""Unified service API for CLI, FastAPI, and future GUI/Web clients."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
import logging
from pathlib import Path
from threading import RLock, Thread
from time import perf_counter, sleep, time
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
from ai_core.rag.markdown_loader import MarkdownLoaderManager
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


@dataclass(frozen=True)
class MarkdownPageCacheEntry:
    """Cached virtual pages for one Markdown material version."""

    signature: tuple[str, int, int]
    material: dict[str, Any]
    documents: list[Any]
    created_at: float
    last_used: float


@dataclass(frozen=True)
class RangeContextCacheEntry:
    """Short-lived range context memory for repeated AI actions."""

    context: str
    chunks: list[SourceChunk]
    warnings: list[str]
    created_at: float
    last_used: float


class LearningAIService:
    """Facade for the programming learning AI core."""

    def __init__(self) -> None:
        """Create the service with lazy model and vector-store initialization."""

        self.settings = get_settings()
        self.pdf_loader = PDFLoaderManager()
        self.markdown_loader = MarkdownLoaderManager()
        self.text_splitter = PDFTextSplitter()
        self._knowledge_base: DocumentKnowledgeBase | None = None
        self._retriever: PDFRetriever | None = None
        self._range_retriever: RangeRetriever | None = None
        self._materials_registry: MaterialsRegistry | None = None
        self._model: Any | None = None
        self._checkpointer: Any | None = None
        self._markdown_pages_cache: dict[str, MarkdownPageCacheEntry] = {}
        self._range_context_cache: dict[tuple[str, str, int, int], RangeContextCacheEntry] = {}
        self._index_jobs: dict[str, dict[str, Any]] = {}
        self._index_lock = RLock()
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

    def import_reader_material(
        self,
        course_id: str,
        file_path: str,
        file_type: str,
        chapter_title: str | None = None,
    ) -> tuple[dict[str, Any], PDFIngestResult, dict[str, Any]]:
        """Register a material for reading now and build its AI index in the background."""

        if file_type == "pdf":
            page_count = self.pdf_loader.get_page_count(file_path)
            material = self.materials_registry.register_pdf(
                course_id=course_id,
                file_path=file_path,
                chapter_title=chapter_title,
                page_count=page_count,
            )
            documents: list[Any] | None = None
            file_name = Path(file_path).name
        else:
            documents = self._load_material_documents(course_id, file_path, file_type, chapter_title)
            first_meta = documents[0].metadata
            page_count = len(documents)
            material = self.materials_registry.register_markdown(
                course_id=course_id,
                file_path=file_path,
                chapter_title=chapter_title,
                page_count=page_count,
            )
            self._remember_markdown_documents(course_id, material, documents)
            file_name = str(first_meta.get("file_name", ""))

        material = self.materials_registry.update_index_status(course_id, "queued", chunk_count=0)
        self._set_index_job(
            course_id,
            status="queued",
            progress=0.18,
            message="Reader is ready. AI index will build when needed.",
            chunk_count=0,
        )
        result = PDFIngestResult(
            course_id=course_id,
            file_path=file_path,
            file_name=file_name,
            file_type="markdown" if file_type == "markdown" else "pdf",
            chapter_title=chapter_title,
            page_count=page_count,
            chunk_count=0,
            message="Material opened. AI index is queued.",
        )
        return material, result, self.get_material_index_status(course_id)

    def get_material_index_status(self, course_id: str) -> dict[str, Any]:
        """Return the current background indexing status for one imported material."""

        material = self.get_material(course_id)
        with self._index_lock:
            job = dict(self._index_jobs.get(course_id, {}))
        status = job.get("status") or material.get("index_status") or "ready"
        progress = float(job.get("progress") if "progress" in job else (1.0 if status == "ready" else 0.0))
        return {
            "course_id": course_id,
            "status": status,
            "progress": max(0.0, min(1.0, progress)),
            "message": job.get("message") or _index_status_message(status),
            "chunk_count": job.get("chunk_count", material.get("indexed_chunk_count") or 0),
            "error": job.get("error") or material.get("index_error") or "",
        }

    def close_material(self, course_id: str, delete_file: bool = True) -> dict[str, Any]:
        """Close an imported material and remove its local reader/index data."""

        material = self.materials_registry.unregister_material(course_id, delete_file=delete_file)
        with self._index_lock:
            self._index_jobs.pop(course_id, None)
        with self._init_lock:
            self._markdown_pages_cache.pop(course_id, None)
            self._range_context_cache = {
                key: value for key, value in self._range_context_cache.items() if key[0] != course_id
            }
            knowledge_base = self._knowledge_base
        if knowledge_base is not None:
            Thread(target=self._delete_course_chunks, args=(course_id, knowledge_base), daemon=True).start()
        return {
            "message": "Material closed.",
            "material": material,
            "deleted_chunks": 0,
        }

    def ensure_material_indexed(self, course_id: str) -> None:
        """Build a queued material index synchronously before an AI retrieval needs it."""

        try:
            material = self.get_material(course_id)
        except KeyError:
            return
        if material.get("index_status") == "ready":
            return
        file_type = str(material.get("file_type") or "pdf")
        file_path = str(self.materials_registry.resolve_material_path(course_id, expected_type=file_type))
        chapter_title = material.get("chapter_title") or None
        self._set_index_job(
            course_id,
            status="indexing",
            progress=0.34,
            message="Building the AI index for this material.",
            chunk_count=0,
        )
        self.materials_registry.update_index_status(course_id, "indexing", chunk_count=0)
        try:
            documents = self._load_material_documents(course_id, file_path, file_type, chapter_title)
            self._index_material_documents(course_id, file_path, file_type, chapter_title, documents)
        except Exception as exc:
            self.materials_registry.update_index_status(course_id, "failed", error=str(exc))
            self._set_index_job(
                course_id,
                status="failed",
                progress=1.0,
                message="AI index failed.",
                error=str(exc),
            )
            raise

    def ingest_pdf(self, course_id: str, file_path: str, chapter_title: str | None = None) -> PDFIngestResult:
        """Read, chunk, and store a PDF in the local vector database."""

        documents = self.pdf_loader.load_pdf(file_path=file_path, course_id=course_id, chapter_title=chapter_title)
        chunks = self.text_splitter.split_documents(documents)
        self.knowledge_base.delete_course(course_id)
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
            self.materials_registry.update_index_status(course_id, "ready", chunk_count=result.chunk_count)
        except Exception as exc:
            logger.warning("PDF imported but was not registered for the reader: %s", exc)
        return result

    def ingest_markdown(self, course_id: str, file_path: str, chapter_title: str | None = None) -> PDFIngestResult:
        """Read, chunk, and store a Markdown file in the local vector database."""

        documents = self.markdown_loader.load_markdown(file_path=file_path, course_id=course_id, chapter_title=chapter_title)
        chunks = self.text_splitter.split_documents(documents)
        self.knowledge_base.delete_course(course_id)
        self.knowledge_base.add_documents(chunks)
        first_meta = documents[0].metadata
        result = PDFIngestResult(
            course_id=course_id,
            file_path=file_path,
            file_name=str(first_meta.get("file_name", "")),
            file_type="markdown",
            chapter_title=chapter_title,
            page_count=len(documents),
            chunk_count=len(chunks),
            message="Markdown imported successfully.",
        )
        try:
            self.materials_registry.register_markdown(
                course_id=course_id,
                file_path=file_path,
                chapter_title=chapter_title,
                page_count=result.page_count,
            )
            self.materials_registry.update_index_status(course_id, "ready", chunk_count=result.chunk_count)
        except Exception as exc:
            logger.warning("Markdown imported but was not registered for the reader: %s", exc)
        return result

    def _load_material_documents(
        self,
        course_id: str,
        file_path: str,
        file_type: str,
        chapter_title: str | None,
    ) -> list[Any]:
        normalized_type = file_type.strip().lower()
        if normalized_type == "pdf":
            return self.pdf_loader.load_pdf(file_path=file_path, course_id=course_id, chapter_title=chapter_title)
        if normalized_type == "markdown":
            return self.markdown_loader.load_markdown(
                file_path=file_path,
                course_id=course_id,
                chapter_title=chapter_title,
            )
        raise ValueError(f"Unsupported material file_type: {file_type}")

    def _index_material_documents(
        self,
        course_id: str,
        file_path: str,
        file_type: str,
        chapter_title: str | None,
        documents: list[Any] | None,
    ) -> None:
        try:
            if documents is None:
                self._set_index_job(course_id, status="indexing", progress=0.42, message="Extracting PDF text.")
                documents = self._load_material_documents(course_id, file_path, file_type, chapter_title)
            self._set_index_job(course_id, status="indexing", progress=0.48, message="Splitting material text.")
            chunks = self.text_splitter.split_documents(documents)
            self._set_index_job(
                course_id,
                status="indexing",
                progress=0.66,
                message=f"Writing {len(chunks)} chunks to the AI index.",
                chunk_count=len(chunks),
            )
            if not self._material_exists(course_id):
                return
            self.knowledge_base.delete_course(course_id)
            self.knowledge_base.add_documents(chunks)
            if not self._material_exists(course_id):
                self.knowledge_base.delete_course(course_id)
                with self._index_lock:
                    self._index_jobs.pop(course_id, None)
                return
            self.materials_registry.update_index_status(course_id, "ready", chunk_count=len(chunks))
            if file_type == "markdown":
                try:
                    material = self.get_material(course_id)
                    self._remember_markdown_documents(course_id, material, documents)
                except Exception:
                    logger.debug("Markdown cache refresh failed after indexing %s", course_id, exc_info=True)
            self._set_index_job(
                course_id,
                status="ready",
                progress=1.0,
                message="AI index is ready.",
                chunk_count=len(chunks),
            )
        except Exception as exc:
            logger.warning("Failed to index material %s from %s: %s", course_id, file_path, exc)
            try:
                self.materials_registry.update_index_status(course_id, "failed", error=str(exc))
            except Exception:
                logger.debug("Failed to persist index failure for %s", course_id, exc_info=True)
            self._set_index_job(
                course_id,
                status="failed",
                progress=1.0,
                message="AI index failed.",
                error=str(exc),
            )

    def _start_index_thread(
        self,
        course_id: str,
        file_path: str,
        file_type: str,
        chapter_title: str | None,
        documents: list[Any] | None,
        delay_seconds: float = 1.25,
    ) -> None:
        def run_index() -> None:
            if delay_seconds > 0:
                sleep(delay_seconds)
            if self._material_exists(course_id):
                self._index_material_documents(course_id, file_path, file_type, chapter_title, documents)

        Thread(target=run_index, daemon=True).start()

    def _delete_course_chunks(self, course_id: str, knowledge_base: DocumentKnowledgeBase) -> None:
        try:
            knowledge_base.delete_course(course_id)
        except Exception:
            logger.debug("Failed to delete stale chunks for %s", course_id, exc_info=True)

    def _set_index_job(self, course_id: str, **updates: Any) -> None:
        with self._index_lock:
            current = dict(self._index_jobs.get(course_id, {}))
            current.update(updates)
            current["updated_at"] = time()
            if "started_at" not in current:
                current["started_at"] = current["updated_at"]
            self._index_jobs[course_id] = current

    def _material_exists(self, course_id: str) -> bool:
        try:
            self.get_material(course_id)
            return True
        except KeyError:
            with self._index_lock:
                self._index_jobs.pop(course_id, None)
            return False

    def _remember_markdown_documents(self, course_id: str, material: dict[str, Any], documents: list[Any]) -> None:
        try:
            signature = _file_signature(self.materials_registry.resolve_markdown_path(course_id))
        except Exception:
            return
        now = time()
        with self._init_lock:
            self._markdown_pages_cache[course_id] = MarkdownPageCacheEntry(
                signature=signature,
                material=material,
                documents=documents,
                created_at=now,
                last_used=now,
            )

    def ask_pdf(self, course_id: str, question: str, chapter_title: str | None = None) -> PDFQueryResult:
        """Ask a question over imported PDF materials."""

        self.ensure_material_indexed(course_id)
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
        self.ensure_material_indexed(course_id)
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
        self.ensure_material_indexed(course_id)
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
        self.ensure_material_indexed(course_id)
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

        if course_id:
            self.ensure_material_indexed(course_id)
        request = TutorChatRequest(user_message=user_message, course_id=course_id, thread_id=thread_id)
        agent = ProgrammingTutorAgent(self.model, self.retriever, self.checkpointer)
        return agent.chat(request)

    def list_materials(self) -> list[dict[str, Any]]:
        """List imported reader materials."""

        return self.materials_registry.list_materials()

    def get_material(self, course_id: str) -> dict[str, Any]:
        """Get material metadata by course_id."""

        return self.materials_registry.get_material(course_id)

    def get_markdown_pages(self, course_id: str) -> dict[str, Any]:
        """Return virtual Markdown pages for the reader UI."""

        material, documents = self._get_markdown_documents_cached(course_id)
        pages = [
            {
                "page_number": document.metadata.get("page_number"),
                "title": document.metadata.get("page_title") or f"第 {index} 页",
                "preview": _markdown_preview(document.page_content),
                "content": document.page_content,
            }
            for index, document in enumerate(documents, start=1)
        ]
        return {
            "material": {**material, "page_count": len(pages), "file_type": "markdown"},
            "page_count": len(pages),
            "pages": pages,
        }

    def get_markdown_index(self, course_id: str) -> dict[str, Any]:
        """Return lightweight Markdown page metadata for fast reader startup."""

        material, documents = self._get_markdown_documents_cached(course_id)
        pages = [
            {
                "page_number": document.metadata.get("page_number"),
                "title": document.metadata.get("page_title") or f"第 {index} 页",
                "preview": _markdown_preview(document.page_content),
                "char_count": len(document.page_content),
            }
            for index, document in enumerate(documents, start=1)
        ]
        return {
            "material": {**material, "page_count": len(pages), "file_type": "markdown"},
            "page_count": len(pages),
            "pages": pages,
        }

    def get_markdown_page(self, course_id: str, page_number: int) -> dict[str, Any]:
        """Return one virtual Markdown page by 1-based page number."""

        if page_number < 1:
            raise ValueError("page_number must be greater than or equal to 1.")
        material, documents = self._get_markdown_documents_cached(course_id)
        if page_number > len(documents):
            raise ValueError(f"Markdown page {page_number} is outside 1-{len(documents)}.")
        document = documents[page_number - 1]
        return {
            "material": {**material, "page_count": len(documents), "file_type": "markdown"},
            "page_count": len(documents),
            "page": {
                "page_number": document.metadata.get("page_number") or page_number,
                "title": document.metadata.get("page_title") or f"第 {page_number} 页",
                "preview": _markdown_preview(document.page_content),
                "content": document.page_content,
                "char_count": len(document.page_content),
            },
        }

    def update_markdown_page(self, course_id: str, page_number: int, content: str) -> dict[str, Any]:
        """Replace one virtual Markdown page, save the file, and rebuild the AI index in the background."""

        if page_number < 1:
            raise ValueError("page_number must be greater than or equal to 1.")
        material, documents = self._get_markdown_documents_cached(course_id)
        if material.get("file_type") != "markdown":
            raise ValueError("Only Markdown materials can be edited.")
        if page_number > len(documents):
            raise ValueError(f"Markdown page {page_number} is outside 1-{len(documents)}.")

        next_contents = [document.page_content for document in documents]
        next_contents[page_number - 1] = content.replace("\r\n", "\n").replace("\r", "\n")
        markdown_path = self.materials_registry.resolve_markdown_path(course_id)
        markdown_path.write_text("\n\n".join(next_contents).rstrip() + "\n", encoding="utf-8")

        refreshed_documents = self.markdown_loader.load_markdown(
            file_path=str(markdown_path),
            course_id=course_id,
            chapter_title=material.get("chapter_title") or None,
        )
        refreshed_material = self.materials_registry.register_markdown(
            course_id=course_id,
            file_path=str(markdown_path),
            chapter_title=material.get("chapter_title") or None,
            page_count=len(refreshed_documents),
        )
        refreshed_material = self.materials_registry.update_index_status(course_id, "queued", chunk_count=0)
        self._remember_markdown_documents(course_id, refreshed_material, refreshed_documents)
        self._set_index_job(
            course_id,
            status="queued",
            progress=0.42,
            message="Markdown saved. AI index will rebuild when needed.",
            chunk_count=0,
        )
        safe_page_number = min(page_number, len(refreshed_documents))
        document = refreshed_documents[safe_page_number - 1]
        return {
            "material": {**refreshed_material, "page_count": len(refreshed_documents), "file_type": "markdown"},
            "page_count": len(refreshed_documents),
            "page": {
                "page_number": document.metadata.get("page_number") or safe_page_number,
                "title": document.metadata.get("page_title") or f"第 {safe_page_number} 页",
                "preview": _markdown_preview(document.page_content),
                "content": document.page_content,
                "char_count": len(document.page_content),
            },
            "index_status": self.get_material_index_status(course_id),
        }

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
        self.ensure_material_indexed(course_id)
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

        self._remember_range_context(course_id, page_start, page_end, chapter_title, context, chunks, warnings)
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
        self.ensure_material_indexed(course_id)
        cached_context = self._get_range_context_memory(course_id, page_start, page_end, chapter_title, min_chunks=4)
        if cached_context:
            context, chunks, warnings = cached_context
        else:
            if _page_span(page_start, page_end) <= 12:
                chunks = self.range_retriever.get_chunks_by_page_range(
                    course_id, page_start, page_end, chapter_title, limit=_summary_top_k(self.settings.top_k)
                )
            else:
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
            self._remember_range_context(course_id, page_start, page_end, chapter_title, context, chunks, warnings)
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
        self.ensure_material_indexed(course_id)
        cached_context = self._get_range_context_memory(
            course_id, page_start, page_end, chapter_title, min_chunks=min(_quiz_range_top_k(question_count), 4)
        )
        if cached_context:
            context, chunks, warnings = cached_context
        else:
            if _page_span(page_start, page_end) <= 10:
                chunks = self.range_retriever.get_chunks_by_page_range(
                    course_id, page_start, page_end, chapter_title, limit=_quiz_range_top_k(question_count)
                )
            else:
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
            self._remember_range_context(course_id, page_start, page_end, chapter_title, context, chunks, warnings)
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
        self.ensure_material_indexed(course_id)
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

        self.ensure_material_indexed(course_id)
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

        self.ensure_material_indexed(course_id)
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
        self.ensure_material_indexed(course_id)
        cached_context = self._get_range_context_memory(course_id, page_start, page_end, chapter_title, min_chunks=4)
        if cached_context:
            context, chunks, warnings = cached_context
        else:
            if _page_span(page_start, page_end) <= 12:
                chunks = self.range_retriever.get_chunks_by_page_range(
                    course_id, page_start, page_end, chapter_title, limit=_summary_top_k(self.settings.top_k)
                )
            else:
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
            self._remember_range_context(course_id, page_start, page_end, chapter_title, context, chunks, warnings)
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

    def _get_markdown_documents_cached(self, course_id: str) -> tuple[dict[str, Any], list[Any]]:
        material = self.get_material(course_id)
        markdown_path = self.materials_registry.resolve_markdown_path(course_id)
        signature = _file_signature(markdown_path)
        with self._init_lock:
            cached = self._markdown_pages_cache.get(course_id)
            if cached and cached.signature == signature:
                self._markdown_pages_cache[course_id] = MarkdownPageCacheEntry(
                    signature=cached.signature,
                    material=cached.material,
                    documents=cached.documents,
                    created_at=cached.created_at,
                    last_used=time(),
                )
                return dict(cached.material), cached.documents

        documents = self.markdown_loader.load_markdown(
            file_path=str(markdown_path),
            course_id=course_id,
            chapter_title=material.get("chapter_title") or None,
        )
        cached_material = {**material, "page_count": len(documents), "file_type": "markdown"}
        with self._init_lock:
            self._markdown_pages_cache[course_id] = MarkdownPageCacheEntry(
                signature=signature,
                material=cached_material,
                documents=documents,
                created_at=time(),
                last_used=time(),
            )
            self._prune_markdown_cache()
        return dict(cached_material), documents

    def _prune_markdown_cache(self, max_entries: int = 8, ttl_seconds: int = 900) -> None:
        now = time()
        expired = [
            key for key, entry in self._markdown_pages_cache.items() if now - entry.last_used > ttl_seconds
        ]
        for key in expired:
            self._markdown_pages_cache.pop(key, None)
        if len(self._markdown_pages_cache) <= max_entries:
            return
        by_last_used = sorted(self._markdown_pages_cache.items(), key=lambda item: item[1].last_used)
        for key, _entry in by_last_used[: max(0, len(self._markdown_pages_cache) - max_entries)]:
            self._markdown_pages_cache.pop(key, None)

    def _get_range_context_memory(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None,
        min_chunks: int,
        ttl_seconds: int = 600,
    ) -> tuple[str, list[SourceChunk], list[str]] | None:
        key = _range_context_key(course_id, page_start, page_end, chapter_title)
        now = time()
        with self._init_lock:
            entry = self._range_context_cache.get(key)
            if not entry:
                return None
            if now - entry.last_used > ttl_seconds or len(entry.chunks) < min_chunks:
                self._range_context_cache.pop(key, None)
                return None
            refreshed = RangeContextCacheEntry(
                context=entry.context,
                chunks=entry.chunks,
                warnings=entry.warnings,
                created_at=entry.created_at,
                last_used=now,
            )
            self._range_context_cache[key] = refreshed
            return refreshed.context, refreshed.chunks, list(refreshed.warnings)

    def _remember_range_context(
        self,
        course_id: str,
        page_start: int,
        page_end: int,
        chapter_title: str | None,
        context: str,
        chunks: list[SourceChunk],
        warnings: list[str],
    ) -> None:
        if not context or context == NO_RANGE_CONTENT_MESSAGE or not chunks:
            return
        key = _range_context_key(course_id, page_start, page_end, chapter_title)
        clipped_context = _clip_memory_context(context)
        now = time()
        with self._init_lock:
            self._range_context_cache[key] = RangeContextCacheEntry(
                context=clipped_context,
                chunks=chunks,
                warnings=list(warnings),
                created_at=now,
                last_used=now,
            )
            self._prune_range_context_cache()

    def _prune_range_context_cache(self, max_entries: int = 24, ttl_seconds: int = 600) -> None:
        now = time()
        expired = [
            key for key, entry in self._range_context_cache.items() if now - entry.last_used > ttl_seconds
        ]
        for key in expired:
            self._range_context_cache.pop(key, None)
        if len(self._range_context_cache) <= max_entries:
            return
        by_last_used = sorted(self._range_context_cache.items(), key=lambda item: item[1].last_used)
        for key, _entry in by_last_used[: max(0, len(self._range_context_cache) - max_entries)]:
            self._range_context_cache.pop(key, None)

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


def _page_span(page_start: int, page_end: int) -> int:
    return max(1, page_end - page_start + 1)


def _range_context_key(
    course_id: str,
    page_start: int,
    page_end: int,
    chapter_title: str | None,
) -> tuple[str, str, int, int]:
    return (course_id, chapter_title or "", page_start, page_end)


def _clip_memory_context(context: str, max_chars: int = 7000) -> str:
    if len(context) <= max_chars:
        return context
    return context[: max(0, max_chars - 4)].rstrip() + "\n..."


def _new_warnings(existing: list[str], candidates: list[str]) -> list[str]:
    return [warning for warning in candidates if warning not in existing]


def _report_progress(progress_callback: ProgressCallback | None, value: float, message: str) -> None:
    if progress_callback is not None:
        progress_callback(value, message)


def _file_signature(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _markdown_preview(text: str, max_chars: int = 160) -> str:
    compact = " ".join(
        text.replace("```", " ")
        .replace("#", " ")
        .replace("*", " ")
        .replace("`", " ")
        .split()
    )
    return compact[:max_chars]


def _index_status_message(status: str) -> str:
    if status == "queued":
        return "AI index is queued."
    if status == "indexing":
        return "AI index is building."
    if status == "failed":
        return "AI index failed."
    return "AI index is ready."


