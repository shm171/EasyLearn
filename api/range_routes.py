from __future__ import annotations

"""FastAPI routes for page-range PDF AI actions."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ai_core.schemas import RangeAskRequest, RangeQuizRequest, RangeSummaryRequest
from ai_core.service import LearningAIService
from api.dependencies import get_learning_service


router = APIRouter(prefix="/range", tags=["page range"])


@router.post("/ask")
def ask_range(
    request: RangeAskRequest,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Ask a question using only a specified PDF page range."""

    try:
        return service.ask_pdf_in_range(
            course_id=request.course_id,
            question=request.question,
            page_start=request.page_start,
            page_end=request.page_end,
            chapter_title=request.chapter_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/summary")
def summarize_range(
    request: RangeSummaryRequest,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Summarize a specified PDF page range."""

    try:
        return service.summarize_range(
            course_id=request.course_id,
            page_start=request.page_start,
            page_end=request.page_end,
            chapter_title=request.chapter_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/quiz")
def generate_quiz_from_range(
    request: RangeQuizRequest,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Generate programming quiz questions from a specified page range."""

    try:
        return service.generate_quiz_from_range(
            course_id=request.course_id,
            page_start=request.page_start,
            page_end=request.page_end,
            programming_language=request.programming_language,
            difficulty=request.difficulty,
            question_types=list(request.question_types),
            question_count=request.question_count,
            chapter_title=request.chapter_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/key-points")
def key_points_from_range(
    request: RangeSummaryRequest,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Extract key points from a specified PDF page range."""

    try:
        return service.get_key_points_from_range(
            course_id=request.course_id,
            page_start=request.page_start,
            page_end=request.page_end,
            chapter_title=request.chapter_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
