from __future__ import annotations

"""FastAPI routes for the local PDF reader UI."""

from pathlib import Path
import re
import shutil
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.responses import FileResponse

from ai_core.materials_registry import MaterialsRegistry
from ai_core.schemas import CodeSelectionExplainRequest, CurrentPageAskRequest, SelectionAskRequest
from ai_core.service import LearningAIService
from api.dependencies import get_learning_service


router = APIRouter(prefix="/reader", tags=["pdf reader"])


def _safe_slug(value: str, default: str = "pdf") -> str:
    slug = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value).strip("._-")
    return slug or default


@router.get("/materials")
def list_materials(service: LearningAIService = Depends(get_learning_service)) -> list[dict[str, Any]]:
    """List imported PDF materials."""

    return service.list_materials()


@router.get("/materials/{course_id}")
def get_material(
    course_id: str,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Return metadata for one imported PDF material."""

    try:
        return service.get_material(course_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/pdf/{course_id}")
def get_pdf(
    course_id: str,
    service: LearningAIService = Depends(get_learning_service),
) -> FileResponse:
    """Serve a registered PDF from the materials/ directory."""

    try:
        pdf_path = service.materials_registry.resolve_pdf_path(course_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(path=pdf_path, media_type="application/pdf", filename=pdf_path.name)


@router.post("/materials/import")
def import_local_pdf(
    course_id: str = Form(...),
    chapter_title: str | None = Form(default=None),
    file: UploadFile = File(...),
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Upload a local PDF, save it into materials/, ingest it, and register it."""

    if not course_id.strip():
        raise HTTPException(status_code=400, detail="course_id cannot be empty")
    original_name = Path(file.filename or "material.pdf").name
    if Path(original_name).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only .pdf files are supported.")

    registry = MaterialsRegistry()
    safe_course_id = _safe_slug(course_id.strip(), "course")
    safe_stem = _safe_slug(Path(original_name).stem, "material")
    target_path = registry.materials_dir / f"{safe_course_id}__{safe_stem}.pdf"
    counter = 1
    while target_path.exists():
        target_path = registry.materials_dir / f"{safe_course_id}__{safe_stem}_{counter}.pdf"
        counter += 1

    try:
        with target_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        ingest_result = service.ingest_pdf(
            course_id=course_id.strip(),
            file_path=str(target_path),
            chapter_title=chapter_title or None,
        )
        material = service.get_material(course_id.strip())
    except Exception as exc:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        file.file.close()

    return {
        "message": "PDF imported successfully.",
        "material": material,
        "ingest_result": ingest_result.model_dump(),
    }


@router.post("/current-page/ask")
def ask_current_page(
    request: CurrentPageAskRequest,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Ask AI using current page and nearby page context."""

    try:
        return service.ask_current_page(
            course_id=request.course_id,
            question=request.question,
            page_number=request.page_number,
            chapter_title=request.chapter_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/selection/ask")
def ask_selection(
    request: SelectionAskRequest,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Explain, summarize, ask about, or generate exercises from selected text."""

    try:
        return service.explain_selected_text(
            course_id=request.course_id,
            selected_text=request.selected_text,
            page_number=request.page_number,
            chapter_title=request.chapter_title,
            action=request.action,
            question=request.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/selection/explain-code")
def explain_code_selection(
    request: CodeSelectionExplainRequest,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Explain selected code from a PDF page."""

    try:
        return service.explain_code_selection(
            course_id=request.course_id,
            selected_text=request.selected_text,
            page_number=request.page_number,
            programming_language=request.programming_language,
            chapter_title=request.chapter_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/selection/generate-quiz")
def generate_quiz_from_selection(
    request: SelectionAskRequest,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Generate practice questions from selected PDF text."""

    try:
        return service.explain_selected_text(
            course_id=request.course_id,
            selected_text=request.selected_text,
            page_number=request.page_number,
            chapter_title=request.chapter_title,
            action="generate_quiz",
            question=request.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
