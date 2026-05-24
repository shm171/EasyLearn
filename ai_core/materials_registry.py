from __future__ import annotations

"""Small UTF-8 JSON registry for imported PDF learning materials."""

from datetime import datetime
import json
from pathlib import Path
from typing import Any


class MaterialsRegistry:
    """Persist and validate PDF metadata for the browser reader."""

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
        """Return all registered PDFs sorted by course ID."""

        data = self._read()
        return [data[key] for key in sorted(data)]

    def get_material(self, course_id: str) -> dict[str, Any]:
        """Return one registered PDF by course ID."""

        data = self._read()
        material = data.get(course_id)
        if not material:
            raise KeyError(f"Material not found for course_id: {course_id}")
        return dict(material)

    def register_pdf(
        self,
        course_id: str,
        file_path: str,
        chapter_title: str | None,
        page_count: int,
    ) -> dict[str, Any]:
        """Create or update one registry entry after a PDF import."""

        resolved_path = self._validate_material_pdf_path(file_path)
        try:
            stored_path = resolved_path.relative_to(self.project_root).as_posix()
        except ValueError:
            stored_path = resolved_path.as_posix()

        material = {
            "course_id": course_id,
            "file_path": stored_path,
            "file_name": resolved_path.name,
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

        material = self.get_material(course_id)
        return self._validate_material_pdf_path(str(material.get("file_path", "")))

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

    def _validate_material_pdf_path(self, file_path: str) -> Path:
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project_root / path
        resolved_path = path.resolve()

        if resolved_path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF files can be registered as learning materials.")
        if not resolved_path.exists():
            raise FileNotFoundError(f"Registered PDF file not found: {resolved_path}")

        try:
            resolved_path.relative_to(self.materials_dir)
        except ValueError as exc:
            raise ValueError("PDF reader can only serve files inside the materials/ directory.") from exc

        return resolved_path
