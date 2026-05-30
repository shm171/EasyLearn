from __future__ import annotations

"""PowerPoint loading utilities for reader materials."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import base64
import json
import mimetypes
import posixpath
import re
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from langchain_core.documents import Document


SUPPORTED_PPTX_SUFFIXES = {".pptx", ".pptm"}
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PPTX_NAMESPACE = f"{{{P_NS}}}"
DRAWING_NAMESPACE = f"{{{A_NS}}}"
RELATIONSHIP_EMBED = f"{{{R_NS}}}embed"
DEFAULT_SLIDE_SIZE = (12192000, 6858000)
SUPPORTED_IMAGE_MIME_PREFIX = "image/"


@dataclass(frozen=True)
class PptxSlide:
    """One readable slide extracted from a PowerPoint deck."""

    title: str
    content: str
    text_blocks: list[str]
    layout: dict[str, Any]


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
                slide_size = _presentation_size(archive)
                slides = [
                    _extract_slide(archive, name, index, slide_size)
                    for index, name in enumerate(_slide_names(archive), start=1)
                ]
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
                        "slide_layout": json.dumps(slide.layout, ensure_ascii=False, separators=(",", ":")),
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


def _presentation_size(archive: ZipFile) -> tuple[int, int]:
    if "ppt/presentation.xml" not in archive.namelist():
        return DEFAULT_SLIDE_SIZE
    root = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
    size = root.find(f"{PPTX_NAMESPACE}sldSz")
    if size is None:
        return DEFAULT_SLIDE_SIZE
    width = _int_attr(size, "cx", DEFAULT_SLIDE_SIZE[0])
    height = _int_attr(size, "cy", DEFAULT_SLIDE_SIZE[1])
    if width <= 0 or height <= 0:
        return DEFAULT_SLIDE_SIZE
    return width, height


def _extract_slide(
    archive: ZipFile,
    slide_name: str,
    slide_number: int,
    slide_size: tuple[int, int],
) -> PptxSlide:
    root = ElementTree.fromstring(archive.read(slide_name))
    relationships = _slide_relationships(archive, slide_name)
    text_blocks = [_normalize_block(block) for block in _extract_text_blocks(root)]
    text_blocks = [block for block in text_blocks if block]
    title = _infer_title(text_blocks, slide_number)
    content = _format_slide_content(title, text_blocks)
    layout = _extract_slide_layout(archive, root, relationships, slide_size)
    return PptxSlide(title=title, content=content, text_blocks=text_blocks, layout=layout)


def _extract_text_blocks(root: ElementTree.Element) -> list[str]:
    blocks: list[str] = []
    for shape in root.iter(f"{PPTX_NAMESPACE}sp"):
        tx_body = shape.find(f"{PPTX_NAMESPACE}txBody")
        if tx_body is None:
            continue
        paragraphs = [paragraph["text"] for paragraph in _extract_paragraph_layouts(tx_body) if paragraph["text"]]
        if paragraphs:
            blocks.append("\n".join(paragraphs))

    for graphic_frame in root.iter(f"{PPTX_NAMESPACE}graphicFrame"):
        table_text = _extract_table_text(graphic_frame)
        if table_text:
            blocks.append(table_text)
    return blocks


def _extract_slide_layout(
    archive: ZipFile,
    root: ElementTree.Element,
    relationships: dict[str, str],
    slide_size: tuple[int, int],
) -> dict[str, Any]:
    width, height = slide_size
    elements: list[dict[str, Any]] = []
    background = _extract_background(root, archive, relationships, slide_size)
    if background:
        elements.append({**background, "order": 0})

    sp_tree = root.find(f"{PPTX_NAMESPACE}cSld/{PPTX_NAMESPACE}spTree")
    children = list(sp_tree) if sp_tree is not None else []
    for order, child in enumerate(children, start=1):
        name = _local_name(child.tag)
        element: dict[str, Any] | None = None
        if name == "sp":
            element = _extract_shape_layout(child, order, slide_size)
        elif name == "pic":
            element = _extract_picture_layout(archive, child, relationships, order, slide_size)
        elif name == "graphicFrame":
            element = _extract_table_layout(child, order, slide_size)
        if element:
            elements.append(element)

    return {
        "width": width,
        "height": height,
        "aspect_ratio": width / height,
        "background": _slide_background_color(root) or "#ffffff",
        "elements": elements,
    }


def _extract_background(
    root: ElementTree.Element,
    archive: ZipFile,
    relationships: dict[str, str],
    slide_size: tuple[int, int],
) -> dict[str, Any] | None:
    background = root.find(f"{PPTX_NAMESPACE}cSld/{PPTX_NAMESPACE}bg")
    if background is None:
        return None
    blip = background.find(f".//{DRAWING_NAMESPACE}blip")
    rel_id = _relationship_id(blip) if blip is not None else ""
    target = relationships.get(rel_id)
    image = _image_data_uri(archive, target) if target else None
    if not image:
        return None
    width, height = slide_size
    return {
        "type": "image",
        "x": 0,
        "y": 0,
        "width": width,
        "height": height,
        "dataUri": image["data_uri"],
        "mimeType": image["mime_type"],
        "alt": "Slide background",
        "objectFit": "cover",
    }


def _extract_shape_layout(
    shape: ElementTree.Element,
    order: int,
    slide_size: tuple[int, int],
) -> dict[str, Any] | None:
    box = _element_box(shape, slide_size)
    shape_properties = shape.find(f"{PPTX_NAMESPACE}spPr")
    fill = _solid_fill_color(shape_properties, deep=False)
    stroke = _line_color(shape_properties)
    tx_body = shape.find(f"{PPTX_NAMESPACE}txBody")
    paragraphs = _extract_paragraph_layouts(tx_body) if tx_body is not None else []
    paragraphs = [paragraph for paragraph in paragraphs if paragraph["text"]]
    name = _non_visual_name(shape)
    placeholder = _placeholder_type(shape)

    if paragraphs:
        return {
            "type": "text",
            "order": order,
            **box,
            "name": name,
            "placeholder": placeholder,
            "text": "\n".join(paragraph["text"] for paragraph in paragraphs),
            "paragraphs": paragraphs,
            "fill": fill or "",
            "stroke": stroke or "",
        }

    if fill or stroke:
        return {
            "type": "shape",
            "shape": "rect",
            "order": order,
            **box,
            "name": name,
            "fill": fill or "transparent",
            "stroke": stroke or "transparent",
        }
    return None


def _extract_picture_layout(
    archive: ZipFile,
    picture: ElementTree.Element,
    relationships: dict[str, str],
    order: int,
    slide_size: tuple[int, int],
) -> dict[str, Any] | None:
    blip = picture.find(f".//{DRAWING_NAMESPACE}blip")
    rel_id = _relationship_id(blip) if blip is not None else ""
    target = relationships.get(rel_id)
    image = _image_data_uri(archive, target) if target else None
    if not image:
        return None
    return {
        "type": "image",
        "order": order,
        **_element_box(picture, slide_size),
        "name": _non_visual_name(picture),
        "alt": _non_visual_description(picture),
        "dataUri": image["data_uri"],
        "mimeType": image["mime_type"],
        "objectFit": "contain",
    }


def _extract_table_layout(
    graphic_frame: ElementTree.Element,
    order: int,
    slide_size: tuple[int, int],
) -> dict[str, Any] | None:
    rows: list[list[str]] = []
    for row in graphic_frame.iter(f"{DRAWING_NAMESPACE}tr"):
        cells: list[str] = []
        for cell in row.iter(f"{DRAWING_NAMESPACE}tc"):
            text = " ".join(
                (node.text or "").strip()
                for node in cell.iter(f"{DRAWING_NAMESPACE}t")
                if (node.text or "").strip()
            )
            cells.append(text)
        if any(cells):
            rows.append(cells)
    if not rows:
        return None
    return {
        "type": "table",
        "order": order,
        **_element_box(graphic_frame, slide_size),
        "rows": rows,
    }


def _extract_paragraph_layouts(tx_body: ElementTree.Element) -> list[dict[str, Any]]:
    paragraphs: list[dict[str, Any]] = []
    for paragraph in tx_body.findall(f"{DRAWING_NAMESPACE}p"):
        paragraph_properties = paragraph.find(f"{DRAWING_NAMESPACE}pPr")
        runs = _extract_text_runs(paragraph)
        text = "".join(run["text"] for run in runs).strip()
        if not text:
            continue
        first_run = runs[0] if runs else {}
        level = _int_attr(paragraph_properties, "lvl", 0) if paragraph_properties is not None else 0
        bullet = False
        if paragraph_properties is not None:
            bullet = (
                paragraph_properties.find(f"{DRAWING_NAMESPACE}buChar") is not None
                or paragraph_properties.find(f"{DRAWING_NAMESPACE}buAutoNum") is not None
                or level > 0
            )
            if paragraph_properties.find(f"{DRAWING_NAMESPACE}buNone") is not None:
                bullet = False
        paragraphs.append(
            {
                "text": text,
                "runs": runs,
                "level": level,
                "bullet": bullet,
                "align": (paragraph_properties.get("algn") if paragraph_properties is not None else "") or "left",
                "fontSize": first_run.get("fontSize") or _paragraph_font_size(paragraph) or 22,
                "color": first_run.get("color") or "#202427",
                "bold": bool(first_run.get("bold")),
                "italic": bool(first_run.get("italic")),
            }
        )
    return paragraphs


def _extract_text_runs(paragraph: ElementTree.Element) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for node in paragraph:
        if node.tag == f"{DRAWING_NAMESPACE}br":
            runs.append({"text": "\n"})
            continue
        if node.tag not in {f"{DRAWING_NAMESPACE}r", f"{DRAWING_NAMESPACE}fld"}:
            continue
        text = "".join(text_node.text or "" for text_node in node.iter(f"{DRAWING_NAMESPACE}t"))
        if not text:
            continue
        properties = node.find(f"{DRAWING_NAMESPACE}rPr")
        run: dict[str, Any] = {"text": text}
        font_size = _font_size(properties)
        if font_size:
            run["fontSize"] = font_size
        color = _solid_fill_color(properties)
        if color:
            run["color"] = color
        if properties is not None:
            run["bold"] = _bool_attr(properties, "b")
            run["italic"] = _bool_attr(properties, "i")
        runs.append(run)
    if runs:
        return runs
    text = "".join(text_node.text or "" for text_node in paragraph.iter(f"{DRAWING_NAMESPACE}t")).strip()
    return [{"text": text}] if text else []


def _extract_table_text(root: ElementTree.Element) -> str:
    rows: list[str] = []
    for row in root.iter(f"{DRAWING_NAMESPACE}tr"):
        cells: list[str] = []
        for cell in row.iter(f"{DRAWING_NAMESPACE}tc"):
            text = " ".join(
                (node.text or "").strip()
                for node in cell.iter(f"{DRAWING_NAMESPACE}t")
                if (node.text or "").strip()
            )
            cells.append(text)
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def _slide_relationships(archive: ZipFile, slide_name: str) -> dict[str, str]:
    rels_path = f"{posixpath.dirname(slide_name)}/_rels/{posixpath.basename(slide_name)}.rels"
    if rels_path not in archive.namelist():
        return {}
    root = ElementTree.fromstring(archive.read(rels_path))
    relationships: dict[str, str] = {}
    base_dir = posixpath.dirname(slide_name)
    for relationship in root:
        if _local_name(relationship.tag) != "Relationship":
            continue
        rel_id = relationship.get("Id") or ""
        target = relationship.get("Target") or ""
        if not rel_id or not target:
            continue
        if target.startswith("/"):
            normalized = target.lstrip("/")
        else:
            normalized = posixpath.normpath(posixpath.join(base_dir, target))
        relationships[rel_id] = normalized.replace("\\", "/")
    return relationships


def _image_data_uri(archive: ZipFile, target: str | None) -> dict[str, str] | None:
    if not target or target not in archive.namelist():
        return None
    mime_type = mimetypes.guess_type(target)[0] or ""
    if not mime_type.startswith(SUPPORTED_IMAGE_MIME_PREFIX):
        return None
    data = archive.read(target)
    encoded = base64.b64encode(data).decode("ascii")
    return {"mime_type": mime_type, "data_uri": f"data:{mime_type};base64,{encoded}"}


def _element_box(element: ElementTree.Element, slide_size: tuple[int, int]) -> dict[str, Any]:
    slide_width, slide_height = slide_size
    xfrm = _first(
        element.find(f".//{DRAWING_NAMESPACE}xfrm"),
        element.find(f".//{PPTX_NAMESPACE}xfrm"),
    )
    if xfrm is None:
        return {"x": 0, "y": 0, "width": slide_width, "height": slide_height, "rotation": 0}
    off = xfrm.find(f"{DRAWING_NAMESPACE}off")
    ext = xfrm.find(f"{DRAWING_NAMESPACE}ext")
    return {
        "x": _int_attr(off, "x", 0),
        "y": _int_attr(off, "y", 0),
        "width": max(1, _int_attr(ext, "cx", slide_width)),
        "height": max(1, _int_attr(ext, "cy", slide_height)),
        "rotation": _rotation_degrees(xfrm.get("rot")),
    }


def _slide_background_color(root: ElementTree.Element) -> str | None:
    background = root.find(f"{PPTX_NAMESPACE}cSld/{PPTX_NAMESPACE}bg")
    if background is None:
        return None
    return _solid_fill_color(background)


def _solid_fill_color(element: ElementTree.Element | None, deep: bool = True) -> str | None:
    if element is None:
        return None
    solid_fill = element.find(f".//{DRAWING_NAMESPACE}solidFill") if deep else element.find(f"{DRAWING_NAMESPACE}solidFill")
    if solid_fill is None:
        return None
    srgb = solid_fill.find(f"{DRAWING_NAMESPACE}srgbClr")
    if srgb is not None:
        value = srgb.get("val") or ""
        return _hex_color(value)
    return None


def _line_color(shape_properties: ElementTree.Element | None) -> str | None:
    if shape_properties is None:
        return None
    line = shape_properties.find(f"{DRAWING_NAMESPACE}ln")
    return _solid_fill_color(line) if line is not None else None


def _font_size(properties: ElementTree.Element | None) -> int | None:
    if properties is None:
        return None
    size = properties.get("sz")
    if not size:
        return None
    try:
        return max(8, round(int(size) / 100))
    except ValueError:
        return None


def _paragraph_font_size(paragraph: ElementTree.Element) -> int | None:
    for tag in ("rPr", "defRPr", "endParaRPr"):
        properties = paragraph.find(f".//{DRAWING_NAMESPACE}{tag}")
        size = _font_size(properties)
        if size:
            return size
    return None


def _non_visual_name(element: ElementTree.Element) -> str:
    properties = element.find(f".//{PPTX_NAMESPACE}cNvPr")
    return (properties.get("name") if properties is not None else "") or ""


def _non_visual_description(element: ElementTree.Element) -> str:
    properties = element.find(f".//{PPTX_NAMESPACE}cNvPr")
    return (properties.get("descr") if properties is not None else "") or _non_visual_name(element)


def _placeholder_type(shape: ElementTree.Element) -> str:
    placeholder = shape.find(f".//{PPTX_NAMESPACE}ph")
    return (placeholder.get("type") if placeholder is not None else "") or ""


def _relationship_id(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return element.get(RELATIONSHIP_EMBED) or element.get("embed") or ""


def _int_attr(element: ElementTree.Element | None, name: str, default: int) -> int:
    if element is None:
        return default
    try:
        return int(element.get(name, default))
    except (TypeError, ValueError):
        return default


def _bool_attr(element: ElementTree.Element, name: str) -> bool:
    value = str(element.get(name) or "").lower()
    return value in {"1", "true", "on"}


def _rotation_degrees(value: str | None) -> float:
    if not value:
        return 0
    try:
        return round(int(value) / 60000, 2)
    except ValueError:
        return 0


def _hex_color(value: str) -> str | None:
    stripped = value.strip().lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{6}", stripped):
        return f"#{stripped.upper()}"
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first(*values: ElementTree.Element | None) -> ElementTree.Element | None:
    for value in values:
        if value is not None:
            return value
    return None


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
