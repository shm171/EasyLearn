from __future__ import annotations

"""PowerPoint loading utilities for reader materials."""

from dataclasses import dataclass
from pathlib import Path
import re
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from langchain_core.documents import Document


SUPPORTED_PPTX_SUFFIXES = {".pptx", ".pptm"}
PPTX_NAMESPACE = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
DRAWING_NAMESPACE = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


@dataclass(frozen=True)
class PptxSlide:
    """One readable slide extracted from a PowerPoint deck."""

    title: str
    content: str
    text_blocks: list[str]


class PptxLoaderManager:
    """Read modern PowerPoint files into one document per slide."""

    def get_slide_count(self, file_path: str) -> int:
        """Return the number of slides without extracting full text."""

        path = _validate_pptx_path(file_path)
        try:
            with ZipFile(path) as archive:
                return len(_slide_names(archive))
        except BadZipFile as exc:
            raise ValueError("PowerPoint file is not a valid .pptx/.pptm archive.") from exc

    def load_pptx(self, file_path: str, course_id: str, chapter_title: str | None = None) -> list[Document]:
        """Load a .pptx/.pptm file into slide documents."""

        path = _validate_pptx_path(file_path)
        try:
            with ZipFile(path) as archive:
                slides = [_extract_slide(archive, name, index) for index, name in enumerate(_slide_names(archive), start=1)]
        except BadZipFile as exc:
            raise ValueError("PowerPoint file is not a valid .pptx/.pptm archive.") from exc
        except ElementTree.ParseError as exc:
            raise ValueError("PowerPoint slide XML could not be parsed.") from exc

        if not slides:
            raise ValueError("PowerPoint file does not contain readable slides.")

        documents: list[Document] = []
        for index, slide in enumerate(slides, start=1):
            content = slide.content.strip() or f"# 幻灯片 {index}\n\n（此页未提取到文本内容。）"
            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "course_id": course_id,
                        "file_path": str(path),
                        "file_name": path.name,
                        "file_type": "pptx",
                        "chapter_title": chapter_title,
                        "page_number": index,
                        "page_title": slide.title or f"幻灯片 {index}",
                        "slide_number": index,
                        "slide_text_blocks": "\n\n".join(slide.text_blocks),
                    },
                )
            )
        return documents


def _validate_pptx_path(file_path: str) -> Path:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PowerPoint file not found: {file_path}")
    suffix = path.suffix.lower()
    if suffix == ".ppt":
        raise ValueError("Legacy .ppt files are not supported yet. Please save as .pptx first.")
    if suffix not in SUPPORTED_PPTX_SUFFIXES:
        raise ValueError("Only .pptx and .pptm PowerPoint files are supported.")
    return path


def _slide_names(archive: ZipFile) -> list[str]:
    return sorted(
        (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
        key=_slide_number,
    )


def _slide_number(name: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", name)
    return int(match.group(1)) if match else 0


def _extract_slide(archive: ZipFile, slide_name: str, slide_number: int) -> PptxSlide:
    root = ElementTree.fromstring(archive.read(slide_name))
    text_blocks = [_normalize_block(block) for block in _extract_text_blocks(root)]
    text_blocks = [block for block in text_blocks if block]
    title = _infer_title(text_blocks, slide_number)
    content = _format_slide_content(title, text_blocks)
    return PptxSlide(title=title, content=content, text_blocks=text_blocks)


def _extract_text_blocks(root: ElementTree.Element) -> list[str]:
    blocks: list[str] = []
    for shape in root.iter(f"{PPTX_NAMESPACE}sp"):
        tx_body = shape.find(f"{PPTX_NAMESPACE}txBody")
        if tx_body is None:
            continue
        paragraphs: list[str] = []
        for paragraph in tx_body.findall(f"{DRAWING_NAMESPACE}p"):
            parts = [node.text or "" for node in paragraph.iter(f"{DRAWING_NAMESPACE}t")]
            text = "".join(parts).strip()
            if text:
                paragraphs.append(text)
        if paragraphs:
            blocks.append("\n".join(paragraphs))

    for graphic_frame in root.iter(f"{PPTX_NAMESPACE}graphicFrame"):
        table_text = _extract_table_text(graphic_frame)
        if table_text:
            blocks.append(table_text)
    return blocks


def _extract_table_text(root: ElementTree.Element) -> str:
    rows: list[str] = []
    for row in root.iter(f"{DRAWING_NAMESPACE}tr"):
        cells: list[str] = []
        for cell in row.iter(f"{DRAWING_NAMESPACE}tc"):
            text = " ".join((node.text or "").strip() for node in cell.iter(f"{DRAWING_NAMESPACE}t") if (node.text or "").strip())
            cells.append(text)
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _normalize_block(block: str) -> str:
    lines = [" ".join(line.split()) for line in block.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _infer_title(blocks: list[str], slide_number: int) -> str:
    for block in blocks:
        first_line = block.splitlines()[0].strip()
        if first_line:
            return first_line[:80]
    return f"幻灯片 {slide_number}"


def _format_slide_content(title: str, blocks: list[str]) -> str:
    lines = [f"# {title}"]
    body_blocks = list(blocks)
    if body_blocks and body_blocks[0].splitlines()[0].strip() == title:
        first_block_lines = body_blocks[0].splitlines()[1:]
        body_blocks = (["\n".join(first_block_lines)] if first_block_lines else []) + body_blocks[1:]
    for block in body_blocks:
        if not block.strip():
            continue
        block_lines = block.splitlines()
        if len(block_lines) == 1:
            lines.append(f"- {block_lines[0]}")
        else:
            lines.append("\n".join(f"- {line}" for line in block_lines))
    return "\n\n".join(lines).strip()
