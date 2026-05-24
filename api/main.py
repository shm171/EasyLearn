from __future__ import annotations

"""FastAPI entrypoint for the programming learning AI core."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.dependencies import get_learning_service
from api.reader_routes import router as reader_router
from api.range_routes import router as range_router
from ai_core.schemas import (
    ChapterSummary,
    ChapterSummaryRequest,
    EvaluationReport,
    PDFIngestRequest,
    PDFIngestResult,
    PDFQueryRequest,
    PDFQueryResult,
    Quiz,
    QuizGenerationRequest,
    TutorChatRequest,
    TutorChatResponse,
    UserAnswer,
)


app = FastAPI(title="AI Programming Learning Core", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(reader_router)
app.include_router(range_router)
service = get_learning_service()


class QuizEvaluationPayload(BaseModel):
    """Payload for evaluating a quiz submission."""

    quiz: Quiz
    user_answers: list[UserAnswer]


@app.post("/pdf/ingest", response_model=PDFIngestResult)
def ingest_pdf(request: PDFIngestRequest) -> PDFIngestResult:
    """Import a PDF into the vector database."""

    return service.ingest_pdf(
        course_id=request.course_id,
        file_path=request.file_path,
        chapter_title=request.chapter_title,
    )


@app.post("/pdf/ask", response_model=PDFQueryResult)
def ask_pdf(request: PDFQueryRequest) -> PDFQueryResult:
    """Ask a question over imported PDFs."""

    return service.ask_pdf(
        course_id=request.course_id,
        question=request.question,
        chapter_title=request.chapter_title,
    )


@app.post("/chapters/summary", response_model=ChapterSummary)
def summarize_chapter(request: ChapterSummaryRequest) -> ChapterSummary:
    """Generate a structured chapter summary."""

    return service.summarize_chapter(course_id=request.course_id, chapter_title=request.chapter_title)


@app.post("/quizzes/generate", response_model=Quiz)
def generate_quiz(request: QuizGenerationRequest) -> Quiz:
    """Generate a programming quiz."""

    return service.generate_programming_quiz(
        course_id=request.course_id,
        chapter_title=request.chapter_title,
        programming_language=request.programming_language,
        difficulty=request.difficulty,
        question_types=list(request.question_types),
        question_count=request.question_count,
    )


@app.post("/quizzes/evaluate", response_model=EvaluationReport)
def evaluate_quiz(payload: QuizEvaluationPayload) -> EvaluationReport:
    """Evaluate quiz answers."""

    return service.evaluate_answers(quiz=payload.quiz, user_answers=payload.user_answers)


@app.post("/tutor/chat", response_model=TutorChatResponse)
def chat_with_tutor(request: TutorChatRequest) -> TutorChatResponse:
    """Chat with the programming tutor."""

    return service.chat_with_tutor(
        user_message=request.user_message,
        course_id=request.course_id,
        thread_id=request.thread_id,
    )


