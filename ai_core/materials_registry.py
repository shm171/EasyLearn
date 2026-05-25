from __future__ import annotations

"""Small UTF-8 JSON registry for imported reader learning materials."""

from datetime import datetime
import json
from pathlib import Path
from typing import Any


class MaterialsRegistry:
    """Persist and validate material metadata for the browser reader."""

    MARKDOWN_SUFFIXES = {".md", ".markdown"}

    def __init__(
        self,
        project_root: Path | None = None,
        registry_path: Path | None = None,
        materials_dir: Path | None = None,
    ) -> None:
        self.project_root = (project_root or Path(__file__).resolve().parents[1]).resolve()
        self.materials_dir = (materials_dir or self.project_root / "materials").resolve()
        self.registry_path = registry_path or self.project_root / "data" / "materials_registry.json"
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.materials_dir.mkdir(parents=True, exist_ok=True)

    def list_materials(self) -> list[dict[str, Any]]:
        """Return all registered reader materials sorted by course ID."""

        data = self._read()
        return [self._normalize_material(key, data[key]) for key in sorted(data)]

    def get_material(self, course_id: str) -> dict[str, Any]:
        """Return one registered material by course ID."""

        data = self._read()
        material = data.get(course_id)
        if not material:
            raise KeyError(f"Material not found for course_id: {course_id}")
        return self._normalize_material(course_id, material)

    def register_pdf(
        self,
        course_id: str,
        file_path: str,
        chapter_title: str | None,
        page_count: int,
    ) -> dict[str, Any]:
        """Create or update one registry entry after a PDF import."""

        return self.register_material(
            course_id=course_id,
            file_path=file_path,
            chapter_title=chapter_title,
            page_count=page_count,
            file_type="pdf",
        )

    def register_markdown(
        self,
        course_id: str,
        file_path: str,
        chapter_title: str | None,
        page_count: int,
    ) -> dict[str, Any]:
        """Create or update one registry entry after a Markdown import."""

        return self.register_material(
            course_id=course_id,
            file_path=file_path,
            chapter_title=chapter_title,
            page_count=page_count,
            file_type="markdown",
        )

    def register_material(
        self,
        course_id: str,
        file_path: str,
        chapter_title: str | None,
        page_count: int,
        file_type: str,
    ) -> dict[str, Any]:
        """Create or update one registry entry after an import."""

        normalized_type = self._normalize_file_type(file_type)
        resolved_path = self._validate_material_path(file_path, normalized_type)
        try:
            stored_path = resolved_path.relative_to(self.project_root).as_posix()
        except ValueError:
            stored_path = resolved_path.as_posix()

        material = {
            "course_id": course_id,
            "file_path": stored_path,
            "file_name": resolved_path.name,
            "file_type": normalized_type,
            "chapter_title": chapter_title,
            "page_count": page_count,
            "last_updated": datetime.now().replace(microsecond=0).isoformat(),
        }
        data = self._read()
        data[course_id] = material
        self._write(data)
        return material

    def resolve_pdf_path(self, course_id: str) -> Path:
        """Return a safe absolute path for serving the registered PDF."""

        return self.resolve_material_path(course_id, expected_type="pdf")

    def resolve_markdown_path(self, course_id: str) -> Path:
        """Return a safe absolute path for reading the registered Markdown file."""

        return self.resolve_material_path(course_id, expected_type="markdown")

    def resolve_material_path(self, course_id: str, expected_type: str | None = None) -> Path:
        """Return a safe absolute path for a registered material."""

        material = self.get_material(course_id)
        file_type = self._normalize_file_type(str(material.get("file_type") or expected_type or "pdf"))
        if expected_type and file_type != expected_type:
            raise ValueError(f"Registered material is {file_type}, not {expected_type}.")
        return self._validate_material_path(str(material.get("file_path", "")), file_type)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.registry_path.exists():
            return {}
        with self.registry_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("materials_registry.json must contain a JSON object")
        return data

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        with self.registry_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _validate_material_path(self, file_path: str, file_type: str) -> Path:
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project_root / path
        resolved_path = path.resolve()

        suffix = resolved_path.suffix.lower()
        if file_type == "pdf" and suffix != ".pdf":
            raise ValueError("PDF materials must use a .pdf file.")
        if file_type == "markdown" and suffix not in self.MARKDOWN_SUFFIXES:
            raise ValueError("Markdown materials must use a .md or .markdown file.")
        if not resolved_path.exists():
            raise FileNotFoundError(f"Registered material file not found: {resolved_path}")

        try:
            resolved_path.relative_to(self.materials_dir)
        except ValueError as exc:
            raise ValueError("Reader can only serve files inside the materials/ directory.") from exc

        return resolved_path

    def _normalize_material(self, course_id: str, material: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(material)
        normalized.setdefault("course_id", course_id)
        normalized["file_type"] = self._infer_file_type(normalized)
        return normalized

    def _infer_file_type(self, material: dict[str, Any]) -> str:
        stored_type = material.get("file_type")
        if stored_type:
            return self._normalize_file_type(str(stored_type))
        suffix = Path(str(material.get("file_path") or material.get("file_name") or "")).suffix.lower()
        if suffix in self.MARKDOWN_SUFFIXES:
            return "markdown"
        return "pdf"

    def _normalize_file_type(self, file_type: str) -> str:
        normalized = file_type.strip().lower()
        if normalized in {"md", "markdown"}:
            return "markdown"
        if normalized == "pdf":
            return "pdf"
        raise ValueError(f"Unsupported material file_type: {file_type}")
