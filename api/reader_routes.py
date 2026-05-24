from __future__ import annotations

"""FastAPI routes for the local PDF reader UI."""

from pathlib import Path
import os
import re
import shutil
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from starlette.responses import FileResponse

from ai_core.agents.reading_agent import _extract_response_text
from ai_core.materials_registry import MaterialsRegistry
from ai_core.schemas import CodeSelectionExplainRequest, CurrentPageAskRequest, SelectionAskRequest
from ai_core.service import LearningAIService
from api.dependencies import get_learning_service


router = APIRouter(prefix="/reader", tags=["pdf reader"])


class ApiConfigPayload(BaseModel):
    """Local chat API configuration submitted from the reader UI."""

    ai_provider: str = "deepseek"
    deepseek_model: str = "deepseek-chat"
    deepseek_api_key: str | None = Field(default=None)


class ApiTestPayload(BaseModel):
    """Payload for testing the configured chat API."""

    message: str = "请用一句中文回复：API 配置成功。"


def _safe_slug(value: str, default: str = "pdf") -> str:
    slug = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value).strip("._-")
    return slug or default


def _env_path() -> Path:
    return MaterialsRegistry().project_root / ".env"


def _masked_key(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return f"{value[:2]}***"
    return f"{value[:6]}...{value[-4:]}"


def _write_env_values(values: dict[str, str]) -> None:
    path = _env_path()
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    output_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output_lines.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            output_lines.append(f"{key}={remaining.pop(key)}")
        else:
            output_lines.append(line)

    for key, value in remaining.items():
        output_lines.append(f"{key}={value}")

    path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
    for key, value in values.items():
        os.environ[key] = value


@router.get("/materials")
def list_materials(service: LearningAIService = Depends(get_learning_service)) -> list[dict[str, Any]]:
    """List imported PDF materials."""

    return service.list_materials()


@router.get("/api-config")
def get_api_config(service: LearningAIService = Depends(get_learning_service)) -> dict[str, Any]:
    """Return non-sensitive local API configuration."""

    service.reload_model_config()
    settings = service.settings
    return {
        "ai_provider": settings.ai_provider,
        "deepseek_model": settings.deepseek_model,
        "deepseek_api_key_set": bool(settings.deepseek_api_key),
        "deepseek_api_key_preview": _masked_key(settings.deepseek_api_key),
    }


@router.post("/api-config")
def save_api_config(
    payload: ApiConfigPayload,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Save local chat API configuration into .env."""

    provider = payload.ai_provider.strip().lower() or "deepseek"
    if provider != "deepseek":
        raise HTTPException(status_code=400, detail="当前窗口只支持配置 DeepSeek 聊天 API。")

    values = {
        "AI_PROVIDER": provider,
        "DEEPSEEK_MODEL": payload.deepseek_model.strip() or "deepseek-chat",
        "EMBEDDING_PROVIDER": "huggingface",
    }
    if payload.deepseek_api_key and payload.deepseek_api_key.strip():
        values["DEEPSEEK_API_KEY"] = payload.deepseek_api_key.strip()

    _write_env_values(values)
    config = service.reload_model_config()
    return {
        "message": "API configuration saved.",
        **config,
        "deepseek_api_key_preview": _masked_key(service.settings.deepseek_api_key),
    }


@router.post("/api-config/test")
def test_api_config(
    payload: ApiTestPayload,
    service: LearningAIService = Depends(get_learning_service),
) -> dict[str, Any]:
    """Call the configured chat API with a short test message."""

    try:
        service.reload_model_config()
        response = service.model.invoke(payload.message)
        return {
            "ok": True,
            "answer": _extract_response_text(response),
            "model": service.settings.deepseek_model,
            "provider": service.settings.ai_provider,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
